"""Register before world time zero, preserve the P1 handoff and run all four P2 worlds."""

import argparse
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid5
from zipfile import ZipFile

import psutil
from p2_paths import (
    CONTROL,
    EXPECTED,
    GIB,
    HERE,
    KERNEL,
    NAME,
    NS,
    PROJECT,
    ROOT,
    RULES,
    SEEDS,
    SUPPLIES,
    api,
    exclusive_json,
    pool,
    previous,
    read,
    sha,
)

# isort: split
import dispatch as old
import worldio
from execution import checked_metrics
from p2_analysis import analyze
from p2_io import run_case
from p2_report import report
from qualify_p2 import check

from lab.tools.study_lock import worker_lock
from threemind_lab.experiment_storage import scan_pool
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.storage_files import atomic_json, file_lock
from threemind_lab.storage_volumes import directory_identity, tree_usage


def identity(key):
    return str(uuid5(NS, NAME + "/" + key))


def status(stage, **values):
    atomic_json(
        CONTROL / "status.json",
        dict(
            stage=stage,
            pid=os.getpid(),
            process_created=psutil.Process().create_time(),
            utc=datetime.now(UTC).isoformat(),
            **values,
        ),
    )


def check_pause():
    stage = read(previous.CONTROL / "status.json")
    case = previous.EXPECTED / "evidence/cases/world-0-reference"
    if stage.get("error") != "operator STOP" or not (previous.CONTROL / "STOP").is_file():
        raise RuntimeError("P1 has not acknowledged a complete-state pause")
    if (
        psutil.pid_exists(stage["pid"])
        and abs(psutil.Process(stage["pid"]).create_time() - stage["process_created"]) < 1
    ):
        raise RuntimeError("P1 worker is still alive")
    last = max(case.glob("seg-*.zip"))
    proofs = []
    for file in (case / "seg-0024.zip", last):
        with ZipFile(file) as z:
            seg = json.loads(z.read("segment.json"))
            digest = hashlib.sha256(z.read("end.zip")).hexdigest()
        w = worldio.restore_end(file)
        if (
            w.time_us != seg["end_us"]
            or hashlib.sha256(worldio.state_bytes(w.capture())).hexdigest() != seg["end_hash"]
        ):
            raise ValueError("P1 complete state readback differs")
        checked_metrics(w)
        proofs.append(
            {
                "time_us": w.time_us,
                "file": file.name,
                "checkpoint_sha256": digest,
                "world_sha256": seg["end_hash"],
                "start_sha256": seg["start_hash"],
                "native_cores": len(w.engines),
                "alive": sum(b.physical for b in w.bodies.values()),
                "births": w.totals["births"],
                "predations": w.totals["predations"],
                "generation": max(b.generation for b in w.bodies.values()),
            }
        )
    if (
        proofs[0]["time_us"] != 1500000000
        or proofs[0]["world_sha256"] != proofs[1]["start_sha256"]
        or seg["pause"] != "operator STOP"
    ):
        raise ValueError("P1 milestone continuity")
    return {"scope": case.name, "milestones": proofs, "paused_utc": stage["utc"]}


def admit():
    store = pool()
    with store.study_lock(previous.NAME), file_lock(store.lock):
        s = store._read()
        p1 = s["studies"][previous.NAME]
        changes = p1.setdefault("capacity_revisions", {})
        if NAME in changes and NAME in s["studies"]:
            return changes[NAME]
        if p1["status"] != "reserved" or any(
            t["status"] not in ("complete", "cancelled") for t in s.get("transfers", {}).values()
        ):
            raise RuntimeError("P1 reservation or transfer in progress")
        part = p1["parts"][0]
        if part["directory"] != previous.DESTINATION or part["bytes"] != 22 * GIB or NAME in s["studies"]:
            raise RuntimeError("unexpected allocation")
        if store.path(previous.NAME, part["name"]).resolve() != previous.EXPECTED.resolve():
            raise ValueError("P1 volume changed")
        used = tree_usage(previous.EXPECTED)
        saved = min(22 * GIB, used + GIB)
        part["bytes"] = saved
        req = store._request(NAME, [{"name": "worlds", "bytes": 22 * GIB}], False)
        req["directory_id"] = previous.DESTINATION
        placement = store._plan(s, req)
        if not placement["fits"] or placement["parts"][0]["directory"] != previous.DESTINATION:
            raise RuntimeError("22 GiB unavailable on I for P2")
        changes[NAME] = {
            "original_bytes": 22 * GIB,
            "p1_used_bytes": used,
            "p1_paused_bytes": saved,
            "p2_bytes": 22 * GIB,
        }
        s["studies"][NAME] = placement
        atomic_json(store.file, s)
        return changes[NAME]


def return_capacity():
    store = pool()
    store.finish(NAME)
    with store.study_lock(previous.NAME), file_lock(store.lock):
        s = store._read()
        old_study = s["studies"][previous.NAME]
        record = old_study["capacity_revisions"][NAME]
        part = old_study["parts"][0]
        if part["bytes"] == record["original_bytes"]:
            return True
        rows, _ = scan_pool(s["directories"], s["studies"], s.get("transfers", {}).values())
        if (
            part["bytes"] != record["p1_paused_bytes"]
            or rows[part["directory"]]["available_bytes"] < record["original_bytes"] - part["bytes"]
        ):
            return False
        part["bytes"] = record["original_bytes"]
        atomic_json(store.file, s)
        return True


def sources():
    values = old.sources()
    for f in [*HERE.glob("*.py"), *HERE.glob("protocol.*.md")]:
        values[f.relative_to(ROOT).as_posix()] = sha(f)
    return values


def text_document(rec, title, body, role, key):
    rec.text(
        {
            "identity": identity("doc-" + key),
            "request_id": identity("text-" + key),
            "expected_revision": 0,
            "kind": role,
            "title": title,
            "markdown": body,
        }
    )


def prepare():
    CONTROL.mkdir(parents=True, exist_ok=True)
    if not (CONTROL / "pause.json").exists():
        exclusive_json(CONTROL / "pause.json", check_pause())
    if not (CONTROL / "qualification.json").exists():
        exclusive_json(CONTROL / "qualification.json", check())
    fixed = sources()
    exclusive_json(CONTROL / "frozen.json", fixed)
    if not (CONTROL / "registered.json").exists():
        protocol = (HERE / "protocol.zh.md").read_text(encoding="utf8")
        with api() as client:
            rec = ResearchRecorder(CONTROL, PROJECT, client=client)
            rec.register(
                {
                    "source_key": NAME,
                    "title": "OCEAN63-P2　幼体生长、亲代哺育与环境选择",
                    "classification": "formal",
                    "execution_status": "planned",
                    "executor": "ai",
                    "kernels": [KERNEL],
                    "experiment_date": "2026-11-22",
                    "date_basis": "Prospective registration before P2 world time zero.",
                    "question": "Does scarcity increase predation across generations and do early hunters leave more surviving children?",
                    "protocol": protocol,
                    "protocol_version": sha(HERE / "protocol.zh.md"),
                    "required_roles": ["protocol", "original", "report", "note"],
                    "metadata": {
                        "worlds": 2,
                        "paired_supply_seconds": [1, 8],
                        "founders": 53,
                        "litter": 3,
                        "horizon_seconds": 2400,
                        "drive": "I",
                        "environment": RULES,
                        "birth": "threemind.birth/2",
                    },
                },
                request_id=identity("register"),
            )
            for lang in ("zh", "en"):
                text_document(
                    rec,
                    "OCEAN63-P2 protocol " + lang,
                    (HERE / f"protocol.{lang}.md").read_text(encoding="utf8"),
                    "protocol",
                    "protocol-" + lang,
                )
            text_document(
                rec,
                "P2 engineering qualification",
                json.dumps(read(CONTROL / "qualification.json"), indent=2),
                "note",
                "qualification",
            )
            rec.append("stage", "p1-handoff", read(CONTROL / "pause.json"), request_id=identity("handoff"))
            rec.synchronize(strict=True)
            if rec.status["pending"]:
                raise RuntimeError("P2 registration pending")
            prior = ResearchRecorder(previous.CONTROL, PROJECT, client=client)
            prior.resume_recording()
            prior.append("stage", "paused-for-P2", read(CONTROL / "pause.json"), request_id=identity("P1-pause"))
            prior.synchronize(strict=True)
            exclusive_json(
                CONTROL / "registered.json",
                {
                    "record": rec.experiment,
                    "protocol_sha256": sha(HERE / "protocol.zh.md"),
                    "registered_utc": datetime.now(UTC).isoformat(),
                },
            )
    allocation = admit()
    home = pool().guard(NAME, "worlds", check_directory=False)
    if home.resolve() != EXPECTED.resolve():
        raise RuntimeError("P2 is pinned to I")
    root = home / "evidence"
    root.mkdir(exist_ok=True, parents=True)
    exclusive_json(root / "allocation.json", allocation)
    for key in ("frozen", "qualification", "registered", "pause"):
        exclusive_json(root / (key + ".json"), read(CONTROL / (key + ".json")))
    for name, digest in fixed.items():
        if name == "_threemind_native":
            continue
        target = root / "frozen" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(ROOT / name, target)
        if sha(target) != digest:
            raise RuntimeError("frozen source differs: " + name)
    for lang in ("zh", "en"):
        name = f"protocol.{lang}.md"
        if not (root / name).exists():
            shutil.copyfile(HERE / name, root / name)
        if sha(root / name) != sha(HERE / name):
            raise ValueError(name)
    return root


def attach(rec, path, root, role):
    name = path.relative_to(root).as_posix()
    rec.attach(
        {
            "logical_id": "P2:" + name,
            "role": role,
            "label": name,
            "format": {".zip": "application/zip", ".md": "text/markdown", ".json": "application/json"}.get(
                path.suffix, "application/octet-stream"
            ),
            "byte_count": path.stat().st_size,
            "sha256": sha(path),
            "locator": {"kind": "file", "resource_id": NAME + "-originals", "member": name},
        },
        request_id=identity("file-" + name),
    )


def grant():
    # Explicit host-admin action; never invoked by the worker.
    root = EXPECTED / "evidence"
    if not (root / "registered.json").exists():
        raise ValueError("register P2 first")
    rid = NAME + "-originals"
    with api() as client:
        state = client.request("GET", "/api/v2/storage")
        target = next((r for r in state["targets"] if r["id"] == NAME + "-volume"), None)
        if target is None:
            target = client.request(
                "POST",
                "/api/v2/storage/targets",
                body={
                    "target_id": NAME + "-volume",
                    "name": "P2 local evidence",
                    "kind": "filesystem",
                    "path": str(EXPECTED),
                    "expected_revision": 0,
                    "configuration": {"volume_identity": directory_identity(EXPECTED)},
                },
            )
        if Path(target["configuration"]["path"]).resolve() != EXPECTED.resolve():
            raise ValueError("P2 target mismatch")
        resource = next((r for r in state["resources"] if r["id"] == rid), None)
        if resource is None:
            resource = client.request(
                "POST",
                "/api/v2/storage/resources",
                body={
                    "resource_id": rid,
                    "target_id": target["id"],
                    "relative_path": "evidence",
                    "registered_work_path": str(root),
                    "expected_revision": 0,
                    "writer_mode": "cooperative",
                },
            )
        if resource["locator"]["relative_path"] != "evidence" or resource["locator"]["target_id"] != target["id"]:
            raise ValueError("P2 evidence scope")
        receipt = client.request(
            "POST", "/api/v2/storage/record-evidence-grants", body={"project_id": PROJECT, "resource_id": rid}
        )
        rec = ResearchRecorder(CONTROL, PROJECT, client=client)
        rec.resume_recording()
        attach(rec, root / "protocol.zh.md", root, "protocol")
        rec.synchronize(strict=True)
        evidence = client.call(
            "records.verify", {"path": {"project": PROJECT, "experiment": rec.experiment}, "query": {"hashes": False}}
        )["evidence"]
        item = next(r for r in evidence if r["logical_id"] == "P2:protocol.zh.md")
        response = client.client.get(f"/api/v2/projects/{PROJECT}/record-evidence/{item['id']}/content")
        response.raise_for_status()
        if response.content != (root / "protocol.zh.md").read_bytes():
            raise ValueError("P2 protocol readback")
        if not (EXPECTED / "grant.json").exists():
            exclusive_json(EXPECTED / "grant.json", receipt)


def deliver(root):
    analysis = root / "analysis"
    analysis.mkdir(exist_ok=True)
    findings = analyze(root)
    exclusive_json(analysis / "findings.json", findings)
    reports = {}
    for lang in ("zh", "en"):
        reports[lang] = report(findings, lang)
        old.write_once_text(analysis / f"report.{lang}.md", reports[lang])
    files = [
        f
        for f in sorted(root.rglob("*"))
        if f.is_file() and f.name not in {"manifest.json", "progress.json", "verified.json"}
    ]
    exclusive_json(
        root / "manifest.json",
        {f.relative_to(root).as_posix(): {"bytes": f.stat().st_size, "sha256": sha(f)} for f in files},
    )
    with api() as client:
        client.client.timeout = 3600
        rec = ResearchRecorder(CONTROL, PROJECT, client=client)
        rec.resume_recording()
        for lang, md in reports.items():
            text_document(rec, "OCEAN63-P2 " + lang, md, "report", "report-" + lang)
        rec.synchronize(strict=True)
        if not (EXPECTED / "grant.json").exists():
            return "originals sealed locally; research-page readback awaits a grant"
        for f in files:
            if f == root / "protocol.zh.md":
                continue
            attach(
                rec, f, root, "original" if f.suffix == ".zip" else "analysis" if f.parent == analysis else "support"
            )
        attach(rec, root / "manifest.json", root, "manifest")
        rec.synchronize(strict=True)
        args = {"path": {"project": PROJECT, "experiment": rec.experiment}, "query": {"hashes": True}}
        verified = client.call("records.verify", args)
        if verified["problems"] or verified["coverage"] != "verified":
            raise ValueError("final research-page evidence verification")
        rec.finalize(request_id=identity("finalize"))
        rec.synchronize(strict=True)
        exclusive_json(
            root / "verified.json",
            {
                "record": rec.experiment,
                "manifest": sha(root / "manifest.json"),
                "pending": rec.status["pending"],
                "originals_read_back": True,
            },
        )
        return "complete"


def run():
    with worker_lock(CONTROL / "worker"):
        root = prepare()
        with api() as client:
            rec = ResearchRecorder(CONTROL, PROJECT, client=client)
            rec.resume_recording()
            rec.append("stage", "worlds-running", {"path": str(root), "rules": RULES}, request_id=identity("start"))
            rec.synchronize(strict=True)
        for block in range(len(SEEDS)):
            for arm, interval in SUPPLIES.items():
                status("running", case=f"world-{block}-{arm}")
                run_case(root, block, arm, interval)
        status("checking all worlds")
        final = deliver(root)
        status(final, p1_original_reservation_restored=return_capacity())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "grant", "publish"))
    action = parser.parse_args().action
    if action == "run":
        try:
            run()
        except Exception as e:
            status("requires attention", error=str(e))
            raise
    elif action == "prepare":
        print(prepare())
    elif action == "grant":
        grant()
    else:
        print(deliver(EXPECTED / "evidence"))
