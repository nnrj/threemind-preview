"""Explicit structural inheritance, independent of Lab, storage and wall clocks.

This is a new individual's initial condition, never an exact continuation of the
parent. The rule is versioned separately from Core dynamics and artifact codecs.
"""

from threemind_core import StateImage
from threemind_kernels.registry import state_kernel

BIRTH_RULE = "threemind.birth/1"


def birth(image: StateImage) -> StateImage:
    state = image.to_dict()
    descriptor = state_kernel(image)
    if descriptor.kernel_id == "threemind.experimental-weight-decay/1":
        raise ValueError("structural inheritance is not defined for the R48 research kernel; "
                         "use a blank instance or an exact complete-state fork")
    if descriptor.kernel_id == "threemind.continuous-memory/5.3":
        raise ValueError("structural inheritance of decay age is not defined for memory/5.3; "
                         "use a blank instance or an exact complete-state fork")
    if descriptor.kernel_id == "threemind.continuous-memory/5.2":
        raise ValueError("structural inheritance of contribution ages is not defined for memory/5.2; "
                         "use a blank instance or an exact complete-state fork")
    if descriptor.kernel_id == "unified-associative":
        raise ValueError("structural inheritance is not defined for this historical kernel; "
                         "create a blank instance or preserve an exact checkpoint fork")
    if descriptor.kernel_id in {
        f"threemind.causal/{version}" for version in range(1, 9)
    }:
        from threemind_kernels.legacy.inheritance import birth as historical_birth

        return historical_birth(image)
    parent = descriptor.create(state=image, backend="reference")
    config = descriptor.configuration(state["config"])
    if descriptor.kernel_id in (
        "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1"
    ):
        from threemind_kernels.local import LocalEdge, LocalEngine, LocalNode

        if descriptor.kernel_id == "threemind.continuous-memory/5":
            from threemind_kernels.local5 import (
                Local5Edge as LocalEdge,
            )
            from threemind_kernels.local5 import (
                Local5Engine as LocalEngine,
            )
            from threemind_kernels.local5 import (
                Local5Node as LocalNode,
            )
        elif descriptor.kernel_id == "threemind.continuous-memory/5.1":
            from threemind_kernels.local51 import (
                Local51Edge as LocalEdge,
            )
            from threemind_kernels.local51 import (
                Local51Engine as LocalEngine,
            )
            from threemind_kernels.local51 import (
                Local51Node as LocalNode,
            )

        engine = LocalEngine(config)
        engine.next_node = state["next_node"]
        for row in parent.observation_nodes():
            n = LocalNode(
                row["id"],
                row["channel"],
                support=row["support"],
                stability=row["stability"],
                local_plasticity=row["local_plasticity"],
                touches=row["touches"],
                half_life=row["half_life"],
                region=row["region"],
            )
            engine.nodes[n.id], engine.receptors[n.channel] = n, n.id
            engine.regions.setdefault(n.region, set()).add(n.id)
        for row in parent.induced_edges(engine.nodes):
            e = LocalEdge(
                row["source"],
                row["target"],
                row["weight"],
                stability=row["stability"],
                touches=row["touches"],
                half_life=row["half_life"],
            )
            key = e.source, e.target
            engine.edges[key] = e
            engine.outgoing.setdefault(e.source, set()).add(key)
            for id in key:
                engine.incident.setdefault(id, set()).add(key)
            engine._edge_timer(e)
        for n in engine.nodes.values():
            engine._node_timers(n)
            if config.energy_simulation_enabled and config.energy_starvation_damage_enabled:
                engine.timers.set((5, n.id, 0), config.propagation_interval_us)
        return engine.capture_state()
    if descriptor.kernel_id == "threemind.lif/1":
        from threemind_kernels.lif import LifEngine, Membrane, Synapse

        engine = LifEngine(config)
        engine.next_node, engine.next_synapse = state["next_node"], state["next_synapse"]
        for row in state["membranes"]:
            node = Membrane(row["id"], row["channel"], config.rest_mv)
            engine.nodes[node.id], engine.channels[node.channel] = node, node.id
        for row in state["synapses"]:
            edge = Synapse(row["id"], row["source"], row["target"], row["weight"])
            engine.edges[edge.source, edge.target] = edge
            engine.outgoing.setdefault(edge.source, set()).add(edge.target)
            engine.incoming.setdefault(edge.target, set()).add(edge.source)
        return engine.capture_state()
    retained = state.get("operator_state", {}).get("retention")
    if "operator_state" in state:
        state["operator_state"] = {"short_term": [], "fast": []}
        if descriptor.kernel_id in ("threemind.continuous-memory/2", "threemind.continuous-memory/3"):
            from threemind_kernels.novelty import COUNTERS, TOTALS

            state["operator_state"]["novelty"] = {
                "serial": 0,
                "pending": [],
                "audit": dict.fromkeys(COUNTERS, 0) | dict.fromkeys(TOTALS, 0.0),
            }
        if retained is not None:
            connected = {n for edge in state["edges"] for n in (edge["source"], edge["target"])}
            state["operator_state"]["retention"] = {
                "edges": [[a, b, h, 0.0] for a, b, h, _ in retained["edges"]],
                "nodes": [[n, h, 0.0] for n, h, _ in retained["nodes"]],
                "dormant": [],
                "isolated": [[n["id"], "0"] for n in state["nodes"] if n["id"] not in connected],
                "fatigue": [],
                "salience": [],
                "charge": [],
                "cursor": [],
                "blocked": [],
                "audit": dict.fromkeys(retained["audit"], 0),
            }
    state.update(
        time_us="0",
        state_time_us="0",
        next_step_us=str(state["config"]["step_us"]),
        next_propagation_us=str(state["config"]["propagation_interval_us"]),
        quiet_since_us=None,
        transport={"sent": 0.0, "received": 0.0, "activated": 0.0, "discarded": 0.0},
        traversed=[],
        sequence=0,
        next_event=0,
        sources_open=True,
        life="waiting",
        queue=[],
        silenced_nodes=[],
        silenced_edges=[],
    )
    if "resources" in state:
        from threemind_core.resources import Resources

        state["resources"] = Resources().to_dict()
    if "energy" in state:
        from threemind_core.energy import Energy

        state["energy"] = Energy.initial(config).to_dict()
    if "attention" in state:
        from threemind_core.attention import Attention

        state["attention"] = Attention().to_dict()
    for node in state["nodes"]:
        for key in (
            "activation",
            "inhibition",
            "trace",
            "direct",
            "associative",
            "pending_inhibition",
            "generated_inhibition",
        ):
            node[key] = 0.0
        node["last_touch_us"] = "0"
        node["birth_us"] = "0"
    for edge in state["edges"]:
        edge["eligibility"] = 0.0
        edge["birth_us"] = "0"
        edge["last_touch_us"] = "0"
    return StateImage.from_dict(state)
