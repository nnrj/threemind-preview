"""Read closed ocean records and independently recount events, exposure and registered outcomes."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from statistics import mean
from zipfile import ZipFile

import pyarrow as pa
from pyarrow import ipc
from apparatus import read, sha
from execution import SECOND, encoded, restore
from registration import directory, exclusive_json


def raw_world(path):
    with ZipFile(path) as z:
        spec=json.loads(z.read("world.json"))
    state=spec["context"]
    while "bodies" not in state:
        state=next(state[k] for k in ("material","enclosure","group","community","world") if k in state)
    return {b["id"]:b for b in state["bodies"]},spec["protocol"],spec["time_us"]


def lines(path):
    with gzip.open(path,"rt",encoding="utf8") as stream:
        for line in stream:
            yield json.loads(line)


def ratio(n,d):
    return n/d if d else None


def source_snapshot(case,segment_index):
    return case/("initial.zip" if segment_index==0 else f"seg-{segment_index-1:04d}/end.zip")


def audit_segment(seg,previous,include_capture=False):
    meta=read(seg/"segment.json")
    bodies,protocol,t=raw_world(previous)
    assert t==meta["start_us"] and sha(seg/"end.zip")==meta["snapshot_sha256"]
    live={i for i,b in bodies.items() if b["physical"]}
    steps=live_ticks=0
    events=[]
    for part in sorted((seg/"inputs").glob("*.arrow")):
        with pa.memory_map(str(part),"r") as stream:
            arr=ipc.open_file(stream)
            for k in range(arr.num_record_batches):
                batch=arr.get_batch(k)
                for now,evs in zip(batch.column("time_us").to_pylist(),batch.column("events").to_pylist()):
                    t+=protocol["period_us"]
                    assert t==now,"missing or duplicate input tick"
                    observed=json.loads(evs)
                    for e in observed:
                        if e["kind"]=="birth":
                            assert e["individual"] not in live
                            live.add(e["individual"])
                        elif e["kind"] in ("body_engulfed","consciousness_dead","body_age_limit"):
                            live.discard(e["individual"])
                    events.extend(observed)
                    steps+=1
                    live_ticks+=len(live)
    assert events==list(lines(seg/"events.jsonl.gz"))
    assert t==meta["end_us"] and live_ticks==meta["live_ticks"],"exposure/clock disagreement"
    end,_,now=raw_world(seg/"end.zip")
    assert live=={i for i,b in end.items() if b["physical"]} and t==now
    assert sum(e["kind"]=="nutrient_contact" for e in events)==sum(b["grains"] for b in end.values())-sum(b["grains"] for b in bodies.values())
    assert len(end)-len(bodies)==sum(e["kind"]=="birth" for e in events)
    assert sum(b["grains"] for b in end.values())==meta["grains"]
    prey=[]
    if include_capture and any(e["kind"]=="body_engulfed" for e in events):
        # The historical detector logged the energy received, but not the reserve just
        # before a victim was eaten. Read it during a deterministic replay on a copy.
        w=restore(previous)
        ordinary=w._consume_body_energy
        def observe_transfer(hunter,victim):
            reserve=victim.storage
            out=ordinary(hunter,victim)
            prey.append(dict(time_us=w.time_us,predator=hunter.id,prey=victim.id,
                            prey_reserve=reserve,transferred=out["transferred"]))
            return out
        w._consume_body_energy=observe_transfer
        replay=[]
        while w.time_us<t:
            replay.extend(w.step())
        assert replay==events and encoded(w.capture())==encoded(restore(seg/"end.zip").capture())
    return events,live_ticks,steps,prey


def summarize_events(events,body_seconds):
    counts=Counter(e["kind"] for e in events)
    meals=[e for e in events if e["kind"]=="carrion_meal"]
    kills=[e for e in events if e["kind"]=="body_engulfed"]
    food=[e for e in events if e["kind"]=="nutrient_contact"]
    return dict(grains=len(food),living_body_minutes=body_seconds/60,grain_rate=ratio(60*len(food),body_seconds),
        predations=len(kills),predation_rate=ratio(60*len(kills),body_seconds),births=counts["birth"],
        carrion_meals=len(meals),carrion_rate=ratio(60*len(meals),body_seconds),
        deaths=counts["consciousness_dead"],grain_energy=sum(e["energy"] for e in food),
        live_prey_energy=sum(e["transferred"] for e in kills),carrion_energy=sum(e["received"] for e in meals),
        losing_carrion_meals=sum(e["net_after_shell"]<0 for e in meals))


def generation_counts(members):
    groups=defaultdict(list)
    for m in members:
        groups[m["generation"]].append(m)
    return {g:dict(individuals=len(rows),alive=sum(m["physical"] for m in rows),
                   reproduced=sum(m["children"]>0 for m in rows),earliest_birth_us=min(m["birth_us"] for m in rows))
            for g,rows in sorted(groups.items())}


def feeding_cohorts(case,result,events):
    # Births are on one-second reproductive ticks. Sample the motor ledger at the
    # tick ending age 60, including the final state when it is itself that tick.
    rows={m["id"]:m for m in result["members"] if m["birth_us"]>300*SECOND}
    first60=defaultdict(float)
    babies=defaultdict(list)
    died={}
    for e in events:
        kind=e["kind"]
        if kind in ("body_engulfed","consciousness_dead","body_age_limit"):
            died.setdefault(e["individual"],e["time_us"])
        if kind=="birth":
            babies[e["parent"]].append(e["time_us"])
        if kind not in ("nutrient_contact","body_engulfed","carrion_meal"):
            continue
        i=e["predator"] if kind=="body_engulfed" else e["individual"]
        if i not in rows or e["time_us"]>rows[i]["birth_us"]+60*SECOND:
            continue
        if kind=="body_engulfed":
            first60[i]+=e["transferred"]-e.get("shell_cost",0.)
        elif kind=="carrion_meal":
            first60[i]+=e["net_after_shell"]
        else:
            first60[i]+=e["energy"]
    motors={}
    if rows:
        def sample(t,members):
            for m in members:
                if m["id"] in rows and t==m["birth_us"]+60*SECOND:
                    motors[m["id"]]=m["motor_energy"]
        for part in sorted(case.glob("seg-*/trajectory.jsonl.gz")):
            for t in lines(part):
                sample(t["time_us"],t["members"])
        sample(result["time_us"],result["members"])
    phenotypes={}
    losses=defaultdict(list)
    excluded=Counter()
    for i,m in rows.items():
        birth=m["birth_us"]
        if i in died and died[i]<=birth+60*SECOND:
            excluded["died_by_60"]+=1
            continue
        if result["time_us"]<birth+60*SECOND:
            excluded["censored_before_60"]+=1
            continue
        assert i in motors
        balance=first60[i]-motors[i]
        losing=balance<0
        record=dict(generation=m["generation"],parent=m["parent"],balance=balance,negative=losing)
        if i in died or result["time_us"]>=birth+180*SECOND:
            record["children_60_to_180"]=sum(birth+60*SECOND<t<=birth+180*SECOND for t in babies[i])
            losses[losing].append(record["children_60_to_180"])
        else:
            excluded["censored_before_180"]+=1
        phenotypes[i]=record
    def counts(predicate):
        group=[v["negative"] for v in phenotypes.values() if predicate(v)]
        return dict(negative=sum(group),observed=len(group),proportion=ratio(sum(group),len(group)))
    inherited={label:counts(lambda v:v["parent"] in phenotypes and phenotypes[v["parent"]]["negative"]==condition)
               for label,condition in (("negative",True),("nonnegative",False))}
    early=counts(lambda v:v["generation"] in (1,2))
    late=counts(lambda v:3<=v["generation"]<=5)
    repro={label:dict(observed=len(losses[v]),mean_children=mean(losses[v]) if losses[v] else None)
           for label,v in (("negative",True),("nonnegative",False))}
    def test(a,b):
        return None if a is None or b is None else a<b
    return dict(individuals=phenotypes,exclusions=dict(excluded),reproduction=repro,offspring=inherited,
        per_generation={g:counts(lambda x:x["generation"]==g) for g in sorted({x["generation"] for x in rows.values()})},
        generations_1_2=early,generations_3_5=late,
        prediction_tests=dict(lower_reproduction=test(repro["negative"]["mean_children"],repro["nonnegative"]["mean_children"]),
            offspring_similarity=test(inherited["nonnegative"]["proportion"],inherited["negative"]["proportion"]),
            later_reduction=test(late["proportion"],early["proportion"])))


def audit_case(code,case):
    result=read(case/"result.json")
    initial,protocol,start=raw_world(case/"initial.zip")
    all_events=[]
    ticks=steps=0
    prey=[]
    intervals={}
    for index,meta_path in enumerate(sorted(case.glob("seg-*/segment.json"))):
        meta=read(meta_path)
        ev,l,n,captures=audit_segment(meta_path.parent,source_snapshot(case,index),
                                      include_capture=code=="38" and case.name!="parent-search")
        all_events.extend(ev)
        ticks+=l
        steps+=n
        prey.extend(captures)
        if (meta["end_us"]%SECOND==0 and meta["end_us"]//SECOND in (300,600,900,1500,2400)
                or meta["end_us"]==result["time_us"]):
            intervals[str(meta["end_us"])]=summarize_events(all_events,ticks*protocol["period_us"]/SECOND)
    total_s=ticks*protocol["period_us"]/SECOND
    stats=summarize_events(all_events,total_s)
    assert stats["grains"]==result["grains"]-sum(b["grains"] for b in initial.values())
    assert abs(total_s-result["living_body_seconds"])<1e-8
    registered=dict(case=case.name,time_us=result["time_us"],initial_us=start,endpoint=result["reason"],
        founders_or_branch_population=len(initial),alive=result["alive"],cumulative_grains=result["grains"],
        maximum_generation=max(m["generation"] for m in result["members"]),deferred_births=result["totals"]["deferred_births"],
        generations=generation_counts(result["members"]),input_ticks=steps,**stats,intervals=intervals)
    if code in ("38","39C"):
        registered["feeding_events"]=[{k:v for k,v in e.items() if k not in ("energy","traits")} for e in all_events
                                      if e["kind"] in ("body_engulfed","carrion_meal")]
        registered["candidate_live_predations"]=[e for e in registered["feeding_events"] if e["kind"]=="body_engulfed"
                    and result["members"][e["predator"]].get("cohort")=="candidate"]
    if prey:
        registered["prey_reserve_and_transfer"]=prey
    if code=="39C":
        registered["maintenance_and_movement"]={m["id"]:{k:m[k] for k in ("body_maintenance","motor_energy","body_unserved")} for m in result["members"]}
        if start==300*SECOND:
            registered["offspring"]=feeding_cohorts(case,result,all_events)
    return registered


def exceeds(values):
    return None if not values or any(v is None for v in values) else all(v>0 for v in values)


def difference(a,b):
    return None if a is None or b is None else a-b


def evaluate(code,work,cases):
    if code=="30":
        random=[]
        direct=[]
        for g in range(2):
            core=cases[f"world-{g}-core"]
            for mode in ("random","random-fast"):
                other=cases[f"world-{g}-{mode}"]
                random.extend(difference(core[k],other[k]) for k in ("grains","grain_rate"))
            direct.append(difference(core["grain_rate"],cases[f"world-{g}-direct"]["grain_rate"]))
        return dict(full_exceeds_random=exceeds(random),differences_random=random,internal_gain=exceeds(direct),differences_direct=direct)
    if code=="28":
        gate=read(work/"stage-gate.json")
        diffs=[difference(cases[f"common-{g}-inherited"]["grain_rate"],cases[f"common-{g}-blank"]["grain_rate"])
               if f"common-{g}-inherited" in cases else None for g in range(3)]
        return dict(ecological_cycle=gate["passed"],eligible_worlds=gate["qualified"],energy_shortage=gate["shortage"],
                    common_garden_differences=diffs,consistent_inherited_gain=exceeds(diffs))
    if code=="38":
        fork=read(work/"supply-fork.json")
        tests={}
        if fork["applied"]:
            for cutoff in (600,900):
                # Extinct communities have zero further meals or births.
                def at(key):
                    r=cases[key]
                    return r["intervals"].get(str(cutoff*SECOND),r["intervals"][str(r["time_us"])] if r["endpoint"]=="extinct" and r["time_us"]<=cutoff*SECOND else None)
                a,b=at("original"),at("reduced")
                if a is not None and b is not None:
                    tests[cutoff]=dict(original=a,reduced=b,increased_predation=b["predations"]>a["predations"])
        by_branch={}
        natural=set()
        for key in ("original","reduced") if fork["applied"] else ("common",):
            events=(cases["common"]["candidate_live_predations"] if key!="common" else [])+cases[key]["candidate_live_predations"]
            members={m["id"]:m for m in read(work/"cases"/key/"result.json")["members"]}
            hunters={e["predator"] for e in events}
            natural.update(i for i in hunters if members[i]["generation"]>0)
            by_branch[key]=dict(hunters=sorted(hunters),predations=len(events),meets=len(hunters)>=2 and len(events)>=3,
                natural_offspring_hunters=sorted(i for i in hunters if members[i]["generation"]>0))
        return dict(parent_selected=fork["eligible"],fork_applied=fork["applied"],supply=tests,lineage=by_branch,
                    qualifying_lineage=any(r["meets"] for r in by_branch.values()) if fork["eligible"] else None)
    tests={}
    for mode in ("original","reduced"):
        preds=[cases.get(f"world-{g}-{mode}",{}).get("offspring",{}).get("prediction_tests",{}) for g in range(2)]
        checks=[p.get(k) for p in preds for k in ("lower_reproduction","offspring_similarity","later_reduction")]
        tests[mode]=None if any(v is None for v in checks) else all(checks)
    effects={}
    for outcome in ("carrion_rate","predation_rate"):
        diffs=[difference(cases.get(f"world-{g}-reduced",{}).get(outcome),cases.get(f"world-{g}-original",{}).get(outcome))
               for g in range(2)]
        effects[outcome]=dict(differences=diffs,increased_in_both=exceeds(diffs))
    return dict(energy_loss_predictions=tests,supply_effects=effects,world_seeds=[382101,382102])


def analyze(code):
    work=directory(code)
    closed=read(work/"calculation-complete.json")
    out=work/"analysis"
    out.mkdir(exist_ok=True)
    cases={}
    for case,digest in closed["results"].items():
        path=work/"cases"/case
        assert sha(path/"result.json")==digest
        cases[case]=audit_case(code,path)
    findings=dict(code=code,cases=cases,targets=evaluate(code,work,cases),independent_event_and_exposure_check=True)
    exclusive_json(out/"findings.json",findings)
    return findings


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("code",choices=("28","30","38","39C"))
    analyze(p.parse_args().code)
