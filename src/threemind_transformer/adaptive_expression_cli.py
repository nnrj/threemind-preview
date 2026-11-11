"""Bounded JSONL teacher updates for a personal expression adapter."""

import argparse
import json
import time
from pathlib import Path

import psutil
import torch

from .adaptive_expression import AdaptiveExpression


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("teach", "decode"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--wall-seconds", type=int, default=1800)
    args = parser.parse_args()
    if not 1 <= args.wall_seconds <= 7200 or not 1 <= args.steps <= 10000:
        parser.error("bounded time/steps required")
    if args.output.exists() or args.input.stat().st_size > 128 * 2**20:
        parser.error("output exists or input exceeds128MiB")
    if args.operation == "decode" and args.parent is None:
        parser.error("decode needs a saved personal adapter")
    device = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(2)
    born = time.monotonic()

    def guard():
        if time.monotonic() - born > args.wall_seconds:
            raise RuntimeError("wall time budget")
        if psutil.Process().memory_info().rss > 4 * 2**30 or psutil.virtual_memory().available < 2 * 2**30:
            raise RuntimeError("memory reserve")
        if device == "cuda" and torch.cuda.memory_allocated() > 3 * 2**30:
            raise RuntimeError("GPU budget")

    adapter = AdaptiveExpression.restore(args.parent, device=device) if args.parent else AdaptiveExpression(device=device)
    rows = []
    with args.input.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            if index >= 128:
                raise ValueError("128records per invocation")
            guard()
            row = json.loads(line)
            if args.operation == "teach":
                if set(row) != {"process", "text", "receipt"}:
                    raise ValueError("teaching requires process,text,receipt")
                adapter.teach(**row)
            else:
                if set(row) != {"process"}:
                    raise ValueError("inference accepts process only, no teaching targets")
                rows.append(adapter.decode([row["process"]])[0])
    if args.operation == "teach":
        manifest = adapter.adapt(args.output, steps=args.steps, check=guard)
        print(json.dumps({"revision": manifest["revision"], "checkpoint": str(args.output)}))
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
