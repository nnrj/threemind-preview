"""Compare frozen full-/2 and /3 results without executing dynamics."""

import hashlib
import json

import analyze
import matplotlib.pyplot as plt

HERE = analyze.HERE
read = analyze.read


def main():
    directory = HERE / "run-03"
    hashes = read(directory / "checksums.json")
    for name, digest in hashes.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    old = read(directory / "results.json")
    new = read(HERE / "run-02/results.json")
    comparisons = []
    for v2 in old["runs"]:
        legacy = next(r for r in new["runs"] if r["curriculum"] == v2["curriculum"] and r["mode"] == "legacy-stability")
        common = v2["config"].keys() & legacy["config"].keys()
        assert all(v2["config"][k] == legacy["config"][k] for k in common)
        rows = []
        for a, b in zip(v2["stages"], legacy["stages"]):
            assert a["seconds"] == b["seconds"]
            sa = read(directory / v2["case"] / f"t{a['seconds']}.json.gz")
            sb = read(HERE / "run-02" / legacy["case"] / f"t{b['seconds']}.json.gz")
            # Different individuals may allocate different node IDs. Compare the
            # declared common receptor wiring, never transplant ID meanings.
            na = {n["id"]: n["channel"] for n in sa["nodes"]}
            nb = {n["id"]: n["channel"] for n in sb["nodes"]}
            ea = {(na[e["source"]], na[e["target"]], e["birth_us"]): e for e in sa["edges"]}
            eb = {(nb[e["source"]], nb[e["target"]], e["birth_us"]): e for e in sb["edges"]}
            shared = ea.keys() & eb.keys()
            field_differences = {
                k: max((abs(ea[key][k] - eb[key][k]) for key in shared), default=0)
                for k in ("weight", "stability", "eligibility")
            }
            probe_max = max(
                (
                    abs(x - y)
                    for p, q in zip(a.get("probes", []), b.get("probes", []))
                    for w in ("primary", "full")
                    for x, y in zip(p["integrals"][w], q["integrals"][w])
                ),
                default=0,
            )
            rows.append(
                {
                    "seconds": a["seconds"],
                    "nodes_v2": a["nodes"],
                    "nodes_v3_legacy": b["nodes"],
                    "raw_edge_rows_exact": sa["edges"] == sb["edges"],
                    "edge_identity_sets_exact": ea.keys() == eb.keys(),
                    "edge_discrete_fields_exact": all(
                        ea[key][k] == eb[key][k] for key in shared for k in ("touches", "last_touch_us")
                    ),
                    "edge_float_field_max_abs_difference": field_differences,
                    "text_partition_exact": a["partitions"]["TT"] == b["partitions"]["TT"],
                    "partition_statistics_exact": a["partitions"] == b["partitions"],
                    "probe_integrals_max_absolute_difference": probe_max,
                    "v2_resolved_cues": sum(p.get("diagnostic_choice") is not None for p in a.get("probes", [])[1:]),
                }
            )
        comparisons.append({"curriculum": v2["curriculum"], "common_config_fields_identical": True, "stages": rows})
    summary = {
        "checked_files": len(hashes),
        "source": "run-03/results.json",
        "comparisons": comparisons,
        "v2_wall_seconds": old["wall_seconds"],
        "v2_timings": {r["case"]: r["timing_seconds"] for r in old["runs"]},
    }
    (HERE / "comparison-v2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), layout="constrained")
    for r in [*new["runs"], *old["runs"]]:
        if r["curriculum"] != "repeat":
            continue
        mode = r["mode"]
        color = {"adaptive-half-life": "#176DAD", "legacy-stability": "#C86625", "full-v2": "#3B8060"}[mode]
        label = {"adaptive-half-life": "/3 scheme 1", "legacy-stability": "/3 scheme 2", "full-v2": "Full /2"}[mode]
        style = {
            "color": color,
            "label": label,
            "linestyle": ":" if mode == "full-v2" else "-",
            "marker": "x" if mode == "full-v2" else "o",
            "markersize": 7 if mode == "full-v2" else 4,
        }
        rows = [s for s in r["stages"] if 530 <= s["seconds"] <= 830]
        axes[0].plot([s["seconds"] - 530 for s in rows], [s["partitions"]["TT"]["count"] for s in rows], **style)
        rows = [s for s in r["stages"] if s["seconds"] >= 834]
        axes[1].plot([s["seconds"] - 834 for s in rows], [s["nodes"] for s in rows], **style)
    axes[0].set(
        title="Repeated text edges: /2 and scheme 2 coincide",
        xlabel="Seconds after teaching reference",
        ylabel="Original text edges",
    )
    axes[1].set(
        title="Nodes after physical background stops",
        xlabel="Seconds after all external input stops",
        ylabel="Nodes (text and background)",
    )
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.legend(fontsize=9)
    fig.suptitle("Full old-kernel control: identical text, repetition and telemetry", fontsize=13)
    fig.savefig(HERE / "legacy-comparison.png", dpi=180)
    analyze.save_svg(fig, HERE / "legacy-comparison.svg")
    print(
        json.dumps(
            {
                "checked_files": len(hashes),
                "all_edge_rows_exact": all(s["raw_edge_rows_exact"] for r in comparisons for s in r["stages"]),
                "all_partition_stats_exact": all(
                    s["partition_statistics_exact"] for r in comparisons for s in r["stages"]
                ),
                "probe_max_difference": max(
                    s["probe_integrals_max_absolute_difference"] for r in comparisons for s in r["stages"]
                ),
                "node_differences": [
                    (r["curriculum"], s["seconds"], s["nodes_v2"], s["nodes_v3_legacy"])
                    for r in comparisons
                    for s in r["stages"]
                    if s["nodes_v2"] != s["nodes_v3_legacy"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
