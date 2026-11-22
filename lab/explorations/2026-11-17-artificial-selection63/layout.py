"""Explicit world-layout and motor-replay research copies; Core is unmodified."""
import argparse
import copy
import gc
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid5

import ring as r
import study
from lab.tools.study_lock import worker_lock

WORK = r.ROOT / ".work/artificial-selection63-layout-20261117"


class LayoutRing(r.Ring):
    def __init__(self, *args, phase=0., replay=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.body["phase"] = phase
        self.replay = replay
        self.proposed = []
        self.ancestry["declared_layout_phase"] = phase
        self.ancestry["applied_motor_source"] = "saved-original-layout-actions" if replay is not None else "current-core-activity"
        self.origin = self.snapshot()

    def stimulus(self, now, background=False):
        if background:
            return super().stimulus(now, True)
        region = int((self.body["x"] + self.body["phase"]) % 1 >= .5)
        channels = [(r.channel_id(self.seed, r.SENSE_NS, region*4+i), 1.) for i in range(4)]
        if self.body["v"]:
            channels.append((r.channel_id(self.seed, r.SENSE_NS, 8+int(self.body["v"] < 0)),
                             r.math.tanh(abs(self.body["v"])/.375)))
        return r.Stimulus(now, tuple(channels), .8)

    def control(self, nodes):
        value = super().control(nodes)
        self.proposed.append({"step": len(self.rows), "control": value})
        return self.replay[len(self.rows)] if self.replay is not None else value

    def run_layout(self, seconds=60, guard=None):
        result = super().run(seconds, guard=guard)
        proposed = {p["step"]: p["control"] for p in self.proposed}
        for i, row in enumerate(self.rows):
            row["physical_region"] = row["region"]
            row["region"] = int((row["body"]["x"] + row["body"]["phase"]) % 1 >= .5)
            row["proposed_control"] = proposed.get(i, 0.)
            row["applied_control"] = row["control"]
        result["region1"] = sum(row["region"] for row in self.rows) / len(self.rows)
        result["phase"] = self.body["phase"]
        result["replayed"] = self.replay is not None
        return result


def execute(folder, key, seed, *, whole, position, phase, replay=None, seconds=60, guard=None):
    if (folder / "result.json").exists():
        return r.read(folder / "result.json")
    if folder.exists():
        raise RuntimeError("Preserve incomplete layout evidence: " + str(folder))
    folder.mkdir(parents=True)
    obj = LayoutRing(key, seed, whole=whole, position=position, phase=phase, replay=replay)
    for field in ("core", "session", "supplier", "next_sense", "next_background", "next_motor"):
        assert obj.origin[field] == whole[field], field
    r.save(folder / "initial.json.gz", obj.origin)
    r.save(folder / "ancestry.json", obj.ancestry)
    try:
        result = obj.run_layout(seconds, guard=guard)
    except BaseException:
        r.save(folder / "interrupted.json.gz", obj.snapshot())
        r.save(folder / "interrupted-trace.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
        raise
    final = obj.snapshot()
    assert r.digest(final) == result["final_whole_hash"]
    r.save(folder / "final.json.gz", final)
    r.save(folder / "trajectory.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
    r.save(folder / "result.json", result)
    return result


def apparatus(work):
    destination = work / "apparatus-v1"
    assert not destination.exists()
    normal = r.Ring("layout-independent-apparatus", r.INSTRUMENT_SEED, position=.125)
    reference = normal.run(3)
    initial = normal.origin
    closed = LayoutRing("layout-independent-apparatus", r.INSTRUMENT_SEED, whole=initial, phase=0)
    a = closed.run_layout(3)
    actions = [x["control"] for x in normal.rows]
    replay = LayoutRing("layout-independent-apparatus", r.INSTRUMENT_SEED, whole=initial, phase=0, replay=actions)
    b = replay.run_layout(3)
    assert normal.snapshot() == closed.snapshot() == replay.snapshot()
    assert reference["region1"] == a["region1"] == b["region1"]
    swapped = LayoutRing("layout-independent-apparatus", r.INSTRUMENT_SEED, whole=initial, phase=.5)
    assert normal.stimulus(0).channels != swapped.stimulus(0).channels
    swap_result = swapped.run_layout(3)
    assert swapped.origin["core"] == initial["core"]
    assert all(row["region"] == 1-row["physical_region"] for row in swapped.rows)
    for name, obj, result in (("reference", normal, reference), ("closed", closed, a),
                               ("replay", replay, b), ("swapped", swapped, swap_result)):
        r.save(destination / name / "initial.json.gz", obj.origin)
        r.save(destination / name / "final.json.gz", obj.snapshot())
        r.save(destination / name / "trajectory.json.gz", {"rows": obj.rows, "inputs": obj.inputs, "events": obj.events})
        r.save(destination / name / "result.json", result)
    r.save(work / "apparatus.json", {"passed": True, "seed": r.INSTRUMENT_SEED,
        "normal_closed_replay_whole_hash": r.digest(normal.snapshot()),
        "swapped_core_initial_unchanged": True, "swapped_channel_identity_checked": True})


def client_context():
    import httpx
    from threemind_lab.config import load_env
    from threemind_lab.operations_client import OperationsClient
    load_env()
    return OperationsClient(url="http://127.0.0.1:8877", username=os.environ.get("THREEMIND_API_USERNAME"),
        password=os.environ.get("THREEMIND_API_PASSWORD"), token=os.environ.get("THREEMIND_API_TOKEN"),
        transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source="ai")


def register(work, main):
    from threemind_lab.research_recorder import ResearchRecorder
    assert r.read(work / "apparatus.json")["passed"]
    assert not (work / "registration.json").exists()
    sources = [r.HERE / n for n in ("ring.py", "study.py", "layout.py", "layout-protocol.zh.md", "layout-protocol.en.md")]
    for source in sources:
        dest = work / "frozen-source" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    r.save(work / "frozen.json", {"sources": {p.name: study.sha(p) for p in sources},
        "main_registration": r.read(main / "registration.json"), "main_frozen_sha256": study.sha(main / "frozen.json")})
    with client_context() as client:
        recorder = ResearchRecorder(work, study.PROJECT, client=client)
        recorder.register({"source_key": "as63-02:layout-control:20261117:v1",
            "title": "AS63-02：人工选择后代的布局变化与动作重放对照",
            "classification": "formal", "execution_status": "running", "executor": "ai",
            "kernels": [r.KERNEL], "protocol": (r.HERE / "layout-protocol.zh.md").read_text("utf8"),
            "protocol_version": study.sha(r.HERE / "layout-protocol.zh.md"),
            "required_roles": ["protocol", "report", "note", "original"],
            "metadata": {"independent_populations": 16, "stages": 768, "additional_control": True,
                         "main_record": r.read(main / "registration.json")["record"]}},
            request_id=uuid5(r.NS, "layout-register"))
        for lang in ("zh", "en"):
            recorder.text({"identity": str(uuid5(r.NS, "layout-protocol-document-"+lang)),
                "request_id": str(uuid5(r.NS, "layout-protocol-"+lang)), "expected_revision": 0,
                "kind": "protocol", "title": "AS63-02 protocol "+lang,
                "markdown": (r.HERE / f"layout-protocol.{lang}.md").read_text("utf8")})
        recorder.synchronize(strict=True)
        r.save(work / "registration.json", {"project": study.PROJECT, "record": recorder.experiment,
            "pending": recorder.status["pending"], "registered_before_layout_interventions": True})
    print(json.dumps(r.read(work / "registration.json")), flush=True)


def run(work, main):
    import psutil
    assert r.read(main / "science-complete.json")["populations"] == 16
    assert r.read(work / "registration.json")["pending"] == 0
    frozen = r.read(work / "frozen.json")
    for name, expected in frozen["sources"].items():
        assert study.sha(r.HERE / name) == expected, name
    study.frozen_check(main)
    assert not (work / "in-flight.json").exists()
    lock = worker_lock(work)
    try:
        start = time.monotonic()
        total = 0
        old_bytes = sum(p.stat().st_size for p in work.rglob("*") if p.is_file())
        added_bytes = 0
        last_check = 0.
        def guard():
            nonlocal last_check
            now = time.monotonic()
            if now-last_check >= 1:
                study.guard(work)
                last_check = now
            if now-start > 3600:
                raise RuntimeError("layout one-hour budget")
            if old_bytes+added_bytes > 2**30:
                raise RuntimeError("layout one-GiB original budget")
        for seed in r.SEEDS:
            folder = work / "populations" / str(seed)
            if (folder / "complete.json").exists():
                raise RuntimeError("prior completed layout populations require explicit continuation review")
            r.save(work / "in-flight.json", {"seed": seed, "pid": os.getpid(), "created": psutil.Process().create_time()})
            rows = []
            for arm in study.ARMS:
                for i in range(4):
                    candidate = main / "populations" / str(seed) / arm / "g2" / f"c{i}"
                    whole = r.read(candidate / "development/final.json.gz")
                    for j in (0, 2):
                        base = candidate / f"held-{j}"
                        baseline = r.read(base / "result.json")
                        trace = r.read(base / "trajectory.json.gz")
                        assert baseline["life"] != "dead", "cannot silently use incomplete motor series"
                        actions = [row["control"] for row in trace["rows"]]
                        for condition in ("closed", "replay"):
                            key = f"{arm}/c{i}/held-{j}/{condition}"
                            result = execute(folder / key, key, seed, whole=whole, position=r.TEST_STARTS[j],
                                phase=.5, replay=actions if condition == "replay" else None, guard=guard)
                            added_bytes += sum(p.stat().st_size for p in (folder / key).iterdir() if p.is_file())
                            rows.append({"seed": seed, "arm": arm, "candidate": i, "start_index": j,
                                "condition": condition, "baseline_key": baseline["key"], "baseline_region1": baseline["region1"],
                                "region1": result["region1"], "result": result})
                            total += 1
                            if total % 16 == 0:
                                gc.collect()
                                progress = {"stages": total, "planned": 768, "seed": seed, "wall_seconds": time.monotonic()-start}
                                (work / "progress.json").write_text(json.dumps(progress), encoding="utf8")
                                print(json.dumps(progress), flush=True)
            r.save(folder / "complete.json", {"seed": seed, "rows": rows})
            (work / "in-flight.json").unlink()
        r.save(work / "science-complete.json", {"populations": 16, "stages": total, "wall_seconds": time.monotonic()-start})
    finally:
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("apparatus", "register", "run"))
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--main", type=Path, default=study.DEFAULT_WORK)
    args = parser.parse_args()
    if args.command == "apparatus":
        apparatus(args.work.resolve())
        print("layout apparatus passed")
    elif args.command == "register":
        register(args.work.resolve(), args.main.resolve())
    else:
        run(args.work.resolve(), args.main.resolve())
