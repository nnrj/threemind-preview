"""Show actual simultaneous A/B trajectories; no simulation or interpolation."""

import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from threemind_runtime.adapters import channel_id

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True, layout="constrained")
for ax, order in zip(axes, ("AB", "BA"), strict=True):
    folder = ROOT / f".work/target-background-20261002/cases/matrix/100121/telemetry/{order}/wait1/cue1"
    state = json.loads(gzip.decompress((folder / "parent-state.json.gz").read_bytes()))
    channels = {n["channel"]: n["id"] for n in state["nodes"]}
    targets = {s: str(channels[channel_id(100121, "priority-memory/1", i)]) for i, s in enumerate("AB")}
    events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
    record = next(e["payload"] for e in events if e.get("payload", {}).get("analysis_schema"))
    rows = [s for s in record["series"] if int(s["time_us"]) <= 8840000]
    times = [(int(s["time_us"]) - 8000000) / 1e6 for s in rows]
    for s, color in zip("AB", ("#b7603f", "#267969"), strict=True):
        values = [r["activation_vector"].get(targets[s], 0) for r in rows]
        ax.step(times, values, where="post", label=s, color=color)
        ax.scatter(times, values, s=7, color=color)
    ax.axvline(0.12, color="#9a9a9a", ls=":", label="Readout at 120 ms")
    ax.axvline(0.8, color="#9a9a9a", ls="--", label="Old 800 ms span")
    ax.set(title=f"Teaching order {order}: later-taught {order[-1]} leads", xlabel="Time after cue (s)", xlim=(0, 0.84))
    ax.grid(alpha=0.18)
    ax.legend(fontsize=8)
axes[0].set_ylabel("Actual node activation")
(HERE / "figures").mkdir(exist_ok=True)
for suffix in ("png", "svg"):
    fig.savefig(HERE / f"figures/brief-response.{suffix}", dpi=160)
plt.close(fig)
