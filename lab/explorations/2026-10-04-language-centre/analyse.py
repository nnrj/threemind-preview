"""E42 preregistered analysis: fixed windows; no answer-based decoder fitting."""

import gzip
import html
import json
from collections import Counter

from experiment import SEEDS, WORK, classify, curriculum, read_json

from lab.tools.language_observation import nearest_word
from lab.tools.service_study import new_json


def fraction(rows):
    return {
        "correct": sum(bool(v) for v in rows),
        "total": len(rows),
        "rate": sum(bool(v) for v in rows) / len(rows) if rows else None,
    }


def predictions(seed, kind):
    result = []
    for index in sorted((WORK / "computations").glob(f"s{seed}-{kind}-*-index.json")):
        output = index.with_name(index.name.removesuffix("-index.json")) / "result.json"
        if not output.exists():
            continue
        rows, decoded = read_json(index), read_json(output)["windows"]
        if len(rows) != len(decoded):
            raise ValueError("incomplete decoder batch")
        result.extend(
            row | {"decoded": value, "prediction": classify(value.get("text"))} for row, value in zip(rows, decoded)
        )
    return result


def internal_changes(key):
    """No-input trajectory rises/re-entry, distinguished from monotone decay."""
    path = WORK / "cases" / key / "observations.jsonl.gz"
    if not path.exists():
        return {}
    previous, seen, increases, reentries, peak_step = {}, set(), 0, 0, 0.0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["new_input"] or row["pending_external_before"]:
                raise ValueError("no-input dynamics analysis contains an external input")
            for frame in row["process"]["trajectory"]:
                current = {n["id"]: float(n["activation"]) for n in frame["nodes"]}
                if seen:
                    for node, value in current.items():
                        delta = value - previous.get(node, 0.0)
                        increases += delta > 1e-9
                        reentries += node in seen and node not in previous and value > 1e-9
                        peak_step = max(peak_step, delta)
                seen.update(current)
                previous = current
    return {
        "rising_node_steps": increases,
        "reentry_node_steps": reentries,
        "largest_activation_increase": peak_step,
        "tolerance": 1e-9,
    }


def main():
    cases = {p.parent.name: read_json(p) for p in (WORK / "cases").glob("*/result.json")}
    output = {
        "schema": "threemind.e42-analysis/1",
        "primary_window": 1,
        "primary_window_us": [500000, 1000000],
        "seeds": [],
        "limitations": [
            "Four-word controlled vocabulary; no general dialogue claim.",
            "Pretrained Qwen prior is present in both sensory and expressive routes.",
            "Raw nearest-word similarity is diagnostic, not the primary answer metric.",
            "Zero activity is evaluated for silence, separately from active-window translation.",
        ],
    }
    stream_rows = []
    for seed in SEEDS:
        selection_file = WORK / f"selection-{seed}.json"
        if not selection_file.exists():
            continue
        selection = read_json(selection_file)
        # Mirror the original filesystem enumeration explicitly: runner does not
        # sort these globs. Their actual order is saved in each training request.
        all_cal = [read_json(p) for p in (WORK / "cases").glob(f"s{seed}-cal-*/result.json")]
        heldout = [(c, w) for c in all_cal if c["split"] == "heldout" for w in c["windows"]]
        cal_rows = []
        for candidate in selection["candidates"]:
            if candidate.get("status") == "numerical_failure":
                cal_rows.append(candidate | {"active_accuracy": None, "silent_correct": None, "texts": []})
                continue
            decoded = read_json(WORK / "computations" / (candidate["head_key"] + "-validation") / "result.json")[
                "windows"
            ]
            if len(decoded) != len(heldout):
                raise ValueError("heldout row mismatch")
            active = [(c, w, d) for (c, w), d in zip(heldout, decoded) if w["summary"]["has_activity"]]
            silent = [d for (c, w), d in zip(heldout, decoded) if not w["summary"]["has_activity"]]
            cal_rows.append(
                candidate
                | {
                    "active_accuracy": fraction([classify(d.get("text")) == c["label"] for c, w, d in active]),
                    "silent_correct": fraction([not d.get("text") for d in silent]),
                    "texts": [
                        {
                            "case": c["key"],
                            "window": w["window"],
                            "active": w["summary"]["has_activity"],
                            "expected": c["label"],
                            "text": d.get("text"),
                        }
                        for (c, w), d in zip(heldout, decoded)
                    ],
                }
            )
        chosen = next(c for c in cal_rows if c["head_key"] == selection["chosen"]["head_key"])
        exemplars = [
            (c["label"], w["raw"])
            for c in all_cal
            if c["split"] == "train"
            for w in c["windows"]
            if w["summary"]["has_activity"]
        ]
        decoded = predictions(seed, "formal")
        controls = predictions(seed, "controls")
        early = predictions(seed, "early-stream")
        conditions = {}
        primary = []
        for condition in ("ordinary", "reversed", "blank", "frozen"):
            key = f"s{seed}-{condition}"
            probe = [r for r in decoded if r["key"].startswith(key + "-probe-") and r["window"] == 1]
            for r in probe:
                scores = nearest_word(r["raw"], exemplars)
                diagnostic = scores[0][0] if scores and any(r["raw"]) else None
                primary.append(
                    {k: r[k] for k in ("key", "probe", "label", "prediction", "summary")}
                    | {"text": r["decoded"].get("text"), "raw_prediction": diagnostic, "raw_scores": scores}
                )
            own = [r for r in primary if r["key"].startswith(key + "-probe-")]
            spontaneous = [r for r in decoded if r["key"] == key + "-spontaneous"]
            initial = cases.get(key)
            final = cases.get(key + "-spontaneous")
            active = [w for w in (final or {}).get("windows", []) if w["summary"]["has_activity"]]
            last_active = max((int(w["summary"]["last_active_us"]) for w in active), default=None)
            conditions[condition] = {
                "primary_text": fraction([r["prediction"] == r["label"] for r in own]),
                "primary_raw_diagnostic": fraction([r["raw_prediction"] == r["label"] for r in own]),
                "active_primary": sum(r["summary"]["has_activity"] for r in own),
                "spontaneous_windows": len((final or {}).get("windows", [])),
                "spontaneous_active_windows": len(active),
                "last_active_after_teaching_seconds": (last_active - int(initial["time_us"])) / 1e6
                if last_active is not None and initial
                else None,
                "final_life": (final or {}).get("life"),
                "no_input_activity_changes": internal_changes(key + "-spontaneous"),
                "spontaneous_word_counts": dict(
                    Counter(r["prediction"] or "unclassified" for r in spontaneous if r["summary"]["has_activity"])
                ),
                "generated_on_silent_window": sum(
                    bool(r["decoded"].get("text")) for r in spontaneous if not r["summary"]["has_activity"]
                ),
                "last_taught_sentence": curriculum(seed, condition == "reversed")[-1] if condition != "blank" else None,
            }
            for r in spontaneous:
                early_row = next((e for e in early if e["key"] == r["key"] and e["window"] == r["window"]), None)
                stream_rows.append(
                    {
                        "seed": seed,
                        "condition": condition,
                        "window": r["window"],
                        "summary": r["summary"],
                        "text": r["decoded"].get("text"),
                        "early_text": early_row["decoded"].get("text") if early_row else None,
                        "raw_scores": nearest_word(r["raw"], exemplars),
                        "core_unchanged_for_decoder_comparison": True,
                    }
                )
        normal = [r for r in primary if "-ordinary-" in r["key"]]
        reverse = {r["probe"]: r for r in primary if "-reversed-" in r["key"]}
        original = {r["key"]: r for r in primary}
        interventions = {}
        for kind in ("zero", "shuffled", "swapped_experience"):
            rows = [r for r in controls if r["control"] == kind]
            interventions[kind] = {
                "rows": len(rows),
                "changed_text": sum(r["decoded"].get("text") != original[r["key"]]["text"] for r in rows),
                "correct_for_original_label": fraction([r["prediction"] == r["label"] for r in rows]),
                "text_distribution": dict(Counter(r["decoded"].get("text") or "<silence>" for r in rows)),
            }
        reversal = fraction(
            [
                r["prediction"] == r["label"] and reverse[r["probe"]]["prediction"] == reverse[r["probe"]]["label"]
                for r in normal
                if r["probe"] in reverse
            ]
        )
        calibration_passed = (chosen["active_accuracy"]["rate"] or 0) >= 0.75
        normal_rate = conditions["ordinary"]["primary_text"]["rate"] or 0
        blank_rate = conditions["blank"]["primary_text"]["rate"] or 0
        seed_passed = calibration_passed and normal_rate > blank_rate and (reversal["rate"] or 0) > 0.5
        output["seeds"].append(
            {
                "seed": seed,
                "chosen": selection["chosen"],
                "calibration": cal_rows,
                "active_calibration_passed": calibration_passed,
                "conditions": conditions,
                "matched_reversal": reversal,
                "controls": interventions,
                "feasibility_seed_passed": seed_passed,
                "primary": primary,
                "formal_complete": len(primary) == 32,
            }
        )
    output["feasibility_gate_passed"] = (
        sum(s["feasibility_seed_passed"] and s["formal_complete"] for s in output["seeds"]) >= 3
    )
    output["scratch_training_started"] = False
    target = WORK / "analysis-v1.json"
    new_json(target, output)
    new_json(WORK / "spontaneous-stream.json", stream_rows)
    # A self-contained evidence viewer, readable without a running service.
    cards = []
    for r in stream_rows:
        s = r["summary"]
        cards.append(
            f"<tr><td>{r['seed']} / {html.escape(r['condition'])}</td><td>{int(s['start_us']) / 1e6:.2f}–{int(s['end_us']) / 1e6:.2f}s</td>"
            f"<td>{s['peak_total_activation']:.5f}</td><td>{html.escape(r['early_text'] or '（静默）')}</td>"
            f"<td>{html.escape(r['text'] or '（静默）')}</td></tr>"
        )
    document = (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>ThreeMind E42 · 无新输入活动流</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:16px;color:#233d36;background:#f2f7f5}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #dae5e0;text-align:left}section{overflow:auto}p{line-height:1.7}</style>"
        "<h1>无新输入时，实际活动与语言转换</h1><p>每行来自保存的真实活动。两列文字使用同一段活动，分别通过80步和600步校准的冻结输出器；转换器不接收上一窗口文字。静默不补写。这里是翻译器输出，不是已经验证的完整思维内容。</p>"
        "<section><table><thead><tr><th>接线种子 / 经历</th><th>模拟时间</th><th>窗内总激活峰值</th><th>80步校准</th><th>600步校准</th></tr></thead><tbody>"
        + "".join(cards)
        + "</tbody></table></section>"
    )
    with (WORK / "spontaneous-stream.html").open("x", encoding="utf-8") as f:
        f.write(document)
    print(
        json.dumps(
            {"seeds": len(output["seeds"]), "gate": output["feasibility_gate_passed"], "path": str(target)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
