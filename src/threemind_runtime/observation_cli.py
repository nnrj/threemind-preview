"""Bounded, reproducible offline analysis and batch composition of observation tools."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .observation_tools import TOOLS, run_tool

MAX_BYTES = 64 * 1024**2


def load_record(path, window=None):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source exceeds 64 MiB uncompressed input budget; export a single window")
    try:
        records = [json.loads(raw)]
    except json.JSONDecodeError:
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    matches = [
        r
        for r in records
        if r.get("payload", r).get("kind") == "temporal_readout"
        and r.get("payload", r).get("analysis_schema")
        and (window is None or r.get("payload", r).get("window_id") == window)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one complete activity window, found {len(matches)}; select --window")
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reusable ThreeMind observation tools (no Core modification)")
    parser.add_argument("tool", choices=["list", *TOOLS, "batch"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--window")
    parser.add_argument("--right-window")
    parser.add_argument("--relative", action="store_true")
    parser.add_argument("--epsilon", type=float, default=1e-12)
    parser.add_argument("--node-ids", type=int, nargs="+")
    parser.add_argument("--settle-us", type=int, default=800000)
    parser.add_argument("--pattern-drift-max", type=float, default=0.08)
    parser.add_argument("--amplitude-drift-max", type=float, default=0.12)
    parser.add_argument("--response-floor", type=float, default=1e-8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.tool == "list":
            print(json.dumps(TOOLS, ensure_ascii=False, indent=2))
            return
        if not args.input or not args.output:
            raise ValueError("--input and a new --output file are required")
        if args.tool == "batch":
            if args.input.stat().st_size > 1024**2:
                raise ValueError("batch manifest exceeds 1 MiB")
            manifest = json.loads(args.input.read_text(encoding="utf-8"))
            if manifest.get("schema") != "threemind.observation-batch/1" or set(manifest) != {"schema", "steps"}:
                raise ValueError("unknown observation batch schema or fields")
            steps = manifest["steps"]
            if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
                raise ValueError("batch needs 1 to 32 steps")
        else:
            steps = [
                {
                    "tool": args.tool,
                    "inputs": {
                        "left" if args.tool == "compare" else "record": {
                            "path": str(args.input.resolve()),
                            "window": args.window,
                        },
                        **(
                            {"right": {"path": str(args.right.resolve()), "window": args.right_window}}
                            if args.right
                            else {}
                        ),
                    },
                    "options": {
                        "epsilon": args.epsilon,
                        **({"relative": args.relative} if args.tool == "compare" else {}),
                        **({"node_ids": args.node_ids} if args.tool == "response" else {}),
                        **(
                            {
                                "node_ids": args.node_ids,
                                "settle_us": args.settle_us,
                                "pattern_drift_max": args.pattern_drift_max,
                                "amplitude_drift_max": args.amplitude_drift_max,
                                "response_floor": args.response_floor,
                            }
                            if args.tool == "target"
                            else {}
                        ),
                    },
                }
            ]
        with args.output.open("x", encoding="utf-8") as out:
            size = 0
            for index, step in enumerate(steps):
                if set(step) - {"tool", "inputs", "options"}:
                    raise ValueError("unknown step field")
                records = {}
                for key, ref in step["inputs"].items():
                    if set(ref) - {"path", "window"}:
                        raise ValueError("unknown input reference field")
                    source = Path(ref["path"])
                    if not source.is_absolute():
                        source = args.input.resolve().parent / source
                    if source.resolve() == args.output.resolve():
                        raise ValueError("output cannot be an input source")
                    records[key] = load_record(source, ref.get("window"))
                result = run_tool(step["tool"], records, step.get("options"))
                line = json.dumps({"step": index, "result": result}, ensure_ascii=False, allow_nan=False) + "\n"
                size += len(line.encode())
                if size > 256 * 1024**2:
                    raise ValueError("256 MiB output budget reached; earlier completed steps preserved")
                out.write(line)
                out.flush()
        print(json.dumps({"steps_completed": len(steps), "bytes": size, "output": str(args.output)}))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
