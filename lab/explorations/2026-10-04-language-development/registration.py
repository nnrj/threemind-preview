"""Explicit pre-compute formatting correction, retaining the original registration."""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import encoded, new_json, read_json
from threemind_lab.provenance import capture_implementation


def main():
    work = ROOT / ".work/language-development-20261004"
    path = work / "platform.json"
    old = read_json(path)
    current = capture_implementation("native")
    if old["implementation"] == current:
        return
    if list((work / "cases").glob("*")) or list((work / "models").glob("*.safetensors")):
        raise RuntimeError("pre-compute amendment only")
    previous = old["implementation"]["source_files"]
    changed = [name for name, digest in current["source_files"].items() if previous.get(name) != digest]
    allowed = {"src/threemind_transformer/development.py", "src/threemind_transformer/development_cli.py"}
    if not changed or not set(changed) <= allowed or set(previous) != set(current["source_files"]):
        raise RuntimeError("only the two pre-compute formatting corrections are authorized here")
    for name in changed:
        before = (work / "frozen-sources" / name).read_text(encoding="utf-8")
        after = (ROOT / name).read_text(encoding="utf-8")
        if ast.dump(ast.parse(before)) != ast.dump(ast.parse(after)):
            raise RuntimeError("format correction must not change Python syntax tree")
        target = work / "registration-amendment-1" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after, encoding="utf-8")
    new_json(work / "platform-original.json", old)
    new_json(work / "registration-amendment-1" / "reason.json", {
        "reason": "Ruff inserted import separator blank lines after initial preparation; no compute had started.",
        "changed": changed, "syntax_trees_equal": True, "core_unchanged": True,
        "previous_implementation": old["implementation"]["source_sha256"],
        "current_implementation": current["source_sha256"],
    })
    path.write_bytes(encoded(old | {"implementation": current}))
    print(json.dumps({"pre_compute_registration_amendment": changed}))


if __name__ == "__main__":
    main()
