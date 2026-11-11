"""CLI/probe observation using the same delivery boundaries and host as Lab."""

from dataclasses import asdict, replace
from types import SimpleNamespace
from uuid import uuid4

from .bus import InputBus
from .event_observation import advance_observed
from .readout_config import ActivityReadoutConfig, StructuralReadoutConfig, TemporalReadoutConfig
from .readout_host import ReadoutHost

SESSION_VERSION = "threemind.cli-readouts/1"


class ReadoutSession:
    def __init__(self, engine, *, record, config=None, state=None, policies=None, event_sink=None):
        self.engine, self.event_sink = engine, event_sink
        if state and state.get("schema") != SESSION_VERSION:
            raise ValueError("incompatible CLI readout context")
        self.config = config if config is not None else (state or {}).get("configuration", {})
        if set(self.config) - {"structural_readout", "temporal_readout", "activity_readout"}:
            raise ValueError(
                "unknown readout configuration; use structural_readout, temporal_readout, activity_readout"
            )
        self.spec = SimpleNamespace(
            structural_readout=StructuralReadoutConfig(**self.config.get("structural_readout", {})),
            temporal_readout=TemporalReadoutConfig(**self.config.get("temporal_readout", {})),
            activity_readout=ActivityReadoutConfig(**self.config.get("activity_readout", {"enabled": False})),
        )
        self.bus = InputBus(engine, (state or {}).get("input_bus"), policies=policies)
        self.bus.verify(engine.capture_state().to_dict())
        self.host = ReadoutHost(
            self.spec,
            (state or {}).get("session_id", str(uuid4())),
            engine.time_us,
            state=(state or {}).get("readouts"),
            record=record,
        )

    def schedule(self, frames, *, source="manual-cli-text", adapter_id="text-sensor", envelope_id=None, at=None):
        """A carrier is one envelope; all original frames and labels are retained."""
        frames = list(frames)
        at = self.engine.time_us if at is None else at
        envelope_id = str(envelope_id or uuid4())
        self.bus.reserve(len(frames), sum(len(f["stimulus"].channels) for f in frames))
        receipts = []
        for i, frame in enumerate(frames):
            stimulus = replace(frame["stimulus"], time_us=at + frame["stimulus"].time_us)
            receipts.append(
                self.bus.schedule(
                    stimulus,
                    {
                        "envelope_id": envelope_id,
                        "source": source,
                        "adapter_id": adapter_id,
                        "frame_index": i,
                        "frame_count": len(frames),
                        "labels": frame.get("labels", {}),
                        **({"stimulus_unit": frame["stimulus_unit"]} if "stimulus_unit" in frame else {}),
                    },
                )
            )
        return receipts

    def observe_event(self, event):
        delivered = self.bus.observe(event)
        if delivered:
            self.host.delivered(delivered)
        if self.event_sink:
            self.event_sink(event, delivered)

    def begin_observation(self, observation_id=None):
        """Observe a bounded process without a cue; shares the UI/API observer."""
        return self.host.begin_observation(self.engine, observation_id or uuid4())

    def advance_to(self, until_us, *, stop_when=None, guard=None, pace=None):
        if until_us < self.engine.time_us:
            raise ValueError("observation deadline precedes current simulation time")
        first = True
        while first or self.engine.time_us < until_us and self.engine.life != "dead":
            first = False
            if guard:
                guard()
            target = min(until_us, self.engine.time_us + min(20000, self.engine.config.step_us * 10))
            if self.host.next_us is not None:
                target = min(target, max(self.engine.time_us, self.host.next_us))
            if self.bus.next_time_us is not None:
                target = min(target, max(self.engine.time_us, self.bus.next_time_us))
            if pace:
                pace(target)
            advance_observed(self.engine, target, self.observe_event, record_spikes=self.event_sink is not None)
            self.host.observe(self.engine)
            if stop_when and stop_when():
                break
            if self.engine.time_us >= until_us or self.engine.life == "dead":
                break

    def capture(self):
        return {
            "schema": SESSION_VERSION,
            "session_id": self.host.run_id,
            "configuration": {
                "structural_readout": asdict(self.spec.structural_readout),
                "temporal_readout": asdict(self.spec.temporal_readout),
                **(
                    {"activity_readout": asdict(self.spec.activity_readout)}
                    if "activity_readout" in self.config
                    else {}
                ),
            },
            "input_bus": self.bus.capture(),
            "readouts": self.host.capture(),
        }
