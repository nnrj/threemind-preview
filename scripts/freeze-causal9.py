"""Generate the multi-kernel baseline from a fixed Git revision, never current dynamics.

Only the explicitly listed trusted files at BASELINE are executed. This is an
offline test oracle, not the user-supplied kernel-definition interpreter.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "b53fba1"
sys.path.insert(0, str(ROOT / "tests_v2"))
from kernel_witnesses import CASES, exercise


def freeze():
    revision = subprocess.check_output(["git", "rev-parse", BASELINE], cwd=ROOT, text=True).strip()
    package = types.ModuleType("frozen_causal9")
    package.__path__ = []
    sys.modules[package.__name__] = package
    sources = []
    for name in ("spec", "resources", "energy", "attention", "spatial", "restoration", "engine"):
        path = f"src/threemind_core/{name}.py"
        raw = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
        sources.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest()})
        module = types.ModuleType(f"frozen_causal9.{name}")
        module.__file__ = f"git:{revision}:{path}"
        sys.modules[module.__name__] = module
        exec(compile(raw, module.__file__, "exec"), module.__dict__)  # noqa: S102 -- fixed trusted baseline
    from frozen_causal9.engine import Engine
    from frozen_causal9.spec import Config, Stimulus

    for path in (
        "docs/zh/consciousness-hypothesis.md",
        "docs/en/consciousness-hypothesis.md",
        "crates/threemind-core/src/lib.rs",
        "crates/threemind-core/src/restoration.rs",
        "crates/threemind-core/src/attention.rs",
        "crates/threemind-core/src/energy.rs",
        "crates/threemind-core/src/resources.rs",
        "crates/threemind-core/src/spatial.rs",
    ):
        raw = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
        sources.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest()})

    return {
        "schema": "threemind.kernel-baseline/1",
        "revision": revision,
        "kernel_id": "threemind.causal/9",
        "state_schema": "threemind.state/6",
        "hypotheses": "docs/zh/consciousness-hypothesis.md",
        "sources": sources,
        "cases": {
            name: {**case, "snapshots": exercise(case, config_type=Config, stimulus_type=Stimulus, factory=Engine)}
            for name, case in CASES.items()
        },
    }


if __name__ == "__main__":
    document = freeze()
    output = ROOT / "tests_v2/fixtures/causal9-baseline.json"
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest = {key: value for key, value in document.items() if key != "cases"}
    manifest["witness_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    packaged = ROOT / "src/threemind_kernels/baselines/causal9.json"
    packaged.parent.mkdir(parents=True, exist_ok=True)
    packaged.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(output.relative_to(ROOT))
