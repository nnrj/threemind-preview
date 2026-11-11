"""Explicit structural inheritance, independent of Lab, storage and wall clocks.

This is a new individual's initial condition, never an exact continuation of the
parent. The rule is versioned separately from Core dynamics and artifact codecs.
"""

from .spec import Config
from .engine import StateImage

BIRTH_RULE = "threemind.birth/1"


def birth(image: StateImage) -> StateImage:
    state = image.to_dict()
    from .spec import DYNAMICS

    if state.get("dynamics") != DYNAMICS:
        raise ValueError("Older dynamics are read-only; create a new causal/8 consciousness")
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
        from .resources import Resources

        state["resources"] = Resources().to_dict()
    if "energy" in state:
        from .energy import Energy

        state["energy"] = Energy.initial(Config(**state["config"])).to_dict()
    if "attention" in state:
        from .attention import Attention

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
