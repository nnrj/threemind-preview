"""Cost calibration and exact-continuation checks before scientific founders."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import mujoco

from physical import defaults
from session import SurvivalSession


def protocol(seed=270001):
    return dict(schema='threemind.granular-survival/1',world=defaults()|{'seed':seed},
        core=dict(seed=seed,energy_simulation_enabled=True,energy_starvation_damage_enabled=True,
            energy_initial_reserve=100000.,energy_capacity=100000.),
        food_interval_us=1000000,energy_per_grain=0.)


def main(output,seconds):
    output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    rows=[]
    with SurvivalSession(protocol()) as s:
        for second in range(1,seconds+1):
            while s.engine.time_us<second*1000000 and s.engine.life!='dead':
                s.step()
            rows.append(s.metrics())
            if second%5==0: print(json.dumps({'second':second,'cost':rows[-1]['core']['energy'],
                'nodes':rows[-1]['core']['nodes'],'edges':rows[-1]['core']['edges'],
                'wall_seconds':time.monotonic()-start}),flush=True)
        image=s.engine.capture_state()
        context=s.context()
        traces=[]
        for _ in range(10): s.step(traces.append)
        with SurvivalSession(protocol(),image=image,context=context) as restored:
            other=[]
            for _ in range(10): restored.step(other.append)
            assert traces==other,'restored measured input/actions differ'
            assert s.engine.capture_state().digest==restored.engine.capture_state().digest,'restored Core differs'
            assert s.context()==restored.context(),'restored physics/counters differ'
        # Read-only observation/capture did not itself advance or alter Core.
        previous=s.engine.capture_state().digest
        s.metrics(); s.context(); s.metrics()
        assert previous==s.engine.capture_state().digest
        result=dict(scope='engineering calibration, not a learning candidate',protocol=protocol(),
            mujoco=mujoco.__version__,xml_hash=s.world.xml_hash,rows=rows,
            exact_restore=True,read_only=True,wall_seconds=time.monotonic()-start)
        (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'completed':True,'wall_seconds':result['wall_seconds']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--seconds',type=int,default=30)
    a=p.parse_args()
    main(a.output,a.seconds)
