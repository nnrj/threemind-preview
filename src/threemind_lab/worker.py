from __future__ import annotations

import csv
import hashlib
import io
import json
import socket
import threading
import time
import zipfile
from uuid import UUID, uuid4, uuid5

import psycopg

from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.body import EnvironmentHost
from threemind_runtime.energy_supply import EnergySupplier
from threemind_runtime.event_observation import advance_observed, spike_record
from threemind_runtime.inheritance import birth  # noqa: F401 -- preserve the historical Lab import

from .database import Conflict, Database
from .experiment_bundles import TransferCancelled
from .measurements import energy_endpoints
from .protocols import StudySpec, resolve_arm
from .provenance import capture_implementation
from .statistics import compare_pairs, phase_evidence, summarize


class Worker:
    def __init__(self, database: Database, *, backend="native", name=None, max_active=2, task_family="all"):
        if task_family not in ("all", "playground", "kernel-reference"):
            raise ValueError("unsupported worker task family")
        if task_family == "kernel-reference" and backend != "reference":
            raise ValueError("kernel-reference workers require the reference backend")
        self.task_family = task_family
        self.db, self.backend = database, backend
        self.name = name or f"{socket.gethostname()}-{uuid4().hex[:8]}"
        self.max_active = max_active
        self.stopping = False
        self.implementation = capture_implementation(backend)
        self.capabilities = None
        self.announced_at = None
        self.last_optional_probe = time.monotonic()

    def refresh_optional_capabilities(self):
        """Retry an unavailable renderer only when idle, at most once per minute.

        A startup timeout is an observation, not a permanent loss of capability.
        The subprocess keeps its timeout and exact GL backend; Core never runs.
        """
        now = time.monotonic()
        if self.stopping or now - self.last_optional_probe < 60:
            return
        self.last_optional_probe = now
        from .language_tools import features as language_features

        self.capabilities["features"].update(language_features())
        self.db.announce_worker(self.name, self.capabilities)
        self.announced_at = time.monotonic()
        rgb = self.capabilities["features"].get("worker.world_rgb_v1", {})
        if rgb.get("state") != "unavailable":
            return
        from threemind_runtime.capabilities import check, world_rgb_probe

        self.capabilities["features"]["worker.world_rgb_v1"] = check("世界离屏 RGB 感官", world_rgb_probe)
        self.db.announce_worker(self.name, self.capabilities)
        self.announced_at = time.monotonic()

    def once(self):
        if self.capabilities is None:
            from threemind_runtime.capabilities import kernel_feature, probe_worker

            self.capabilities = probe_worker(self.backend)
            self.capabilities["features"][f"worker.backend:{self.backend}"] = {"state": "available"}
            default_kernel = resolve_kernel().kernel_id
            default_feature = kernel_feature(default_kernel)
            self.capabilities["features"][default_feature] = dict(self.capabilities["features"]["worker.core"])
            from .compute_tools import worker_feature

            self.capabilities["features"]["worker.transformer_v1"] = worker_feature()
            from .language_tools import features as language_features

            self.capabilities["features"].update(language_features())
            self.capabilities["features"]["worker.research_documents"] = {
                "name": "研究记录与报告",
                "state": "available",
                "reason": "固定来源采集与文档任务；不需要运行意识内核。",
            }
            self.capabilities["features"]["worker.research_events_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.experiment_bundle_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.data_bundle_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.development_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.environment_seed_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.raw_readout_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.activity_analysis_v2"] = {"state": "available"}
            self.capabilities["features"]["worker.evolution_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.ecology_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.ecology_evidence_v1"] = {"state": "available"}
            self.capabilities["features"]["worker.ecology_observer_v1"] = {
                "state": "available",
                "name": "生态观察与预警",
            }
            self.capabilities["features"]["worker.assessment_v1"] = {"state": "available", "name": "独立评估"}
            self.capabilities["features"]["worker.probe_calibration_v1"] = {
                "state": "available",
                "name": "感官与探针校准",
            }
            self.capabilities["features"]["worker.temporal_probe_v1"] = {"state": "available", "name": "时序观察实验"}
            self.capabilities["features"]["worker.temporal_reports_v1"] = {"state": "available", "name": "时序报告来源"}
            from .report_publication import capability

            self.capabilities["features"]["worker.report_export_v1"] = capability()
        self.capabilities["task_family"] = self.task_family
        self.capabilities["host_id"] = self.db.blobs.storage.host_info()["host_id"]
        self.capabilities["features"].update(self.db.blobs.features())
        if self.announced_at is None or time.monotonic() - self.announced_at >= 30:
            self.db.announce_worker(self.name, self.capabilities)
            self.announced_at = time.monotonic()
        # The database matches the local report before changing a job's lease;
        # unavailable workers may still settle exhausted leases without running.
        job = self.db.claim(self.name, max_active=self.max_active, capabilities=self.capabilities)
        if not job:
            self.refresh_optional_capabilities()
            return False
        heartbeat_stop = threading.Event()

        def heartbeat():
            while not heartbeat_stop.wait(15):
                try:
                    self.db.renew(job)
                except Conflict:
                    return
                except psycopg.OperationalError:
                    continue

        heartbeat_thread = threading.Thread(target=heartbeat, name="job-lease", daemon=True)
        heartbeat_thread.start()
        from . import permissions
        actor_context = permissions.actor_context.set(None)
        try:
            lineage = job['params'].get('execution_actor')
            authorization = job['params'].get('authorization', {})
            # Already admitted model advancement is not stopped by logout or
            # token expiry. New asynchronous data/tool operations recheck grants
            # before opening originals or applying an additional research step.
            if lineage and job['kind'] != 'run':
                permissions.restore_execution_actor(self.db, lineage, action=authorization.get('action'),
                    project=job['project_id'], resources=authorization.get('resources'))
            if job["kind"] in ("bundle_export", "bundle_import", "bundle_resume"):
                from .experiment_bundles import execute

                result = execute(self, job)
            elif job["kind"] == "transformer":
                from .transformer_tools import execute

                result = execute(self.db, job, backend=self.backend)
            elif job["kind"] == "run":
                result = self.run(job)
            elif job["kind"] == "research_plan":
                from .research_plans import execute

                result = execute(self, job)
            elif job["kind"] == "export":
                result = self.export(job)
            elif job["kind"] == "study":
                result = self.study(job)
            elif job["kind"] == "evolution":
                from .evolution import execute

                execute(self, job)
                return True  # Coordinator atomically defers/finalizes its own lease.
            elif job["kind"] == "evolution_export":
                from .evolution_export import execute

                result = execute(self.db, job)
            elif job["kind"] == "ecology":
                from .ecology_worker import execute

                result = execute(self, job)
            elif job["kind"] == "ecology_export":
                from .ecology_export import execute

                result = execute(self.db, job)
            elif job["kind"] == "ecology_observe":
                from .ecology_observers import execute

                execute(self.db, job)
                return True  # Observer commits its cursor and yields its lease atomically.
            elif job["kind"] == "analysis":
                result = self.analysis(job)
            elif job["kind"] == "probe_calibration":
                from .calibration import execute

                result = execute(self.db, job, backend=self.backend, implementation=self.implementation)
            elif job["kind"] == "data_export":
                if job["params"].get("plan_id"):
                    from .data_bundles import execute

                    result = execute(self, job)
                else:
                    result = self.data_export(job)
            elif job["kind"] in ("data_restore", "data_resume"):
                from .data_bundles import execute

                result = execute(self, job)
            elif job["kind"] == "report_source":
                from .report_sources import capture

                result = capture(self.db, job)
            elif job["kind"] == "report_export":
                from .report_exports import execute

                result = execute(self.db, job)
            else:
                raise ValueError("unknown job type")
            self.db.finish(job, result=result)
        except TransferCancelled as exc:
            try:
                self.db.finish(job, result={"cancelled": True, "reason": str(exc)}, cancelled=True)
            except Conflict:
                pass
        except Conflict:
            # A stale worker must not turn another worker's job into a failure.
            return True
        except Exception as exc:  # noqa: BLE001 -- durable job boundary: record failure and keep the worker available
            try:
                self.db.finish(
                    job, error=f"{type(exc).__name__}: {exc}"[:2000], result=getattr(exc, "execution_evidence", None)
                )
            except Conflict:
                pass
        finally:
            permissions.actor_context.reset(actor_context)
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        return True

    def serve(self):
        while not self.stopping:
            try:
                if not self.once():
                    time.sleep(0.25)
            except psycopg.OperationalError:
                # Durable state remains authoritative; a storage outage is not model death.
                time.sleep(1)

    def run(self, job):
        from .run_cycle import run_model

        return run_model(self, job)

    def export(self, job):
        if "innate_version_id" in job["params"]:
            from .development import export

            return export(self.db, job)
        from threemind_runtime.profile import profile_from_spec

        p = job["params"]
        cp, image = self.db.load_checkpoint(job["project_id"], job["run_id"], p.get("checkpoint_id"))
        format = p.get("format", "tmind")
        original = self.db.get_run(job["project_id"], job["run_id"])
        protocol = cp["context"].get("protocol") or original["spec"]
        profile = profile_from_spec(protocol)
        metadata = {
            "checkpoint_id": str(cp["id"]),
            "state_hash": image.digest,
            "time_us": str(cp["time_us"]),
            "revision": cp["revision"],
        }
        if format in ("tmind", "json"):
            raw = ArtifactCodec.encode(image, format, profile=profile)
            artifact = self.db.put_artifact(
                job,
                f"model-r{cp['revision']}.{format}",
                "application/zip" if format == "tmind" else "application/json",
                raw,
                metadata,
            )
        elif format == "evidence":
            from .evidence import export_evidence

            artifact = export_evidence(self.db, job, cp, image, protocol, profile, metadata)
        else:
            raise ValueError("unsupported export")
        return {"artifact_id": str(artifact["id"]), **metadata}

    def study(self, job):
        from contextlib import ExitStack

        with ExitStack() as resources:
            return self._study(job, resources)

    def _study(self, job, resources):
        protocol = StudySpec(**job["params"]["protocol"])
        study_id = job["params"]["study_id"]
        children = []
        for seed in protocol.seeds:
            self.db.renew(job)
            base = (
                protocol.base.model_copy(update={"seed": seed, "replay": protocol.replay_blocks[str(seed)]})
                if protocol.base.environment == "replay"
                else protocol.base.model_copy(update={"seed": seed})
            )
            engine = create_engine(base.config, backend=self.backend, kernel_id=base.kernel_id)
            from .input_cycle import RuntimeInputs

            warm_id = uuid5(UUID(study_id), f"warmup:{seed}")
            warm_spec = base.model_copy(
                update={
                    "duration_s": max(0.000001, protocol.warmup_s),
                    "phases": [],
                    "max_channels": None,
                    "actuator_feedback": True,
                }
            )
            warm_inputs = RuntimeInputs(self.db, job["project_id"], warm_id, engine, warm_spec, {}, 0)
            environment = EnvironmentHost(warm_spec, engine.time_us)
            resources.callback(environment.close)
            if protocol.base.environment == "replay":
                warm_inputs.replay(base.replay)
            end = round(protocol.warmup_s * 1e6)
            warm_events = []
            spike_bytes = [0]
            supplier = EnergySupplier(base.energy_supply, engine)

            def observe_warmup(
                event, warm_events=warm_events, warm_inputs=warm_inputs, supplier=supplier, spike_bytes=spike_bytes
            ):
                if event["kind"] == "spikes":
                    spike_bytes[0] += 200 + 12 * len(event["payload"]["nodes"])
                    if spike_bytes[0] > 64 * 1024**2:
                        raise ValueError("共同培养脉冲记录超过 64 MiB；请缩短培养、减少规模或显式关闭脉冲记录。")
                    warm_events.append(spike_record(event))
                elif event["kind"] == "energy":
                    provider = supplier.delivered(event)
                    warm_events.append(
                        {
                            "key": f"energy:{event['event_id']}",
                            "time_us": event["time_us"],
                            "kind": "energy_delivered",
                            "payload": event["payload"] | {"core_event_id": event["event_id"], "provider": provider},
                        }
                    )
                elif event["kind"] == "modulation":
                    warm_events.append(
                        {
                            "key": f"modulation:{event['event_id']}",
                            "time_us": event["time_us"],
                            "kind": "input_modulation_delivered",
                            "payload": event["payload"] | {"core_event_id": event["event_id"]},
                        }
                    )
                elif event["kind"] == "stimulus":
                    provenance = warm_inputs.observe(event)
                    warm_events.append(
                        {
                            "key": f"input:{event['event_id']}",
                            "time_us": event["time_us"],
                            "kind": "input_delivered",
                            "payload": event["payload"],
                            "provenance": {k: v for k, v in provenance.items() if k != "stimulus"},
                        }
                    )

            while engine.time_us < end and engine.life != "dead":
                offer = supplier.prepare(engine)
                if offer is not None:
                    warm_events.append(
                        {
                            "key": f"energy-provider:{offer['event_id']}",
                            "time_us": str(engine.time_us),
                            "kind": "energy_scheduled",
                            "payload": offer,
                        }
                    )
                environment.poll(engine, warm_inputs.automatic)
                target = min(end, engine.time_us + 20000)
                if supplier.deadline is not None:
                    target = min(target, supplier.deadline)
                if environment.deadline() is not None:
                    target = min(target, environment.deadline())
                advance_observed(engine, target, observe_warmup, record_spikes=base.record_spikes)
            initial = engine.capture_state()
            parent = self.db.create_run(
                job["project_id"],
                f"{protocol.name} · 共同培养 seed {seed}",
                warm_spec.model_dump(),
                run_id=warm_id,
                execution={"backend": self.backend},
            )
            if not parent["revision"]:
                self.db.save_checkpoint(
                    job["project_id"],
                    parent["id"],
                    initial,
                    context={
                        "environment": environment.physical_state(),
                        "body_tools": environment.capture(),
                        "initialized": True,
                        "recording": "warmup inputs + final checkpoint",
                        "protocol": warm_spec.model_dump(),
                        "input_bus": warm_inputs.bus.capture(),
                        "input_bus_run_id": str(warm_id),
                        "study_id": study_id,
                        "implementation": self.implementation,
                        "energy_supplier": supplier.capture(),
                    },
                    expected_revision=0,
                    status="dead" if engine.life == "dead" else "completed",
                    job=job,
                    events=warm_events,
                    input_changes=warm_inputs.take_changes(),
                    observations=[engine.metrics() | energy_endpoints(engine.metrics())],
                )
            if engine.life == "dead":
                raise ValueError(
                    f"共同培养在 {engine.time_us} μs 已死亡；已保存证据，未将死亡状态伪装成可运行实验分支。"
                )
            with self.db.tx(job["project_id"]) as db:
                origin_checkpoint = db.execute(
                    "SELECT id FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1", (parent["id"],)
                ).fetchone()
            for arm in protocol.arms:
                spec = resolve_arm(base, arm).model_copy(
                    update={
                        "study_id": study_id,
                        "condition": arm.name,
                        "block_seed": seed,
                    }
                )
                arm_engine = create_engine(state=initial, backend=self.backend)
                arm_engine.reconfigure(resolve_kernel(spec.kernel_id).configuration(spec.config))
                image = arm_engine.capture_state()
                run = self.db.create_run(
                    job["project_id"],
                    f"{arm.name} · seed {seed}",
                    spec.model_dump(),
                    origin_hash=initial.digest,
                    parent_id=parent["id"],
                    origin_checkpoint_id=origin_checkpoint["id"],
                    origin_kind="paired",
                    run_id=uuid5(UUID(study_id), f"arm:{seed}:{arm.name}"),
                    execution={"backend": self.backend},
                )
                context = {
                    "environment": environment.physical_state(),
                    "body_tools": environment.capture(),
                    "paired_origin_hash": initial.digest,
                    "energy_supplier": supplier.capture(),
                    "input_bus_run_id": str(warm_id),
                    "implementation": self.implementation,
                    "initialized": False,
                    "replay_loaded": True,
                    "next_input_us": str(environment.next_environment_us),
                }
                if not run["revision"]:
                    self.db.save_checkpoint(
                        job["project_id"],
                        run["id"],
                        image,
                        context=context,
                        expected_revision=0,
                        status="queued",
                        job=job,
                    )
                with self.db.tx(job["project_id"]) as db:
                    if (
                        run["status"] == "queued"
                        and not db.execute(
                            "SELECT id FROM jobs WHERE run_id=%s AND kind='run'", (run["id"],)
                        ).fetchone()
                    ):
                        db.execute(
                            "INSERT INTO jobs(id,project_id,run_id,kind) VALUES(%s,%s,%s,'run')",
                            (uuid4(), job["project_id"], run["id"]),
                        )
                children.append(str(run["id"]))
            environment.close()
        return {"study_id": study_id, "runs": children}

    def data_export(self, job):
        from .queries import checkpoint_rows

        p = job["params"]
        cp, image, rows = checkpoint_rows(
            self.db,
            job["project_id"],
            job["run_id"],
            p["table"],
            p["checkpoint_id"],
            minimum=p["minimum"],
            source=p.get("source"),
            revision=p.get("revision"),
        )
        format = p["format"]
        from dataclasses import fields

        from threemind_core.engine import Edge, Node

        columns = (
            list(rows[0])
            if rows
            else [f.name for f in fields(Node if p["table"] == "nodes" else Edge)]
            if p["table"] != "changes"
            else [
                "source",
                "target",
                "change",
                "weight_before",
                "weight_after",
                "weight_delta",
                "stability_before",
                "stability_after",
                "from_time_us",
                "to_time_us",
                "quality",
            ]
        )
        if format == "jsonl":
            raw = "".join(json.dumps(r, allow_nan=False) + "\n" for r in rows).encode()
        elif format == "csv":
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            raw = buffer.getvalue().encode("utf-8-sig")
        else:
            import pyarrow as pa
            import pyarrow.parquet as pq

            schema = pa.schema(
                [
                    (
                        name,
                        pa.string()
                        if name.endswith("_us") or name in ("change", "quality")
                        else pa.int64()
                        if name in ("id", "source", "target", "channel", "touches")
                        else pa.float64(),
                    )
                    for name in columns
                ]
            )
            if image.to_dict()["dynamics"] == "unified-associative":
                # Preserve historical field types instead of imposing the modern
                # node schema. Identity strings also preserve uint64 values.
                legacy_rows = [{key: str(value) if key in ("id", "source", "target", "channel")
                                and value is not None else value for key, value in row.items()} for row in rows]
                table = pa.Table.from_pylist(legacy_rows) if legacy_rows else pa.table({name: [] for name in columns})
            else:
                table = pa.Table.from_pylist(rows, schema=schema)
            output = pa.BufferOutputStream()
            pq.write_table(table, output, compression="zstd")
            raw = output.getvalue().to_pybytes()
        name = p["table"] + "." + format
        metadata = {
            "schema": "threemind.query/2",
            "selection": p,
            "checkpoint_id": str(cp["id"]),
            "revision": cp["revision"],
            "state_hash": image.digest,
            "time_us": cp["time_us"],
            "rows": len(rows),
            "columns": columns,
            "data_sha256": hashlib.sha256(raw).hexdigest(),
            "is_complete_model": False,
        }
        if image.to_dict()["dynamics"] == "unified-associative" and format == "parquet":
            metadata["identity_encoding"] = "original-string-or-decimal/1"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(name, raw)
            archive.writestr("selection.json", json.dumps(metadata, indent=2).encode())
        artifact = self.db.put_artifact(
            job, f"query-r{cp['revision']}-{p['table']}.zip", "application/zip", output.getvalue(), metadata
        )
        return {"artifact_id": str(artifact["id"]), **metadata}

    def analysis(self, job):
        p = job["params"]
        with self.db.tx(job["project_id"], repeatable=True) as db:
            study = db.execute("SELECT protocol FROM studies WHERE id=%s", (p["study_id"],)).fetchone()
            if study is None:
                raise ValueError("study not found")
            conditions = {a["name"] for a in study["protocol"]["arms"]}
            if p["control"] == p["treatment"] or not {p["control"], p["treatment"]} <= conditions:
                raise ValueError("select two distinct frozen conditions")
            runs = db.execute(
                "SELECT * FROM runs WHERE spec->>'study_id'=%s ORDER BY created_at", (p["study_id"],)
            ).fetchall()
            if not runs or any(r["status"] not in ("completed", "dead") for r in runs):
                raise ValueError("all study runs must complete before analysis")
            expected = {(seed, arm) for seed in study["protocol"]["seeds"] for arm in conditions}
            actual = {(r["spec"].get("block_seed"), r["spec"].get("condition")) for r in runs}
            if actual != expected or len(runs) != len(expected):
                raise ValueError("study membership is missing, duplicated, or outside the frozen design")
            groups = {}
            for run in runs:
                obs = db.execute(
                    "SELECT metrics FROM observations WHERE run_id=%s ORDER BY time_us", (run["id"],)
                ).fetchall()
                groups.setdefault(run["spec"]["block_seed"], {})[run["spec"]["condition"]] = (
                    run,
                    summarize([o["metrics"] for o in obs], run["spec"]),
                    phase_evidence([o["metrics"] for o in obs], run["spec"]),
                )
        pairs = []
        for seed, arms in sorted(groups.items()):
            if p["control"] not in arms or p["treatment"] not in arms:
                continue
            control, a, a_phases = arms[p["control"]]
            treatment, b, b_phases = arms[p["treatment"]]
            if control["origin_hash"] != treatment["origin_hash"]:
                raise ValueError("paired initial states differ")
            pairs.append(
                {
                    "seed": seed,
                    "control_run": str(control["id"]),
                    "treatment_run": str(treatment["id"]),
                    "origin_hash": control["origin_hash"],
                    "control_state_hash": control["state_hash"],
                    "treatment_state_hash": treatment["state_hash"],
                    "control": a,
                    "treatment": b,
                    "phase_evidence": {"control": a_phases, "treatment": b_phases},
                }
            )
        result = compare_pairs(pairs, seed=p.get("seed", 71423))
        result["phase_method"] = "half-open-microsecond/2"
        artifact = self.db.put_artifact(
            job,
            "paired-analysis.json",
            "application/json",
            json.dumps(result, indent=2, allow_nan=False).encode(),
            {"study_id": p["study_id"]},
        )
        table = io.StringIO(newline="")
        columns = [
            "metric",
            "n",
            "missing_pairs",
            "control_mean",
            "treatment_mean",
            "difference",
            "ci95_low",
            "ci95_high",
            "paired_dz",
            "p",
            "p_holm",
        ]
        writer = csv.DictWriter(table, fieldnames=columns)
        writer.writeheader()
        for row in result["metrics"]:
            writer.writerow(
                {
                    **{key: row.get(key) for key in columns},
                    "ci95_low": row["ci95"][0] if row["ci95"] else None,
                    "ci95_high": row["ci95"][1] if row["ci95"] else None,
                }
            )
        csv_artifact = self.db.put_artifact(
            job,
            "paired-endpoints.csv",
            "text/csv",
            table.getvalue().encode("utf-8-sig"),
            {"study_id": p["study_id"], "data_hash": result["data_hash"]},
        )
        return {"artifact_id": str(artifact["id"]), "csv_artifact_id": str(csv_artifact["id"]), "analysis": result}
