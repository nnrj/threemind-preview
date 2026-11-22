"""Legacy ecological comparisons, conducted on new 6.3 cohorts in the original habitats."""
import argparse
import os
import time
from _threemind_native import _threemind_native
from apparatus import *
from execution import run_case, restore, SECOND
from registration import directory, exclusive_json
from lab.tools.study_lock import worker_lock
from lab.tools.ocean_species import save_live_candidate
from threemind_lab.storage_files import atomic_json


def validate_freeze(code):
    work = directory(code)
    if read(work/"registration.json")["pending"] != 0:
        raise RuntimeError("incomplete registration")
    for path, digest in read(work/"frozen.json").items():
        candidate = Path(_threemind_native.__file__) if path == "_threemind_native" else ROOT/path
        if sha(candidate) != digest:
            raise RuntimeError(f"applied source differs from registration: {path}")
    return work


def run30():
    for g in range(2):
        for mode in ("core","direct","random","random-fast"):
            run_case("30",f"world-{g}-{mode}",lambda:Contact63(contact(g,mode)),600)


def living_parents(w, n, *, different_families):
    alive = [i for i,b in w.bodies.items() if b.physical and w.engines[i].life=="active"]
    by_age = sorted(alive,key=lambda i:(-w.bodies[i].generation,i))
    if different_families:
        roots = {}
        for i in by_age:
            founder = i
            while w.bodies[founder].parent is not None:
                founder = w.bodies[founder].parent
            roots.setdefault(founder,i)
        by_age = [roots[k] for k in sorted(roots)]
    return [by_age[j%len(by_age)] for j in range(n)] if by_age else []


def run28():
    code = "28"
    work = directory(code)
    phase1 = {}
    for g in range(3):
        modes = ["core","passive","random"]
        for mode in modes[g:]+modes[:g]:
            result = run_case(code,f"ecology-{g}-{mode}",lambda:Primitive63(primitive(g,mode)),900)
            if mode=="core":
                phase1[g] = result
    qualified = [g for g,r in phase1.items() if r["reason"]=="horizon" and r["grains"] and r["totals"]["births"]]
    shortage = any(m["core_energy"]["unserved_total"]>0 or
                   m["core_energy"]["reserve"] < primitive(g)["initial_energy"]*.5
                   for g,r in phase1.items() for m in r["members"])
    passed = len(qualified)>=2 and shortage
    exclusive_json(work/"stage-gate.json",dict(passed=passed,qualified=qualified,shortage=shortage))
    latest = phase1.copy()
    if passed:
        for g in range(3):
            w = restore(work/phase1[g]["end_snapshot"])
            donors = living_parents(w,8,different_families=False)
            exclusive_json(work/f"enclosure-parents-{g}.json",dict(donors=donors,source=phase1[g]["end_snapshot"]))
            if donors:
                images = [w.engines[i].capture_state() for i in donors]
                p = primitive(g,predation=True,mutation_sigma=.15,environment_seed=282100+g)
                latest[g] = run_case(code,f"enclosure-{g}",lambda:Primitive63(p,founder_images=images),900)
    for g,r in latest.items():
        w = restore(work/r["end_snapshot"])
        donors = living_parents(w,4,different_families=True)
        exclusive_json(work/f"common-parents-{g}.json",dict(donors=donors,source=r["end_snapshot"]))
        for mode in ("inherited","blank") if donors else ():
            p = primitive(g,founders=4,reproduction=False,environment_seed=283100+g)
            images = [w.engines[i].capture_state() for i in donors]
            if mode=="blank":
                images = [create_engine(im.to_dict()["config"],kernel_id=KERNEL,backend="native").capture_state()
                          for im in images]
            run_case(code,f"common-{g}-{mode}",lambda:Primitive63(p,founder_images=images),300)


def supply_fork(snapshot_path, interval):
    w = restore(snapshot_path)
    prior = w.p.nutrient_interval_us
    w.p = type(w.p).model_validate(w.p.model_dump(by_alias=True) | {"nutrient_interval_us":interval})
    w.next_food_us = w.time_us+interval
    w.research["supply_change"] = dict(time_us=w.time_us,old_interval_us=prior,new_interval_us=interval)
    return w


def run38():
    code = "38"
    work = directory(code)
    candidate = work/"selected-parent.tmspecies"
    def select(w,events):
        kills = [e for e in events if e["kind"]=="body_engulfed" and e.get("method")=="enclosure"]
        if not kills:
            return False
        ev = min(kills,key=lambda e:(e["time_us"],e["predator"]))
        save_live_candidate(w,ev["predator"],candidate,name="OCEAN63-38 selected parent",
                            evidence=[ev|{"summary":"Parent's own complete enclosure of a living individual"}],
                            source=dict(case="parent-search",criterion="own observed natural predation",
                                        event_world_us=ev["time_us"]))
        return True
    search = run_case(code,"parent-search",lambda:enclosure(E37_INPUT),1200,stop_event=select)
    assert candidate.is_file() == (search["reason"]=="qualified_parent")
    source = candidate if candidate.exists() else None
    common = run_case(code,"common",lambda:enclosure(E38_INPUT,source),300)
    if common["time_us"] != 300*SECOND or not common["alive"]:
        exclusive_json(work/"supply-fork.json",dict(applied=False,common=common["end_snapshot"],eligible=bool(source)))
        return
    exclusive_json(work/"supply-fork.json",dict(applied=True,common=common["end_snapshot"],eligible=bool(source)))
    for label,interval in (("original",SECOND),("reduced",2*SECOND)):
        run_case(code,label,lambda:supply_fork(work/common["end_snapshot"],interval),900,milestones=[600])


def execute(codes):
    import psutil
    for code in codes:
        work = validate_freeze(code)
        if (work/"calculation-complete.json").exists():
            continue
        with worker_lock(work.parent):
            atomic_json(work/"worker.json",dict(pid=os.getpid(),created=psutil.Process().create_time(),
                                                started=time.time(),code=code))
            if code=="39C":
                from extend import run_long
                run_long()
            else:
                {"30":run30,"28":run28,"38":run38}[code]()
            results = sorted((work/"cases").glob("*/result.json"))
            exclusive_json(work/"calculation-complete.json",dict(code=code,results={p.parent.name:sha(p) for p in results}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("codes",nargs="+",choices=["30","28","38","39C"])
    execute(p.parse_args().codes)
