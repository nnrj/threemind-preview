"""Execute frozen Git V3 source as an order witness, not as a matched whole-kernel control."""

import hashlib
import importlib
import json
import subprocess
import sys

from common import WORK, new_json


def run():
    folder = WORK / "historical_v3"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("", encoding="utf-8")
    hashes = {}
    for name in ("runtime.py", "model.py", "frames.py", "attention.py"):
        raw = subprocess.run(["git", "show", f"97d8592:core/threemind/{name}"], capture_output=True, check=True).stdout
        (folder / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    sys.path.insert(0, str(WORK))
    module = importlib.import_module("historical_v3.runtime")
    SensoryFrame = importlib.import_module("historical_v3.frames").SensoryFrame
    cases = []
    for dose in (0.2, 0.4, 0.8):
        engine = module.ConsciousnessRuntime(config=module.RuntimeConfig())
        engine._advance([SensoryFrame("manual", {1: dose, 2: dose})])
        before = list(engine.edges.values())
        engine._advance([SensoryFrame("manual", {1: dose, 3: dose})])
        cases.append(
            {
                "dose": dose,
                "before_edges": before,
                "after_edges": list(engine.edges.values()),
                "nodes": list(engine.nodes.values()),
            }
        )
    new_json(
        WORK / "historical-order.json",
        {
            "revision": "97d8592",
            "sha256": hashes,
            "scope": "unmodified old operators; not whole-kernel equivalence",
            "cases": cases,
        },
    )
    print(json.dumps({"historical_witnesses": len(cases)}))


if __name__ == "__main__":
    run()
