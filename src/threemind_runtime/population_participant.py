"""A mutable, database-free participant with the existing Runtime input/output tools.

Lab can supply its audited input gateway and subclass the slice hooks for commands,
phases and physical telemetry. Core and the population coordinator do not own those
services. Every observation goes through an optional, read-only evidence subscriber.
"""

from __future__ import annotations

from dataclasses import asdict

from pydantic import Field

from threemind_core import Stimulus

from .body import BodyFilter, BodyFilterConfig, InteroceptionConfig, interoceptive_frame
from .bus import InputBus, OutputBus
from .energy_supply import EnergySupplier, EnergySupplyConfig
from .event_observation import advance_observed, spike_record
from .host import create_engine
from .media import AcousticConfig, ProjectorConfig
from .output_organs import OutputOrgans
from .readout_config import StructuralReadoutConfig, TemporalReadoutConfig
from .readout_host import ReadoutHost
from .sensory import InputBusConfig
from .source_policies import SourcePolicies
from .world_schema import Model, digest


class ParticipantConfig(Model):
    input_bus: InputBusConfig = Field(default_factory=InputBusConfig)
    source_policies: SourcePolicies = Field(default_factory=SourcePolicies)
    body_filter: BodyFilterConfig = Field(default_factory=BodyFilterConfig)
    interoception: InteroceptionConfig = Field(default_factory=InteroceptionConfig)
    energy_supply: EnergySupplyConfig = Field(default_factory=EnergySupplyConfig)
    acoustic_output: AcousticConfig = Field(default_factory=AcousticConfig)
    activation_projector: ProjectorConfig = Field(default_factory=ProjectorConfig)
    structural_readout: StructuralReadoutConfig = Field(default_factory=StructuralReadoutConfig)
    temporal_readout: TemporalReadoutConfig = Field(default_factory=TemporalReadoutConfig)
    actuator_feedback: bool = True
    sample_us: int = Field(default=100000, ge=1000, le=10000000)
    trace: bool = False
    record_spikes: bool = True


class PortableInputs:
    """Same gateway shape as Lab RuntimeInputs; evidence ownership stays with caller."""

    def __init__(self, owner, state=None):
        self.owner = owner
        self.bus = InputBus(owner.engine, state, owner.options.input_bus, owner.options.source_policies)
        if state:
            self.bus.verify(owner.engine.capture_state().to_dict())

    def automatic(
        self,
        key,
        adapter_id,
        stimulus,
        *,
        source_enabled=True,
        configuration=None,
        raw_stimulus=None,
        filter_reason=None,
        transduction=None,
    ):
        policy = self.owner.options.source_policies.resolve(adapter_id)
        metadata = {
            "envelope_id": f"{self.owner.identity}:{key}",
            "frame_index": 0,
            "frame_count": 1,
            "first_scheduled_index": 0,
            "last_scheduled_index": 0,
            "scheduled_frame_count": 1,
            "adapter_id": adapter_id,
            "source": adapter_id,
            "budgeted": False,
            "configuration_hash": digest(configuration or {}),
            "labels": {},
        }
        enabled = source_enabled and policy["enabled"] and filter_reason is None and self.owner.engine.life != "dead"
        receipt = (
            self.bus.schedule(stimulus, metadata)
            if enabled
            else metadata
            | {
                "status": "filtered",
                "reason": filter_reason
                or (
                    "core_dead"
                    if self.owner.engine.life == "dead"
                    else "sources_closed"
                    if not source_enabled
                    else policy["reason"]
                ),
            }
        )
        self.owner.emit(
            {
                "kind": "input_scheduled",
                "time_us": str(self.owner.engine.time_us),
                "payload": {
                    "receipt": receipt,
                    "raw_stimulus": (raw_stimulus or stimulus).to_dict(),
                    "requested_stimulus": stimulus.to_dict(),
                    "configuration": configuration or {},
                    "transduction": transduction,
                    "source_policy": policy,
                },
            }
        )

    def observe(self, event):
        return self.bus.observe(event)


class CoreParticipant:
    def __init__(
        self,
        identity,
        image,
        sensory_seed,
        *,
        backend="native",
        options=None,
        state=None,
        input_factory=None,
        record=None,
    ):
        self.identity, self.seed = str(identity), sensory_seed
        self.backend = backend
        options = options or ParticipantConfig()
        self.options = ParticipantConfig.model_validate_json(options.model_dump_json())
        self.engine = create_engine(state=image, backend=backend)
        self.output = OutputBus()
        if record is not None:
            self.output.subscribe("evidence", record)
        self.record_sequence = 0
        self.source_enabled, self.body_enabled = True, True
        self.next_interoception_us = self.next_observation_us = self.engine.time_us
        self.dead_recorded = False
        context = state or {}
        if state:
            if any(state.get(k) != v for k, v in self.contract().items()):
                raise ValueError("participant tools or identity changed; exact continuation refused")
            for field in ("source_enabled", "body_enabled", "dead_recorded"):
                if type(state.get(field)) is not bool:
                    raise ValueError("invalid participant lifecycle state")
                setattr(self, field, state[field])
            for field in ("record_sequence", "next_interoception_us", "next_observation_us"):
                if type(state.get(field)) is not int or state[field] < 0:
                    raise ValueError("invalid participant observation clock")
                setattr(self, field, state[field])
        self.inputs = input_factory(self, context) if input_factory else PortableInputs(self, context.get("input_bus"))
        self.body_filter = BodyFilter(self.options.body_filter, sensory_seed, context.get("body_filter"))
        self.energy = EnergySupplier(self.options.energy_supply, self.engine, context.get("energy_supplier"))
        self.readouts = ReadoutHost(
            self.options, self.identity, self.engine.time_us, state=context.get("readouts"), record=self.emit
        )
        self.organs = OutputOrgans(
            self.options.acoustic_output,
            self.options.activation_projector,
            self.engine.time_us,
            state=context.get("output_organs"),
        )
        self.organs.output.subscribe(
            "evidence",
            lambda payload: self.emit({"kind": "organ_output", "time_us": payload["time_us"], "payload": payload}),
        )

    def contract(self):
        options = self.options.model_dump(mode="json")
        if options.pop("record_spikes") is False:
            options["record_spikes"] = False
        return {
            "schema": "threemind.population-participant/1",
            "identity": self.identity,
            "sensory_seed": self.seed,
            "options_hash": digest(options),
        }

    def emit(self, event):
        # Add our envelope without copying nested evidence for an unused output.
        # OutputBus isolates each actual consumer, including retained callbacks.
        event = dict(event)
        event.setdefault("key", f"participant:{self.record_sequence}")
        self.record_sequence += 1
        self.output.publish(event)

    def actions(self):
        return self.engine.activations() if self.options.actuator_feedback and self.engine.life != "dead" else None

    def receive(self, frame, evidence):
        effective, filtered = self.body_filter.process(frame)
        self.inputs.automatic(
            f"population-world:{evidence['global_delivery_us']}",
            "mujoco",
            effective if effective is not None else Stimulus(frame.time_us, (), frame.intensity),
            source_enabled=self.source_enabled and self.body_enabled and self.engine.life != "dead",
            raw_stimulus=frame,
            filter_reason=None if effective is not None else filtered["reason"],
            transduction={"population": evidence, "body_filter": filtered},
            configuration={
                "seed": self.seed,
                "body_filter": asdict(self.options.body_filter),
                "world_hash": evidence["world_hash"],
                "ecology_hash": evidence["ecology_hash"],
            },
        )

    def observe(self, event):
        if event["kind"] == "spikes":
            self.emit(spike_record(event))
        elif event["kind"] == "stimulus":
            provenance = self.inputs.observe(event)
            self.readouts.delivered(provenance)
            self.emit(
                {
                    "key": f"input:{event['event_id']}",
                    "kind": "input_delivered",
                    "time_us": event["time_us"],
                    "payload": event["payload"],
                    "provenance": {k: v for k, v in (provenance or {}).items() if k != "stimulus"},
                }
            )
        elif event["kind"] == "energy":
            self.emit(
                {
                    "key": f"energy:{event['event_id']}",
                    "kind": "energy_delivered",
                    "time_us": event["time_us"],
                    "payload": event["payload"]
                    | {"provider": self.energy.delivered(event), "core_event_id": event["event_id"]},
                }
            )
        elif event["kind"] == "modulation":
            self.emit(
                {
                    "key": f"modulation:{event['event_id']}",
                    "kind": "input_modulation_delivered",
                    "time_us": event["time_us"],
                    "payload": event["payload"] | {"core_event_id": event["event_id"]},
                }
            )

    def before_slice(self):
        """Lab hook for real commands, phase lifecycle and host telemetry."""

    def external_deadline(self):
        return None

    def boundary_reached(self):
        """Host lifecycle changes take effect before population reproduction."""

    def is_observation_boundary(self):
        return False

    def advance_engine(self, target):
        advance_observed(self.engine, target, self.observe, record_spikes=self.options.record_spikes)

    def metrics(self):
        return self.engine.metrics()

    def advance_to(self, target):
        if type(target) is not int or target < self.engine.time_us:
            raise ValueError("participant time cannot go backwards")
        while self.engine.time_us < target and self.engine.life != "dead":
            self.before_slice()
            if self.engine.life == "dead":
                break
            now = self.engine.time_us
            if (
                self.source_enabled
                and self.body_enabled
                and self.options.interoception.enabled
                and now >= self.next_interoception_us
            ):
                self.next_interoception_us = now + self.options.interoception.sample_us
                frame = interoceptive_frame(self.options.interoception, self.seed, self.next_interoception_us)
                self.inputs.automatic(
                    f"interoception:{now}",
                    "simulated-interoception",
                    frame,
                    configuration={"seed": self.seed, **asdict(self.options.interoception)},
                )
            offer = self.energy.prepare(self.engine, source_enabled=self.source_enabled)
            if offer is not None:
                self.emit(
                    {
                        "key": f"energy-provider:{offer['event_id']}",
                        "kind": "energy_scheduled",
                        "time_us": str(now),
                        "payload": offer,
                    }
                )
            step = self.engine.config.step_us if self.options.trace else min(20000, self.engine.config.step_us * 10)
            stop = min(target, now + step, self.next_observation_us)
            deadlines = [self.organs.next_us, self.readouts.next_us, self.external_deadline()]
            if self.source_enabled or self.energy.pending:
                deadlines.append(self.energy.deadline)
            if self.source_enabled and self.body_enabled and self.options.interoception.enabled:
                deadlines.append(self.next_interoception_us)
            if self.readouts.next_us is not None:
                deadlines.append(self.inputs.bus.next_time_us)
            stop = min([stop, *(max(now, value) for value in deadlines if value is not None)])
            self.advance_engine(stop)
            self.boundary_reached()
            self.readouts.observe(self.engine)
            self.organs.observe(self.engine)
            if (
                self.engine.time_us >= self.next_observation_us
                or self.engine.life == "dead"
                or self.is_observation_boundary()
            ):
                self.emit({"kind": "metric_sample", "time_us": str(self.engine.time_us), "payload": self.metrics()})
                if self.engine.time_us >= self.next_observation_us:
                    self.next_observation_us = self.engine.time_us + self.options.sample_us
        if self.engine.life == "dead" and not self.dead_recorded:
            self.dead_recorded = True
            self.emit({"kind": "core_death_observed", "time_us": str(self.engine.time_us), "payload": self.metrics()})

    def body_failed(self, policy):
        self.body_enabled = False
        if policy == "close_all":
            self.source_enabled = False
            self.engine.close_inputs()
        elif policy != "detach_body":
            raise ValueError("unknown body failure input policy")

    def capture(self):
        return self.contract() | {
            "source_enabled": self.source_enabled,
            "body_enabled": self.body_enabled,
            "dead_recorded": self.dead_recorded,
            "record_sequence": self.record_sequence,
            "next_interoception_us": self.next_interoception_us,
            "next_observation_us": self.next_observation_us,
            "input_bus": self.inputs.bus.capture(),
            "body_filter": self.body_filter.capture(),
            "energy_supplier": self.energy.capture(),
            "readouts": self.readouts.capture(),
            "output_organs": self.organs.capture(),
        }

    def archive_engine(self, reference):
        """After a durable commit, release a dead brain detached from its body.

        Observation tools and their exact clocks remain intact. A later final
        readout can still materialize every raw node through the state reader.
        """
        from .cold_state import FrozenCore

        if self.body_enabled or self.engine.life != "dead" or not self.dead_recorded:
            raise ValueError("only an observed dead core with its body detached can be archived")
        if not isinstance(self.engine, FrozenCore):
            self.engine = FrozenCore(self.engine, reference, backend=self.backend)
            self.inputs.bus.engine = self.engine
            if hasattr(self.inputs, "engine"):
                self.inputs.engine = self.engine

    def close(self):
        pass  # Core has no external device handles; Lab subclasses own their optional attachments.
