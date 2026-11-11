"""Freeze reviewed legacy presentation behavior; never inspect application data."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    "97d8592:adapters/threemind_adapters/outputs.py",
    "97d8592:adapters/threemind_adapters/temporal.py",
    "0c5e64a:legacy/ui/src/Lab.tsx",
    "0c5e64a:legacy/ui/src/MediaControls.tsx",
    "0c5e64a:legacy/ui/src/styles.css",
    "db4e0a4:src/threemind_runtime/chat_readout.py",
    "db4e0a4:threemind-ui/src/v2/conversation.tsx",
]


def main():
    sources = {ref: subprocess.check_output(["git", "show", ref], cwd=ROOT) for ref in SOURCES}
    tree = ast.parse(sources[SOURCES[0]])
    adapter = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "StructuralReadoutAdapter")
    # Execute the actual, dependency-free legacy formatting functions, not a rewrite.
    adapter.body = [
        n
        for n in adapter.body
        if isinstance(n, ast.FunctionDef)
        and n.name
        in {
            "_activity_rank",
            "_display_nodes",
            "_display_readout",
            "_readable_labels",
        }
    ]
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), adapter],
        type_ignores=[],
    )
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), SOURCES[0], "exec"), namespace)  # noqa: S102 -- frozen legacy functions, no application data
    old = namespace["StructuralReadoutAdapter"]()
    nodes = [
        {"id": 9, "activation": 0.2, "direct_touch": 0.5, "associative_touch": 0, "stability": 0.1},
        {"id": 3, "activation": 0.8, "direct_touch": 0.1, "associative_touch": 0.1, "stability": 0.1},
        {"id": 7, "activation": 0.8, "direct_touch": 0.1, "associative_touch": 0.2, "stability": 0.1},
    ]
    labels = {3: "松子", 7: "甲", 9: "松子"}
    cases = []
    for enabled in (True, False):
        ordered = old._display_nodes(nodes, {"label_sort_by_activation": enabled})
        readable = old._readable_labels([{"label": labels[n["id"]]} for n in ordered])
        cases.append(
            {
                "sort_by_activation": enabled,
                "node_ids": [n["id"] for n in ordered],
                "text": old._display_readout([], "anonymous", readable, None, {"label_display_limit": 0}),
            }
        )
    result = {
        "schema": "threemind.chat-restoration-reference/1",
        "sources": {
            ref: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for ref, raw in sources.items()
        },
        "nodes": nodes,
        "labels": labels,
        "cases": cases,
        "temporal": {"default_display_items": 7, "default_ranking": "composite", "consider_activation_strength": True},
        "interaction": [
            "one chronological conversation",
            "user right, readers left",
            "readable text first",
            "anonymous identity and node IDs secondary",
            "temporal interval and classification",
            "media toolbar before textarea",
            "intensity and send below textarea",
            "bottom pin respects upward reading",
        ],
        "approved_new_behavior": [
            "complete raw evidence retained",
            "timestamp delivery",
            "exact envelope provenance",
            "successful send clears; failure retains draft",
            "IME guard",
            "bounded virtual history",
        ],
    }
    target = ROOT / "docs/benchmarks/chat-restoration-reference.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
