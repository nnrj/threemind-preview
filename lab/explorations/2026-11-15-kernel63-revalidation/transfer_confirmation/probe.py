"""Declared two-step causal diagnostic; fixed output projection, no teacher labels."""
import copy
import time

from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent / 'transfer'), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]

import transfer_rig as g
import spec
import pilot_m2 as m


def probe(rig, cue, *, observed=False, restore_mid=False, pause_mid=False):
    start = rig.time
    initial = len(rig.rows)
    values = spec.cue_values(cue)
    rig.tick(start, values)
    events = {start+500_000: {'K': .2}, start+1_000_000: {'K': .2}, start+1_500_000: {'K': .2}}
    first_action = 0
    for stamp in range(start+1000, start+1_500_001, 1000):
        rig.tick(stamp, events.get(stamp), frequent=observed and (stamp-start) % 50_000 == 0)
        if stamp == start+110_000:
            first_action = int(rig.actuator > 1e-4)-int(rig.actuator < -1e-4)
            rig.body['gate'] = first_action
            events[start+250_000] = {'X' if first_action > 0 else 'Z' if first_action < 0 else 'N': .2}
        if stamp == start+360_000:
            step = int(rig.actuator > 1e-4)-int(rig.actuator < -1e-4)
            rig.body['gate'] = max(-1, min(1, rig.body['gate']+step))
        rig.rows.append({'time_us': stamp, 'response': rig.actuator, 'body': copy.deepcopy(rig.body)})
        if stamp == start+500_000:
            if restore_mid:
                other = g.Rig.restore(rig.save()); rig.__dict__.update(other.__dict__)
            if pause_mid:
                before = rig.save(); time.sleep(.03)
                assert before == rig.save(), 'wall-clock mutation'
    rows = rig.rows[initial:]
    def integral(lo, hi):
        return sum(r['response']*.001 for r in rows if lo <= r['time_us']-start <= hi)
    return {'start_us': start, 'cue': cue, 'cue_values': values,
            'first': rows[109]['response'], 'choice': first_action, 'final_gate': rig.body['gate'],
            'early_integral': integral(100_000, 300_000), 'late_integral': integral(500_000, 1_500_000),
            'trace_count': len(rows), 'final_sha256': m.digest(rig.save())}
