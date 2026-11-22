"""R50 audit v2: normalize serialized microsecond integers. No measurement or acceptance-rule changes; preserve frozen audit.py."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)


def digest(x):
    return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def audit(work):
    cases=read(work/"cases.json"); result=read(work/"analysis-v1.json");cache={};seconds=0;files=0
    assert not (work/"in-flight.json").exists() and not (work/"STOP").exists()
    assert read(work/"status.json")==dict(state="awaiting-analysis",sequences_completed=640)
    configs={}
    for c in cases:
        folder=work/"subjects"/c["key"];before=read(folder/"birth.json.gz")
        assert before["case"]==c
        cfg=before["core"]["config"].copy();assert cfg["prune_weight"]==c["cutoff"]
        cfg.pop("prune_weight")
        if c["origin"] in configs: assert configs[c["origin"]]==cfg
        else: configs[c["origin"]]=cfg
        for phase in ("teaching","probe"):
            r=read(folder/phase/"complete.json")
            for key,h in (("state_file","sha256"),("result_file","result_sha256")):
                p=work/r[key];assert p.resolve().is_relative_to(work.resolve())
                assert hashlib.sha256(p.read_bytes()).hexdigest()==r[h];files+=1
            after=read(work/r["state_file"])
            assert r["before_sha256"]==digest(before) and r["after_sha256"]==digest(after)
            assert int(r["start_us"])==int(before["core"]["time_us"]) and int(r["end_us"])==int(after["core"]["time_us"])
            assert int(r["end_us"])>=int(r["start_us"])
            assert after["core"]["dynamics"]=="threemind.continuous-memory/6.0"
            assert after["events"][:len(before["events"])]==before["events"]
            assert after["mapping"]==before["mapping"] and after["case"]==c
            seconds+=(int(r["end_us"])-int(r["start_us"]))/1e6;before=after
        q=read(folder/"probe/result.json.gz")
        end=1_000_000 if c["course"]=="novelty" else 128_000_000
        assert q["response"]["start_us"]==end+c["delay"]*1_000_000
        assert len(q["baseline"]["frames"])==len(q["response"]["frames"])==20
        cache[c["origin"],c["cutoff"],c["course"],c["delay"],c["history"],c["cue"]]=q
    metrics={}
    for m in result["measurements"]:
        o,p,course,d=(m[k] for k in ("origin","cutoff","course","delay"))
        v=[];counts=[]
        for h in (0,1):
            g=cache[o,p,course,d,h,False]["before"]
            assert g==cache[o,p,course,d,h,True]["before"]
            counts.append(sum({e["source_symbol"],e["target_symbol"]}=={"cue","out"+str(h)} for e in g["edges"]))
        for i in range(20):
            for n in ("out0","out1"):
                for f in ("activation","inhibition","direct","associative"):
                    v.append(sum(hs*qs*(cache[o,p,course,d,h,q]["response"]["frames"][i][n][f]-cache[o,p,course,d,h,q]["baseline"]["frames"][i][n][f]) for h,hs in ((0,-1),(1,1)) for q,qs in ((False,-1),(True,1))))
        norm=math.sqrt(math.fsum(x*x for x in v)/160)
        assert counts==m["edge_counts"] and math.isclose(norm,m["rms"],abs_tol=1e-14)
        assert max(abs(x-y) for x,y in zip(v,m["vector"]))<1e-14
        metrics[o,p,course,d]=(v,norm,counts)
    summed={}
    for o in range(8):
        goals={}
        for p in (.008,.018):
            goals[f"weak_initial:{p}"]=metrics[o,p,"weak",1][2]==[2,2]
            goals[f"weak_absent:{p}"]=metrics[o,p,"weak",30][2]==[0,0]
        goals["weak_response"]=metrics[o,.018,"weak",30][1]<=max(1e-4,.1*metrics[o,.008,"weak",1][1])
        for c in ("massed","spaced","strong","novelty"):
            for d in (1,300):
                a,an,ae=metrics[o,.008,c,d];b,bn,be=metrics[o,.018,c,d]
                err=math.sqrt(math.fsum((y-x)**2 for x,y in zip(a,b))/160)
                cs=math.fsum(x*y for x,y in zip(a,b))/(160*an*bn) if an*bn else 0
                goals[f"preserve:{c}:{d}"]=err<=max(1e-5,.1*an) and (an<=1e-4 or (cs>=.98 and bn>=.9*an)) and all(y>=x for x,y in zip(ae,be))
            if c!="novelty":
                _,n,e=metrics[o,.018,c,300];goals[f"retention:{c}"]=e==[2,2] and n>1e-4
        assert goals==result["details"][o]["goals"]
        for k,v in goals.items():summed[k]=summed.get(k,0)+int(v)
    assert summed==result["counts"]
    decision=all(v>=(8 if k.startswith("preserve:") else 6) for k,v in summed.items() if k!="weak_absent:0.008") and summed["weak_absent:0.018"]>summed["weak_absent:0.008"]
    assert decision==result["adopt_0018"]
    return dict(passed=True,independent_origins=8,sequences=len(cases),complete_boundaries=2*len(cases),checked_files=files,
                internal_seconds=seconds,counts=summed,adopt_0018=decision,method="Independent file, state-chain and arithmetic audit; no Core/analysis imports. Same assistant, not an external replication.")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--work",type=Path,required=True);work=p.parse_args().work
    a=audit(work)
    with (work/"independent-audit-v1.json").open("x",encoding="utf-8") as f:json.dump(a,f,indent=2)
    print(json.dumps(a))
