"""Illustrate an actual recorded transient, without re-simulation or smoothing."""

import gzip
import json
from pathlib import Path

from matplotlib.figure import Figure

from threemind_runtime.observation_cli import load_record

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    folder = ROOT / ".work/memory-transfer-20260930/cases/memory/930101/ordinary/full/wait-300/A"
    record = load_record(folder / "events.jsonl.gz")["payload"]
    meta = json.loads((folder / "result.json").read_bytes())
    points = json.loads(gzip.decompress((folder / "trajectory.json.gz").read_bytes()))
    channels = {n["channel"]: n["id"] for p in points for n in p["nodes"]}
    targets = [channels[ch] for ch in meta["extra"]["targets"]]
    t0 = int(record["start_us"])
    times = [(int(s["time_us"]) - t0) / 1e6 for s in record["series"]]
    decision = (int(record["ranking_time_us"]) - t0) / 1e6
    fig = Figure(figsize=(9, 6), layout="constrained")
    ax, total = fig.subplots(2, 1, sharex=True)
    for ident, label in zip(targets, ("Learned target", "Alternative target")):
        ax.step(times, [s["activation_vector"].get(str(ident), 0) for s in record["series"]], where="post", label=label)
    total.step(
        times,
        [sum(s["activation_vector"].values()) for s in record["series"]],
        where="post",
        color="#317c71",
        label="All nodes",
    )
    for item in (ax, total):
        item.axvline(decision, color="#ba6641", linestyle="--", label="Convergence decision")
        item.grid(alpha=0.2)
        item.legend()
        item.set_ylabel("Activation")
    total.set_xlabel("Simulation seconds since cue window began")
    fig.suptitle("A learned response can end before convergence\nOriginal 300-second retention evidence; no retraining")
    fig.savefig(HERE / "transient-before-convergence.png", dpi=160)


if __name__ == "__main__":
    main()
