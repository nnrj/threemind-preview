"""Fixed E43 window scores and explicit, secondary sensor-basis diagnostics."""

import argparse
import html
import json
from collections import Counter

import numpy as np
from experiment import CONDITIONS, HERE, PROBES, WORDS, WORK, read_json

from lab.tools.language_observation import nearest_word
from lab.tools.service_study import new_json


def classify(text):
    matches = [w for w in WORDS if w in (text or "")]
    return matches[0] if len(matches) == 1 else None


def nearest(vector, exemplars):
    scores = nearest_word(vector, exemplars)
    return {"prediction": scores[0][0] if any(vector) else None, "scores": scores}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    assets = read_json(WORK / "assets.json")
    cases = {p.parent.name: read_json(p) for p in (WORK / "cases").glob("*/result.json")}
    decoded = {}
    for path in sorted((WORK / "computations").glob("*/result.json")):
        index = read_json(path.parent / "index.json")
        results = read_json(path)["windows"]
        if len(index) != len(results):
            raise ValueError("decoder batch length differs")
        decoded.update({(r["key"], r["window"]): d for r, d in zip(index, results)})
    rows, streams, window_diagnostics = [], [], []
    for case in cases.values():
        if case["kind"] != "probe":
            continue
        seed = case["seed"]
        exemplars = [(e["label"], e["values"]) for e in assets["calibration"][str(seed)]]
        if case["probe"] is None:
            for w in case["windows"]:
                d = decoded.get((case["key"], w["window"]))
                streams.append(
                    {
                        "seed": seed,
                        "condition": case["condition"],
                        "checkpoint": case["checkpoint"],
                        "window": w["window"],
                        "summary": w["summary"],
                        "decoder": d,
                        "basis": nearest(w["basis"]["values"], exemplars),
                    }
                )
            continue
        w = next((w for w in case["windows"] if w["window"] == 1), None)
        if w is None:
            continue
        baseline = cases.get(case["key"].rsplit("-p", 1)[0] + "-p8")
        for observed in case["windows"]:
            reference = next(
                (b for b in (baseline or {}).get("windows", []) if b["window"] == observed["window"]), None
            )
            own_values = np.asarray(observed["basis"]["values"])
            difference = own_values - np.asarray(reference["basis"]["values"]) if reference else None
            window_diagnostics.append(
                {
                    "key": case["key"],
                    "seed": seed,
                    "condition": case["condition"],
                    "checkpoint": case["checkpoint"],
                    "probe": case["probe"],
                    "label": case["label"],
                    "window": observed["window"],
                    "raw_prediction": nearest(own_values.tolist(), exemplars)["prediction"],
                    "delta_prediction": nearest(difference.tolist(), exemplars)["prediction"]
                    if difference is not None
                    else None,
                }
            )
        b = next((b for b in (baseline or {}).get("windows", []) if b["window"] == 1), None)
        vector = np.asarray(w["basis"]["values"])
        delta = vector - np.asarray(b["basis"]["values"]) if b else None
        d = decoded.get((case["key"], 1))
        rows.append(
            {k: case[k] for k in ("key", "seed", "condition", "checkpoint", "probe", "label", "cue_index")}
            | {
                "decoder": d,
                "prediction": classify(d.get("text")) if d else None,
                "raw": nearest(vector.tolist(), exemplars),
                "cue_minus_no_cue": nearest(delta.tolist(), exemplars) if delta is not None else None,
                "basis_norm": float(np.linalg.norm(vector)),
                "cue_delta_norm": float(np.linalg.norm(delta)) if delta is not None else None,
                "outside_basis_peak_total": w["basis"]["outside_basis_peak_total"],
                "summary": w["summary"],
            }
        )
    table, contrasts = [], []
    for seed in (17, 29):
        for point in PROBES:
            for condition in CONDITIONS:
                own = [r for r in rows if (r["seed"], r["checkpoint"], r["condition"]) == (seed, point, condition)]
                if not own:
                    continue
                table.append(
                    {
                        "seed": seed,
                        "checkpoint": point,
                        "condition": condition,
                        "n": len(own),
                        "decoded_n": sum(r["decoder"] is not None for r in own),
                        "text_correct": sum(r["prediction"] == r["label"] for r in own if r["decoder"] is not None),
                        "basis_correct": sum(r["raw"]["prediction"] == r["label"] for r in own),
                        "cue_delta_correct": sum(
                            r["cue_minus_no_cue"] is not None and r["cue_minus_no_cue"]["prediction"] == r["label"]
                            for r in own
                        ),
                        "text_distribution": dict(
                            Counter((r["decoder"] or {}).get("text", "<not decoded>") for r in own)
                        ),
                        "mean_cue_delta_norm": float(
                            np.mean([r["cue_delta_norm"] for r in own if r["cue_delta_norm"] is not None])
                        ),
                    }
                )
            spaced = {
                r["probe"]: r for r in rows if (r["seed"], r["checkpoint"], r["condition"]) == (seed, point, "spaced")
            }
            reverse = {
                r["probe"]: r for r in rows if (r["seed"], r["checkpoint"], r["condition"]) == (seed, point, "reversed")
            }
            frozen = {
                r["probe"]: r for r in rows if (r["seed"], r["checkpoint"], r["condition"]) == (seed, point, "frozen")
            }
            if spaced and reverse:
                both = [name for name in spaced if name in reverse]
                contrasts.append(
                    {
                        "seed": seed,
                        "checkpoint": point,
                        "n": len(both),
                        "paired_text_correct": sum(
                            spaced[n]["prediction"] == spaced[n]["label"]
                            and reverse[n]["prediction"] == reverse[n]["label"]
                            for n in both
                        ),
                        "paired_basis_correct": sum(
                            spaced[n]["raw"]["prediction"] == spaced[n]["label"]
                            and reverse[n]["raw"]["prediction"] == reverse[n]["label"]
                            for n in both
                        ),
                        "paired_cue_delta_correct": sum(
                            spaced[n]["cue_minus_no_cue"]["prediction"] == spaced[n]["label"]
                            and reverse[n]["cue_minus_no_cue"]["prediction"] == reverse[n]["label"]
                            for n in both
                        ),
                        "text_changed_from_frozen": sum(
                            (spaced[n]["decoder"] or {}).get("text") != (frozen[n]["decoder"] or {}).get("text")
                            for n in spaced
                            if n in frozen
                        ),
                        "classified_word_changed_from_frozen": sum(
                            spaced[n]["prediction"] != frozen[n]["prediction"] for n in spaced if n in frozen
                        ),
                        "compared_frozen_n": len(set(spaced) & set(frozen)),
                    }
                )
    checkpoints = []
    for path in sorted((WORK / "cases").glob("*/checkpoints/*/summary.json")):
        v = read_json(path)
        m, t = v["metrics"], v["metrics"]["transport"]
        checkpoints.append(
            {
                "seed": v["seed"],
                "condition": v["condition"],
                "requested_seconds": v["requested_seconds"],
                "actual_seconds": int(v["time_us"]) / 1e6,
                "life": v["life"],
                "nodes": m["nodes"],
                "edges": m["edges"],
                "mean_weight": m["mean_weight"],
                "activation": m["activation"],
                "sent": t["sent"],
                "passed_emission_floor": t["sent"] - t["discarded"],
                "presentations": v["lesson_cursor"],
            }
        )
    dose_rows = []

    def passed(case):
        transport = case["metrics"]["transport"]
        return transport["sent"] - transport["discarded"]

    for key, case in cases.items():
        if case["kind"] != "probe-dose":
            continue
        original = cases[key.removeprefix("d1-")]
        baseline = cases[f"{case['source']}-t830-p8"]
        d = decoded.get((key, 1))
        old = decoded.get((original["key"], 1))
        dose_rows.append(
            {
                "key": key,
                "seed": case["seed"],
                "condition": case["condition"],
                "probe": case["probe"],
                "label": case["label"],
                "text_at_1": (d or {}).get("text"),
                "text_at_half": (old or {}).get("text"),
                "prediction_at_1": classify((d or {}).get("text")),
                "prediction_at_half": classify((old or {}).get("text")),
                "cue_attributable_passed_at_1": passed(case) - passed(baseline),
                "cue_attributable_passed_at_half": passed(original) - passed(baseline),
                "passed_difference_scope": "paired cue minus no-language total emission-floor passage; not a decoded meaning",
            }
        )
    source_elapsed = {}
    for key, case in cases.items():
        if case["kind"] != "source":
            continue
        start_file = WORK / "cases" / key / "initial/state.tmind"
        end_file = WORK / "cases" / (key + "-t830-p8") / "result.json"
        if start_file.exists() and end_file.exists():
            source_elapsed[key] = end_file.stat().st_mtime - start_file.stat().st_mtime
    output = {
        "schema": "threemind.e43-analysis/1",
        "primary_window": 1,
        "table": table,
        "contrasts": contrasts,
        "checkpoints": checkpoints,
        "primary_rows": rows,
        "no_new_language": streams,
        "all_window_secondary_diagnostics": window_diagnostics,
        "secondary_cue_dose": dose_rows,
        "structural_diagnostic": read_json(WORK / "structural-diagnostic.json")
        if (WORK / "structural-diagnostic.json").exists()
        else None,
        "completed_cases": len(cases),
        "simulation_wall_seconds": sum(v["wall_seconds"] for v in cases.values()),
        "source_groups_elapsed_seconds_including_restore_io": source_elapsed,
        "elapsed_basis": "file timestamps across each sequential source and all forks; includes restore and I/O omitted from inner simulation timers",
        "elapsed_phase_including_intervening_analysis_seconds": max(
            p.stat().st_mtime for p in (WORK / "computations").glob("*/result.json")
        )
        - min(p.stat().st_mtime for p in (WORK / "cases").glob("*/initial/state.tmind"))
        if decoded
        else None,
        "decode_wall_seconds": sum(
            read_json(p).get("elapsed_seconds", 0) for p in (WORK / "computations").glob("*/result.json")
        ),
        "source_life": {k: v["life"] for k, v in cases.items() if v["kind"] == "source"},
        "frozen_head": True,
        "primary_projection_includes_background": True,
        "core_changed": False,
        "scratch_training_started": False,
    }
    print(
        json.dumps({"table": table, "contrasts": contrasts, "completed_cases": len(cases)}, ensure_ascii=False),
        flush=True,
    )
    if args.preview:
        return
    new_json(WORK / "analysis-v1.json", output)
    new_json(HERE / "results.json", output)
    tr = []
    for r in streams:
        tr.append(
            f"<tr><td>{r['seed']} / {html.escape(r['condition'])}</td><td>{r['checkpoint']}s + {r['window'] * 0.5:.1f}s</td>"
            f"<td>{r['summary']['peak_total_activation']:.4f}</td><td>{html.escape((r['decoder'] or {}).get('text') or '（静默 / 未译出）')}</td></tr>"
        )
    (WORK / "language-stream.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>ThreeMind E43</title><style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:16px;background:#f3f8f5;color:#23413a}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #bdccc6;text-align:left}section{overflow:auto}</style>"
        "<h1>E43 无新语言输入的活动与转译</h1><p>物理遥测背景继续输入。文字来自冻结的转换器，未经筛选，不会反馈给内核。每个时间点为独立快照分支，不是连续拼接的思维过程。</p>"
        "<section><table><thead><tr><th>种子 / 教学</th><th>模拟秒</th><th>活动峰值</th><th>原样转译</th></tr></thead><tbody>"
        + "".join(tr)
        + "</tbody></table></section>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
