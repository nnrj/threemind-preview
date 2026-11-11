"""Bounded graph/process expression, train/continue/decode via JSONL."""

import argparse, json, time
from dataclasses import asdict
from pathlib import Path
import psutil
import torch
from .graph_expression import GraphExpressionConfig, fit, load
from .local_activity import local_process, FIELDS, POLICY


def view_config(view):
    return GraphExpressionConfig(node_fields=FIELDS, use_edges=False) if view != "graph" else GraphExpressionConfig()


def prepare(row, view):
    value = local_process(row["process"]) if view == "local" else row["process"]
    if view != "graph" and (tuple(value["node_fields"]) != FIELDS or any(f["edges"] for f in value["frames"])):
        raise ValueError("local view requires the six activity fields and no structural edges")
    return dict(row, process=value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=("train", "decode", "config", "prepare"))
    p.add_argument("--view", choices=("local", "prepared-local", "graph"), default="local")
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--config", type=Path)
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    p.add_argument("--steps", type=int, default=4000)
    p.add_argument("--learning-rate", type=float, default=0.001)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--wall-seconds", type=int, default=3600)
    args = p.parse_args()
    torch.set_num_threads(2)
    if args.operation == "config":
        print(json.dumps(asdict(view_config(args.view)), indent=2))
        return
    if args.input is None or args.output is None:
        p.error("input and output required")
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.input.stat().st_size > 256 * 2**20:
        raise ValueError("split input above256MiB")
    if not 1 <= args.wall_seconds <= 14400:
        raise ValueError("wall budget")
    if not 1 <= args.batch_size <= 32:
        raise ValueError("batch size must be1..32")
    device = "cuda" if args.device != "cpu" and torch.cuda.is_available() else "cpu"
    started = time.monotonic()

    def guard():
        if time.monotonic() - started > args.wall_seconds:
            raise RuntimeError("wall budget")
        if psutil.Process().memory_info().rss > 4 * 2**30 or psutil.virtual_memory().available < 2 * 2**30:
            raise RuntimeError("memory reserve")
        if device == "cuda" and torch.cuda.memory_allocated() > 3 * 2**30:
            raise RuntimeError("GPU budget")

    rows = []
    for line in args.input.open(encoding="utf-8"):
        if not line.strip():
            continue
        guard()
        row = json.loads(line)
        if set(row) - ({"id", "process", "text"} if args.operation == "train" else {"id", "process"}):
            raise ValueError("undeclared inference fields or teaching labels")
        rows.append(prepare(row, args.view))
        if len(rows) > (128 if args.operation == "train" else 512):
            raise ValueError("record budget")
    if not rows:
        raise ValueError("empty input")
    if args.operation == "prepare":
        if args.view != "local":
            raise ValueError("prepare accepts raw local observations")
        with args.output.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        return
    if args.operation == "decode":
        if args.checkpoint is None:
            p.error("checkpoint required")
        model, _ = load(args.checkpoint, device)
        with args.output.open("x", encoding="utf-8") as stream:
            for i in range(0, len(rows), args.batch_size):
                guard()
                part = rows[i : i + args.batch_size]
                outputs = model.decode([r["process"] for r in part])
                for row, out in zip(part, outputs):
                    evidence = {
                        "view": args.view,
                        "window_start_us": row["process"]["start_us"],
                        "window_end_us": row["process"]["end_us"],
                        "observed_channels": len({n["channel"] for f in row["process"]["frames"] for n in f["nodes"]}),
                        "local_policy": POLICY if args.view != "graph" else None,
                    }
                    stream.write(
                        json.dumps(
                            {"id": row.get("id"), "output": out, "device": device, "observation": evidence},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
    else:
        if args.config:
            config = GraphExpressionConfig(**json.loads(args.config.read_text(encoding="utf-8")))
        elif args.checkpoint:
            config = load(args.checkpoint, "cpu")[0].config
        else:
            config = view_config(args.view)
        if args.view != "graph" and (config.node_fields != FIELDS or config.use_edges):
            raise ValueError("checkpoint/config does not describe local activity")
        _, meta = fit(
            rows,
            args.output,
            config=config,
            initial=args.checkpoint,
            steps=args.steps,
            learning_rate=args.learning_rate,
            batch_size=args.batch_size,
            device=device,
            check=guard,
        )
        print(json.dumps({"checkpoint": str(args.output), "steps": meta["steps"], "device": device}))


if __name__ == "__main__":
    main()
