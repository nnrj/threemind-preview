"""Combine the registered primary analysis and separately labelled diagnostics."""

import json
from collections import Counter

from analyse import fraction, internal_changes
from experiment import HERE, WORK, classify, read_json

from lab.tools.language_observation import nearest_word
from lab.tools.service_study import new_json


def transport(metrics):
    value = metrics["transport"]
    accepted = value["sent"] - value["discarded"]
    return {
        "sent": value["sent"],
        "below_floor": value["discarded"],
        "passed_emission_floor": accepted,
        "passed_fraction": accepted / value["sent"] if value["sent"] else None,
    }


def main():
    primary = read_json(WORK / "analysis-v1.json")
    rows = []
    for path in sorted((WORK / "computations").glob("release-decoded-*-index.json")):
        result = read_json(path.with_name(path.name.removesuffix("-index.json")) / "result.json")
        index = read_json(path)
        if len(index) != len(result["windows"]):
            raise ValueError("incomplete diagnostic decoding")
        rows.extend(
            row | {"text": decoded.get("text"), "prediction": classify(decoded.get("text"))}
            for row, decoded in zip(index, result["windows"])
        )
    cal = [read_json(p) for p in (WORK / "cases").glob("s17-cal-*/result.json")]
    exemplars = [
        (c["label"], w["raw"])
        for c in cal
        if c["split"] == "train"
        for w in c["windows"]
        if w["summary"]["has_activity"]
    ]
    groups = []
    for intensity, facilitation in ((1, 0), (4, 0), (1, 1), (4, 1)):
        conditions = {}
        for condition in ("ordinary", "reversed"):
            key = (
                f"s17-{condition}"
                if (intensity, facilitation) == (1, 0)
                else f"release-i{intensity}-f{facilitation}-{condition}"
            )
            path = WORK / "cases" / key / "result.json"
            if not path.exists():
                conditions[condition] = {"status": "not_run"}
                continue
            taught = read_json(path)
            observed = read_json(WORK / "cases" / (key + "-spontaneous") / "result.json")
            probes = [r for r in rows if r["key"].startswith(key + "-probe-")]
            if (intensity, facilitation) == (1, 0):
                probes = [r for r in primary["seeds"][0]["primary"] if r["key"].startswith(key + "-probe-")]
            answers = []
            for row in probes:
                scores = row.get("raw_scores") or nearest_word(row["raw"], exemplars)
                answers.append(
                    {
                        "probe": row["probe"],
                        "label": row["label"],
                        "text": row["text"],
                        "prediction": row["prediction"],
                        "raw_prediction": scores[0][0] if scores else None,
                    }
                )
            windows = observed["windows"]
            last = max(
                (int(w["summary"]["last_active_us"]) for w in windows if w["summary"]["has_activity"]), default=None
            )
            t0, t1 = transport(taught["metrics"]), transport(observed["metrics"])
            conditions[condition] = {
                "status": "complete",
                "key": key,
                "nodes": taught["metrics"]["nodes"],
                "edges": taught["metrics"]["edges"],
                "mean_weight": taught["metrics"]["mean_weight"],
                "teaching_transmission": t0,
                "no_input_passed_emission_floor": t1["passed_emission_floor"] - t0["passed_emission_floor"],
                "no_input_changes": internal_changes(key + "-spontaneous"),
                "last_activity_after_teaching_seconds": (last - int(taught["time_us"])) / 1e6 if last else None,
                "observation_seconds": (int(observed["time_us"]) - int(taught["time_us"])) / 1e6,
                "final_life": observed["life"],
                "text_accuracy": fraction([r["prediction"] == r["label"] for r in answers]),
                "raw_diagnostic_accuracy": fraction([r["raw_prediction"] == r["label"] for r in answers]),
                "text_distribution": dict(Counter(r["text"] or "<silence>" for r in answers)),
                "answers": answers,
                "stream": [
                    {"window": r["window"], "text": r["text"], "summary": r["summary"]}
                    for r in rows
                    if r["key"] == key + "-spontaneous"
                ],
            }
        a = conditions["ordinary"].get("answers", [])
        b = {r["probe"]: r for r in conditions["reversed"].get("answers", [])}
        groups.append(
            {
                "intensity": intensity,
                "facilitation_tau_s": facilitation,
                "conditions": conditions,
                "matched_reversal": fraction(
                    [
                        r["prediction"] == r["label"] and b[r["probe"]]["prediction"] == b[r["probe"]]["label"]
                        for r in a
                        if r["probe"] in b
                    ]
                ),
            }
        )
    cases = [read_json(p) for p in (WORK / "cases").glob("*/result.json")]
    computations = [read_json(p) for p in (WORK / "computations").glob("*/result.json")]
    failures = [
        {"path": str(p.relative_to(WORK)), "error": read_json(p)["error"]}
        for p in (WORK / "computations").glob("*/failure.json")
    ]
    result = {
        "schema": "threemind.e42-results/1",
        "primary": primary,
        "diagnostic": {"purpose": "single-seed follow-up, not replacement of the primary gate", "groups": groups},
        "input_geometry": read_json(WORK / "input-audit-17-29.json"),
        "resources": {
            "core_cases": len(cases),
            "successful_computations": len(computations),
            "case_seconds": sum(r["wall_seconds"] for r in cases),
            "compute_seconds": sum(r.get("elapsed_seconds", 0) for r in computations),
            "local_bytes_before_archive": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
        },
        "failures": failures,
        "not_run": {
            "seeds": [43, 71],
            "reason": "registered futility after both initial seeds failed",
            "scratch_training": True,
            "family_logic": True,
        },
    }
    new_json(HERE / "results.json", result)
    print(
        json.dumps(
            {
                "resources": result["resources"],
                "diagnostic": [
                    {
                        "intensity": g["intensity"],
                        "facilitation": g["facilitation_tau_s"],
                        "reversal": g["matched_reversal"],
                        "conditions": {
                            k: {n: v for n, v in c.items() if n not in ("answers", "stream", "text_distribution")}
                            for k, c in g["conditions"].items()
                        },
                    }
                    for g in groups
                ],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
