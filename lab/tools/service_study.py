"""Bounded, reusable research runner using public Runtime and Lab services.

Case persistence is extracted from the 2026-09-30 memory-transfer runner.
No kernel-state edits, worker claims, arbitrary plugin loading or old-data scans.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid5

import psutil

from threemind_core import Stimulus
from threemind_lab import notebooks
from threemind_lab.config import ROOT, Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_records import ResearchRecords
from threemind_runtime import create_engine
from threemind_runtime.event_observation import spike_record
from threemind_runtime.readout_config import ActivityReadoutConfig, TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.telemetry import TELEMETRY_VERSION

GIB = 1024**3


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))


def read_json(path):
    return json.loads(path.read_bytes())


def write_gzip(path, value):
    with gzip.open(path, "xb") as stream:
        stream.write(encoded(value))


@dataclass(frozen=True)
class StudyConfig:
    name: str
    title: str
    sources: Path
    work: Path
    usage_start: int
    instance_limit: int = 2048
    wall_seconds: int = 7200
    storage_soft: int = 6 * GIB
    storage_hard: int = 8 * GIB
    usage_soft_delta: int = 6
    usage_hard_delta: int = 10

    def __post_init__(self):
        work = self.work.resolve()
        base = (ROOT / ".work").resolve()
        if work == base or not work.is_relative_to(base):
            from threemind_lab.config import load_env
            from threemind_lab.research_storage import ResearchStorage

            load_env()
            storage = ResearchStorage(os.getenv("THREEMIND_STORAGE_CONTROL") or None)
            managed = storage.writable_root() / "experiments"
            if work == managed or not work.is_relative_to(managed):
                raise ValueError("dedicated managed experiments or historical .work subdirectory required")
        if not 0 <= self.usage_start <= 100 or not 0 < self.storage_soft < self.storage_hard:
            raise ValueError("invalid study budgets")
        if self.instance_limit < 1 or self.wall_seconds <= 0:
            raise ValueError("positive instance and wall budgets required")
        object.__setattr__(self, "work", work)
        object.__setattr__(self, "sources", self.sources.resolve())


class Study:
    def __init__(self, config: StudyConfig, *, prepare=False):
        self.settings, self.work, self.here = config, config.work, config.sources
        self.name = config.name
        os.environ["OMP_NUM_THREADS"] = os.environ["MKL_NUM_THREADS"] = "2"
        host_settings = Settings.from_env()
        self.db = Database(host_settings.database_url, checkpoint_backend=host_settings.checkpoint_backend)
        self.db.require_current_schema()
        self.implementation = capture_implementation("native")
        self.active_case = None
        self.last_check = self.last_storage_check = 0
        self.completed_count = None
        self.completed_wall = 0
        self.readers = {
            "structural_readout": {"enabled": False},
            "temporal_readout": asdict(TemporalReadoutConfig(max_response_us=5_000_000, baseline_us=0)),
            "activity_readout": asdict(
                ActivityReadoutConfig(
                    analysis_version=2,
                    interval_us=20000,
                    periodic_max_samples=60,
                    max_response_us=5_000_000,
                    baseline_us=0,
                    trigger_manual=False,
                )
            ),
        }
        if prepare:
            self.prepare()
        self.meta = read_json(self.work / "platform.json")
        self.project = self.meta["project_id"]
        if encoded(self.meta["settings"]) != encoded(asdict(config)):
            raise ValueError("registered study settings differ; do not silently change budgets")
        if self.implementation != self.meta["implementation"]:
            raise RuntimeError("implementation changed; create a separately registered study")
        sources = {p.relative_to(ROOT).as_posix(): p for p in self.here.glob("*.py")}
        sources[Path(__file__).resolve().relative_to(ROOT).as_posix()] = Path(__file__).resolve()
        manifest = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in sorted(sources.items())}
        self.runner_signature = digest(manifest)
        self.runner_common_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        revision = self.work / "runner-revisions" / self.runner_signature
        if not revision.exists():
            for name, path in sources.items():
                destination = revision / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
            new_json(revision / "manifest.json", manifest)
        self.records = ResearchRecords(self.db)
        self.recorder = ResearchRecorder(self.work, self.project, service=self.records, actor={'id': LOCAL_USER})
        if (self.recorder.control / 'identity.json').exists():
            self.recorder.resume_recording()
        else:
            self.recorder.register({'source_key': 'lab-exploration:' + self.here.name,
                'title': config.title, 'executor': 'ai', 'execution_status': 'running',
                'protocol': (self.here / 'design.zh.md').read_text(encoding='utf-8'),
                'protocol_version': self.meta['design_sha256'],
                'metadata': {'source_path': self.here.relative_to(ROOT).as_posix(),
                             'platform_project_id': self.project, 'implementation': self.implementation,
                             'recording_start': 'before first maintained host case'}})
        self.recorder.synchronize(strict=True)
        with self.db.tx(self.project) as tx:
            tx.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
            designs = tx.execute('SELECT id,revision,title FROM notes WHERE id=ANY(%s)',
                ([UUID(self.identity('design:' + lang)) for lang in ('zh', 'en')],)).fetchall()
        for note in designs:
            self.recorder.attach({'logical_id': f'note:{note["id"]}:r{note["revision"]}',
                'role': 'protocol', 'label': note['title'], 'format': 'text/markdown',
                'locator': {'kind': 'note', 'id': str(note['id']), 'revision': note['revision']}})
        self.recorder.synchronize(strict=True)

    def prepare(self):
        self.work.mkdir(parents=True, exist_ok=True)
        if (self.work / "platform.json").exists():
            raise RuntimeError("study already prepared; use resume operations")
        project = self.db.create_project({"id": LOCAL_USER}, self.settings.title)
        self.project = str(project["id"])
        notebook = notebooks.ensure_default(self.db, self.project, LOCAL_USER)
        with self.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        self.meta = {
            "project_id": self.project,
            "notebook_id": str(notebook["id"]),
            "started_at_epoch": time.time(),
            "database_bytes_before": size,
            "settings": asdict(self.settings),
            "implementation": self.implementation,
            "design_sha256": hashlib.sha256((self.here / "design.zh.md").read_bytes()).hexdigest(),
        }
        new_json(self.work / "platform.json", self.meta)
        self.complete_registration()

    def complete_registration(self):
        """Retry note/source publication after partial preparation, without a new project."""
        for language in ("zh", "en"):
            source = self.here / f"design.{language}.md"
            self.note(
                f"design:{language}", f"执行登记 / Study registration {language}", source.read_text(encoding="utf-8")
            )
            frozen = self.work / f"design-frozen.{language}.md"
            if not frozen.exists():shutil.copy2(source, frozen)
        for name in self.implementation["source_files"]:
            destination = self.work / "frozen-sources" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():shutil.copy2(ROOT / name, destination)

    def identity(self, name):
        return str(uuid5(UUID(self.project), name))

    def note(self, key, title, text):
        # Repository-relative Markdown links are not valid notebook URLs.
        # Resolve only local Markdown documents; do not relax URL validation.
        def document_link(match):
            label,url=match.group(1),match.group(2)
            if url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
                path=(self.here/url).resolve()
                if path.is_relative_to(ROOT) and path.is_file():
                    url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
            return f'[{label}]({url})'
        text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',document_link,text)
        saved = notebooks.save_note(
            self.db,
            self.project,
            LOCAL_USER,
            self.identity(key),
            {
                "operation_id": self.identity(key + ":write"),
                "expected_revision": 0,
                "kind": "note",
                "collection_id": self.meta["notebook_id"],
                "title": title,
                "body": {"format": "markdown", "text": text},
            },
        )
        if getattr(self, 'recorder', None):
            self.recorder.attach({'logical_id': f'note:{saved["id"]}:r{saved["revision"]}',
                'role': 'note', 'label': title, 'format': 'text/markdown',
                'locator': {'kind': 'note', 'id': str(saved['id']), 'revision': saved['revision']}})
            self.recorder.synchronize()
        return saved

    def record_file(self, path, role):
        """Index an existing original; never recopy or alter its bytes."""
        path = Path(path).resolve()
        if not path.is_relative_to(self.work) or not path.is_file():
            raise ValueError('recorded original must be a file in this experiment directory')
        storage = self.db.blobs.storage
        resource = next((r for r in storage.resources() if self.work.is_relative_to(storage.resolve_locator(r['locator']))), None)
        if resource is None:
            target_id = 'record-work:' + hashlib.sha256(str(self.work.parent).encode()).hexdigest()[:24]
            try:
                storage.target(target_id)
            except ValueError:
                storage.register_target(self.work.parent, 'Maintained research originals', target_id=target_id)
            resource = storage.register_resource('record-study:' + self.project,
                storage.locator(target_id, self.work.name), writer_mode='cooperative')
        self.records.grant_resource(self.project, {'id': LOCAL_USER}, resource['id'])
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024**2):
                checksum.update(block)
        self.recorder.attach({'logical_id': 'file:' + path.relative_to(self.work).as_posix(), 'role': role,
            'label': path.relative_to(self.work).as_posix(), 'format': ''.join(path.suffixes).lstrip('.') or 'opaque',
            'byte_count': path.stat().st_size, 'sha256': checksum.hexdigest(),
            'locator': {'kind': 'file', 'resource_id': resource['id'],
                        'member': path.relative_to(storage.resolve_locator(resource['locator'])).as_posix()}})

    def guard(self, force=False):
        now = time.time()
        if not force and now - self.last_check < 1:
            return
        self.last_check = now
        c = self.settings
        if (self.work / "STOP").exists():
            raise RuntimeError("study STOP file")
        usage = self.work / "usage.json"
        if not usage.exists() or now - usage.stat().st_mtime > 1800:
            raise RuntimeError("refresh account usage at least every 30 minutes")
        if read_json(usage)["used_percent"] >= c.usage_start + c.usage_hard_delta:
            raise RuntimeError("account budget")
        if now - self.meta["started_at_epoch"] > 12 * 3600:
            raise RuntimeError("orchestration time budget")
        if psutil.Process().memory_info().rss > 4 * GIB or psutil.virtual_memory().available < 2 * GIB:
            raise RuntimeError("memory reserve")
        if shutil.disk_usage("C:/").free < 5 * GIB or shutil.disk_usage("E:/").free < 15 * GIB:
            raise RuntimeError("disk reserve")
        active = time.monotonic() - self.active_case.born_wall if self.active_case else 0
        if self.completed_count is not None:
            if self.completed_count >= c.instance_limit or self.completed_wall + active > c.wall_seconds:
                raise RuntimeError("instance or aggregate simulation budget")
            if now - self.last_storage_check < 30:
                return
        cases = list((self.work / "cases").rglob("result.json"))
        self.completed_count = len(cases)
        self.completed_wall = sum(read_json(path)["wall_seconds"] for path in cases)
        if self.completed_count >= c.instance_limit or self.completed_wall + active > c.wall_seconds:
            raise RuntimeError("instance or aggregate simulation budget")
        local = sum(p.stat().st_size for p in self.work.rglob("*") if p.is_file())
        with self.db.tx() as tx:
            db_size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        self.storage_bytes = local + max(0, db_size - self.meta["database_bytes_before"])
        if self.storage_bytes > c.storage_soft:
            raise RuntimeError("simulation storage stop; archive reserve remains")
        self.last_storage_check = time.time()

    def allow_extension(self):
        self.guard(force=True)
        if (
            read_json(self.work / "usage.json")["used_percent"]
            >= self.settings.usage_start + self.settings.usage_soft_delta
        ):
            raise RuntimeError("extension account budget")


def case_run_spec(kernel, seed, config, readers, observe, runtime=None):
    """Explicit physical-input configuration for research runners that supply pacing.

    This only builds the recorded protocol. The caller must implement real-time
    pacing before enabling live telemetry; Core still receives ordinary stimuli.
    Existing callers retain their exact replay/unbounded defaults.
    """
    runtime = dict(runtime or {})
    allowed = {"environment", "clock", "host_telemetry", "process_telemetry", "runtime_telemetry"}
    if set(runtime) - allowed:
        raise ValueError("unsupported research runtime override")
    return RunSpec(
        kernel_id=kernel,
        seed=seed,
        config=config,
        structural_readout=readers["structural_readout"],
        temporal_readout=readers["temporal_readout"] if observe else {"enabled": False},
        activity_readout=readers["activity_readout"] if observe else {"enabled": False},
        **({"environment": "replay", "clock": "unbounded"} | runtime),
    )


class Case:
    def __init__(
        self, study, key, kernel, seed, *, config=None, parent=None, observe=False, inherited=False, runtime=None
    ):
        self.study, self.key, self.kernel, self.seed = study, key, kernel, seed
        self.id = study.identity(key)
        self.folder = study.work / "cases" / key
        self.folder.mkdir(parents=True, exist_ok=True)
        if (self.folder / "result.json").exists():
            raise RuntimeError(f"completed case must be loaded rather than overwritten: {key}")
        from threemind_runtime import birth

        start_image = birth(parent["image"]) if parent and inherited else parent["image"] if parent else None
        self.engine = (
            create_engine(state=start_image, backend="native")
            if parent
            else create_engine(dict(config or {}, seed=seed), kernel_id=kernel, backend="native")
        )
        intervention = None
        if parent and config:
            original = self.engine.capture_state()
            previous = self.engine.config.to_dict()
            self.engine.reconfigure(replace(self.engine.config, **config))
            intervention = {
                "time_us": str(self.engine.time_us),
                "before": original.digest,
                "after": self.engine.capture_state().digest,
                "before_config": previous,
                "after_config": self.engine.config.to_dict(),
                "method": "public reconfigure",
            }
        start_digest = self.engine.capture_state().digest
        self.config = self.engine.config.to_dict()
        self.spec = case_run_spec(kernel, seed, self.config, study.readers, observe, runtime)
        self.study.db.create_run(
            study.project,
            key,
            self.spec.model_dump(mode="json"),
            run_id=self.id,
            parent_id=parent["id"] if parent and not parent.get("external_project") else None,
            origin_hash=parent["image"].digest if parent else None,
            origin_kind="imported"
            if parent and parent.get("external_project")
            else "inherited"
            if inherited
            else "fork"
            if parent
            else "created",
        )
        study.recorder.append('subject', self.key, {'original_run_id': self.id, 'kernel': self.kernel,
            'seed': self.seed, 'config': self.config,
            'origin_kind': 'inherited' if inherited else 'fork' if parent else 'created',
            'parent_run_id': parent['id'] if parent else None, 'birth_state_hash': start_digest})
        study.recorder.attach({'logical_id': 'run:' + self.id, 'role': 'subject', 'label': self.key,
            'format': 'threemind.runtime-run', 'locator': {'kind': 'run', 'id': self.id}})
        study.recorder.synchronize(strict=True)
        self.events, self.observations, self.pulses = [], [], []
        if intervention:
            self.events.append(
                {
                    "key": "study:reconfigure",
                    "kind": "research_intervention",
                    "time_us": str(self.engine.time_us),
                    "payload": intervention,
                }
            )
        self.inputs = RuntimeInputs(
            study.db,
            study.project,
            self.id,
            self.engine,
            self.spec,
            {},
            0,
            initial_image=start_image.to_dict() if parent else None,
        )
        read_state = None  # Each independent probe starts its own observation window; Core clone remains exact.
        if read_state:
            read_state["session_id"] = self.id
            read_state["readouts"]["run_id"] = self.id
            read_state["input_bus"] = self.inputs.bus.capture()
        self.session = ReadoutSession(
            self.engine,
            record=self.events.append,
            config={
                "structural_readout": {"enabled": False},
                "temporal_readout": asdict(self.spec.temporal_readout),
                "activity_readout": asdict(self.spec.activity_readout),
            },
            state=read_state,
            policies=self.spec.source_policies,
            event_sink=self.event,
        )
        self.session.bus = self.inputs.bus
        self.session.host.run_id = self.id
        if self.engine.capture_state().digest != start_digest:
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
        if time.monotonic() - self.born_wall > 300:
            raise RuntimeError("case 300-second wall budget")
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
            version=TELEMETRY_VERSION
            if adapter == "host-telemetry"
            else "threemind.stimulus-unit/1"
            if adapter == "stimulus-units"
            else "anonymous-frames/1",
        )
        self.inputs.changes["envelopes"].append(item)
        self.inputs.schedule(
            item,
            [
                {
                    "stimulus": stim,
                    "labels": labels or {},
                    **({"stimulus_unit": payload["units"][0]} if adapter == "stimulus-units" else {}),
                }
            ],
        )
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

    def finish(self, extra=None):
        self.session.host.close(self.engine.time_us, "run_ended")
        self.sample(enforce_budget=False)
        image = self.engine.capture_state()
        with gzip.open(self.folder / "parent-state.json.gz", "xb") as f:
            f.write(image.payload)
        state = self.session.capture()
        context = {
            "initialized": True,
            "implementation": self.study.implementation,
            "input_bus_run_id": self.id,
            "input_bus": self.inputs.bus.capture(),
            "readouts": self.session.host.capture(),
            "start_us": "0",
            "study_protocol": self.study.meta["design_sha256"],
            "runner_sha256": self.study.runner_common_sha256,
            "runner_manifest_sha256": self.study.runner_signature,
            "observational_study": self.study.name,
        }
        changes = self.inputs.take_changes()
        write_gzip(self.folder / "inputs.json.gz", changes)
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
            input_changes=changes,
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
        self.study.recorder.append('stage', self.key + ':finish', {'run_id': self.id,
            'time_us': result['time_us'], 'state_sha256': image.digest, 'life': result['life'], 'extra': extra or {}})
        for filename, role in (('result.json', 'result'), ('inputs.json.gz', 'input'),
                               ('observations.jsonl.gz', 'process'), ('events.jsonl.gz', 'process'),
                               ('parent-state.json.gz', 'checkpoint')):
            self.study.record_file(self.folder / filename, role)
        self.study.recorder.synchronize()
        if self.study.completed_count is not None:
            self.study.completed_count += 1
            self.study.completed_wall += result["wall_seconds"]
        self.study.active_case = None
        return result | {"image": image}


def load_case(study, key):
    result = read_json(study.work / "cases" / key / "result.json")
    _, image = study.db.load_checkpoint(study.project, result["id"])
    if image.digest != result["state_sha256"]:
        raise RuntimeError("saved study state checksum mismatch")
    return result | {"image": image}
