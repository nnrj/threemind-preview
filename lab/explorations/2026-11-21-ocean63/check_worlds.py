"""Small, nonformal, whole-world branch and funded-birth witnesses."""
from datetime import datetime,timezone
from apparatus import *
from execution import snapshot,restore,encoded,checked_metrics


def main():
    out = ROOT/".work"/("ocean63-witness-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    out.mkdir()
    rows=[]
    for k,w in (("primitive",Primitive63(primitive(11,founders=2))),
                ("contact",Contact63(contact(11,"core")|{"founders":2})),
                ("direct",Contact63(contact(11,"direct")|{"founders":2})),
                ("enclosure",enclosure(E37_INPUT))):
        for _ in range(4):
            w.step()
        p=out/(k+".zip")
        snapshot(w,p)
        v = restore(p)
        assert encoded(v.step())==encoded(w.step())
        assert encoded(v.capture())==encoded(w.capture())
        rows.append(dict(world=k,whole_restore=True,next_step_equal=True,balance=checked_metrics(w)["energy_balance_error"]))
    # Force the life stage and funding in the apparatus witness, never in the formal worlds.
    for cls, config in ((Primitive63,primitive(11)),(Contact63,contact(11,"core"))):
        p=config | dict(founders=1,reproduction_age_us=0,reproduction_cooldown_us=20000,reproduction_interval_us=20000,
                        nutrient_capacity=0,nutrient_initial=0)
        w=cls(p)
        grant=8000.
        w.bodies[0].storage+=grant
        w.totals["initial_core"]+=grant
        for _ in range(2):
            w.step()
        assert len(w.engines)>1
        child=w.engines[1]
        assert child.dynamics==KERNEL and child.metrics()["energy"]["initial_total"]==0
        rows.append(dict(world=cls.__name__,child_kernel=child.dynamics,birth=True,balance=checked_metrics(w)["energy_balance_error"]))
    print(json.dumps(rows,indent=2),flush=True)
    (out/"checks.json").write_text(json.dumps(rows,indent=2),encoding="utf8")


if __name__=="__main__":
    main()
