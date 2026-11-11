"""Supplementary outcomes remain separate from the original fixed comparisons."""

import json

from analyze import analyze_case
from experiment import HERE, WORK, latest
from followup import CASES

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_evolution_cli import load_population


def coverage(root):
    receipt = read_json(root / "control-receipt.json")
    initial = read_json(root / "initial/manifest.json")["context"]
    donor_ids = [b["id"] for b in initial["bodies"] if b["physical"]]
    old = {b["id"]: b for b in initial["bodies"]}
    final = latest(root)
    result = read_json(final / "result.json")
    members = {m["id"]: m for m in result["members"]}
    outcome = {
        "initial_living_ids": donor_ids,
        "initial_donor_food": sum(members[i]["grains"] - old[i]["grains"] for i in donor_ids),
        "initial_donor_survivors": sum(members[i]["physical"] for i in donor_ids),
        "newborn_food": sum(m["grains"] for i, m in members.items() if i not in old),
        "newborn_survivors": sum(m["physical"] for i, m in members.items() if i not in old),
    }
    if receipt.get("operation") == "silence":
        world = load_population(final / "final")
        live_edges = masked = 0
        for i in donor_ids:
            if not world.bodies[i].physical:
                continue
            state = world.engines[i].capture_state().to_dict()
            edges = {(e["source"], e["target"]) for e in state["edges"]}
            live_edges += len(edges)
            masked += len(edges & set(map(tuple, state["silenced_edges"])))
        outcome |= {
            "initial_masked_edges": sum(map(len, receipt["edges"].values())),
            "final_live_donor_edges": live_edges,
            "final_live_donor_masked_edges": masked,
            "final_live_donor_unmasked_edges": live_edges - masked,
            "scope": "endpoint coverage among still-living initial donors; newborn masks reset by normal birth/1",
        }
    return outcome


def main():
    rows = []
    for key in CASES:
        root = WORK / "cases" / key
        if not (root / "result.json").exists():
            continue
        row, _ = analyze_case(root)
        if key.startswith("control-"):
            row["intervention_scope"] = coverage(root)
        rows.append(row)
    lookup = {r["case"]: r for r in rows}
    differences = []
    for label, left, right in (
        ("independent confirmation", "confirm-3-core", "confirm-3-random"),
        ("persistent history retained minus erased", "control-0-inherited", "control-0-naive"),
        ("existing communication retained minus silenced", "control-0-sham", "control-0-silence"),
    ):
        if left not in lookup or right not in lookup:
            continue
        a, b = lookup[left], lookup[right]
        differences.append(
            {
                "contrast": label,
                "left": left,
                "right": right,
                **{name: a[name] - b[name] for name in ("food", "living_body_s", "physical_survivors", "core_cost")},
                "body_cost": a["totals_delta"]["body_heat"] - b["totals_delta"]["body_heat"],
                "both_complete": all(
                    x["status"] == "extinct"
                    or (
                        x["status"] == "horizon_paused"
                        and x["duration_s"] == (1800 if left.startswith("confirm") else 300)
                    )
                    for x in (a, b)
                ),
            }
        )
    answer = {
        "worlds": rows,
        "differences": differences,
        "unexecuted": [k for k in CASES if k not in lookup],
        "incomplete": [
            r["case"]
            for r in rows
            if r["status"] != "extinct"
            and not (
                r["status"] == "horizon_paused"
                and r["duration_s"] == (1800 if r["case"].startswith("confirm-") else 300)
            )
        ],
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "active_copies_and_births": sum(r["active_copies_and_births"] for r in rows),
        "interpretation": "one further independent pair and, conditionally, one source population's paired interventions",
    }
    write_json(WORK / "analysis/followup-summary.json", answer)
    for lang in ("zh", "en"):
        from make_report import table

        zh = lang == "zh"
        title = "## 补充：独立确认与因果对照" if zh else "## Supplement: independent confirmation and causal controls"
        grid = [
            [
                r["case"],
                r["status"],
                r["duration_s"],
                r["food"],
                f"{r['food_per_body_s']:.5f}",
                f"{r['living_body_s']:.1f}",
                r["physical_survivors"],
                f"{r['core_cost']:.1f}",
                f"{r['totals_delta']['body_heat']:.1f}",
            ]
            for r in rows
        ]
        headers = (
            ["世界", "状态", "模拟秒", "摄食", "颗/活体秒", "活体秒", "存活", "Core耗能", "身体耗能"]
            if zh
            else ["World", "Status", "Seconds", "Food", "Food/body-s", "Living body-s", "Survivors", "Core cost", "Body cost"]
        )
        text = title + "\n\n" + table(headers, grid) + "\n\n"
        for d in differences:
            if zh:
                names = {
                    "independent confirmation": "独立确认：意识减随机",
                    "persistent history retained minus erased": "经历保留减清除",
                    "existing communication retained minus silenced": "连接通信保留减静默",
                }
                text += f"- {names[d['contrast']]}：摄食{d['food']:+d}颗；累计活体时间{d['living_body_s']:+.1f}秒；存活数{d['physical_survivors']:+d}；Core耗能{d['core_cost']:+.1f}；身体耗能{d['body_cost']:+.1f}。\n"
            else:
                text += f"- {d['contrast']}: food {d['food']:+d}; living body-s {d['living_body_s']:+.1f}; survivors {d['physical_survivors']:+d}; Core cost {d['core_cost']:+.1f}; body cost {d['body_cost']:+.1f}.\n"
        text += (
            "\n"
            + (
                "这些对照使用一个固定来源世界，不能把后代数量当独立复制。静默保留既有活动和在途信号，未来新边与后代仍可通信；新环境经历对照同时重置两边的活动、时钟和初始能量。后续耗能差也是干预的后果，必须与运动及存活一起解释，不能仅从节省能量后的生存改善认定学会了更好的觅食。"
                if zh
                else "These interventions use one fixed source world; offspring are not independent replicates. Silencing preserves existing activity and in-flight signals while permitting new edges and unmasked births. Common-garden controls reset both arms' activity, clocks and initial energy. Later energy differences are intervention consequences and must be interpreted alongside behavior and survival, not equated with better learned foraging."
            )
            + "\n"
        )
        donor_rows = []
        for row in rows:
            scope = row.get("intervention_scope")
            if scope:
                donor_rows.append(
                    [
                        row["case"],
                        len(scope["initial_living_ids"]),
                        scope["initial_donor_food"],
                        scope["initial_donor_survivors"],
                        int(row["totals_delta"]["births"]),
                        scope["newborn_food"],
                        scope["newborn_survivors"],
                    ]
                )
        if donor_rows:
            text += "\n" + table(
                ["世界", "起始活体", "原个体摄食", "原个体存活", "新出生", "后代摄食", "后代存活"]
                if zh
                else ["World", "Initial bodies", "Original intake", "Original survivors", "Births", "Offspring intake", "Offspring survivors"],
                donor_rows,
            ) + "\n"
        if "control-0-silence" in lookup:
            scope = lookup["control-0-silence"]["intervention_scope"]
            text += (
                "\n"
                + (
                    f"静默开始时覆盖{scope['initial_masked_edges']}条连接；结束时原存活来源仍有{scope['final_live_donor_masked_edges']}条连接被静默，另有{scope['final_live_donor_unmasked_edges']}条未被静默。原个体存活{scope['initial_donor_survivors']}个，新增后代存活{scope['newborn_survivors']}个；后代按正常出生规则清空研究用屏蔽。"
                    if zh
                    else f"Initially masked {scope['initial_masked_edges']} edges. At the endpoint, surviving original donors have {scope['final_live_donor_masked_edges']} masked and {scope['final_live_donor_unmasked_edges']} unmasked edges. Original survivors: {scope['initial_donor_survivors']}; newborn survivors: {scope['newborn_survivors']}. Normal births reset research masks."
                )
                + "\n"
            )
        if answer["unexecuted"]:
            text += "\n" + ("未执行：" if zh else "Unexecuted: ") + ", ".join(answer["unexecuted"]) + "\n"
        if answer["incomplete"]:
            text += "\n" + ("未完成：" if zh else "Incomplete: ") + ", ".join(answer["incomplete"]) + "\n"
        p = HERE / f"followup-report.{lang}.md"
        with p.open("x", encoding="utf-8") as f:
            f.write(text)
    print(json.dumps({k: v for k, v in answer.items() if k != "worlds"}, indent=2))


if __name__ == "__main__":
    main()
