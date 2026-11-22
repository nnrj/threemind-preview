"""Dated scheduling amendment. The registered worlds and both study drivers stay frozen."""

from pathlib import Path
import subprocess
import sys
import time
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dispatch as p1
from execution import checked_metrics, restore
from registration import BATCH, PEAK_GIB, directory
from threemind_lab import storage_volumes as volumes
from threemind_lab.storage_files import atomic_json, file_lock


KEY = "author-priority-20261122"
REQUEST = "Operator priority 2026-11-22: pause 39C at a complete state for OCEAN63-P1; resume after verified P1."
GIB = 1024**3
PAUSED_CASE = "world-0-reduced"
PAUSED_AT = 1624900000
CHECKSUM = "22c80fb49987b0e222d366daf62ec4762df3276a9d667fefc68397d917869473"
ADMIN = p1.CONTROL / KEY


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def pause_receipt():
    study = directory("39C")
    require((study / "STOP").read_text(encoding="utf-8-sig").strip() == REQUEST, "39C pause request differs")
    queue = p1.read(study.parent / "queue.json")
    expected_error = f"{PAUSED_CASE} paused at complete state {PAUSED_AT}: operator STOP"
    require(queue.get("code") == "39C" and queue.get("error") == expected_error, "39C has not acknowledged the pause")
    segment = sorted((study / "cases" / PAUSED_CASE).glob("seg-*"))[-1]
    record = p1.read(segment / "segment.json")
    checkpoint = segment / "end.zip"
    require(record["reason"] == "paused" and record["pause"] == "operator STOP", "incomplete pause")
    require(p1.sha(checkpoint) == record["snapshot_sha256"] == CHECKSUM, "39C checkpoint digest differs")
    world = restore(checkpoint)
    checked_metrics(world)
    require(record["end_us"] == world.time_us == PAUSED_AT, "39C checkpoint time differs")
    with ZipFile(checkpoint) as archive:
        for i, engine in world.engines.items():
            require(engine.capture_state().payload == archive.read(f"cores/{i}.json"), f"39C Core {i} differs")
    return dict(record=p1.read(study / "registration.json")["record"], case=PAUSED_CASE, time_us=world.time_us,
                checkpoint=checkpoint.relative_to(study).as_posix(), sha256=CHECKSUM, pause_utc=queue["utc"],
                core_count=len(world.engines), living=sum(b.physical for b in world.bodies.values()))


def place_on_i():
    """One atomic placement; only the unused commitments of the three closed parts can change."""
    store = p1.pool()
    with store.study_lock(BATCH), file_lock(store.lock):
        state = store._read()
        original = state["studies"][BATCH]
        require(original["status"] == "reserved", "the old batch is not open")
        if KEY in original.get("capacity_revisions", {}):
            require(p1.NAME in state["studies"], "incomplete paired reservation")
            return original["capacity_revisions"][KEY]
        require(p1.NAME not in state["studies"], "P1 already has an unrelated placement")
        require(all(t["status"] in ("complete", "cancelled") for t in state.get("transfers", {}).values()),
                "an active storage transfer must settle before this change")
        parts = {p["name"]: p for p in original["parts"]}
        require(parts["study-39c"]["bytes"] == PEAK_GIB["39C"] * GIB, "39C reservation differs")
        changes = {}
        for code in ("30", "28", "38"):
            part = parts["study-" + code]
            work = store.path(BATCH, part["name"])
            receipt = p1.read(work / "publication/complete.json")
            require(receipt["api_readback"] and receipt["bilingual_reports"] and not receipt["pending"],
                    f"missing final verification for {code}")
            require(part["directory"] == p1.DESTINATION and part["bytes"] == PEAK_GIB[code] * GIB,
                    f"unexpected original placement for {code}")
            used = volumes.tree_usage(work)
            budget = min(part["bytes"], used + GIB)
            changes[code] = dict(original_bytes=part["bytes"], observed_bytes=used, reserved_bytes=budget,
                                 verification_sha256=p1.sha(work / "publication/complete.json"))
            part["bytes"] = budget
        request = store._request(p1.NAME, p1.PARTS, False)
        request["directory_id"] = p1.DESTINATION
        placement = store._plan(state, request)
        require(placement["fits"] and placement["parts"][0]["directory"] == p1.DESTINATION, "22 GiB unavailable on I")
        revision = dict(completed_parts=changes, ongoing_39c_bytes=parts["study-39c"]["bytes"],
                        p1_bytes=placement["parts"][0]["bytes"], utc=p1.stamp())
        original.setdefault("capacity_revisions", {})[KEY] = revision
        state["studies"][p1.NAME] = placement
        atomic_json(store.file, state)
        return revision


def preserve_file(source, target):
    if not target.exists():
        with target.open("xb") as out:
            out.write(source.read_bytes())
    require(source.read_bytes() == target.read_bytes(), f"dated source differs: {source.name}")


def register_order(root, pause):
    data = root / "evidence"
    change = data / "revisions" / KEY
    rid = p1.read(root / "grant.json")["resource_id"]
    with p1.api() as client:
        old = p1.ResearchRecorder(directory("39C"), p1.PROJECT, client=client)
        old.resume_recording()
        old.append("stage", KEY, dict(action="complete-state pause for P1", **pause),
                   request_id=p1.identity("39C:" + KEY))
        old.synchronize(strict=True)
        rec = p1.ResearchRecorder(p1.CONTROL, p1.PROJECT, client=client)
        rec.resume_recording()
        rec.append("correction", KEY, dict(previous_order="four old studies, turn reports, P1",
                   order="P1, 39C resumption, turn reports", old_studies_verified=["30", "28", "38"],
                   pause=pause, amendment_sha256=p1.sha(change / "priority.md")),
                   request_id=p1.identity(KEY))
        proof = data / "protocol.zh.md"
        amendment = change / "priority.md"
        p1.attach(rec, proof, data, rid, "protocol")
        p1.attach(rec, amendment, data, rid, "support")
        rec.append("stage", "priority-start", dict(data_location=str(root), schedule=KEY),
                   request_id=p1.identity("priority-start"))
        rec.synchronize(strict=True)
        require(old.status["pending"] == rec.status["pending"] == 0, "journals have pending operations")
        entries = client.call("records.verify", dict(path=dict(project=p1.PROJECT, experiment=rec.experiment),
                                                     query=dict(hashes=False)))["evidence"]
        by_name = {item["logical_id"]: item["id"] for item in entries}
        for file in (proof, amendment):
            entry = by_name["P1:" + file.relative_to(data).as_posix()]
            response = client.client.get(f"/api/v2/projects/{p1.PROJECT}/record-evidence/{entry}/content")
            response.raise_for_status()
            require(response.content == file.read_bytes(), f"research record readback failed: {file.name}")


def archive_request(marker):
    saved = marker.with_name("priority-20261122-STOP.acknowledged")
    if saved.exists():
        require(saved.read_text(encoding="utf-8-sig").strip() == REQUEST and not marker.exists(),
                "a later operator pause is in effect")
        return
    require(marker.read_text(encoding="utf-8-sig").strip() == REQUEST, "a different operator pause is in effect")
    marker.rename(saved)


def run_p1():
    p1.prepare()
    pause = pause_receipt()
    storage = place_on_i()
    root = p1.admit()
    p1.when_api_available(p1.enroll, root)
    data = root / "evidence"
    p1.copy_frozen(data)
    change = data / "revisions" / KEY
    change.mkdir(parents=True, exist_ok=True)
    for name in ("priority.md", "priority.py"):
        preserve_file(Path(__file__).with_name(name), change / name)
    p1.exclusive_json(change / "39c-pause.json", pause)
    p1.exclusive_json(change / "storage.json", storage)
    p1.when_api_available(register_order, root, pause)
    archive_request(p1.CONTROL / "STOP")
    for block in range(len(p1.SEEDS)):
        for arm, interval in p1.SUPPLIES.items():
            p1.status("running", case=f"world-{block}-{arm}", schedule=KEY)
            p1.run_case(data, block, arm, interval)
    p1.status("verifying scientific observations and writing reports")
    (data / "analysis").mkdir(exist_ok=True)
    findings = p1.analyze(data)
    p1.exclusive_json(data / "analysis/findings.json", findings)
    p1.when_api_available(p1.deliver, root, findings)


def current_process(script):
    for process in p1.psutil.process_iter(["name", "cmdline"]):
        try:
            if "python" in (process.info["name"] or "").lower():
                for arg in process.info["cmdline"] or []:
                    path = Path(arg)
                    if path.name == script.name and (Path(process.cwd()) / path).resolve() == script:
                        return True
        except (OSError, p1.psutil.Error):
            continue
    return False


def launch(script):
    with (ADMIN / (script.stem + ".log")).open("ab") as log:
        return subprocess.Popen([sys.executable, "-B", "-u", str(script)], cwd=p1.ROOT,
                                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)


def finish_earlier_batch():
    study = directory("39C")
    pause = p1.read(p1.EXPECTED / "evidence/revisions" / KEY / "39c-pause.json")
    require(p1.sha(study / pause["checkpoint"]) == pause["sha256"] == CHECKSUM, "old checkpoint differs")
    require(not (study.parent / "STOP").exists(), "old batch has a later operator pause")
    archive_request(study / "STOP")
    driver = p1.OLD / "followthrough.py"
    collector = p1.OLD / "collect.py"
    helper = p1.ROOT / ".work/ocean63-host-retry-20261122/retry.py"
    atomic_json(ADMIN / "handback.json", dict(stage="resuming 39C", utc=p1.stamp(), checkpoint=pause))
    if not p1.gate() and not current_process(collector):
        launch(collector)
    if not (study / "calculation-complete.json").exists():
        if not current_process(driver) and not current_process(helper):
            launch(driver).wait()
        while current_process(driver) or current_process(helper):
            time.sleep(30)
        if not (study / "calculation-complete.json").exists():
            error = p1.read(study.parent / "queue.json").get("error", "")
            require("host resource reserve reached" in error and helper.is_file(), "39C paused: " + error)
            launch(helper).wait()
        require((study / "calculation-complete.json").is_file(), "39C requires attention before reporting")
    while not (p1.gate() and p1.pool().study(BATCH)["status"] == "complete"):
        require(current_process(collector), "historical report collector stopped before verification")
        time.sleep(30)
    p1.when_api_available(p1.revise)
    atomic_json(ADMIN / "handback.json", dict(stage="39C and four dated turn reports complete", utc=p1.stamp()))


def main():
    ADMIN.mkdir(parents=True, exist_ok=True)
    with p1.worker_lock(p1.CONTROL / "worker"):
        local_receipt = p1.HERE / "results/verified.json"
        receipt = p1.EXPECTED / "evidence/verified.json"
        try:
            if not (receipt.exists() and local_receipt.exists() and p1.read(receipt) == p1.read(local_receipt)):
                p1.status("preparing the authorized priority change")
                run_p1()
            p1.note_completion(p1.read(receipt.parent / "analysis/findings.json"))
            p1.pool().finish(p1.NAME)
            p1.status("complete", receipt=str(receipt))
        except Exception as exc:
            p1.status("requires attention", error=str(exc))
            raise
        try:
            finish_earlier_batch()
        except Exception as exc:
            atomic_json(ADMIN / "handback.json", dict(stage="requires attention", error=str(exc), utc=p1.stamp()))
            raise


if __name__ == "__main__":
    main()
