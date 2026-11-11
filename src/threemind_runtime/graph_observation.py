"""Read-only, anonymous graph measurements over the existing OutputBus.

No Core input, event advancement, ranking, semantic annotations or lazy-state
materialization. Short-term quantities are stored values accompanied by age.
"""

import math
from .bus import OutputBus

VERSION = "threemind.graph-activity/1"
NODE_FIELDS = (
    "activation",
    "inhibition",
    "trace",
    "support",
    "stability",
    "local_plasticity",
    "direct",
    "associative",
    "generated_inhibition",
    "pending_inhibition",
    "touches",
)
EDGE_FIELDS = (
    "weight",
    "stability",
    "eligibility",
    "touches",
    "short_term_present",
    "available",
    "active",
    "utilization",
    "short_term_age_s",
    "fast_present",
    "fast_value",
    "fast_age_s",
)


def graph_frame(state):
    """Whitelist measurements, excluding queued stimuli/configuration/labels."""
    when = int(state["time_us"])
    nodes = [
        {"id": str(n["id"]), "channel": int(n["channel"]), "values": [float(n[k]) for k in NODE_FIELDS]}
        for n in state["nodes"]
    ]
    short = {
        (str(r["source"]), str(r["target"])): r["state"] for r in state.get("operator_state", {}).get("short_term", [])
    }
    fast = {(str(r["source"]), str(r["target"])): r["state"] for r in state.get("operator_state", {}).get("fast", [])}
    edges = []
    for e in state["edges"]:
        key = str(e["source"]), str(e["target"])
        s = short.get(key)
        f = fast.get(key)
        values = [float(e[k]) for k in EDGE_FIELDS[:4]]
        values += (
            [1, float(s["available"]), float(s["active"]), float(s["utilization"]), (when - int(s["time_us"])) / 1e6]
            if s
            else [0] * 5
        )
        values += [1, float(f["value"]), (when - int(f["time_us"])) / 1e6] if f else [0] * 3
        edges.append({"source": key[0], "target": key[1], "values": values})
    if any(not math.isfinite(v) for row in nodes + edges for v in row["values"]):
        raise ValueError("nonfinite graph observation")
    return {"time_us": str(when), "nodes": nodes, "edges": edges}


class GraphActivityStream:
    def __init__(self):
        self.bus = OutputBus()

    def subscribe(self, name, consumer):
        return self.bus.subscribe(name, consumer)

    def sample(self, engine):
        self.publish(graph_frame(engine.capture_state().to_dict()))

    def publish(self, frame):
        if set(frame) != {"time_us", "nodes", "edges"}:
            raise ValueError("graph frame fields")
        self.bus.publish(frame)


def graph_process(process):
    """Convert recorded state samples; actual sample times remain explicit."""
    return {
        "schema": VERSION,
        "node_fields": list(NODE_FIELDS),
        "edge_fields": list(EDGE_FIELDS),
        "start_us": str(process["start_us"]),
        "end_us": str(process["end_us"]),
        "frames": [graph_frame(state) for state in process["states"]],
    }
