"""Bounded independent-world processes; no shared Core or telemetry input."""

import argparse
import json
import subprocess
import sys
import time

from experiment import HERE, ROOT, WORK, active_workers, latest

from lab.tools.ocean_cli import read_json


def main(stage, workers):
    if not 1 <= workers <= 3:
        raise ValueError("amended maximum is three workers")
    existing = active_workers()
    if existing and (stage != "forks" or any(not r["case"].startswith("phase1-") for r in existing)):
        raise RuntimeError("another E29 batch still owns a live worker")
    if stage == "forks":
        for g in (0, 1):
            result = read_json(latest(WORK / "cases" / f"phase1-{g}-core") / "result.json")
            if result["status"] != "extinct" and (
                result["status"] != "horizon_paused" or result["time_us"] != 1800000000
            ):
                raise RuntimeError("both preregistered ecological sources must finish first")
    queue = (
        [f"phase1-{g}-{m}" for g in range(3) for m in (("random", "core") if g == 1 else ("core", "random"))]
        if stage == "phase1"
        else [
            f"fork-{g}-{m}"
            for g in (0, 1)
            for m in (
                ("ecology", "recombination", "transfer", "sharing")
                if g == 0
                else ("recombination", "transfer", "sharing", "ecology")
            )
        ]
    )
    runner = HERE / "experiment.py"
    if stage in ("confirm", "controls"):
        registration = read_json(WORK / "followup-registration.json")
        prefix = "confirm-" if stage == "confirm" else "control-"
        queue = [key for key in registration["cases"] if key.startswith(prefix)]
        if stage == "controls" and not read_json(WORK / "followup-confirmation-decision.json")["passed"]:
            raise RuntimeError("independent confirmation did not pass")
        runner = HERE / "followup.py"
    batch = WORK / "batches" / f"{stage}-{time.time_ns()}"
    batch.mkdir(parents=True, exist_ok=False)
    active, outcomes = {}, []
    failed = False
    with (batch / "events.jsonl").open("x", encoding="utf-8") as record:

        def emit(value):
            row = {"observed_epoch": time.time(), **value}
            record.write(json.dumps(row, ensure_ascii=False) + "\n")
            record.flush()
            print(json.dumps(row, ensure_ascii=False), flush=True)

        try:
            while queue or active:
                while queue and not failed:
                    external = [r for r in active_workers() if r["case"] not in active]
                    if len(active) + len(external) >= workers:
                        break
                    key = queue.pop(0)
                    log = (batch / f"{key}.log").open("x", encoding="utf-8")
                    child = subprocess.Popen(
                        [sys.executable, str(runner), "case", "--case", key],
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    active[key] = (child, log)
                    emit({"event": "started", "case": key, "pid": child.pid})
                for key, (child, log) in list(active.items()):
                    code = child.poll()
                    if code is None:
                        continue
                    log.close()
                    del active[key]
                    folder = WORK / "cases" / key
                    if (folder / "result.json").exists():
                        answer = read_json(latest(folder) / "result.json")
                        ok = code == 0 and answer["status"] in ("extinct", "horizon_paused")
                        row = {k: answer[k] for k in ("status", "time_us", "wall_seconds", "error")}
                    else:
                        unavailable = (
                            key.startswith("fork-")
                            and (WORK / f"fork-group-{key.split('-')[1]}-unavailable.json").exists()
                        )
                        ok = code == 0 and unavailable
                        row = {"status": "source_extinct" if unavailable else "failed_before_result"}
                    row |= {"event": "finished", "case": key, "exit_code": code, "complete": ok}
                    outcomes.append(row)
                    emit(row)
                    failed |= not ok
                if failed:
                    # Preserve running worlds through their normal safe-stop path.
                    for marker in active_workers():
                        if marker["case"] in active:
                            path = WORK / marker["output"] / "STOP"
                            if not path.exists():
                                path.write_text("Batch safety stop; preserve state.\n", encoding="utf-8")
                    if not active:
                        break
                time.sleep(2)
        except KeyboardInterrupt:
            for marker in active_workers():
                if marker["case"] in active:
                    (WORK / marker["output"] / "STOP").write_text(
                        "Interrupted scheduler: save state.\n", encoding="utf-8"
                    )
            for child, log in active.values():
                child.wait(timeout=60)
                log.close()
            raise
        emit({"event": "batch_complete", "stage": stage, "failed": failed, "unstarted": queue})
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["phase1", "forks", "confirm", "controls"])
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    main(args.stage, args.workers)
