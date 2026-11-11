"""Host-side provenance around Core's own recoverable event queue."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from threemind_core import Stimulus

from .sensory import InputBusConfig
from .source_policies import SourcePolicies


class InputBus:
    def __init__(
        self, engine, state=None, config: InputBusConfig | None = None, policies: SourcePolicies | None = None
    ):
        self.engine, self.config = engine, config or InputBusConfig()
        self.policies = policies or SourcePolicies()
        self.pending = {int(key): value for key, value in (state or {}).get("pending", {}).items()}
        if state and state.get("schema") != "threemind.input-bus/1":
            raise ValueError("unsupported input bus state")
        self._frames = sum(v.get("budgeted", True) for v in self.pending.values())
        self._channels = sum(v["channel_count"] for v in self.pending.values() if v.get("budgeted", True))
        self._next_valid, self._next_time = False, None

    def schedule(self, stimulus: Stimulus, metadata: dict):
        """Caller reserves an entire carrier before scheduling any of its frames."""
        policy = self.policies.resolve(metadata.get("source", "manual-anonymous"))
        if not policy["enabled"]:
            raise ValueError(f"input source disabled: {policy['source']} ({policy['reason']})")
        # Runtime callers carry logical provenance; untrusted carrier flags cannot override its policy.
        stimulus = replace(stimulus, bypass_attention=policy["bypass_attention"])
        if metadata.get("budgeted", True):
            self.reserve(1, len(stimulus.channels))
        event_id = self.engine.inject(stimulus)
        entry = {
            **deepcopy(metadata),
            "source_policy": policy,
            "core_event_id": event_id,
            "scheduled_time_us": str(stimulus.time_us),
            "channel_count": len(stimulus.channels),
        }
        self.pending[event_id] = entry
        if self._next_valid:
            self._next_time = (
                min(self._next_time, stimulus.time_us) if self._next_time is not None else stimulus.time_us
            )
        if entry.get("budgeted", True):
            self._frames += 1
            self._channels += entry["channel_count"]
        return entry

    def observe(self, event):
        if event["kind"] != "stimulus":
            return None
        metadata = self.pending.pop(event["event_id"], None)
        if metadata and self._next_time == int(metadata["scheduled_time_us"]):
            self._next_valid = False
        if metadata and metadata.get("budgeted", True):
            self._frames -= 1
            self._channels -= metadata["channel_count"]
        return {
            **(metadata or {}),
            "core_event_id": event["event_id"],
            "delivered_time_us": event["time_us"],
            "core_sequence": event["sequence"],
            "stimulus": event.get("input_gate", {}).get("effective_stimulus", event["payload"]),
            **({"input_gate": event["input_gate"]} if "input_gate" in event else {}),
        }

    def capture(self):
        return {"schema": "threemind.input-bus/1", "pending": {str(k): deepcopy(v) for k, v in self.pending.items()}}

    @property
    def next_time_us(self):
        if not self._next_valid:
            self._next_time = min((int(v["scheduled_time_us"]) for v in self.pending.values()), default=None)
            self._next_valid = True
        return self._next_time

    def remaining_channels(self):
        return self._channels

    def pending_count(self):
        return self._frames

    def reserve(self, frame_count, channel_count):
        if (
            self.pending_count() + frame_count > self.config.max_pending_frames
            or self.remaining_channels() + channel_count > self.config.max_pending_channels
        ):
            raise ValueError("输入队列容量不足；整个载体尚未排入内核，请等待递送或提高输入总线预算。")

    def verify(self, image):
        queued = {q["id"]: q for q in image["queue"] if q["kind"] == "stimulus"}
        for event_id, metadata in self.pending.items():
            event = queued.get(event_id)
            if event is None or str(event["time_us"]) != metadata["scheduled_time_us"]:
                raise ValueError("input provenance does not match the captured Core queue")
            policy = metadata.get("source_policy")
            if policy is not None and (
                policy.get("enabled") is not True
                or type(policy.get("bypass_attention")) is not bool
                or policy["bypass_attention"] != event["payload"].get("bypass_attention", False)
            ):
                raise ValueError("saved source policy differs from the captured Core frame")


class OutputBus:
    """Synchronous evidence subscriptions and explicitly lossy latest-value views.

    No graph, labels or observations are fed back into Core by this bus.
    Exceptions from evidence consumers propagate; they cannot silently lose data.
    """

    def __init__(self):
        self._subscribers = {}

    def subscribe(self, name, consumer):
        if name in self._subscribers:
            raise ValueError("output subscription already exists")
        self._subscribers[name] = consumer
        return lambda: self._subscribers.pop(name, None)

    def publish(self, frame, *, owned=False):
        """Copy by default; an exclusive consumer may take an owned frame.

        With owned=True the publisher relinquishes all mutable frame objects.
        Multiple consumers still receive separate copies. Core-owned objects
        must never be published with this option.
        """
        consumers = tuple(self._subscribers.values())
        if owned and len(consumers) == 1:
            consumers[0](frame)
            return
        for consumer in consumers:
            consumer(deepcopy(frame))


class LatestOutput:
    def __init__(self):
        self.frame, self.skipped = None, 0

    def __call__(self, frame):
        if self.frame is not None:
            self.skipped += 1
        self.frame = frame

    def take(self):
        value = {"frame": self.frame, "skipped": self.skipped}
        self.frame, self.skipped = None, 0
        return value
