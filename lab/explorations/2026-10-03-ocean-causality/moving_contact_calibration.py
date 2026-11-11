"""Calibrate contacts already moving; starting from rest hid shell escape effects."""
import json
from experiment import WORK,protocol
from lab.tools.ocean_contact import ContactOcean
from lab.tools.ocean_cli import write_json,read_json

rows=[]
for speed in (.01,.02,.04,.08):
    for shell in (0,.2,.8):
        w=ContactOcean(protocol(founders=2,nutrient_initial=0,reproduction=False,founder_variation=0))
        a,b=w.bodies.values()
        a.radius,b.radius=.011,.008
        a.elongation=b.elongation=0
        a.position,b.position=[.1,.1],[.119,.1]
        a.velocity,b.velocity=[0,speed],[0,-speed]
        a.angle=0; b.angle=3.141592653589793; b.shell=shell
        for step in range(200):
            for _ in range(4):
                w._move(a,[0,1,0]); w._move(b,[0,1,0]); w.time_us+=w.p.physics_us
            w._predation([0,1])
            if w.totals['predations'] or w.totals['capture_breaks']:break
        rows.append({'speed':speed,'shell':shell,'time_s':w.time_us/1e6,
            'predations':w.totals['predations'],'starts':w.totals['capture_starts'],
            'breaks':w.totals['capture_breaks'],'shell_cost':w.totals['shell_heat']})
write_json(WORK/'calibration/moving-contacts.json',rows)
contrasts=[]
for speed in (.01,.02,.04,.08):
    small=next(r for r in rows if r['speed']==speed and r['shell']==0)
    large=next(r for r in rows if r['speed']==speed and r['shell']==.8)
    if small['predations']>large['predations'] and large['breaks']:
        contrasts.append(speed)
result=read_json(WORK/'calibration/accepted.json')
result.update(moving_contacts=rows,shell_escape_speeds=contrasts,
              distinction='controlled sustained capture versus moving-contact escape; no Core performance selection')
if not contrasts:raise RuntimeError('shell has no demonstrated escape benefit; inspect before formal runs')
write_json(WORK/'calibration/accepted-v2.json',result)
print(json.dumps({'shell_escape_speeds':contrasts,'rows':rows}),flush=True)
