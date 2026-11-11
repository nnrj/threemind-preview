"""Read-only evidence checks and exportable figures; never advances Core."""

import gzip
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(HERE.parents[2] / ".work/retention-plot-config"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from threemind_runtime.sensory import TextSensor


def read(path):
    body = path.read_bytes()
    return json.loads(gzip.decompress(body) if path.suffix == ".gz" else body)


def save_svg(figure, path):
    figure.savefig(path)
    # Matplotlib path attributes contain line-end spaces; removing those spaces
    # leaves the XML geometry intact and keeps exported source diffs clean.
    path.write_text("\n".join(line.rstrip() for line in path.read_text("utf-8").splitlines()) + "\n", "utf-8")


def main():
    checked = {}
    for name in ("run-01", "run-02", "trace-01"):
        directory = HERE / name
        hashes = read(directory / "checksums.json")
        for file, expected in hashes.items():
            assert hashlib.sha256((directory / file).read_bytes()).hexdigest() == expected, (name, file)
        checked[name] = len(hashes)
    data = read(HERE / "run-02/results.json")
    trace = read(HERE / "trace-01/results.json")
    sensor = TextSensor(20261004)
    labels = {sensor.identity(0x400000 + ord(c)): c for c in "苹果树叶天空雪花红绿蓝白是色的。"}
    summary = {"checked_evidence_files": checked, "runs": [], "trace": [], "wall_seconds": data["wall_seconds"]}
    old = read(HERE / "run-01/results.json")
    assert all(
        s["partitions"]["TT"]["count"] == s["partitions"]["TB"]["count"] == 0 for r in old["runs"] for s in r["stages"]
    )
    assert all(s["partitions"]["TB"]["count"] == 0 for r in data["runs"] for s in r["stages"])
    for kind in ("repeat", "single"):
        configs = [r["config"] for r in data["runs"] if r["curriculum"] == kind]
        assert {k for k in configs[0] if configs[0][k] != configs[1][k]} == {"consolidation_mode"}
    for run in data["runs"]:
        stages = []
        for stage in run["stages"]:
            if stage["seconds"] < 530:
                continue
            saved = read(HERE / "run-02" / run["case"] / f"t{stage['seconds']}.json.gz")
            text_ids = {n["id"]: labels[n["channel"]] for n in saved["nodes"] if n["channel"] in labels}
            remaining_chars = sorted(
                {text_ids[e[k]] for e in saved["edges"] for k in ("source", "target") if e[k] in text_ids}
            )
            probes = stage.get("probes", [])
            full_delta_max = max(
                (
                    abs(a - b)
                    for p in probes[1:]
                    for a, b in zip(p["integrals"]["full"], probes[0]["integrals"]["full"])
                ),
                default=0,
            )
            stages.append(
                {
                    "seconds": stage["seconds"],
                    "text": stage["partitions"]["TT"],
                    "background": stage["partitions"]["BB"],
                    "text_nodes": len(text_ids),
                    "paired_edges": sum(p["present"] for p in stage["paired_character_edges"]),
                    "remaining_connected_characters": remaining_chars,
                    "cue_probe_count": len(probes[1:]),
                    "resolved_cues": sum(p["diagnostic_choice"] is not None for p in probes[1:]),
                    "maximum_abs_full_window_delta": full_delta_max,
                }
            )
        summary["runs"].append(
            {
                "case": run["case"],
                "timing_seconds": run["timing_seconds"],
                "wall_seconds": run["wall_seconds"],
                "stages": stages,
            }
        )
    for row in trace:
        summary["trace"].append({k: v for k, v in row.items() if k != "rows"})
    (HERE / "analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    colors = {"adaptive-half-life": "#176DAD", "legacy-stability": "#C86625"}
    titles = {"adaptive-half-life": "Scheme 1: adaptive H", "legacy-stability": "Scheme 2: legacy stability"}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 180})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
    for run in data["runs"]:
        rows = [s for s in run["stages"] if 530 <= s["seconds"] <= 830]
        times = [s["seconds"] - 530 for s in rows]
        mode = run["mode"]
        style = {
            "color": colors[mode],
            "label": titles[mode],
            "marker": "o" if mode == "adaptive-half-life" else "s",
            "markersize": 5,
            "linestyle": "-" if mode == "adaptive-half-life" else "--",
        }
        ax = axes[0, 0] if run["curriculum"] == "repeat" else axes[1, 0]
        ax.plot(times, [s["partitions"]["TT"]["cohort"]["surviving"] for s in rows], **style)
        if run["curriculum"] == "repeat":
            axes[0, 1].plot(times, [100 * s["partitions"]["TT"]["cohort"]["relative_weight"] for s in rows], **style)
            tail = [s for s in run["stages"] if s["seconds"] >= 530]
            axes[1, 1].plot([s["seconds"] - 530 for s in tail], [s["partitions"]["BB"]["count"] for s in tail], **style)
    for ax, title, y in zip(
        axes.flat,
        (
            "Repeated text: original edge survival",
            "Repeated text: retained cohort weight",
            "Single presentation: edge survival",
            "Background edges: input stops at +304 s",
        ),
        ("Edges (baseline 132)", "% of own baseline weight", "Edges (baseline 132)", "Active background edges"),
    ):
        ax.set(title=title, xlabel="Simulated seconds after teaching reference", ylabel=y)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
    axes[1, 1].axvline(304, color="#777777", linewidth=1, linestyle=":")
    axes[1, 1].axvspan(304, 1504, color="#dddddd", alpha=0.25)
    axes[0, 0].annotate(
        "12 shared-frame edges only\n(no word/color pair remains)",
        xy=(300, 12),
        xytext=(90, 58),
        fontsize=8,
        arrowprops={"arrowstyle": "->", "color": "#777777"},
    )
    fig.suptitle(
        "Text retention with identical recorded physical telemetry\n57 presentations per sentence versus one; default retention parameters",
        fontsize=14,
    )
    fig.savefig(HERE / "retention.png")
    save_svg(fig, HERE / "retention.svg")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), layout="constrained")
    for r in trace:
        mode = "adaptive-half-life" if r["case"].startswith("scheme1") else "legacy-stability"
        times = [int(x["time_us"]) / 1e6 for x in r["rows"]]
        axes[0].plot(times, [x["text_H_max_s"] for x in r["rows"]], color=colors[mode], label=titles[mode])
        axes[1].plot(times, [x["text_weight_sum"] for x in r["rows"]], color=colors[mode], label=titles[mode])
    axes[0].set(title="Sampled maximum text-edge H", ylabel="Seconds (scheme 2 H is unused)")
    axes[1].set(title="Text-edge weight during repeated teaching", ylabel="Weight sum")
    for ax in axes:
        ax.set_xlabel("Simulated seconds")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
    fig.savefig(HERE / "repetition-diagnostic.png")
    save_svg(fig, HERE / "repetition-diagnostic.svg")
    print(json.dumps({"hash_checks": checked, "runs": len(summary["runs"]), "figures": 2}))


if __name__ == "__main__":
    main()
