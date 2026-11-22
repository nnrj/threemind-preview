"""Check saved population contrasts with stdlib arithmetic and binomial sums.

This reads derived population tables, never creates subjects, and supplements
the separate raw-state audit. It is an internal arithmetic check.
"""
import argparse
import csv
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def near(a,b):
    assert abs(a-b) <= 1e-12, (a,b)


def main(layout=False):
    work = ROOT / (".work/artificial-selection63-layout-20261117" if layout else
                   ".work/artificial-selection63-20261117")
    source = work / "analysis-v1"
    result = json.loads((source / "analysis.json").read_text("utf8"))
    assert json.loads((source / "audit.json").read_text("utf8"))["passed"]
    with (source / "population-scores.csv").open(encoding="utf8",newline="") as stream:
        rows = list(csv.DictReader(stream))
    checked=[]
    for t in result["tests"]:
        values=[]
        for seed in range(1117100,1117116):
            population=[x for x in rows if int(x["seed"])==seed]
            arm=t["arm"]
            if layout:
                row=next(x for x in population if x["arm"]==arm)
                difference=float(row["closed_region1"])-float(row["replay_region1"])
                difference *= 1 if arm=="region1" else -1
            else:
                g=t["generation"]
                row=next(x for x in population if x["arm"]==arm and int(x["generation"])==g)
                if t["hypothesis"]=="H2":
                    comparator=next(x for x in population if x["arm"]=="random" and int(x["generation"])==g)
                    other=float(comparator[arm])
                elif t["hypothesis"]=="H3":
                    comparator=next(x for x in population if x["arm"]==arm and int(x["generation"])==g-1)
                    other=float(comparator[arm])
                else:
                    other=float(row["blank_region1"])
                    if arm=="region0":other=1-other
                difference=float(row[arm])-other
            values.append(difference)
        for actual,saved in zip(values,t["values"]):near(actual,saved)
        mean=math.fsum(values)/len(values)
        positive=sum(x>1e-12 for x in values)
        negative=sum(x < -1e-12 for x in values)
        n=positive+negative
        p=sum(math.comb(n,k) for k in range(positive,n+1))/2**n if n else 1.
        near(mean,t["mean"])
        near(p,t["p_raw"])
        assert (positive,negative,16-n)==(t["positive"],t["negative"],t["ties"])
        checked.append({"mean":mean,"positive":positive,"negative":negative,"ties":16-n,"p_raw":p})
    indices=sorted(range(len(checked)),key=lambda i:checked[i]["p_raw"])
    for rank,i in enumerate(indices):
        corrected=min(1.,max((len(indices)-j)*checked[indices[j]]["p_raw"] for j in range(rank+1)))
        near(corrected,result["tests"][i]["p_holm"])
        assert (checked[i]["mean"]>=.01 and corrected<=.05)==result["tests"][i]["passed"]
        checked[i]["p_holm"]=corrected
    receipt={"passed":True,"population_count":16,"contrast_count":len(checked),
             "method":"population CSV arithmetic; exact binomial sums; Holm family verification", "contrasts":checked}
    path=source/"statistics-check.json"
    payload=json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if path.exists():assert path.read_text("utf8")==payload
    else:path.write_text(payload,encoding="utf8")
    print(json.dumps({"passed":True,"contrasts":len(checked),"file":str(path)}))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--layout",action="store_true")
    main(parser.parse_args().layout)
