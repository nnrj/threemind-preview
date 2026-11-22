"""Explicit structural inheritance, independent of Lab, storage and wall clocks.

This is a new individual's initial condition, never an exact continuation of the
parent. The rule is versioned separately from Core dynamics and artifact codecs.
"""

from threemind_core import StateImage
from threemind_kernels.registry import state_kernel

BIRTH_RULE = "threemind.birth/1"
KERNEL60_BIRTH_RULE = "threemind.birth/2"
KERNEL60 = "threemind.continuous-memory/6.0"
KERNEL61 = "threemind.continuous-memory/6.1"
KERNEL62 = "threemind.continuous-memory/6.2"
KERNEL63 = "threemind.continuous-memory/6.3"


def birth_rule(kernel_id: str) -> str:
    """Name the rule actually used, without relabelling historical births."""
    return KERNEL60_BIRTH_RULE if kernel_id in (KERNEL60, KERNEL61, KERNEL62, KERNEL63) else BIRTH_RULE


def birth_metadata(image: StateImage, decay_age: str = "preserve") -> dict:
    kernel = state_kernel(image).kernel_id
    result = {"inheritance_rule": birth_rule(kernel)}
    if kernel in (KERNEL60, KERNEL61, KERNEL62, KERNEL63):
        if decay_age not in ("preserve", "reset"):
            raise ValueError("inheritance decay age must be preserve or reset")
        result["inheritance_decay_age"] = decay_age
    elif decay_age != "preserve":
        raise ValueError("inheritance decay-age selection is defined only for memory/6.0")
    return result


def _birth60(image: StateImage, decay_age: str) -> StateImage:
    """Inherit current persistent values, not a parent's pending experiences.

    Project lazy values to the saved observation time on a private engine. This
    does not advance the parent's clock or deliver any queued event. Sleeping
    connections are retained too; public graph queries intentionally omit them.
    """
    if image.to_dict()["dynamics"] == KERNEL63:
        from threemind_kernels.local63 import Local63Engine as Local60Engine
    elif image.to_dict()["dynamics"] == KERNEL62:
        from threemind_kernels.local62 import Local62Engine as Local60Engine
    elif image.to_dict()["dynamics"] == KERNEL61:
        from threemind_kernels.local61 import Local61Engine as Local60Engine
    else:
        from threemind_kernels.local60 import Local60Engine

    parent = Local60Engine(state=image)
    child = Local60Engine(parent.config)
    for serial, (_, original) in enumerate(sorted(parent.nodes.items()), 1):
        row = parent._project_node(original, parent.time_us)
        node = child.node_type(
            row.id, row.channel, birth_serial=serial,
            support=row.support, stability=row.stability,
            local_plasticity=row.local_plasticity, touches=row.touches,
            half_life=row.half_life, region=row.region, sleeping=row.sleeping,
            decay_age=row.decay_age if decay_age == "preserve" else 0.0,
        )
        child.nodes[node.id] = node
        child.regions.setdefault(node.region, set()).add(node.id)
        child._node_timers(node)
        if child.config.energy_simulation_enabled and child.config.energy_starvation_damage_enabled:
            child.timers.set((5, node.id, 0), child.config.propagation_interval_us)
    child.birth_count = len(child.nodes)
    for key, original in sorted(parent.edges.items()):
        row = parent._project_edge(original, parent.time_us)
        edge = child.edge_type(
            row.source, row.target, row.weight,
            stability=row.stability, touches=row.touches,
            half_life=row.half_life, sleeping=row.sleeping,
            decay_age=row.decay_age if decay_age == "preserve" else 0.0,
        )
        if image.to_dict()["dynamics"] == KERNEL62 and child.config.separates("weights"):
            edge.inhibition_weight = row.inhibition_weight
            if child.config.separates("learning"):
                edge.inhibition_learning = dict(row.inhibition_learning)
                edge.inhibition_learning.update(fast=None, eligibility=0.0, last_pass_us="0", last_touch_us="0")
                if decay_age == "reset":
                    edge.inhibition_learning["decay_age"] = 0.0
        child.edges[key] = edge
        child.outgoing.setdefault(edge.source, set()).add(key)
        for identity in key:
            child.incident.setdefault(identity, set()).add(key)
        child._edge_timer(edge)
    # Validate the same artifact that either backend will receive.
    if image.to_dict()["dynamics"] in (KERNEL61, KERNEL62, KERNEL63):
        for node in child.nodes.values():
            child._node_timers(node)
    result = child.capture_state()
    Local60Engine(state=result)
    return result


def birth(image: StateImage, *, rule: str | None = None, decay_age: str = "preserve") -> StateImage:
    state = image.to_dict()
    descriptor = state_kernel(image)
    metadata = birth_metadata(image, decay_age)
    if rule is not None and rule != metadata["inheritance_rule"]:
        raise ValueError("inheritance rule does not match the saved kernel identity")
    if descriptor.kernel_id in (KERNEL60, KERNEL61, KERNEL62, KERNEL63):
        return _birth60(image, decay_age)
    if descriptor.kernel_id == "threemind.experimental-weight-decay/1":
        raise ValueError("structural inheritance is not defined for the R48 research kernel; "
                         "use a blank instance or an exact complete-state fork")
    if descriptor.kernel_id == "threemind.continuous-memory/5.3":
        raise ValueError(f"structural inheritance of decay age is not defined for {descriptor.kernel_id}; "
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
