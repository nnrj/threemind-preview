"""Post-run independent trace/state arithmetic. Does not import or instantiate Core."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
import random
import statistics as st
from pathlib import Path
ARMS=("intact","sham","target","matched","restored","shuffled","random-local","walksat")
def read(p): return json.loads(gzip.decompress(p.read_bytes())) if p.suffix==".gz" else json.loads(p.read_bytes())
def digest(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def bad(rows,a):
    result=[]
    for i,c in enumerate(rows):
        values=[int(a[abs(x)-1]) if x>0 else 1-int(a[abs(x)-1]) for x in c]
        if sum(values)==0: result.append(i)
    return result
def checked_trace(problem,r,mapping=None):
    a=r["initial_assignment"][:]
    assert len(a)==problem["n"] and all(type(v) is bool for v in a)
    rng=random.Random(problem["rng_seed"])
    assert a==[bool(rng.getrandbits(1)) for _ in a]
    zero_choices=eligible=queries=nonzero_queries=0
    for index,s in enumerate(r["steps"]):
        previous=bad(problem["clauses"],a)
        ci=rng.choice(previous)
        assert s["step"]==index and s["clause"]==ci
        candidates=[abs(x)-1 for x in problem["clauses"][ci]];rng.shuffle(candidates)
        assert s["candidates"]==candidates
        breaks=[]
        for v in candidates:
            alternate=a[:];alternate[v]=not alternate[v]
            breaks.append(len(set(bad(problem["clauses"],alternate))-set(previous)))
        assert breaks==s["breaks"]
        if "queries" in s:
            assert len(s["queries"])==3
            scores=[]
            for b,q in zip(breaks,s["queries"]):
                assert q["category"]==min(b,3)
                assert q["input"]["channels"]==[[mapping["C"+str(min(b,3))],.8]]
                assert q["input"]["intensity"]==1. and q["input"]["time_us"]==q["start_us"]
                assert q["read_us"]-q["start_us"]==110000
                assert q["score"]==q["ports"][0][0]-q["ports"][1][0]
                scores.append(q["score"]);queries+=1;nonzero_queries+=abs(q["score"])>1e-12
            if rng.random()<.25: selected=rng.randrange(3);noise=True
            else:
                best=max(scores);selected=rng.choice([i for i,x in enumerate(scores) if abs(x-best)<=1e-12]);noise=False
        elif r["arm"]=="walksat":
            if 0 in breaks:selected=rng.choice([i for i,x in enumerate(breaks) if x==0]);noise=False
            elif rng.random()<.5:selected=rng.randrange(3);noise=True
            else:
                smallest=min(breaks);selected=rng.choice([i for i,x in enumerate(breaks) if x==smallest]);noise=False
        else:selected=rng.randrange(3);noise=True
        assert selected==s["selected"] and noise==s["noise"]
        if not noise and min(breaks)==0 and max(breaks)>0:
            eligible+=1;zero_choices+=breaks[selected]==0
        v=candidates[selected];a[v]=not a[v]
        assert a==s["assignment"]
    assert a==r["final_assignment"] and len(r["steps"])==r["flips"] and r["flips"]<=96
    solved=not bad(problem["clauses"],a)
    assert solved==r["solved"] and r["outcome"]==("SAT" if solved else "UNKNOWN")
    if not solved:assert r["flips"]==96
    if mapping:
        assert r["end_us"]-r["start_us"]==r["flips"]*600000
    if problem["kind"]=="unsatisfiable-sentinel":assert not solved
    return dict(eligible=eligible,zero_choices=zero_choices,queries=queries,nonzero_queries=nonzero_queries)

def audit_inputs(previous,result,next_state):
    chain=previous["input_digest"];count=previous["input_count"];background=previous["next_background"]
    current=int(previous["core"]["time_us"])
    def inject(event):
        nonlocal chain,count
        chain=digest([chain,event]);count+=1
    def background_until(until):
        nonlocal background
        while background<=until:
            inject(dict(time_us=background,channels=[[previous["mapping"]["K"],.2]],intensity=1.))
            background+=500000
    for step in result["steps"]:
        for q in step["queries"]:
            assert q["start_us"]==current
            inject(q["input"]);background_until(current+110000);background_until(current+200000)
            current+=200000
    assert current==int(next_state["core"]["time_us"])
    assert chain==next_state["input_digest"] and count==next_state["input_count"]
    assert background==next_state["next_background"]

def audit_teaching(folder,material):
    birth=read(folder/"birth.json.gz");mapping=birth["mapping"]
    assert birth["seed"]==material["seed"]
    for history in ("trained","shuffled"):
        teacher=read(folder/f"{history}-teaching.json.gz");parent=read(folder/f"{history}.json.gz")
        before=dict(birth);before["branch"]=dict(parent_sha256=digest(birth),history=history)
        assert teacher["before_sha256"]==digest(before) and teacher["after_sha256"]==digest(parent)
        chain=birth["input_digest"];count=birth["input_count"];background=birth["next_background"]
        def inject(event):
            nonlocal chain,count
            chain=digest([chain,event]);count+=1
        def advance(until):
            nonlocal background
            while background<=until:
                inject(dict(time_us=background,channels=[[mapping["K"],.2]],intensity=1.));background+=500000
        advance(1000000)
        assert len(teacher["events"])==128
        for i,event in enumerate(teacher["events"]):
            rnd=i//8;cat=(i%8)//2;prefix="U" if i%2 else "C"
            preferred=rnd%4 if history=="shuffled" else 0
            port=("P" if cat==preferred else "N") if prefix=="C" else ("Q" if cat==preferred else "R")
            stimulus=dict(time_us=1000000+i*250000,channels=[[mapping[prefix+str(cat)],.4],[mapping[port],.4]],intensity=1.)
            assert event["stimulus"]==stimulus and event["example"]==material["examples"][cat][rnd]
            assert event["category"]==cat and event["prefix"]==prefix and event["teacher_preference"]==(cat==preferred)
            inject(stimulus);advance(stimulus["time_us"]+250000)
        advance(34000000)
        assert chain==parent["input_digest"] and count==parent["input_count"] and background==parent["next_background"]

def audit_matching(folder):
    parent=read(folder/"trained.json.gz");core=parent["core"];selection=read(folder/"selection.json")
    assert parent["seed"] in range(2011100,2011108)
    config=core["config"];nodes={n["channel"]:n["id"] for n in core["nodes"]}
    edges={(e["source"],e["target"]):e for e in core["edges"]}
    events=read(folder/"trained-teaching.json.gz")["events"]
    assert len(events)==128 and int(core["time_us"])==34000000
    for group,prefix,ports in (("target","C",("P","N")),("matched","U",("Q","R"))):
        assert len(selection["groups"][group])==4
        for cat,row in enumerate(selection["groups"][group]):
            pair=[nodes[parent["mapping"][prefix+str(cat)]],nodes[parent["mapping"][ports[int(cat!=0)]]]]
            assert row["edge"]==pair and row["category"]==cat
            edge=edges[tuple(pair)]
            dt=(int(core["time_us"])-int(edge["state_us"]))/1e6
            assert config["consolidation_mode"]=="adaptive-half-life" and config["plasticity"]
            low=config["memory_half_life_min_s"];rate=config["memory_half_life_decay_rate"];h=edge["half_life"]
            end=max(low,h-rate*dt);fall=min(dt,max(0,h-low)/rate) if rate else 0
            integral=(math.log(h/end)/rate if fall>0 else 0)+(dt-fall)/end
            weight=edge["weight"]*math.exp(-math.log(2)*integral)
            assert math.isclose(weight,row["weight"],rel_tol=1e-12,abs_tol=1e-14)
            degrees=[[sum(e["source"]==v for e in core["edges"]),sum(e["target"]==v for e in core["edges"])] for v in pair]
            assert degrees==row["degrees"]
            activity=[e["teaching_activity"] for e in events if e["prefix"]==prefix and e["category"]==cat]
            assert len(activity)==16
            assert all(abs(st.mean(v[i] for v in activity)-row["teaching_activity"][i])<1e-12 for i in (0,1))
    a,b=(selection["groups"][g] for g in ("target","matched"))
    dw=max(abs(x["weight"]-y["weight"]) for x,y in zip(a,b))
    da=max(abs(x["teaching_activity"][i]-y["teaching_activity"][i]) for x,y in zip(a,b) for i in (0,1))
    degree_match=all(x["degrees"]==y["degrees"] for x,y in zip(a,b))
    assert dw==selection["residuals"]["maximum_weight_difference"]
    assert da==selection["residuals"]["maximum_activity_difference"]
    assert degree_match==selection["residuals"]["degrees_equal"]
    assert selection["valid"]==(degree_match and dw<=.05 and da<=.05)
    return selection

def interval(xs,seed=9011):
    rng=random.Random(seed);n=len(xs)
    boots=sorted(st.mean(rng.choices(xs,k=n)) for _ in range(10000))
    return [boots[249],boots[9749]]
def analyze(work):
    existing=work/"analysis-v1.json"
    if existing.exists():
        stored=read(existing)
        print(json.dumps(dict(state="already-analyzed; no replay performed",analysis=str(existing),G1=stored["G1"],G2=stored["G2"])))
        return
    assert read(work/"status.json")["state"]=="awaiting-analysis"
    assert not (work/"STOP").exists() and not (work/"in-flight.json").exists()
    origins=[];checked=0;whole_states=0;comparisons=0;graph_samples=[];clocks=[];input_counts=[]
    for o in range(8):
        folder=work/f"origins/o{o}";material=read(work/f"material/o{o}.json")
        assert read(folder/"done.json")["arms"]==list(ARMS)
        audit_teaching(folder,material)
        per={};traces={};states={}
        for arm in ARMS:
            af=folder/arm
            assert read(af/"done.json")["tests"]==26
            previous=read(af/"whole-000.json.gz") if (af/"whole-000.json.gz").exists() else None
            records=[];traces[arm]=[];states[arm]=[]
            for i,p in enumerate(material["tests"]):
                r=read(af/f"result-{i:03d}.json.gz")
                assert r["problem_id"]==p["id"] and r["arm"]==arm and r["origin"]==o
                counts=checked_trace(p,r,previous["mapping"] if previous else None)
                if previous:
                    next_state=read(af/f"whole-{i+1:03d}.json.gz")
                    assert r["before_sha256"]==digest(previous) and r["after_sha256"]==digest(next_state)
                    assert int(previous["core"]["time_us"])==r["start_us"]
                    assert int(next_state["core"]["time_us"])==r["end_us"]
                    assert previous["readout"]==next_state["readout"] and previous["mapping"]==next_state["mapping"]
                    audit_inputs(previous,r,next_state)
                    graph_samples.append(dict(origin=o,arm=arm,problem=i,time_us=int(next_state["core"]["time_us"]),
                                              nodes=len(next_state["core"]["nodes"]),edges=len(next_state["core"]["edges"])))
                    clocks.append(int(next_state["core"]["time_us"]));input_counts.append(next_state["input_count"])
                    previous=next_state;whole_states+=1
                    normalized=dict(next_state);normalized.pop("branch")
                    states[arm].append(digest(normalized))
                records.append(dict(problem=p["id"],kind=p["kind"],n=p["n"],solved=r["solved"],initial_satisfied=not bad(p["clauses"],r["initial_assignment"]),
                                    flips=r["flips"],wall_seconds=r["wall_seconds"],**counts))
                traces[arm].append(r["steps"]);checked+=1
            sat=[r for r in records if r["kind"]=="satisfiable"]
            policy=[r for r in sat]
            eligible=sum(r["eligible"] for r in policy)
            per[arm]=dict(solved=sum(r["solved"] for r in sat),denominator=len(sat),
                          initial_satisfied=sum(r["initial_satisfied"] for r in sat),new_solutions=sum(r["solved"] and not r["initial_satisfied"] for r in sat),success=st.mean(r["solved"] for r in sat),mean_flips=st.mean(r["flips"] for r in sat),
                          capped_cost=st.mean(r["flips"] if r["solved"] else 96 for r in sat),
                          wall_seconds=sum(r["wall_seconds"] for r in sat),
                          eligible=eligible,zero_choices=sum(r["zero_choices"] for r in policy),
                          zero_rate=sum(r["zero_choices"] for r in policy)/eligible if eligible else None,
                          queries=sum(r["queries"] for r in records),
                          nonzero_queries=sum(r["nonzero_queries"] for r in records),
                          by_problem=records,
                          sizes={str(n):dict(solved=sum(r["solved"] for r in sat if r["n"]==n),
                                            total=sum(r["n"]==n for r in sat)) for n in (12,20)})
        exact=(traces["intact"]==traces["sham"]==traces["restored"] and
               states["intact"]==states["sham"]==states["restored"])
        assert exact
        comparisons+=52
        selection=audit_matching(folder)
        origins.append(dict(origin=o,arms=per,matching=selection["valid"],
                            matching_residuals=selection["residuals"],sham_restore_exact=exact))
    aggregate={}
    for arm in ARMS:
        rows=[o["arms"][arm] for o in origins]
        aggregate[arm]=dict(solved=sum(x["solved"] for x in rows),denominator=sum(x["denominator"] for x in rows),
                            initial_satisfied=sum(x["initial_satisfied"] for x in rows),new_solutions=sum(x["new_solutions"] for x in rows),success=st.mean(x["success"] for x in rows),mean_capped_flips=st.mean(x["capped_cost"] for x in rows),
                            total_solve_seconds=sum(x["wall_seconds"] for x in rows),
                            mean_zero_rate=st.mean(x["zero_rate"] for x in rows if x["zero_rate"] is not None) if any(x["zero_rate"] is not None for x in rows) else None,
                            eligible=sum(x["eligible"] for x in rows),queries=sum(x["queries"] for x in rows),
                            nonzero_queries=sum(x["nonzero_queries"] for x in rows),
                            sizes={str(n):dict(solved=sum(x["sizes"][str(n)]["solved"] for x in rows),
                                              total=sum(x["sizes"][str(n)]["total"] for x in rows)) for n in (12,20)})
    gain=[o["arms"]["intact"]["success"]-o["arms"]["shuffled"]["success"] for o in origins]
    drop=[(o["arms"]["sham"]["zero_rate"]-o["arms"]["target"]["zero_rate"]) if o["arms"]["sham"]["zero_rate"] is not None and o["arms"]["target"]["zero_rate"] is not None else None for o in origins]
    matched=[(o["arms"]["sham"]["zero_rate"]-o["arms"]["matched"]["zero_rate"]) if o["arms"]["sham"]["zero_rate"] is not None and o["arms"]["matched"]["zero_rate"] is not None else None for o in origins]
    g1=st.mean(gain)>=.10 and sum(x>0 for x in gain)>=6
    g2valid=all(o["matching"] and all(o["arms"][a]["eligible"]>=20 for a in ("sham","target","matched")) for o in origins)
    g2=g2valid and st.mean(drop)>=.20 and abs(st.mean(matched))<=.05
    train_seconds=sum(read(work/f"origins/o{o}/{h}-teaching.json.gz")["wall_seconds"]
                      for o in range(8) for h in ("trained","shuffled"))
    result=dict(schema="threemind.sat-analysis/1",independent_origins=8,origins=origins,aggregate=aggregate,
                G1=dict(verdict="PASS" if g1 else "FAIL",planning_threshold=.10,minimum_positive_sources=6,mean_difference=st.mean(gain),
                        source_differences=gain,positive_sources=sum(x>0 for x in gain),bootstrap_95=interval(gain)),
                G2=dict(verdict=("PASS" if g2 else "FAIL") if g2valid else "INVALID",
                        target_threshold=.20,matched_tolerance=.05,mean_target_drop=st.mean(drop) if all(v is not None for v in drop) else None,target_bootstrap_95=interval(drop) if all(v is not None for v in drop) else None,
                        mean_matched_drop=st.mean(matched) if all(v is not None for v in matched) else None,source_target_drops=drop,
                        eligible_and_matching_valid=g2valid),
                audit=dict(recomputed_complete_teaching_histories=16,independently_checked_matching_origins=8,recomputed_input_digest_transitions=whole_states,checked_trajectories=checked,verified_whole_state_transitions=whole_states,
                           exact_sham_restore_problem_comparisons=comparisons,invalid_sat_claims=0,
                           unsat_sentinels=8*2*8,ordinary_rollbacks=0),
                descriptive_graph_samples=graph_samples,
                costs=dict(training_wall_seconds=train_seconds,resources=read(work/"resource-summary.json"),
                           dpll_test_reference_seconds=sum(p["oracle"]["wall_seconds"] for o in range(8) for p in read(work/f"material/o{o}.json")["tests"]),
                           maximum_saved_nodes=max(s["nodes"] for s in graph_samples),
                           maximum_saved_edges=max(s["edges"] for s in graph_samples),
                           final_saved_graphs=[s for s in graph_samples if s["problem"]==25],
                           maximum_subject_internal_us=max(clocks),maximum_subject_input_count=max(input_counts),
                           current_original_bytes=sum(p.stat().st_size for p in work.rglob("*") if p.is_file() and p.name!="analysis-v1.json")))
    target=work/"analysis-v1.json"
    raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode()
    if target.exists():assert target.read_bytes()==raw
    else:target.write_bytes(raw)
    print(json.dumps(dict(G1=result["G1"],G2=result["G2"],aggregate=aggregate,audit=result["audit"],
                         costs=result["costs"]),ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--work",type=Path,required=True);a=p.parse_args();analyze(a.work)

