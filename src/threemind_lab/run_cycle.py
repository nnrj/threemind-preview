from __future__ import annotations

import time
from contextlib import ExitStack
from copy import deepcopy

from threemind_core import StateImage, Stimulus
from threemind_runtime import Runtime, create_engine
from threemind_runtime.body import EnvironmentHost
from threemind_runtime.bus import OutputBus
from threemind_runtime.energy_supply import EnergySupplier
from threemind_runtime.event_observation import advance_observed, spike_record

from .checkpoints import CheckpointWriter
from .input_cycle import RuntimeInputs
from .measurements import energy_endpoints
from .protocols import RunSpec, filter_stimulus, phase_at


def run_model(worker, job):
    with ExitStack() as resources:
        return _run_model(worker, job, resources)


def _run_model(worker, job, resources):
    project, run_id = job["project_id"], job["run_id"]
    operation_id = job.get("params", {}).get("research_operation_id")
    stop_at = int(job["params"]["stop_at_us"]) if operation_id else None
    if operation_id:
        with worker.db.tx(project) as db:
            operation = db.execute(
                "SELECT * FROM research_operations WHERE id=%s AND run_id=%s AND job_id=%s",
                (operation_id, run_id, job["id"]),
            ).fetchone()
        if operation is None:
            raise ValueError("研究推进任务缺少真实操作记录。")
        if operation["status"] in ("completed", "interrupted"):
            return {"run_id": str(run_id), **operation["result"]}
        if operation["status"] != "pending":
            raise ValueError("研究操作已结束，请从当前恢复点创建新的操作。")
    row = worker.db.get_run(project, run_id)
    from .execution import run_backend

    if run_backend(row, default=worker.backend) != worker.backend:
        raise ValueError("worker backend does not match the saved host execution selection")
    spec = RunSpec(**row["spec"])
    context, previous, birth_event = {}, None, None
    if row["revision"]:
        cp, image = worker.db.load_checkpoint(project, run_id)
        context, previous = cp["context"], (cp, image.to_dict())
        if context.get("language"):
            raise ValueError("This checkpoint belongs to the language adapter; continue through Dialogue or explicitly fork its Core state")
        engine = create_engine(state=image, backend=worker.backend, kernel_id=spec.kernel_id)
    else:
        from .development import initial_state

        inherited, birth_event = initial_state(worker.db, project, row)
        if inherited is None and spec.kernel_id == "unified-associative":
            from threemind_kernels.legacy.unified_adapter import UnifiedEngine
            from threemind_kernels.registry import resolve_kernel

            engine = UnifiedEngine(resolve_kernel(spec.kernel_id).configuration(spec.config), consciousness_id=str(run_id))
        else:
            engine = (create_engine(state=inherited, backend=worker.backend, kernel_id=spec.kernel_id)
                      if inherited is not None else create_engine(spec.config, backend=worker.backend, kernel_id=spec.kernel_id))
    start = int(context.get("start_us", engine.time_us))
    saved_end = context.get("end_us", spec.deadline_us(start))
    end = int(saved_end) if saved_end is not None else None
    limits = [value for value in (end, stop_at) if value is not None]
    stop_limit = min(limits) if limits else None
    environment = EnvironmentHost(
        spec,
        engine.time_us,
        state=context.get("body_tools"),
        environment_state=context.get("environment"),
        next_input_us=context.get("next_input_us"),
    )
    resources.callback(environment.close)
    next_observation = int(context.get("next_observation_us", engine.time_us))
    source_enabled = context.get("source_enabled", True)
    phase_index = context.get("phase_index", -1)
    runtime = Runtime(engine, clock=spec.clock, speed=spec.speed)
    last_command = row["last_command"]
    observations, events = [], [birth_event] if birth_event else []

    if not context.get("initialized") and (spec.phases or spec.max_channels is not None):
        # Shared warmup may already have scheduled future external deliveries.
        # Apply the branch's declared receptor gate to those inputs as well.
        state = engine.capture_state().to_dict()
        queue = []
        for event in state["queue"]:
            if event["kind"] == "stimulus":
                if spec.kernel_id == "unified-associative":
                    from threemind_kernels.legacy.unified_adapter import LegacyStimulus

                    decoded = LegacyStimulus.from_dict(event["payload"])
                else:
                    decoded = Stimulus.from_dict(event["payload"])
                item = filter_stimulus(spec, decoded, start)
                if item is None:
                    continue
                event["payload"] = item.to_dict()
            queue.append(event)
        state["queue"] = queue
        engine = create_engine(state=StateImage.from_dict(state), backend=worker.backend)
        runtime.engine = engine
    initial_image = engine.capture_state().to_dict() if row["revision"] else None
    inputs = RuntimeInputs(worker.db, project, run_id, engine, spec, context, start, initial_image)
    energy_supplier = EnergySupplier(spec.energy_supply, engine, context.get("energy_supplier"))
    from .telemetry import RuntimeTelemetry

    telemetry = RuntimeTelemetry(spec, run_id)
    if telemetry.configs:
        events.append(
            {
                "key": f"telemetry-session:{telemetry.session_id}",
                "time_us": str(engine.time_us),
                "kind": "telemetry_session",
                "payload": telemetry.capture()
                | {
                    "previous_session": context.get("telemetry", {}).get("session_id"),
                    "reason": "physical sampling resumed; baselines reset",
                },
            }
        )
    output_bus = OutputBus()
    output_bus.subscribe("observations", lambda metric: observations.append(metric))
    from .organs import OrganHost

    # Resolve the current commit buffer lazily; checkpoint() transfers it whole.
    organs = OrganHost(spec, engine.time_us, lambda event: events.append(event), state=context.get("output_organs"))
    from .readouts import ReadoutHost

    readouts = ReadoutHost(
        spec, run_id, engine.time_us, state=context.get("readouts"), record=lambda event: events.append(event)
    )
    if not context.get("initialized"):
        if spec.environment == "replay" and not context.get("replay_loaded"):
            inputs.replay(spec.replay)
        if spec.intervention:
            engine.intervene(**spec.intervention.model_dump())
            events.append(
                {
                    "key": "initial-intervention",
                    "time_us": str(engine.time_us),
                    "kind": "intervention",
                    "payload": spec.intervention.model_dump(),
                }
            )

    def measure():
        metric = engine.metrics()
        metric.update(energy_endpoints(metric))
        if spec.environment == "robot":
            metric.update(environment.physical.task_metrics())
        metric["elapsed_us"] = str(engine.time_us - start)
        phase = phase_at(spec, engine.time_us - start)
        metric["phase"] = phase[1].name if phase else spec.phases[-1].name if spec.phases else "run"
        return metric

    last_commit_host, last_commit_sim = time.monotonic(), engine.time_us
    last_poll = -float("inf")
    status = "running"
    live_change = None
    spike_bytes = 0

    def observe(event):
        nonlocal spike_bytes
        if event["kind"] == "legacy_epoch":
            events.append({"key": f"legacy-epoch:{event['sequence']}", "time_us": event["time_us"],
                           "kind": "legacy_epoch", "payload": event["payload"]})
        elif event["kind"] == "spikes":
            spike_bytes += 200 + 12 * len(event["payload"]["nodes"])
            events.append(spike_record(event))
        elif event["kind"] == "energy":
            provider = energy_supplier.delivered(event)
            events.append(
                {
                    "key": f"energy:{event['event_id']}",
                    "time_us": event["time_us"],
                    "kind": "energy_delivered",
                    "payload": event["payload"] | {"core_event_id": event["event_id"], "provider": provider},
                }
            )
        elif event["kind"] == "modulation":
            events.append(
                {
                    "key": f"modulation:{event['event_id']}",
                    "time_us": event["time_us"],
                    "kind": "input_modulation_delivered",
                    "payload": event["payload"] | {"core_event_id": event["event_id"]},
                }
            )
        elif event["kind"] == "stimulus":
            provenance = inputs.observe(event)
            readouts.delivered(provenance)
            events.append(
                {
                    "key": f"input:{event['event_id']}",
                    "time_us": event["time_us"],
                    "kind": "input_delivered",
                    "payload": event["payload"],
                    "provenance": {k: v for k, v in (provenance or {}).items() if k != "stimulus"},
                }
            )

    with CheckpointWriter(worker.db, project, run_id, row["revision"], job=job, previous=previous) as writer:

        def commit(commit_status, *, wait=False, research_completion=None):
            nonlocal observations, events, last_commit_host, last_commit_sim, live_change
            nonlocal spike_bytes
            # Apply backpressure BEFORE allocating another snapshot. Observations
            # and events are transferred whole; none are sampled away on overload.
            writer.drain()
            spike_bytes = 0
            image = engine.capture_state()
            recovery = {
                "initialized": True,
                "protocol": spec.model_dump(),
                "start_us": str(start),
                "end_us": str(end) if end is not None else None,
                "next_input_us": str(environment.next_environment_us),
                "next_observation_us": str(next_observation),
                "source_enabled": source_enabled,
                "phase_index": phase_index,
                "environment": environment.physical_state(),
                "body_tools": environment.capture(),
                "telemetry": telemetry.capture(),
                "readouts": readouts.capture(),
                "output_organs": organs.timeline.capture(),
                "energy_supplier": energy_supplier.capture(),
                "input_bus": inputs.bus.capture(),
                "input_bus_run_id": str(run_id),
                "capture_streams": deepcopy(inputs.capture_streams),
                "device_streams": deepcopy(inputs.device_streams),
                "backend": worker.backend,
                "implementation": worker.implementation,
                "recording": "every numerical boundary"
                if spec.trace
                else "inputs + checkpoints + sampled observations",
            }
            writer.submit(
                image,
                context=recovery,
                status=commit_status,
                observations=observations,
                events=events,
                last_command=last_command,
                input_changes=inputs.take_changes(),
                research_completion=research_completion,
                live_protocol_change=live_change,
            )
            live_change = None
            observations, events = [], []
            organs.bytes = 0
            readouts.bytes = 0
            last_commit_host, last_commit_sim = time.monotonic(), engine.time_us
            if wait:
                writer.drain()

        while (stop_limit is None or engine.time_us < stop_limit) and engine.life != "dead" and not worker.stopping:
            # A failed asynchronous commit stops advancement at the next loop.
            if writer.pending is not None and writer.pending.done():
                writer.drain()
            phase = phase_at(spec, engine.time_us - start)
            if phase is not None and phase[0] != phase_index:
                phase_index = phase[0]
                events.append(
                    {
                        "key": f"phase:{phase_index}",
                        "time_us": str(engine.time_us),
                        "kind": "phase",
                        "payload": phase[1].model_dump(),
                    }
                )
                if phase[1].close_sources:
                    source_enabled = False
                    engine.close_inputs()
                    if engine.life == "dead":
                        break
            commands = []
            if time.monotonic() - last_poll >= 0.1:
                with worker.db.tx(project) as db:
                    commands = db.execute(
                        "SELECT * FROM commands WHERE run_id=%s AND id>%s ORDER BY id LIMIT 1000",
                        (run_id, last_command),
                    ).fetchall()
                last_poll = time.monotonic()
            force = False
            for cmd in commands:
                kind, payload = cmd["kind"], cmd["payload"]
                if kind == "stimulus":
                    # Historical command rows remain replayable through the same provenance path.
                    inputs.automatic(
                        f"legacy-command:{cmd['id']}",
                        "manual-anonymous",
                        Stimulus.from_dict({"time_us": str(engine.time_us), **payload}),
                        source_enabled=source_enabled,
                    )
                elif kind == "sensory_input":
                    outcome = inputs.accepted(payload["envelope_id"], source_enabled=source_enabled)
                    events.append(
                        {
                            "key": f"carrier:{cmd['id']}",
                            "time_us": str(engine.time_us),
                            "kind": "input_rejected" if outcome.get("rejected") else "input_scheduled",
                            "payload": outcome,
                        }
                    )
                    # Live packets are already durably admitted. Their scheduling,
                    # delivery audit and command cursor commit with the next regular
                    # checkpoint, atomically with Core state. Forcing a full model
                    # snapshot for every 200 ms packet starves realtime delivery.
                    # Crash recovery replays commands after the committed cursor.
                    force = force or not outcome.get("continuous_capture", False)
                elif kind in ("energy_supply", "input_modulation"):
                    try:
                        if not source_enabled:
                            raise ValueError("external inputs and supply are closed")
                        if payload.get("device"):
                            from .devices import delivery_session

                            with worker.db.tx(project) as db:
                                device = delivery_session(db, run_id, payload["device"]["session_id"])
                            if device is None or device["status"] != "active":
                                raise ValueError("device session ended before port command was processed")
                        when = engine.time_us + max(engine.config.delay_us, payload["delay_us"])
                        if kind == "energy_supply":
                            event_id = engine.supply_energy(payload["amount"], time_us=when, source=payload["source"])
                        else:
                            event_id = engine.modulate_input(
                                time_us=when,
                                **{
                                    key: payload[key]
                                    for key in ("source", "gain", "budget_multiplier", "competition_enabled", "ttl_us")
                                },
                            )
                        result = payload | {
                            "core_event_id": event_id,
                            "scheduled_time_us": str(when),
                            "status": "scheduled",
                        }
                    except ValueError as error:
                        result = payload | {"status": "rejected", "reason": str(error)}
                    events.append(
                        {
                            "key": f"port-command:{cmd['id']}",
                            "time_us": str(engine.time_us),
                            "kind": "energy_scheduled" if kind == "energy_supply" else "input_modulation_scheduled",
                            "payload": result,
                        }
                    )
                    force = True
                elif kind in ("pause", "cancel"):
                    status = "paused" if kind == "pause" else "cancelled"
                elif kind == "close_inputs":
                    source_enabled = False
                    engine.close_inputs()
                elif kind == "checkpoint":
                    force = True
                elif kind == "readout_observe":
                    try:
                        readouts.begin_observation(engine, f"command-{cmd['id']}")
                    except ValueError as error:
                        events.append(
                            {
                                "key": f"observation-rejected:{cmd['id']}",
                                "time_us": str(engine.time_us),
                                "kind": "readout_observation_rejected",
                                "payload": {"reason": str(error)},
                            }
                        )
                    force = True
                elif kind == "intervention":
                    engine.intervene(**payload)
                elif kind == "robot_control":
                    if spec.environment != "robot":
                        raise ValueError("robot control requires a robot task")
                    if payload["action"] == "reset_world":
                        from threemind_runtime.robot_factory import create_robot_world

                        # Already admitted stimuli remain in flight. Only the
                        # external world resets; brain and mapping identity stay.
                        replacement = create_robot_world(spec.robot_protocol, spec.seed, environment_seed=spec.environment_seed)
                        environment.physical.close()
                        environment.physical = replacement
                        environment.next_environment_us = engine.time_us
                    else:
                        payload = payload | environment.physical.intervene(engine.time_us, payload)
                    force = True
                elif kind == "organ_switch":
                    from .organ_controls import switch_spec

                    if live_change is None:
                        live_change = {"before": spec.model_dump(), "operations": []}
                    next_spec = switch_spec(spec.model_dump(), payload["control"], payload["enabled"])
                    live_change["operations"].append(payload)
                    live_change["after"] = next_spec
                    spec = RunSpec(**next_spec)
                    inputs.spec = spec
                    inputs.bus.policies = spec.source_policies
                    organs.timeline.reconfigure(spec.acoustic_output, spec.activation_projector, engine.time_us)
                    force = True
                else:
                    raise ValueError("unsupported command")
                events.append(
                    {"key": f"command:{cmd['id']}", "time_us": str(engine.time_us), "kind": kind, "payload": payload}
                )
                last_command = cmd["id"]
                if kind == "checkpoint" and payload.get("capture_id"):
                    # Give each named request its own acknowledged boundary.
                    # force below drains the writer before any later commands.
                    break
            if status in ("paused", "cancelled") or engine.life == "dead":
                break
            telemetry.poll(inputs, lambda event: events.append(event), source_enabled=source_enabled)
            offer = energy_supplier.prepare(engine, source_enabled=source_enabled)
            if offer is not None:
                events.append(
                    {
                        "key": f"energy-provider:{offer['event_id']}",
                        "time_us": str(engine.time_us),
                        "kind": "energy_scheduled",
                        "payload": offer,
                    }
                )
            # Preserve the final frame's delivery before pausing an official
            # finite episode. This does not kill or reset the consciousness.
            if getattr(environment.physical, "terminated", False) and engine.time_us >= environment.next_environment_us:
                status = "paused"
                events.append({"key": f"robot-episode:{engine.time_us}", "time_us": str(engine.time_us),
                               "kind": "robot_episode_ended", "payload": {"reset_required": True}})
                break
            environment.poll(engine, inputs.automatic, source_enabled=source_enabled)
            step = engine.config.step_us if spec.trace else min(20000, engine.config.step_us * 10)
            target = min(engine.time_us + step, next_observation)
            if stop_limit is not None:
                target = min(target, stop_limit)
            if energy_supplier.deadline is not None:
                target = min(target, energy_supplier.deadline)
            if organs.timeline.next_us is not None:
                target = min(target, organs.timeline.next_us)
            if readouts.next_us is not None:
                target = min(target, max(engine.time_us, readouts.next_us))
                if inputs.bus.next_time_us is not None:
                    target = min(target, inputs.bus.next_time_us)
            environment_deadline = environment.deadline(source_enabled)
            if environment_deadline is not None:
                target = min(target, environment_deadline)
            if phase is not None:
                target = min(target, start + phase[3])
                # Preserve the last integer microsecond of a half-open phase.
                # The observation AT its end may already contain recovery input.
                left_boundary = start + phase[3] - 1
                if engine.time_us < left_boundary:
                    target = min(target, left_boundary)
            if spec.clock != "unbounded":
                while (
                    not worker.stopping
                    and (time.monotonic_ns() - runtime.anchor_host) / 1e9
                    < (target - runtime.anchor_sim) / 1e6 / runtime.speed
                ):
                    runtime.pace(target)
            if worker.stopping:
                break
            if telemetry.meters:
                measured_host, measured_cpu = time.monotonic(), time.thread_time()
                expected_host = runtime.anchor_host / 1e9 + (target - runtime.anchor_sim) / 1e6
                advance_observed(engine, target, observe, record_spikes=spec.record_spikes)
                telemetry.measured(
                    time.monotonic() - measured_host,
                    time.thread_time() - measured_cpu,
                    max(0, measured_host - expected_host),
                )
            else:
                advance_observed(engine, target, observe, record_spikes=spec.record_spikes)
            readouts.observe(engine)
            organs.observe(engine)
            phase_boundary = phase is not None and engine.time_us in (start + phase[3] - 1, start + phase[3])
            if engine.time_us >= next_observation or engine.life == "dead" or phase_boundary:
                output_bus.publish(measure())
                if engine.time_us >= next_observation:
                    next_observation = engine.time_us + spec.sample_us
            if (
                force
                or spec.trace
                or organs.bytes >= 8 * 1024**2
                or readouts.bytes >= 8 * 1024**2
                or spike_bytes >= 4 * 1024**2
                or engine.time_us - last_commit_sim >= spec.checkpoint_us
                or time.monotonic() - last_commit_host >= 2
            ):
                commit("running", wait=force or spec.trace)
        if status == "running":
            status = (
                "paused"
                if worker.stopping
                else "dead"
                if engine.life == "dead"
                else "paused"
                if stop_at is not None and (end is None or engine.time_us < end)
                else "completed"
            )
        inputs.interrupt_capture(status)
        if status != "paused":
            readouts.observe(engine, force=True)
            readouts.close(engine.time_us, "cancelled" if status == "cancelled" else "run_ended")
        organs.observe(engine, final=status != "paused")
        if not observations or observations[-1]["time_us"] != str(engine.time_us):
            output_bus.publish(measure())
        else:
            observations[-1] = measure()
        completion = None
        if operation_id:
            result = {
                "target_us": str(stop_at),
                "actual_time_us": str(engine.time_us),
                "target_reached": engine.time_us == stop_at,
                "status": status,
            }
            completion = {"operation_id": operation_id, "result": result}
            events.append(
                {
                    "key": f"research-operation:{operation_id}",
                    "time_us": str(engine.time_us),
                    "kind": "research_advance",
                    "payload": completion,
                }
            )
        commit(status, wait=True, research_completion=completion)
        return {
            "run_id": str(run_id),
            "revision": writer.revision,
            "status": status,
            **(completion["result"] if completion else {}),
        }
