"""Lab-owned input audit, phase schedule and real host probes around Runtime brains."""

import time
from copy import deepcopy

from threemind_core import Stimulus
from threemind_runtime.population_participant import CoreParticipant, ParticipantConfig

from .input_cycle import RuntimeInputs
from .measurements import energy_endpoints
from .protocols import phase_at
from .telemetry import RuntimeTelemetry


class LabParticipant(CoreParticipant):
    def __init__(self, identity, image, state, *, database, project, run_id, spec, backend, record):
        self.database, self.project, self.run_id, self.spec = database, project, run_id, spec
        context = state or {}
        self.phase_index = context.get("phase_index", -1)
        self.initialized = context.get("initialized", False)
        self.last_command = context.get("last_command", 0)
        self.last_poll = -float("inf")
        self.force_checkpoint = False
        elapsed, self.phase_boundaries = 0, set()
        for phase in spec.phases:
            elapsed += round(phase.duration_s * 1e6)
            self.phase_boundaries.update((elapsed - 1, elapsed))
        self.telemetry = RuntimeTelemetry(spec, run_id)
        self.anchor_host, self.anchor_sim = time.monotonic(), image.to_dict()["time_us"]

        def inputs(owner, restored):
            return RuntimeInputs(
                database, project, run_id, owner.engine, spec, restored, 0, image.to_dict() if state else None
            )

        super().__init__(
            identity,
            image,
            spec.seed,
            backend=backend,
            options=ParticipantConfig(**{key: getattr(spec, key) for key in ParticipantConfig.model_fields}),
            state=state,
            input_factory=inputs,
            record=record,
        )
        if self.telemetry.configs:
            self.emit(
                {
                    "key": f"telemetry-session:{self.telemetry.session_id}",
                    "kind": "telemetry_session",
                    "time_us": str(self.engine.time_us),
                    "payload": self.telemetry.capture()
                    | {
                        "previous_session": context.get("telemetry", {}).get("session_id"),
                        "reason": "physical sampling resumed; baselines reset",
                    },
                }
            )

    def before_slice(self):
        if not self.initialized:
            if self.spec.intervention:
                self.engine.intervene(**self.spec.intervention.model_dump())
                self.emit(
                    {
                        "key": "initial-intervention",
                        "kind": "intervention",
                        "time_us": "0",
                        "payload": self.spec.intervention.model_dump(),
                    }
                )
            self.initialized = True
        self.boundary_reached()
        if time.monotonic() - self.last_poll >= 0.1:
            with self.database.tx(self.project) as db:
                commands = db.execute(
                    "SELECT * FROM commands WHERE run_id=%s AND id>%s ORDER BY id LIMIT 1000",
                    (self.run_id, self.last_command),
                ).fetchall()
            self.last_poll = time.monotonic()
            for command in commands:
                self.apply_command(command)
        if self.engine.life != "dead":
            self.telemetry.poll(self.inputs, self.emit, source_enabled=self.source_enabled)

    def boundary_reached(self):
        phase = phase_at(self.spec, self.engine.time_us)
        if phase and phase[0] != self.phase_index:
            self.phase_index = phase[0]
            self.emit(
                {
                    "key": f"phase:{self.phase_index}",
                    "kind": "phase",
                    "time_us": str(self.engine.time_us),
                    "payload": phase[1].model_dump(),
                }
            )
            if phase[1].close_sources:
                self.source_enabled = False
                self.engine.close_inputs()

    def is_observation_boundary(self):
        return self.engine.time_us in self.phase_boundaries

    def apply_command(self, command):
        kind, payload = command["kind"], command["payload"]
        opened = self.source_enabled and self.engine.life != "dead"
        if kind == "sensory_input":
            outcome = self.inputs.accepted(payload["envelope_id"], source_enabled=opened)
            self.emit(
                {
                    "key": f"carrier:{command['id']}",
                    "kind": "input_rejected" if outcome.get("rejected") else "input_scheduled",
                    "time_us": str(self.engine.time_us),
                    "payload": outcome,
                }
            )
        elif kind == "stimulus":
            self.inputs.automatic(
                f"legacy-command:{command['id']}",
                "manual-anonymous",
                Stimulus.from_dict({"time_us": str(self.engine.time_us), **payload}),
                source_enabled=opened,
            )
        elif kind in ("energy_supply", "input_modulation"):
            try:
                if not opened:
                    raise ValueError("external inputs and supply are closed")
                if payload.get("device"):
                    from .devices import delivery_session

                    with self.database.tx(self.project) as db:
                        device = delivery_session(db, self.run_id, payload["device"]["session_id"])
                    if device is None or device["status"] != "active":
                        raise ValueError("device session ended before port command was processed")
                when = self.engine.time_us + max(self.engine.config.delay_us, payload["delay_us"])
                event = (
                    self.engine.supply_energy(payload["amount"], time_us=when, source=payload["source"])
                    if kind == "energy_supply"
                    else self.engine.modulate_input(
                        time_us=when,
                        **{
                            key: payload[key]
                            for key in ("source", "gain", "budget_multiplier", "competition_enabled", "ttl_us")
                        },
                    )
                )
                result = payload | {"core_event_id": event, "scheduled_time_us": str(when), "status": "scheduled"}
            except ValueError as error:
                result = payload | {"status": "rejected", "reason": str(error)}
            self.emit(
                {
                    "key": f"port-command:{command['id']}",
                    "kind": "energy_scheduled" if kind == "energy_supply" else "input_modulation_scheduled",
                    "time_us": str(self.engine.time_us),
                    "payload": result,
                }
            )
        elif kind == "checkpoint":
            pass  # The owner acknowledges this with an atomic population checkpoint.
        else:
            # Campaign controls own the shared clock. Never silently turn a
            # per-brain pause/resume into an unsynchronised second worker.
            raise ValueError("individual lifecycle commands must use the ecological campaign")
        self.emit(
            {"key": f"command:{command['id']}", "kind": kind, "time_us": str(self.engine.time_us), "payload": payload}
        )
        self.last_command = command["id"]
        self.force_checkpoint = True

    def external_deadline(self):
        phase = phase_at(self.spec, self.engine.time_us)
        if phase:
            return phase[3] - 1 if self.engine.time_us < phase[3] - 1 else phase[3]
        return None

    def advance_engine(self, target):
        if not self.telemetry.meters:
            return super().advance_engine(target)
        wall, cpu = time.monotonic(), time.thread_time()
        super().advance_engine(target)
        self.telemetry.measured(
            time.monotonic() - wall,
            time.thread_time() - cpu,
            max(0, wall - self.anchor_host - (target - int(self.anchor_sim)) / 1e6),
        )

    def metrics(self):
        metric = self.engine.metrics()
        metric.update(energy_endpoints(metric))
        phase = phase_at(self.spec, self.engine.time_us)
        return metric | {
            "elapsed_us": str(self.engine.time_us),
            "phase": phase[1].name if phase else self.spec.phases[-1].name if self.spec.phases else "run",
        }

    def capture(self):
        return super().capture() | {
            "input_bus_run_id": str(self.run_id),
            "capture_streams": deepcopy(self.inputs.capture_streams),
            "device_streams": deepcopy(self.inputs.device_streams),
            "last_command": self.last_command,
            "phase_index": self.phase_index,
            "telemetry": self.telemetry.capture() if self.telemetry.configs else {},
            "initialized": self.initialized,
        }
