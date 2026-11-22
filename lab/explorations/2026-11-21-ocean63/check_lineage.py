"""Engineering witness for selection by the parent's own event and the matched supply fork."""
import argparse
from pathlib import Path
from apparatus import E37_INPUT,E38_INPUT,read,Enclosure63,enclosure
from baseline import supply_fork
from carrion import new_habitat
from execution import snapshot,checked_metrics,encoded
from lab.tools.ocean_species import save_live_candidate
from registration import exclusive_json


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    world=Enclosure63(read(E37_INPUT)|dict(founders=2,founder_variation=0,flow_m_s=0,flow_variation_m_s=0,
                      mixing_m2_s=0,nutrient_initial=0,reproduction=False))
    world.configure({0:"other",1:"other"},{"other":"core"})
    world.action=lambda i:[0.,0.,0.]
    world.bodies[0].radius*=1.3
    for b in world.bodies.values():
        b.position=[.4,.4]
        b.angle=0.
        b.velocity=[0.,0.]
    chosen=None
    for _ in range(100):
        for ev in world.step():
            if ev["kind"]=="body_engulfed" and ev["method"]=="enclosure":
                chosen=ev
                break
        if chosen:
            break
    assert chosen and chosen["predator"]==0
    save_live_candidate(world,0,out/"parent.tmspecies",name="engineering enclosure witness",
                        evidence=[chosen],source=dict(case="engineering",event_world_us=world.time_us))
    reports=[]
    for key,w in (("historical",enclosure(E38_INPUT,out/"parent.tmspecies")),
                  ("carrion",new_habitat(1,out/"parent.tmspecies"))):
        original=w.research["species_founders"]
        assert w.time_us==0 and original["ids"]==list(range(11))
        assert all(w.seeds[i]==world.seeds[0] and w.bodies[i].generation==0 for i in range(11))
        assert all(w.engines[i].capture_state().to_dict()["time_us"] in (0,"0") for i in range(11))
        assert sum(c=="other" for c in w.cohorts.values())==42
        w.step()
        archive=out/(key+".zip")
        snapshot(w,archive)
        left=supply_fork(archive,1000000)
        right=supply_fork(archive,2000000)
        assert encoded(left.metrics())==encoded(right.metrics())
        assert left.next_food_us-left.time_us==1000000 and right.next_food_us-right.time_us==2000000
        assert all(left.engines[i].capture_state().digest==right.engines[i].capture_state().digest for i in left.bodies)
        assert all(left.seeds[i]==right.seeds[i] for i in left.bodies)
        reports.append(dict(world=key,founders=len(w.bodies),candidate_founders=11,matching_fork=True,
                            energy_residual=checked_metrics(w)["energy_balance_error"]))
    exclusive_json(out/"checks.json",dict(scope="engineering only",own_predation=chosen,worlds=reports))
    print("Parent archive, 11+42 founders and matched supply forks passed",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("directory",type=Path)
    main(p.parse_args().directory)
