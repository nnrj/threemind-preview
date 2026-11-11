"""Explicit development controls, kept separate from normal ecological births."""

from dataclasses import asdict

from threemind_core import StateImage
from threemind_core.engine import Node
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth


def naive_same_receptors(image):
    """Remove experience while preserving receptor IDs and external motor wiring.

    A fresh empty brain would assign IDs in its new arrival order, changing this
    apparatus's node-ID-based motor projection. This control keeps those IDs,
    removes edges, and initializes each retained receptor using Core's actual
    blank-node defaults. The operation edits only a new experimental image.
    """
    value = birth(image).to_dict()
    if value["dynamics"] != "threemind.continuous-memory/2":
        raise ValueError("this control requires continuous-memory/2")
    value["nodes"] = [asdict(Node(n["id"], n["channel"])) for n in value["nodes"]]
    value["edges"] = []
    result = StateImage.from_dict(value)
    restored = create_engine(state=result, backend="native").capture_state()
    if restored.digest != result.digest:
        raise ValueError("naive receptor control is not exactly restorable")
    return result
