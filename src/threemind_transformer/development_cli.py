"""Offline trajectory inspection and scratch decoder training; never advances Core."""

import argparse
import json
from pathlib import Path

from .development import TrajectoryBasis, activity_changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["project", "train", "decode"])
    parser.add_argument("--input", required=True, help="JSONL: process rows, or values/text calibration rows")
    parser.add_argument("--output", required=True)
    parser.add_argument("--basis", help="trajectory basis JSON; required for projection/training")
    parser.add_argument("--model", help="frozen model for decoding")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    path = Path(args.input)
    if path.stat().st_size > 256 * 2**20:
        raise ValueError("input exceeds 256 MiB; split into batches")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not 1 <= len(rows) <= 16384:
        raise ValueError("JSONL row limit")
    if args.operation == "project":
        basis = TrajectoryBasis(**json.loads(Path(args.basis).read_text(encoding="utf-8")))
        results = [basis.project(r) | {"changes": activity_changes(r)} for r in rows]
    else:
        import torch

        from .development_model import fit, load

        torch.set_num_threads(2)
        device = "cuda" if args.device != "cpu" and torch.cuda.is_available() else "cpu"
        if args.operation == "train":
            basis = TrajectoryBasis(**json.loads(Path(args.basis).read_text(encoding="utf-8")))
            result = fit(rows, basis, output, seed=args.seed, steps=args.steps, device=device)
            print(json.dumps(result, ensure_ascii=False))
            return
        model, _ = load(args.model, device)
        results = []
        for start in range(0, len(rows), 32):
            results.extend(model.decode([r["values"] for r in rows[start:start + 32]]))
    with output.open("x", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"rows": len(results), "output": str(output)}))


if __name__ == "__main__":
    main()
