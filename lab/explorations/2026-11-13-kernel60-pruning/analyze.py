"""Read-only evaluation against the R50 preregistered rules."""
import argparse
import gzip
import json
import math
from pathlib import Path

COURSES = ("weak", "massed", "spaced", "strong", "novelty")
FIELDS = ("activation", "inhibition", "direct", "associative")


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def rms(values):
    return math.sqrt(sum(x*x for x in values)/len(values))


def target(graph, history):
    return [e for e in graph["edges"] if {e["source_symbol"], e["target_symbol"]} == {"cue", f"out{history}"}]


def vector(probe):
    return [b[n][f]-a[n][f] for a,b in zip(probe["baseline"]["frames"], probe["response"]["frames"])
            for n in ("out0", "out1") for f in FIELDS]


def comparison(baseline, candidate):
    a,b = rms(baseline), rms(candidate)
    error = rms([y-x for x,y in zip(baseline,candidate)])
    cosine = sum(x*y for x,y in zip(baseline,candidate))/(len(baseline)*a*b) if a*b else 0.0
    passed = error <= max(1e-5, .1*a) and (a <= 1e-4 or (cosine >= .98 and b >= .9*a))
    return dict(baseline_rms=a, candidate_rms=b, difference_rms=error, cosine=cosine, passed=passed)


def interval(k,n):
    z=1.959963984540054; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]


def analyze(work):
    cases=load(work/"cases.json")
    assert load(work/"status.json")==dict(state="awaiting-analysis",sequences_completed=len(cases))
    data={};costs={str(p):dict(sequences=0,operation_seconds=0.0) for p in (.008,.018)}
    for c in cases:
        folder=work/"subjects"/c["key"]
        data[c["origin"],c["cutoff"],c["course"],c["delay"],c["history"],c["cue"]]=load(folder/"probe/result.json.gz")
        cost=costs[str(c["cutoff"])];cost["sequences"]+=1
        cost["operation_seconds"]+=sum(load(folder/phase/"complete.json")["wall_seconds"] for phase in ("teaching","probe"))
    metrics={};measurements=[]
    for o in range(8):
        for p in (.008,.018):
            for course in COURSES:
                for d in (1,30 if course=="weak" else 300):
                    per_history=[]; edges=[]
                    for h in (0,1):
                        yes=data[o,p,course,d,h,True];no=data[o,p,course,d,h,False]
                        assert yes["before"]==no["before"], "cue and omission differ before probe"
                        per_history.append([a-b for a,b in zip(vector(yes),vector(no))])
                        edges.append(target(yes["before"],h))
                    v=[a-b for a,b in zip(per_history[1],per_history[0])]
                    m=dict(origin=o,cutoff=p,course=course,delay=d,vector=v,rms=rms(v),
                           edge_counts=[len(e) for e in edges],weights=[[e["weight"] for e in es] for es in edges])
                    metrics[o,p,course,d]=m;measurements.append(m)
    details=[]
    for o in range(8):
        goals={}; comparisons={}
        for p in (.008,.018):
            goals[f"weak_initial:{p}"]=metrics[o,p,"weak",1]["edge_counts"]==[2,2]
            goals[f"weak_absent:{p}"]=metrics[o,p,"weak",30]["edge_counts"]==[0,0]
        goals["weak_response"]=metrics[o,.018,"weak",30]["rms"]<=max(1e-4,.1*metrics[o,.008,"weak",1]["rms"])
        for course in COURSES[1:]:
            for d in (1,300):
                a=metrics[o,.008,course,d];b=metrics[o,.018,course,d]
                cmp=comparison(a["vector"],b["vector"])
                cmp["structure_preserved"]=all(y>=x for x,y in zip(a["edge_counts"],b["edge_counts"]))
                comparisons[f"{course}:{d}"]=cmp
                goals[f"preserve:{course}:{d}"]=cmp["passed"] and cmp["structure_preserved"]
            if course!="novelty":
                m=metrics[o,.018,course,300]
                goals[f"retention:{course}"]=m["edge_counts"]==[2,2] and m["rms"]>1e-4
        details.append(dict(origin=o,goals=goals,comparisons=comparisons))
    counts={k:sum(int(row["goals"][k]) for row in details) for k in details[0]["goals"]}
    required={k:(8 if k.startswith("preserve:") else 6) for k in counts if k!="weak_absent:0.008"}
    decisions={k:counts[k]>=n for k,n in required.items()}
    decisions["weak_improved"]=counts["weak_absent:0.018"]>counts["weak_absent:0.008"]
    return dict(schema="threemind.r50-analysis/1",independent_origins=8,sequences=len(cases),
                counts=counts,required=required,decisions=decisions,adopt_0018=all(decisions.values()),
                wilson95={k:interval(v,8) for k,v in counts.items()},details=details,measurements=measurements,costs=costs)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--work",type=Path,required=True);work=p.parse_args().work
    result=analyze(work)
    with (work/"analysis-v1.json").open("x",encoding="utf-8") as f: json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ("counts","decisions","adopt_0018","costs")},indent=2))
