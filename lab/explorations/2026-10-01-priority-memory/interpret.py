"""Explicit comparisons for prose: keep denominators, blocks and zero baselines."""

from __future__ import annotations

import gzip
import json
from statistics import mean

from runner import WORK

from lab.tools.service_study import new_json, read_json


def main():
    analysis = read_json(WORK / "analysis-final.json")
    rows = [r for r in analysis["rows"] if r["cue"]]

    def select(**filters):
        return [r for r in rows if all(r[k] == v for k, v in filters.items())]

    comparisons = []
    for delay in (1, 30, 300):
        base = select(profile="default", interference="none", i=1, tau=0, history="single4", delay=delay)
        for profile, i, tau in (
            ("default", 0, 0),
            ("default", 0, 0.3),
            ("default", 0, 1),
            ("default", 0, 3),
            ("ordinary2", 0, 1),
            ("stability2", 0, 1),
            ("default", 1, 1),
        ):
            other = select(profile=profile, interference="none", i=i, tau=tau, history="single4", delay=delay)
            assert len(base) == len(other) == 4
            bv, ov = mean(r["net_B"] for r in base), mean(r["net_B"] for r in other)
            comparisons.append(
                {
                    "delay": delay,
                    "profile": profile,
                    "i": i,
                    "tau": tau,
                    "baseline_mean": bv,
                    "candidate_mean": ov,
                    "ratio_of_means": ov / bv if bv > 1e-9 else None,
                    "meets_80_percent_at_this_delay": bv > 1e-9 and ov >= 0.8 * bv,
                    "blocks": [
                        {"seed": r["seed"], "net_B": r["net_B"], "ab_weight": r["ab"].get("weight", 0.0)} for r in other
                    ],
                }
            )
    i_controls = []
    for r in select(profile="default", interference="none", i=0):
        if r["history"] == "single4":
            continue
        matches = select(
            profile="default",
            interference="none",
            i=1,
            seed=r["seed"],
            tau=r["tau"],
            history=r["history"],
            delay=r["delay"],
        )
        assert len(matches) == 1
        i_controls.append(abs(r["net_B"] - matches[0]["net_B"]))
    teaching = []
    for i in (0, 1):
        folder = WORK / "cases/default/100101" / f"i{i}f0/single4/train"
        record = json.loads(gzip.decompress((folder / "teaching-effects.json.gz").read_bytes()))[0]
        before, after = record["before"], record["after"]
        existing = {(e["source"], e["target"]) for e in before["edges"]}
        new_edges = [e for e in after["edges"] if (e["source"], e["target"]) not in existing]
        teaching.append(
            {
                "extra_on": bool(i),
                "channels": 2,
                "element_value": 1.0,
                "intensity": 4.0,
                "raw_input_product_sum": 8.0,
                "request_received": after["transport"]["received"] - before["transport"]["received"],
                "activation_added": after["transport"]["activated"] - before["transport"]["activated"],
                "new_edges": new_edges,
                "request_rule": "min(1, element_value * intensity * direct_gain)",
            }
        )
    out = {
        "schema": "threemind.priority-memory-comparisons/1",
        "comparisons_to_i1f0": comparisons,
        "extra_term_subthreshold_controls": {"pairs": len(i_controls), "largest_net_B_difference": max(i_controls)},
        "illustrative_teaching_receipts": teaching,
        "positive_probe_windows": sum(r["net_B"] > 1e-9 for r in rows),
        "positive_final_windows": sum(r["decision_B"] > 1e-9 for r in rows),
        "untrained_windows": len([r for r in rows if r["history"] == "none"]),
        "untrained_positive": sum(r["net_B"] > 1e-9 and r["history"] == "none" for r in rows),
        "remaining_AB_at_300": sum(bool(r["ab"]) for r in rows if r["delay"] == 300),
        "same_window_memory_cases": len(rows),
    }
    new_json(WORK / "comparisons.json", out)
    print(
        json.dumps(
            {k: v for k, v in out.items() if k not in ("comparisons_to_i1f0", "illustrative_teaching_receipts")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
