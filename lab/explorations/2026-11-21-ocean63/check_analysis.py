"""Readback regression fixtures for event census, exposure, expenditure and follow-up."""
import argparse
import gzip
import json
from pathlib import Path
from apparatus import Primitive63,primitive,Contact63,contact,E38_INPUT,read,Enclosure63
from check_carrion import fixture
from execution import checked_metrics,observe,snapshot,SECOND
from ocean_results import audit_case,feeding_cohorts,evaluate
from registration import exclusive_json
from report import write_report


def fixture_run(out,world,code):
    out.mkdir()
    snapshot(world,out/"initial.zip")
    observe(world,out/"seg-0000",SECOND)
    m=checked_metrics(world)
    s=read(out/"seg-0000/segment.json")
    result=dict(time_us=world.time_us,reason="horizon",members=m["members"],totals=m["totals"],
        alive=sum(b.physical for b in world.bodies.values()),grains=sum(b.grains for b in world.bodies.values()),
        living_body_seconds=s["live_ticks"]*world.p.period_us/SECOND)
    exclusive_json(out/"result.json",result)
    stats=audit_case(code,out)
    assert stats["input_ticks"]==50 and stats["alive"]==2
    return stats


def follow_up(out):
    def m(i,parent,age,g):
        return dict(id=i,parent=parent,birth_us=age*SECOND,generation=g,motor_energy=3.)
    members=[m(1,0,301,1),m(2,1,370,2),m(3,2,431,3),m(4,2,445,3)]
    case=out/"cohort"
    seg=case/"seg-0000"
    seg.mkdir(parents=True)
    with gzip.open(seg/"trajectory.jsonl.gz","wt",encoding="utf8") as f:
        for b in members[:2]:
            f.write(json.dumps(dict(time_us=b["birth_us"]+60*SECOND,members=[b]))+"\n")
    events=[dict(kind="birth",time_us=b["birth_us"],individual=b["id"],parent=b["parent"]) for b in members]
    events+= [dict(kind="nutrient_contact",time_us=390*SECOND,individual=2,energy=8),
              dict(kind="body_engulfed",time_us=439*SECOND,individual=3,predator=99,transferred=2,shell_cost=1),
              dict(kind="consciousness_dead",time_us=450*SECOND,individual=1)]
    f=feeding_cohorts(case,dict(time_us=480*SECOND,members=members),events)
    assert f["individuals"][1]["negative"] and f["individuals"][1]["children_60_to_180"]==1
    assert not f["individuals"][2]["negative"] and "children_60_to_180" not in f["individuals"][2]
    assert f["exclusions"]==dict(censored_before_180=1,died_by_60=1,censored_before_60=1)
    assert f["offspring"]["negative"]["observed"]==1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("directory",type=Path)
    out=parser.parse_args().directory
    out.mkdir(parents=True,exist_ok=False)
    results={}
    results["28"]=fixture_run(out/"primitive",Primitive63(primitive(11,founders=2)),"28")
    results["30"]=fixture_run(out/"contact",Contact63(contact(11,"core")|dict(founders=2)),"30")
    enclosure=Enclosure63(read(E38_INPUT)|dict(founders=2))
    enclosure.configure({i:"other" for i in enclosure.bodies},{"other":"core"})
    results["38"]=fixture_run(out/"enclosure",enclosure,"38")
    results["39C"]=fixture_run(out/"carrion",fixture(),"39C")
    follow_up(out)
    cases={f"world-{g}-{mode}":results["30"] for g in range(2) for mode in ("core","direct","random","random-fast")}
    data=dict(cases=cases,targets=evaluate("30",out,cases))
    assert not data["targets"]["internal_gain"]
    for en in (False,True):
        assert "world-0-random-fast" in write_report("30",data,en)
    exclusive_json(out/"checks.json",dict(types=list(results),events_and_exposure_verified=True,cohort_censoring_verified=True))
    print("Four engineering audits and the follow-up check passed",flush=True)


if __name__=="__main__":
    main()
