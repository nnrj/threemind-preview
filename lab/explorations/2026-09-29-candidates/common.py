"""Public Runtime/Lab service orchestration, with append-only study evidence."""

import copy
import gzip
import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict, replace
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import psutil

from threemind_core import Stimulus
from threemind_lab import notebooks
from threemind_lab.config import ROOT, Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.event_observation import spike_record
from threemind_runtime.readout_config import StructuralReadoutConfig, TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.telemetry import TELEMETRY_VERSION, HostTelemetryConfig, TelemetryEncoder

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/candidates-20260929"
KERNELS = ("threemind.causal/9", "threemind.continuous/1", "threemind.lif/1")
GIB = 1024**3
TEMPORAL = asdict(TemporalReadoutConfig())
READERS = {"structural_readout": asdict(StructuralReadoutConfig(enabled=False)), "temporal_readout": TEMPORAL}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(encoded(value))


def read_json(path):
    return json.loads(path.read_bytes())


def setup():
    os.environ["OMP_NUM_THREADS"] = os.environ["MKL_NUM_THREADS"] = "2"
    (ROOT / ".work/tmp").mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(ROOT / ".work/tmp")


class Study:
    def __init__(self):
        setup()
        self.db = Database(Settings.from_env().database_url)
        self.meta = read_json(WORK / "platform.json")
        self.project = self.meta["project_id"]
        self.implementation = capture_implementation("native")
        if self.implementation != self.meta["implementation"]:
            raise RuntimeError("Implementation changed after preregistration; freeze a new study")
        self.last_check = 0
        self.last_storage_check = 0
        self.active_case = None

    def guard(self, force=False):
        now = time.time()
        if not force and now - self.last_check < 1:
            return
        self.last_check = now
        if (WORK / "STOP").exists():
            raise RuntimeError("explicit budget/operator stop file")
        if now - self.meta["started_at_epoch"] > 24 * 3600:
            raise RuntimeError("24-hour study wall budget reached")
        if psutil.Process().memory_info().rss > 4 * GIB or psutil.virtual_memory().available < 2 * GIB:
            raise RuntimeError("process/host memory budget reached")
        if any(shutil.disk_usage(d).free < 15 * GIB for d in ("D:/", "E:/")):
            raise RuntimeError("15 GiB storage reserve reached")
        # Metadata scans must not run at the per-second safety-check cadence.
        # Once scanning costs >= 1 s, that design otherwise rescans every step.
        if not force and now - self.last_storage_check < 60:
            return
        # This directory belongs exclusively to this study, never scan old data.
        size = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        if size > 7.5 * GIB:
            raise RuntimeError("8 GiB local evidence hard limit reached")
        with self.db.tx() as db:
            current = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        if max(0, current - self.meta["database_bytes_before"]) + size > 19.5 * GIB:
            raise RuntimeError("20 GiB new storage budget reached")
        self.last_storage_check = self.last_check = time.time()

    def identity(self, name):
        return str(uuid5(UUID(self.project), name))


def prepare():
    setup()
    WORK.mkdir(parents=True, exist_ok=True)
    if (WORK / "platform.json").exists():
        raise RuntimeError("study already exists; use its resume commands")
    db = Database(Settings.from_env().database_url)
    try:
        db.require_current_schema()
        with db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        project = db.create_project({"id": LOCAL_USER}, "2026-09-29 多内核初步对照")
        notebook = notebooks.ensure_default(db, project["id"], LOCAL_USER)
        meta = {
            "project_id": str(project["id"]),
            "notebook_id": str(notebook["id"]),
            "started_at_epoch": time.time(),
            "database_bytes_before": size,
            "usage_start_percent": 32,
            "usage_stop_percent": 42,
            "implementation": capture_implementation("native"),
            "design_sha256": hashlib.sha256((HERE / "design.md").read_bytes()).hexdigest(),
        }
        note_id = uuid4()
        notebooks.save_note(
            db,
            project["id"],
            LOCAL_USER,
            note_id,
            {
                "operation_id": str(uuid4()),
                "expected_revision": 0,
                "kind": "note",
                "collection_id": str(notebook["id"]),
                "title": "实验设计：三内核校准、适应、配对与上下文",
                "body": {"format": "markdown", "text": (HERE / "design.md").read_text(encoding="utf-8")},
            },
        )
        meta["design_note_id"] = str(note_id)
        new_json(WORK / "platform.json", meta)
        shutil.copy2(HERE / "design.md", WORK / "design-frozen.md")
        print(json.dumps({"project": meta["project_id"], "note": meta["design_note_id"]}), flush=True)
    finally:
        db.close()


class Case:
    def __init__(self, study, key, kernel, seed, *, config=None, parent=None, observe=False):
        self.study, self.key, self.kernel, self.seed = study, key, kernel, seed
        self.id = study.identity(key)
        self.folder = WORK / "cases" / key
        self.folder.mkdir(parents=True, exist_ok=True)
        if (self.folder / "result.json").exists():
            raise RuntimeError(f"completed case must be loaded rather than overwritten: {key}")
        self.engine = (
            create_engine(state=parent["image"], backend="native")
            if parent
            else create_engine(dict(config or {}, seed=seed), kernel_id=kernel, backend="native")
        )
        self.config = self.engine.config.to_dict()
        self.spec = RunSpec(
            kernel_id=kernel,
            environment="replay",
            clock="unbounded",
            seed=seed,
            config=self.config,
            structural_readout=READERS["structural_readout"],
            temporal_readout=TEMPORAL,
        )
        self.study.db.create_run(
            study.project,
            key,
            self.spec.model_dump(mode="json"),
            run_id=self.id,
            parent_id=parent["id"] if parent else None,
            origin_hash=parent["image"].digest if parent else None,
            origin_kind="fork" if parent else "created",
        )
        self.events, self.observations, self.pulses = [], [], []
        self.inputs = RuntimeInputs(
            study.db,
            study.project,
            self.id,
            self.engine,
            self.spec,
            {},
            0,
            initial_image=parent["image"].to_dict() if parent else None,
        )
        read_state = copy.deepcopy(parent["session"]) if parent else None
        if read_state:
            read_state["session_id"] = self.id
            read_state["readouts"]["run_id"] = self.id
            read_state["input_bus"] = self.inputs.bus.capture()
        self.session = ReadoutSession(
            self.engine,
            record=self.events.append,
            config=READERS,
            state=read_state,
            policies=self.spec.source_policies,
            event_sink=self.event,
        )
        self.session.bus = self.inputs.bus
        self.session.host.run_id = self.id
        if parent and self.engine.capture_state().digest != parent["image"].digest:
            raise RuntimeError("fork observation setup changed kernel state")
        self.born_wall = time.monotonic()
        self.sent = 0
        self.observe = observe
        study.active_case = self
        self.sample()

    def event(self, event, delivered):
        if delivered:
            self.inputs.changes["delivered"].append(delivered)
        if event["kind"] == "spikes":
            self.events.append(spike_record(event))

    def guard(self):
        self.study.guard()
        if time.monotonic() - self.born_wall > 600:
            raise RuntimeError("case 600-second wall budget")
        if len(self.events) > 200000 or len(self.observations) > 200000:
            raise RuntimeError("case event/observation budget; no silent truncation")

    def sample(self, *, enforce_budget=True):
        value = self.engine.metrics()
        if self.kernel.endswith("lif/1"):
            value["physical_nodes"] = self.engine.physical_nodes()
        if enforce_budget and (value["nodes"] > 2000 or value["edges"] > 20000):
            raise RuntimeError("case network safety budget; not a Core parameter change")
        self.observations.append(value)
        return value

    def send(
        self, channels, dose, *, at=None, source="training", labels=None, payload=None, adapter="anonymous-frames"
    ):
        at = self.engine.time_us if at is None else at
        stim = Stimulus(at, tuple((c, 1.0) for c in channels), dose)
        return self.send_stimulus(stim, source=source, labels=labels, payload=payload, adapter=adapter)

    def send_stimulus(self, stim, *, source, labels=None, payload=None, adapter="anonymous-frames"):
        if self.engine.life == "dead":
            return None
        self.sent += 1
        item = envelope_record(
            uuid5(UUID(self.id), f"input:{self.sent}"),
            adapter,
            source,
            payload or {"frames": [stim.to_dict()]},
            {"study": self.study.meta["design_sha256"], "dose": stim.intensity},
            1,
            len(stim.channels),
            version=TELEMETRY_VERSION if adapter == "host-telemetry" else "anonymous-frames/1",
        )
        self.inputs.changes["envelopes"].append(item)
        self.inputs.schedule(item, [{"stimulus": stim, "labels": labels or {}}])
        return item["id"]

    def advance(self, target, *, fast_sample=False):
        quantum = (1000 if self.kernel.endswith("lif/1") else 10000) if fast_sample else 100000
        while self.engine.time_us < target and self.engine.life != "dead":
            self.guard()
            self.session.advance_to(min(target, self.engine.time_us + quantum), guard=self.guard)
            self.sample()
        return self.engine.life != "dead"

    def pulse(self, channels, dose, gap, *, source="training", measure=False):
        if self.engine.life == "dead":
            return False
        start = self.engine.time_us
        before = self.engine.metrics()
        begin = len(self.observations)
        envelope = self.send(channels, dose, source=source)
        self.session.advance_to(start, guard=self.guard)
        self.sample()
        self.advance(start + gap, fast_sample=measure)
        rows = self.observations[begin:]
        after = self.engine.metrics()
        self.pulses.append(
            {
                "envelope": envelope,
                "start_us": str(start),
                "end_us": str(self.engine.time_us),
                "channels": channels,
                "dose": dose,
                "peak_total": max((r["activation"] for r in rows), default=0),
                "peak_mean": max((r["activation"] / max(1, r["nodes"]) for r in rows), default=0),
                "saturated_sample_fraction": sum(r.get("saturated_fraction", 0) for r in rows) / max(1, len(rows)),
                "spikes_delta": after.get("spikes", 0) - before.get("spikes", 0),
                "transport_before": before.get("transport"),
                "transport_after": after.get("transport"),
                "life": self.engine.life,
            }
        )
        return self.engine.life != "dead"

    def add_background(self, block):
        path = WORK / f"host-{block}.jsonl"
        if not path.with_suffix(".complete.json").exists():
            raise RuntimeError("real background capture not complete")
        encoder = TelemetryEncoder(self.seed, HostTelemetryConfig(enabled=True))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            stim, audit = encoder.encode(
                r["measurements"], monotonic_s=r["monotonic_s"], delivery_us=r["elapsed_us"] + 1_000_000
            )
            if stim:
                self.send_stimulus(
                    replace(stim, intensity=0.2),
                    source="host-telemetry",
                    adapter="host-telemetry",
                    payload={"sample": r["index"], "recording_sha256": sha, "audit": audit, "frames": [stim.to_dict()]},
                )

    def finish(self, extra=None):
        self.session.host.close(self.engine.time_us, "run_ended")
        self.sample(enforce_budget=False)
        image = self.engine.capture_state()
        state = self.session.capture()
        context = {
            "initialized": True,
            "implementation": self.study.implementation,
            "input_bus_run_id": self.id,
            "input_bus": self.inputs.bus.capture(),
            "readouts": self.session.host.capture(),
            "start_us": "0",
            "study_protocol": self.study.meta["design_sha256"],
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        self.study.db.save_checkpoint(
            self.study.project,
            self.id,
            image,
            expected_revision=0,
            status="dead"
            if self.engine.life == "dead"
            else "blocked"
            if (extra or {}).get("budget_stop")
            else "paused",
            context=context,
            events=self.events,
            observations=self.observations,
            input_changes=self.inputs.take_changes(),
        )
        result = {
            "id": self.id,
            "key": self.key,
            "kernel": self.kernel,
            "seed": self.seed,
            "config": self.config,
            "state_sha256": image.digest,
            "life": self.engine.life,
            "time_us": str(self.engine.time_us),
            "metrics": self.engine.metrics(),
            "pulses": self.pulses,
            "wall_seconds": time.monotonic() - self.born_wall,
            "session": state,
            "extra": extra or {},
        }
        with gzip.open(self.folder / "observations.jsonl.gz", "xb") as f:
            for row in self.observations:
                f.write(encoded(row) + b"\n")
        with gzip.open(self.folder / "events.jsonl.gz", "xb") as f:
            for row in self.events:
                f.write(encoded(row) + b"\n")
        new_json(self.folder / "result.json", result)
        self.study.active_case = None
        return result | {"image": image}


def load_case(study, key):
    result = read_json(WORK / "cases" / key / "result.json")
    _, image = study.db.load_checkpoint(study.project, result["id"])
    if image.digest != result["state_sha256"]:
        raise RuntimeError("saved study state checksum mismatch")
    return result | {"image": image}
