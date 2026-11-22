"""Dated post-hoc explanation and input-pair audit; no simulation or new scoring."""
import argparse
import gzip
import json
from pathlib import Path


def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)


def explain(work):
    cases=read(work/"cases.json");a=read(work/"analysis-v1.json");data={};checked=0
    for c in cases:
        folder=work/"subjects"/c["key"]
        end=read(folder/"probe/whole.json.gz")
        key=(c["origin"],c["course"],c["delay"],c["history"],c["cue"])
        if key in data:
            assert data[key]["events"]==end["events"]
            assert data[key]["core"]["time_us"]==end["core"]["time_us"]
            assert data[key]["mapping"]==end["mapping"]
            checked+=1
        else:data[key]=end
        times={"weak":[127],"massed":list(range(120,128)),"spaced":[16,17,19,23,31,47,79,127],"strong":[127]}
        scale=c["profile"]["scale"];phase=c["profile"]["phase_us"];mapping=end["mapping"]
        teach=[e for e in end["events"] if e["role"] in ("teaching","prior-pair","new-pair")]
        if c["course"]=="novelty":
            ts=[100000+phase,100000+phase+c["profile"]["novelty_offset_us"]]
            outputs=[1-c["history"],c["history"]];dose=.4
        else:
            ts=[round(t*1e6)+phase for t in times[c["course"]]]
            outputs=[c["history"]]*len(ts);dose=.08 if c["course"]=="weak" else .4
        assert [e["time_us"] for e in teach]==ts
        for e,h in zip(teach,outputs):
            assert dict(e["channels"])=={mapping["cue"]:dose*scale,mapping[f"out{h}"]:dose*scale}
            assert e["intensity"]==(2.0 if c["course"]=="strong" else 1.0)
    novelty=[]
    for o in range(8):
        row=dict(origin=o)
        for cutoff in (.008,.018):
            row[str(cutoff)]=[]
            for h in (0,1):
                p=read(work/f"subjects/o{o}/p{cutoff}/novelty/d300/h{h}/q0/probe/result.json.gz")
                edges=[dict(source=e["source_symbol"],target=e["target_symbol"],weight=e["weight"]) for e in p["before"]["edges"]]
                row[str(cutoff)].append(edges)
        novelty.append(row)
    result=dict(kind="post-hoc explanation; frozen scientific criteria unchanged",input_pairs_exact=checked,
                declared_curricula_verified=len(cases),novelty_connections=novelty)
    # The historical expression rule is descriptive only in R50.
    aux=[]
    import math
    for o in range(8):
        for cutoff in (.008,.018):
            for course in ("massed","spaced","strong"):
                es=[next(m for m in a["measurements"] if m["origin"]==o and m["cutoff"]==cutoff and m["course"]==course and m["delay"]==d) for d in (1,300)]
                u,v=es;cs=sum(x*y for x,y in zip(u["vector"],v["vector"]))/160/u["rms"]/v["rms"] if u["rms"]*v["rms"] else 0
                aux.append(dict(origin=o,cutoff=cutoff,course=course,early_rms=u["rms"],late_rms=v["rms"],cosine=cs,
                     passed=u["rms"]>1e-4 and v["rms"]>1e-4 and v["rms"]>=.1*u["rms"] and cs>=.8))
    result["auxiliary_R47_expression"]=aux
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--work",type=Path,required=True);w=p.parse_args().work
    out=explain(w)
    with (w/"retrospective-diagnostics-v1.json").open("x",encoding="utf-8") as f:json.dump(out,f,indent=2)
    print(json.dumps({k:out[k] for k in ("input_pairs_exact","declared_curricula_verified")}))
