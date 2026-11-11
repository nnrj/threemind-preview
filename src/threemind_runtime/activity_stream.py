"""Opt-in raw activity transport for research and external expression adapters.

OutputBus transports copied measurements. This instrument does not select active
nodes, rank, annotate, pool time bins, or feed information back into Core.
Sampling is controlled explicitly by the caller; it does not advance the engine.
"""

from .bus import OutputBus

VERSION = "threemind.raw-activity-stream/1"


class RawActivityStream:
    def __init__(self):
        self.bus = OutputBus()
        self.published = 0

    def subscribe(self, name, consumer):
        return self.bus.subscribe(name, consumer)

    def publish(self, frame):
        """Replay a measured frame without interpreting its anonymous fields."""
        if "time_us" not in frame or "nodes" not in frame:
            raise ValueError("raw activity requires time_us and complete nodes")
        value = {"schema": VERSION, "time_us": str(frame["time_us"]), "nodes": frame["nodes"]}
        if "sequence" in frame:
            value["sequence"] = frame["sequence"]
        self.bus.publish(value)
        self.published += 1

    def sample(self, engine):
        """Observe the current Core state; no simulation step or state update."""
        self.publish({"time_us": engine.time_us, "nodes": engine.observation_nodes()})
