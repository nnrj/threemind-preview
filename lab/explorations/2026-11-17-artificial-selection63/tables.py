"""Render transparent aggregate tables after both registered analyses finish."""
import csv
import json
import numpy as np

import analyze
import layout
import ring as r
import study


def read_csv(path):
    with path.open(encoding="utf8", newline="") as stream:
        return list(csv.DictReader(stream))


def table(headers, rows):
    return "\n".join(["| "+" | ".join(headers)+" |", "| "+" | ".join("---" for _ in headers)+" |"]+
                     ["| "+" | ".join(str(v) for v in row)+" |" for row in rows])


def percent(x):
    return f"{x*100:.3f}"


def interval(pair):
    return f"[{pair[0]*100:.3f}, {pair[1]*100:.3f}]"


def main():
    source = study.DEFAULT_WORK / "analysis-v1"
    result = r.read(source / "analysis.json")
    extra = r.read(layout.WORK / "analysis-v1/analysis.json")
    assert r.read(source / "audit.json")["passed"]
    assert r.read(layout.WORK / "analysis-v1/audit.json")["passed"]
    populations = read_csv(source / "population-scores.csv")
    retention = read_csv(source / "retention.csv")
    stages = read_csv(source / "stages.csv")
    summary = {"main": result, "layout": extra}
    # Small derived aggregates are tracked; detailed observations stay in ignored storage.
    (r.HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    analyze.write_csv(r.HERE / "population-summary.csv", populations)
    for lang in ("zh", "en"):
        zh = lang == "zh"
        blocks = ["# "+("AS63预定统计与汇总表" if zh else "AS63 registered statistics and summary tables")]
        blocks += [("以下比例均来自未参与选择的保留测试；百分比与百分点保留三位小数，统计计算使用原始值。"
                    if zh else "All proportions use held-out assessments. Percentages and percentage points are displayed to three decimals; calculations use unrounded values.")]
        headers = (["目标","方向/代际","均值差（百分点）","均值差95%区间","正/负/平","原始P","Holm P","达到要求"]
                   if zh else ["Target","Direction/transition","Mean difference (pp)","95% CI (pp)","+/−/tie","Raw P","Holm P","Criterion met"])
        rows = []
        for t in result["tests"]:
            comparison = t["arm"]
            if t["hypothesis"] == "H3":
                comparison += f" G{t['generation']-1}→G{t['generation']}"
            rows.append([t["hypothesis"], comparison, percent(t["mean"]), interval(t["ci95"]),
                         f"{t['positive']}/{t['negative']}/{t['ties']}", f"{t['p_raw']:.8g}", f"{t['p_holm']:.8g}",
                         ("是" if t["passed"] else "否") if zh else str(t["passed"])])
        blocks += ["## "+("八项主比较" if zh else "Eight primary contrasts"), table(headers, rows)]
        rows = []
        for arm in ("region0","region1"):
            for generation in (1,2):
                group = [x for x in retention if x["arm"] == arm and int(x["offspring_generation"]) == generation]
                qualifying = sum(int(x["qualifying_selected_parents"]) for x in group)
                eligible = sum(int(x["eligible_children"]) for x in group)
                retained = sum(int(x["retained_children"]) for x in group)
                no_parent = sum(int(x["qualifying_selected_parents"]) == 0 for x in group)
                passed = sum(x["passed"] == "True" for x in group)
                rows.append([arm, f"G{generation-1}→G{generation}", qualifying, eligible, retained, no_parent, f"{passed}/16"])
        blocks += ["## "+("H1：已有倾向的亲子保留" if zh else "H1: Retention from parents with the target tendency"),
            table(["方向","传代","达标入选亲代数","其全部子代数","达标子代数","无达标亲代的群体","满足本项的群体"]
                  if zh else ["Direction","Transition","Qualifying selected parents","All their offspring","Retained offspring","Populations without qualifying parent","Populations meeting this cell"],
                  rows),
            (f"同时满足两个方向、两次传代的群体：{result['H1']['passed_populations']}/16；群体比例精确95%区间{interval(result['H1']['ci95'])}%。预定可行性门槛为4/16。"
             if zh else f"Populations meeting both directions across both transmissions: {result['H1']['passed_populations']}/16; exact 95% CI {interval(result['H1']['ci95'])}%. Registered feasibility threshold: 4/16.")]
        generation_rows = []
        for direction in ("region0","region1"):
            for arm in (direction,"random"):
                for generation in range(3):
                    t = next(x for x in result["trajectories"] if x["direction"] == direction and x["arm"] == arm and x["generation"] == generation)
                    generation_rows.append([direction,arm,f"G{generation}",percent(t["mean"]),interval(t["ci95"])])
        blocks += ["## "+("各代全体候选的目标区域停留比例" if zh else "Target occupancy of all candidates by generation"),
            table(["计分目标","选择条件","世代","平均比例（%）","95%区间（%）"] if zh else
                  ["Scored target","Selection condition","Generation","Mean (%)","95% CI (%)"],generation_rows)]
        inherited = []
        for arm in ("region0","region1","random"):
            group = [x for x in populations if x["arm"] == arm and int(x["generation"]) == 2]
            for target in ("region0","region1"):
                regular = np.mean([float(x[target]) for x in group])
                blank = np.mean([float(x["blank_region1"]) for x in group])
                blank = 1-blank if target == "region0" else blank
                inherited.append([arm,target,percent(regular),percent(blank),percent(regular-blank)])
        blocks += ["## "+("G2继承对照" if zh else "G2 inheritance control"),
            table(["选择条件","计分目标","正常继承（%）","空白内核（%）","差值（百分点）"] if zh else
                  ["Selection condition","Scored target","Inherited (%)","Uninherited (%)","Difference (pp)"],inherited)]
        motion = []
        for seed in r.SEEDS:
            for label, prefix in (("G0","g0/"),("region0 G2","region0/g2/"),("region1 G2","region1/g2/"),("random G2","random/g2/")):
                group = [x for x in stages if int(x["seed"]) == seed and x["key"].startswith(prefix)
                         and "/held-" in x["key"] and "-uninherited/" not in x["key"]]
                assert len(group) == 16
                motion.append([seed,label,percent(np.mean([float(x["region1"]) for x in group])),
                    f"{np.mean([float(x['travel_distance']) for x in group]):.4f}",
                    f"{np.mean([float(x['net_displacement']) for x in group]):.4f}",
                    percent(np.mean([int(x["zero_motion_steps"])/600 for x in group]))])
        blocks += ["## "+("运动过程的描述性汇总" if zh else "Descriptive movement summaries"),
            ("行程和有符号净位移以环周长为单位。静止步要求速度和控制量的绝对值均不超过1e−12；此表不增加成功或失败标准。"
             if zh else "Travel and signed net displacement are measured in ring circumferences. A stationary step has both speed and command magnitude ≤ 1e−12. This description adds no success or failure criterion."),
            table(["群体种子","条件","区域1比例（%）","平均行程","平均有符号净位移","静止步（%）"] if zh else
                  ["Population seed","Condition","Region1 (%)","Mean travel","Mean signed displacement","Stationary steps (%)"],motion)]
        rows = [[t["arm"], percent(t["mean"]),interval(t["ci95"]),
                 f"{t['positive']}/{t['negative']}/{t['ties']}", f"{t['p_raw']:.8g}",f"{t['p_holm']:.8g}",
                 ("是" if t["passed"] else "否") if zh else str(t["passed"])] for t in extra["tests"]]
        blocks += ["## "+("AS63-02：交换布局后的实时控制−旧动作重放" if zh else "AS63-02: Closed loop minus action replay in the swapped layout"),
            table(["方向","均值差（百分点）","95%区间","正/负/平","原始P","Holm P","达到要求"] if zh else
                  ["Direction","Mean difference (pp)","95% CI","+/−/tie","Raw P","Holm P","Criterion met"],rows)]
        layout_rows = []
        for arm in ("region0","region1","random"):
            group = [x for x in extra["population_scores"] if x["arm"] == arm]
            for direction in ("region0","region1"):
                values = [np.mean([x[key] for x in group]) for key in ("baseline_region1","closed_region1","replay_region1")]
                if direction == "region0":values=[1-x for x in values]
                layout_rows.append([arm,direction]+[percent(x) for x in values])
        blocks += [table(["选择条件","计分目标","原布局实时（%）","交换布局实时（%）","交换布局重放（%）"] if zh else
                        ["Selection condition","Scored target","Original closed loop (%)","Swapped closed loop (%)","Swapped replay (%)"],layout_rows)]
        (r.HERE / f"tables.{lang}.md").write_text("\n\n".join(blocks)+"\n",encoding="utf8")
    print("Aggregate tables and summary saved")


if __name__ == "__main__":
    main()
