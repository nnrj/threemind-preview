"""A dated, bilingual addition to each closed study, using the preserved sensory data."""

import json
from datetime import datetime
from uuid import uuid5

import pyarrow as pa
import pyarrow.ipc as ipc

from paths import CONTROL, OLD, NS, PROJECT, api, directory, exclusive_json, read, sha
from registration import BATCH
from turns import MealTurns
from threemind_lab.research_recorder import ResearchRecorder

OLD_CODES = ("30", "28", "38", "39C")


def gate():
    all_receipts = OLD / "results" / "verified.json"
    if not all_receipts.exists():
        return False
    registered = read(all_receipts)
    for code in OLD_CODES:
        p = directory(code) / "publication/complete.json"
        if not p.is_file() or read(p) != registered[code]:
            return False
        r = registered[code]
        if not r["api_readback"] or not r["bilingual_reports"] or r["pending"]:
            return False
    return True


def retrospective(code):
    work = directory(code)
    done = read(work / "calculation-complete.json")["results"]
    findings = {}
    carry = {}
    # A shared history is scanned once. Retain the last five seconds when scoring each fork.
    first = [k for k in done if k == "common" or k.endswith("-common")]
    for case in first + [k for k in sorted(done) if k not in first]:
        d = work / "cases" / case
        if sha(d / "result.json") != done[case]:
            raise ValueError("closed case digest " + case)
        source = None
        if code == "38" and case in ("original", "reduced"):
            source = carry["common"]
        if code == "39C" and not case.endswith("-common"):
            source = carry[case.rsplit("-", 1)[0] + "-common"]
        observer = MealTurns(source)
        steps = 0
        last = None
        for meta in sorted(d.glob("seg-*/segment.json")):
            segment = read(meta)
            if last is None:
                last = segment["start_us"]
            if last != segment["start_us"]:
                raise ValueError("discontinuous segment " + case)
            for path in sorted((meta.parent / "inputs").glob("*.arrow")):
                with pa.memory_map(str(path), "r") as stream:
                    reader = ipc.open_file(stream)
                    for ix in range(reader.num_record_batches):
                        batch = reader.get_batch(ix)
                        ts = batch.column("time_us").to_numpy()
                        if ts[0] != last + 20_000 or (len(ts) > 1 and not ((ts[1:] - ts[:-1]) == 20_000).all()):
                            raise ValueError("unexpected sensory sampling " + case)
                        events = [e for text in batch.column("events").to_pylist() for e in json.loads(text)]
                        observer.consume(batch, events)
                        last = int(ts[-1])
                        steps += len(ts)
            if last != segment["end_us"]:
                raise ValueError("segment end " + case)
        item = observer.result()
        item.update(steps=steps, previous_case=source is not None, original_case_sha256=done[case], last_us=last)
        findings[case] = item
        if case in first:
            carry[case] = observer
    return findings


def edition(original, findings, code, lang, date):
    zh = lang == "zh"
    overall = sum(v["turns"] for v in findings.values())
    lines = [
        original.rstrip(),
        "",
        f"## {date}　" + ("修订第二版　转弯后摄食" if zh else "Second edition. Turning before feeding"),
        "",
    ]
    if zh:
        lines += [
            "我们按旧水域实验的方法回查了封存的记录。以一次确实摄入营养的事件为终点，比较个体在摄食前五秒的行进方向、营养浓度变化和实际转向指令。下表逐个世界列出观察数。同一身份可多次出现，共同经历在分支前只计一次。"
        ]
    else:
        lines += [
            "We revisited the sealed recordings using the original turning screen. For each observed nutrient ingestion, we compared the individual's water-relative movement, local nutrient gradient and motor commands over the preceding five seconds. Each row is a world or an observation interval. Individuals may recur. Shared events are counted once before a fork."
        ]
    if code == "28":
        lines += [
            "本批每步保存了13项感官量，其中没有身体碰撞量。表中候选符合可以核查的转角、运动和营养方向条件，碰撞情况未知。"
            if zh
            else "The 13 sensory measurements in this study omit body collision. These candidates met the available turning, motion and nutrient-alignment criteria. Collision during the window is unknown."
        ]
    else:
        lines += [
            "我们沿用了旧实验的全部条件，包括至少30°的转弯、转向营养浓度上升的方向，以及观察窗内没有身体碰撞。"
            if zh
            else "We applied the full historical criteria, including a turn of at least 30 degrees, improved alignment with the nutrient gradient and no body collision during the window."
        ]
    lines += [
        "",
        "| 世界或分支 | 摄入颗粒事件 | 有完整窗口的检查次数 | 转弯后摄食次数 | 涉及个体数 |"
        if zh
        else "| World or branch | Grain ingestion events | Eligible windows | Turning and feeding events | Individuals |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, v in findings.items():
        lines.append(f"| {k} | {v['grain_events']} | {v['windows']} | {v['turns']} | {v['individuals']} |")
    lines.append("")
    if code == "28":
        lines.append(
            f"共找到 {overall} 次符合可测条件的转弯摄食候选。"
            if zh
            else f"The available measurements identified {overall} candidate events."
        )
    else:
        lines.append(
            f"在这些记录中，共有 {overall} 次转弯后摄食符合旧实验判据。"
            if zh
            else f"Across these recordings, {overall} turning and feeding events met the historical criteria."
        )
    example = next(((k, e) for k, v in findings.items() for e in v["evidence"]), None)
    if example:
        k, e = example
        t = e["meal_times_us"][0] / 1e6
        i = e["individual"]
        a = e["turn_degrees"]
        lines.append(
            (
                f"例如，在 {k} 中，{i} 号在 {t:g} 内部秒摄入营养颗粒，此前五秒内相对水流的行进方向改变了 {a:.1f}°。"
                if zh
                else f"In {k}, for example, individual {i} ingested a grain at {t:g} seconds of simulated time. Its water-relative direction changed by {a:.1f} degrees over the preceding five seconds."
            )
        )
    lines.append(
        "上述数字描述已发生的运动与摄食。事件级证据见 revisions/turns-r2/findings.json。本次回查保留原先登记的实验判定。"
        if zh
        else "These measurements describe observed movement and ingestion. Event-level evidence is in revisions/turns-r2/findings.json. The original registered outcomes retain their scores."
    )
    return "\n".join(lines) + "\n"


def write_once_text(path, text):
    data = text.encode("utf8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("existing edition differs: " + str(path))
        return
    with path.open("xb") as stream:
        stream.write(data)


def revise():
    if not gate():
        raise RuntimeError("wait for all four verified originals")
    datefile = CONTROL / "revision-date.json"
    if not datefile.exists():
        exclusive_json(datefile, {"date": datetime.now().astimezone().date().isoformat()})
    date = read(datefile)["date"]
    for code in OLD_CODES:
        work = directory(code)
        folder = work / "revisions/turns-r2"
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / "verified.json").exists():
            continue
        findings_file = folder / "findings.json"
        if not findings_file.exists():
            exclusive_json(findings_file, retrospective(code))
        data = read(findings_file)
        with api() as client:
            rec = ResearchRecorder(work, PROJECT, client=client)
            rec.resume_recording()
            rid = read(work / "project-grant.json")["resource_id"]
            rec.attach(
                dict(
                    logical_id=f"OCEAN63-{code}:turns-r2",
                    role="analysis",
                    label="turns-r2 findings",
                    format="application/json",
                    byte_count=findings_file.stat().st_size,
                    sha256=sha(findings_file),
                    locator=dict(kind="file", resource_id=rid, member="revisions/turns-r2/findings.json"),
                ),
                request_id=uuid5(NS, f"{BATCH}-{code}-turns-r2-findings"),
            )
            for lang in ("zh", "en"):
                old = work / f"analysis/report.{lang}.md"
                repo = OLD / "results" / ("ocean63-" + code.lower())
                if (repo / old.name).read_bytes() != old.read_bytes():
                    raise ValueError("original local report mismatch")
                text = edition(old.read_text(encoding="utf8"), data, code, lang, date)
                name = f"report.r2.{lang}.md"
                write_once_text(folder / name, text)
                write_once_text(repo / name, text)
                ident = str(uuid5(NS, f"{BATCH}-{code}-doc-{lang}"))
                rec.text(
                    dict(
                        identity=ident,
                        request_id=str(uuid5(NS, f"{BATCH}-{code}-turns-r2-{lang}")),
                        expected_revision=1,
                        revision_reason="Dated retrospective turning and feeding analysis",
                        kind="report",
                        title=f"OCEAN63-{code} {lang}",
                        markdown=text,
                    )
                )
            rec.synchronize(strict=True)
            for lang in ("zh", "en"):
                ident = str(uuid5(NS, f"{BATCH}-{code}-doc-{lang}"))
                doc = client.request("GET", f"/api/v2/projects/{PROJECT}/research-documents/{ident}")
                assert doc["spec"]["blocks"][0]["markdown"] == (folder / f"report.r2.{lang}.md").read_text(
                    encoding="utf8"
                )
            checked = client.call(
                "records.verify", dict(path=dict(project=PROJECT, experiment=rec.experiment), query=dict(hashes=False))
            )
            item = next(e for e in checked["evidence"] if e["logical_id"] == f"OCEAN63-{code}:turns-r2")
            response = client.client.get(f"/api/v2/projects/{PROJECT}/record-evidence/{item['id']}/content")
            response.raise_for_status()
            if response.content != findings_file.read_bytes() or rec.status["pending"]:
                raise RuntimeError("revision evidence readback")
        exclusive_json(
            folder / "verified.json", dict(code=code, edition=2, findings_sha256=sha(findings_file), date=date)
        )
