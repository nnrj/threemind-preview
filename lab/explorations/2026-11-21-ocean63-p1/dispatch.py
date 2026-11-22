"""Register, wait for the four existing studies, append their reports, then run P1."""

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import time
import traceback
from uuid import uuid5

import psutil
import httpx
from paths import CONTROL, DESTINATION, EXPECTED, HERE, KERNEL, NAME, NS, OLD, PARTS, PROJECT, ROOT, SEEDS, SUPPLIES
from paths import admit, api, exclusive_json, pool, read, sha
from apparatus import E38_INPUT
from lab.tools.study_lock import worker_lock
from p1_report import scientific_conclusions, scientific_report
from outcomes import analyze
from qualification import test_habitat, test_escape, test_pipeline
from revision import gate, revise, write_once_text
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.storage_files import atomic_json
from threemind_lab.storage_volumes import directory_identity
from worldio import run_case


def identity(key):
    return str(uuid5(NS, NAME + "/" + key))


def stamp():
    return datetime.now(timezone.utc).isoformat()


def status(stage, **values):
    atomic_json(
        CONTROL / "status.json",
        dict(
            stage=stage,
            utc=stamp(),
            pid=os.getpid(),
            process_created=psutil.Process().create_time(),
            data_path=str(EXPECTED),
            **values,
        ),
    )


def sources():
    from _threemind_native import _threemind_native

    files = [
        *sorted(HERE.glob("*.py")),
        HERE / "protocol.zh.md",
        HERE / "protocol.en.md",
        E38_INPUT,
        *(OLD / f for f in ("apparatus.py", "execution.py", "carrion.py", "registration.py")),
        *(
            ROOT / "lab/tools" / f
            for f in (
                "ocean.py",
                "ocean_evolution.py",
                "ocean_contact.py",
                "ocean_enclosure.py",
                "ocean_community.py",
                "ocean_groups.py",
                "ocean_material.py",
                "ocean_turning.py",
                "ocean_evolution_cli.py",
                "study_lock.py",
            )
        ),
        ROOT / "src/threemind_runtime/inheritance.py",
    ]
    result = {f.relative_to(ROOT).as_posix(): sha(f) for f in files}
    result["_threemind_native"] = sha(Path(_threemind_native.__file__))
    return result


def source_amendment(original, current):
    if original == current:
        return None
    relative = (HERE / "dispatch.py").relative_to(ROOT).as_posix()
    correction = read(HERE / "coordinator-correction.json")
    if original.get(relative) != correction["original_sha256"] or sha(CONTROL / "dispatch.registered.py") != original[relative]:
        raise RuntimeError("registered coordinator differs")
    expected = {**original, relative: correction["corrected_sha256"]}
    if current != expected:
        later = checkpoint_amendment(original)
        if not later or current != {**expected, **later["revised_files"]}:
            raise RuntimeError("frozen study sources changed outside the two recorded corrections")
        if sha(CONTROL / "dispatch.receipt-corrected.py") != correction["corrected_sha256"]:
            raise RuntimeError("prior coordinator revision differs")
    return correction


def checkpoint_amendment(original):
    relative = (HERE / "worldio.py").relative_to(ROOT).as_posix()
    if original[relative] == sha(HERE / "worldio.py"):
        return None
    later = read(HERE / "scheduling/checkpoint-correction.json")
    driver = (HERE / "dispatch.py").relative_to(ROOT).as_posix()
    if (set(later["revised_files"]) != {relative, driver}
            or later["original_worldio_sha256"] != original[relative]
            or sha(CONTROL / "worldio.registered.py") != original[relative]
            or sha(HERE / "scheduling/qualify_checkpoint.py") != later["qualification_script_sha256"]):
        raise RuntimeError("registered world recorder differs")
    return later


def prepare():
    CONTROL.mkdir(parents=True, exist_ok=True)
    fixed = sources()
    if (CONTROL / "registered.json").exists():
        registered = read(CONTROL / "frozen.json")
        correction = source_amendment(registered, fixed)
        if correction and (CONTROL / "coordinator-correction.json").exists():
            if read(CONTROL / "coordinator-correction.json") != correction:
                raise RuntimeError("registered coordinator correction differs from the current receipt")
        if correction and not (CONTROL / "coordinator-correction.json").exists():
            with api() as client:
                rec = ResearchRecorder(CONTROL, PROJECT, client=client)
                rec.resume_recording()
                rec.append(
                    "correction", "prelaunch-receipt-check", correction, request_id=identity("receipt-correction-01")
                )
                rec.synchronize(strict=True)
                if rec.status["pending"]:
                    raise RuntimeError("coordinator correction was not registered")
            exclusive_json(CONTROL / "coordinator-correction.json", correction)
        later = checkpoint_amendment(registered)
        if later:
            receipt = CONTROL / "checkpoint-correction.json"
            checks = read(CONTROL / "checkpoint-qualification.json")
            if sha(CONTROL / "checkpoint-qualification.json") != later["qualification_sha256"]:
                raise RuntimeError("checkpoint qualification differs")
            if not receipt.exists():
                with api() as client:
                    rec = ResearchRecorder(CONTROL, PROJECT, client=client)
                    rec.resume_recording()
                    rec.append("correction", "checkpoint-id-order-20261122", dict(change=later, checks=checks),
                               request_id=identity("checkpoint-id-order-20261122"))
                    rec.synchronize(strict=True)
                    if rec.status["pending"]:
                        raise RuntimeError("checkpoint correction pending")
            exclusive_json(receipt, later)
        return
    engineering = {**test_habitat(), **test_escape(), **test_pipeline()}
    exclusive_json(CONTROL / "qualification.json", engineering)
    exclusive_json(CONTROL / "frozen.json", fixed)
    protocol = (HERE / "protocol.zh.md").read_text(encoding="utf8")
    with api() as client:
        rec = ResearchRecorder(CONTROL, PROJECT, client=client)
        rec.register(
            dict(
                source_key=NAME,
                title="OCEAN63-P1　稀疏营养、接触捕食与多代繁殖",
                classification="formal",
                execution_status="planned",
                executor="ai",
                kernels=[KERNEL],
                experiment_date="2026-11-21",
                date_basis="Prospective registration; world time starts after the earlier studies close.",
                question="Does predation increase over generations, and do early predators leave more surviving descendants?",
                protocol=protocol,
                protocol_version=sha(HERE / "protocol.zh.md"),
                required_roles=["protocol", "original", "report", "note"],
                metadata=dict(
                    worlds=2,
                    paired_supply_seconds=[1, 8],
                    founders=53,
                    grain_stock=53,
                    litter=2,
                    horizon_seconds=2400,
                    drive="I",
                    birth="threemind.birth/2",
                    order="old studies, revised reports, new worlds",
                ),
            ),
            request_id=identity("registration"),
        )
        rec.text(
            dict(
                identity=identity("protocol-doc"),
                request_id=identity("protocol"),
                expected_revision=0,
                kind="protocol",
                title="OCEAN63-P1 冻结方案",
                markdown=protocol,
            )
        )
        rec.text(
            dict(
                identity=identity("protocol-doc-en"),
                request_id=identity("protocol-en"),
                expected_revision=0,
                kind="protocol",
                title="OCEAN63-P1 protocol",
                markdown=(HERE / "protocol.en.md").read_text(encoding="utf8"),
            )
        )
        rec.synchronize(strict=True)
        if rec.status["pending"]:
            raise RuntimeError("registration pending")
        exclusive_json(
            CONTROL / "registered.json",
            dict(
                record=rec.experiment,
                registered_utc=stamp(),
                protocol_sha256=fixed[(HERE / "protocol.zh.md").relative_to(ROOT).as_posix()],
                pending=0,
            ),
        )


def enroll(root):
    if root.resolve() != EXPECTED.resolve():
        raise ValueError("operator approved only the new I-drive study directory")
    if (root / "grant.json").exists():
        return
    with api() as client:
        state = client.request("GET", "/api/v2/storage")
        target = next(
            (
                v
                for v in state["targets"]
                if v["kind"] == "filesystem" and Path(v["configuration"]["path"]).resolve() == root.resolve()
            ),
            None,
        )
        if target is None:
            target = client.request(
                "POST",
                "/api/v2/storage/targets",
                body=dict(
                    target_id=NAME + "-originals",
                    name="OCEAN63-P1 local originals",
                    kind="filesystem",
                    path=str(root),
                    configuration={"volume_identity": directory_identity(root)},
                    expected_revision=0,
                ),
            )
        # A file resource may address a subdirectory of its target. All public evidence goes there.
        published = root / "evidence"
        published.mkdir(exist_ok=True)
        rid = NAME + "-worlds"
        row = next((r for r in state["resources"] if r["id"] == rid), None)
        if row is None:
            row = client.request(
                "POST",
                "/api/v2/storage/resources",
                body=dict(
                    resource_id=rid,
                    target_id=target["id"],
                    relative_path="evidence",
                    registered_work_path=str(published),
                    expected_revision=0,
                    writer_mode="cooperative",
                ),
            )
        if row["locator"]["relative_path"] != "evidence" or row["locator"]["target_id"] != target["id"]:
            raise ValueError("original-file locator")
        receipt = client.request(
            "POST", "/api/v2/storage/record-evidence-grants", body=dict(project_id=PROJECT, resource_id=rid)
        )
        exclusive_json(root / "grant.json", receipt)


def disclose_start(root):
    grant = read(root / "grant.json")
    with api() as client:
        rec = ResearchRecorder(CONTROL, PROJECT, client=client)
        rec.resume_recording()
        proof = root / "evidence" / "protocol.zh.md"
        attach(rec, proof, proof.parent, grant["resource_id"], "protocol")
        rec.append(
            "stage",
            "queue-released",
            dict(earlier_reports="all four r2 revisions verified", data_location=str(root)),
            request_id=identity("launch-stage"),
        )
        rec.synchronize(strict=True)
        response = client.call(
            "records.verify", dict(path=dict(project=PROJECT, experiment=rec.experiment), query=dict(hashes=False))
        )
        link = next(r for r in response["evidence"] if r["logical_id"] == "P1:protocol.zh.md")
        response = client.client.get(f"/api/v2/projects/{PROJECT}/record-evidence/{link['id']}/content")
        response.raise_for_status()
        if response.content != proof.read_bytes():
            raise RuntimeError("first local evidence readback")


def attach(rec, file, base, rid, role):
    name = file.relative_to(base).as_posix()
    formats = {".zip": "application/zip", ".json": "application/json", ".md": "text/markdown", ".py": "text/plain"}
    rec.attach(
        dict(
            logical_id="P1:" + name,
            role=role,
            label=name,
            format=formats.get(file.suffix, "application/octet-stream"),
            byte_count=file.stat().st_size,
            sha256=sha(file),
            locator=dict(kind="file", resource_id=rid, member=name),
        ),
        request_id=identity("file:" + name),
    )


def copy_frozen(data):
    fixed = read(CONTROL / "frozen.json")
    correction = source_amendment(fixed, sources())
    later = checkpoint_amendment(fixed)
    for relative, digest in fixed.items():
        if relative == "_threemind_native":
            continue
        target = data / "frozen" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        source = ROOT / relative
        if correction and source == HERE / "dispatch.py":
            source = CONTROL / "dispatch.registered.py"
        if later and source == HERE / "worldio.py":
            source = CONTROL / "worldio.registered.py"
        if not target.exists():
            shutil.copyfile(source, target)
        if sha(target) != digest:
            raise RuntimeError("frozen dependency " + relative)
    for key in ("frozen.json", "registered.json", "qualification.json"):
        exclusive_json(data / key, read(CONTROL / key))
    if correction:
        changes = data / "revisions" / "coordinator-01"
        changes.mkdir(parents=True, exist_ok=True)
        exclusive_json(changes / "correction.json", correction)
        corrected = changes / "dispatch.py"
        if not corrected.exists():
            source = CONTROL / "dispatch.receipt-corrected.py" if later else HERE / "dispatch.py"
            shutil.copyfile(source, corrected)
        if sha(corrected) != correction["corrected_sha256"]:
            raise RuntimeError("coordinator revision copy differs")
    if later:
        changes = data / "revisions/checkpoint-id-order-20261122"
        changes.mkdir(parents=True, exist_ok=True)
        exclusive_json(changes / "correction.json", later)
        exclusive_json(changes / "qualification.json", read(CONTROL / "checkpoint-qualification.json"))
        test = changes / "qualify_checkpoint.py"
        if not test.exists():
            shutil.copyfile(HERE / "scheduling/qualify_checkpoint.py", test)
        if sha(test) != later["qualification_script_sha256"]:
            raise RuntimeError("checkpoint qualification source differs")
        for relative, expected in later["revised_files"].items():
            source = ROOT / relative
            target = changes / source.name
            if not target.exists():
                shutil.copyfile(source, target)
            if sha(target) != expected:
                raise RuntimeError("dated checkpoint revision copy differs")
    for lang in ("zh", "en"):
        filename = f"protocol.{lang}.md"
        write_once_text(data / filename, (HERE / filename).read_text(encoding="utf8"))


def deliver(root, findings):
    data = root / "evidence"
    rid = read(root / "grant.json")["resource_id"]
    reports = {}
    for lang in ("zh", "en"):
        reports[lang] = scientific_report(findings, lang)
        for dest in (data / "analysis", HERE / "results"):
            dest.mkdir(exist_ok=True)
            write_once_text(dest / f"report.{lang}.md", reports[lang])
    files = [
        p for p in data.rglob("*") if p.is_file() and p.name not in ("manifest.json", "progress.json", "verified.json")
    ]
    manifest = {f.relative_to(data).as_posix(): dict(bytes=f.stat().st_size, sha256=sha(f)) for f in sorted(files)}
    exclusive_json(data / "manifest.json", manifest)
    with api() as client:
        client.client.timeout = 3600
        rec = ResearchRecorder(CONTROL, PROJECT, client=client)
        rec.resume_recording()
        for lang, text in reports.items():
            rec.text(
                dict(
                    identity=identity("doc-" + lang),
                    request_id=identity("report-" + lang),
                    expected_revision=0,
                    kind="report",
                    title="OCEAN63-P1 " + lang,
                    markdown=text,
                )
            )
        rec.text(
            dict(
                identity=identity("doc-note"),
                request_id=identity("note"),
                expected_revision=0,
                kind="note",
                title="OCEAN63-P1 observations",
                markdown="Two independent habitats, two matched supply conditions each. The lineage and movement observations are nested within each world. Complete sensory and motor samples, motion tracks, events and states are in each sealed segment.",
            )
        )
        for f in sorted(files):
            role = "original" if f.suffix == ".zip" else "analysis" if f.parent.name == "analysis" else "support"
            if f == data / "protocol.zh.md":
                continue
            attach(rec, f, data, rid, role)
        attach(rec, data / "manifest.json", data, rid, "manifest")
        rec.synchronize(strict=True)
        args = dict(path=dict(project=PROJECT, experiment=rec.experiment), query=dict(hashes=True))
        audited = client.call("records.verify", args)
        if audited["coverage"] != "verified" or audited["problems"]:
            raise RuntimeError(str(audited["problems"]))
        for lang, markdown in reports.items():
            body = client.request("GET", f"/api/v2/projects/{PROJECT}/research-documents/{identity('doc-' + lang)}")
            if body["spec"]["blocks"][0]["markdown"] != markdown:
                raise RuntimeError("bilingual report readback")
        for item in audited["evidence"]:
            key = item["logical_id"]
            if not (key.startswith("P1:") and key.endswith(".zip")):
                continue
            expected = manifest[key[3:]]
            digest = hashlib.sha256()
            size = 0
            with client.client.stream(
                "GET", f"/api/v2/projects/{PROJECT}/record-evidence/{item['id']}/content"
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(chunk_size=2**20):
                    size += len(chunk)
                    digest.update(chunk)
            if expected["bytes"] != size or digest.hexdigest() != expected["sha256"]:
                raise RuntimeError("original readback")
        rec.finalize(request_id=identity("finalize"))
        rec.synchronize(strict=True)
        final = client.call(
            "records.verify", dict(path=dict(project=PROJECT, experiment=rec.experiment), query=dict(hashes=False))
        )
        if (
            rec.status["pending"]
            or final["execution_status"] != "completed"
            or final["coverage"] != "indexed"
            or final["problems"]
        ):
            raise RuntimeError("finalized research record verification failed")
        receipt = dict(
            record=rec.experiment,
            resource=rid,
            original_archives=sum(f.suffix == ".zip" for f in files),
            pending=0,
            api_readback=True,
            manifest_sha256=sha(data / "manifest.json"),
            outcomes=findings["outcomes"],
        )
        exclusive_json(data / "verified.json", receipt)
        exclusive_json(HERE / "results" / "verified.json", receipt)


def when_api_available(operation, *args):
    while True:
        try:
            return operation(*args)
        except (httpx.TransportError, ConnectionError):
            status("waiting for the local research service", operation=operation.__name__)
            if (CONTROL / "STOP").exists():
                raise
            time.sleep(45)


def note_completion(findings):
    marker = "<!-- ocean63-p1-verified -->"
    date = datetime.now().astimezone().date().isoformat()
    for lang in ("zh", "en"):
        conclusion = scientific_conclusions(findings["outcomes"], lang)
        for relative in ("plans/research-backlog.md", "history/chronicles/20-artificial-selection.md"):
            file = ROOT / "docs" / lang / relative
            if marker in file.read_text(encoding="utf8"):
                continue
            report_path = HERE / "results" / f"report.{lang}.md"
            target = Path(os.path.relpath(report_path, file.parent)).as_posix()
            heading = "OCEAN63-P1 完成核验" if lang == "zh" else "OCEAN63-P1 verified"
            with file.open("a", encoding="utf8") as out:
                out.write(
                    f"\n{marker}\n\n## {date}　{heading}\n\n" + " ".join(conclusion) + f"\n\n[OCEAN63-P1]({target})\n"
                )


def wait_then_run():
    prepare()
    with worker_lock(CONTROL / "worker"):
        receipt = EXPECTED / "evidence/verified.json"
        local_receipt = HERE / "results/verified.json"
        if receipt.exists() and local_receipt.exists() and read(receipt) == read(local_receipt):
            note_completion(read(EXPECTED / "evidence/analysis/findings.json"))
            pool().finish(NAME)
            status("complete", receipt=str(receipt))
            return
        while not gate() or pool().study("ocean63-20261121")["status"] != "complete":
            status("waiting for the four existing studies and their original-file verification")
            if (CONTROL / "STOP").exists():
                return
            time.sleep(45)
        status("revising the four historical reports")
        when_api_available(revise)
        while not pool().preview(NAME, PARTS, directory_id=DESTINATION)["fits"]:
            status("waiting for 22 GiB on the selected I drive")
            if (CONTROL / "STOP").exists():
                return
            time.sleep(45)
        root = admit()
        when_api_available(enroll, root)
        data = root / "evidence"
        copy_frozen(data)
        when_api_available(disclose_start, root)
        for i in range(len(SEEDS)):
            for arm, interval in SUPPLIES.items():
                status("running", case=f"world-{i}-{arm}")
                run_case(data, i, arm, interval)
        status("verifying scientific observations and writing reports")
        (data / "analysis").mkdir(exist_ok=True)
        findings = analyze(data)
        exclusive_json(data / "analysis/findings.json", findings)
        when_api_available(deliver, root, findings)
        note_completion(findings)
        pool().finish(NAME)
        status("complete", receipt=str(data / "verified.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "queue", "status"))
    action = parser.parse_args().action
    if action == "prepare":
        prepare()
        print(read(CONTROL / "registered.json"))
    elif action == "status":
        print(read(CONTROL / "status.json") if (CONTROL / "status.json").exists() else "not queued")
    else:
        try:
            wait_then_run()
        except Exception as error:
            status("requires attention", error=str(error))
            traceback.print_exc()
            raise
