"""Contact mechanics calibration without a consciousness winning criterion."""
import json
import math
from experiment import WORK, protocol
from lab.tools.ocean_contact import ContactOcean
from lab.tools.ocean_cli import write_json, read_json

rows=[]
for angle in (0,math.pi/2,math.pi):
    for amplitude in (.25,.5,1.):
        for shell in (0,.2,.8):
            w=ContactOcean(protocol(founders=2,nutrient_initial=0,reproduction=False,founder_variation=0))
            a,b=w.bodies.values()
            a.radius,b.radius=.011,.008
            a.elongation=b.elongation=0
            a.position,b.position=[.1,.1],[.119,.1]
            a.angle=0; b.angle=angle; b.shell=shell
            for step in range(200):
                for _ in range(4):
                    w._move(a,[0,amplitude,0]); w._move(b,[0,amplitude,0])
                    w.time_us+=w.p.physics_us
                w._predation([0,1])
                if w.totals['predations'] or w.totals['capture_breaks']:break
            rows.append({'angle':angle,'amplitude':amplitude,'shell':shell,'time_s':w.time_us/1e6,
                         'predations':w.totals['predations'],'starts':w.totals['capture_starts'],
                         'breaks':w.totals['capture_breaks'],'shell_cost':w.totals['shell_heat']})
write_json(WORK/'calibration/glancing-contacts.json',rows)
r=read_json(WORK/'calibration/continuation/result.json')
answer={'status':r['status'],'free_motion':{k:r['totals'][k] for k in ('capture_starts','capture_breaks','predations')},
        'calibration_world_complete':r['time_us']==60000000,'controlled':read_json(WORK/'calibration/controlled.json'),
        'glancing':rows,'failed_recorder_attempt_preserved':True,
        'notes':'progress receipt attempted exclusive re-create; fixed recorder and continued original state, no mechanics changed'}
write_json(WORK/'calibration/accepted.json',answer)
print(json.dumps({'free_motion':answer['free_motion'],'glancing':rows}),flush=True)
