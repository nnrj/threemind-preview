"""Read-only screening of recorded motor turns followed by nutrient ingestion.

This discovers candidates, not a causal test of intentional or learned foraging.
It neither advances Core nor creates inputs. Thresholds belong to this observer.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import json
import math
from pathlib import Path

import numpy as np
from pyarrow import compute as pc, ipc, memory_map

from lab.tools.ocean_cli import read_json, write_json

WINDOW_US = 5_000_000


def measure_window(times, raw, actions):
    """Measurements and explicit screening decisions for one pre-ingestion window."""
    if len(times) < 20 or times[-1] - times[0] < 4_900_000:
        return None
    early = times <= times[0] + 1_000_000
    late = times >= times[-1] - 1_000_000
    velocity = raw[:, 5:7] * .03  # Actual velocity relative to measured local water.
    angle = np.arctan2(raw[:, 8], raw[:, 9])
    world_velocity = np.column_stack((velocity[:, 0]*np.cos(angle)-velocity[:, 1]*np.sin(angle),
                                     velocity[:, 0]*np.sin(angle)+velocity[:, 1]*np.cos(angle)))
    before, after = world_velocity[early].mean(axis=0), world_velocity[late].mean(axis=0)
    cross = float(before[0]*after[1]-before[1]*after[0])
    turn = math.degrees(abs(math.atan2(cross, float(before @ after))))
    gradient = np.column_stack((raw[:, 1]-raw[:, 3], raw[:, 2]-raw[:, 4]))
    length = np.linalg.norm(gradient, axis=1)*np.linalg.norm(velocity, axis=1)
    aligned = np.divide((gradient*velocity).sum(axis=1),length,out=np.zeros(len(raw)),where=length>1e-9)
    first, last = float(aligned[early].mean()), float(aligned[late].mean())
    speed = float(np.linalg.norm(velocity,axis=1).mean())
    collision = float(np.max(raw[:, 23]))
    torque = float(np.abs(actions[:, 2]).mean())
    spin_agreement = float((actions[:, 2] * raw[:, 7]).mean())
    return {'turn_degrees':turn, 'alignment_before':first, 'alignment_after':last,
            'mean_water_relative_speed_m_s':speed, 'mean_absolute_turn_command':torque,
            'turn_command_angular_velocity_product':spin_agreement,'max_collision':collision,
            'passes':bool(turn>=30 and last>=.7 and last-first>=.3 and speed>=.001
                          and torque>=.01 and spin_agreement>0 and collision==0)}


class TurningObserver:
    """Optional passive live observer using the same recorded-sample criterion."""
    def __init__(self):
        self.history = {}
        self.last_hit = {}

    def observe(self, row):
        now = row['time_us']
        food = {}
        for event in row['events']:
            if event['kind'] == 'nutrient_contact' and event['energy'] > 0:
                food.setdefault(event['individual'], []).append(event)
        hits = []
        for item in row['inputs']:
            i = item['individual']
            if len(item['raw']) != 26:
                raise ValueError('Ocean /3 physical sensory layout required')
            recent = self.history.setdefault(i, deque())
            while recent and recent[0][0] < now-WINDOW_US:
                recent.popleft()
            if i in food and now-self.last_hit.get(i, -WINDOW_US) >= WINDOW_US and recent:
                t = np.asarray([v[0] for v in recent])
                r = np.asarray([v[1] for v in recent])
                a = np.asarray([v[2] for v in recent])
                value = measure_window(t, r, a)
                if value is not None and value['passes']:
                    hits.append({'individual':i,'time_us':now,'start_us':int(t[0]),
                                 'end_us':int(t[-1]),'nutrient_events':food[i],**value})
                    self.last_hit[i] = now
            recent.append((now, tuple(item['raw']), tuple(item['action'])))
        self.history = {i:v for i,v in self.history.items() if v and now-v[-1][0] <= WINDOW_US}
        return hits


def screen(folder):
    folder=Path(folder)
    if not (folder/'result.json').exists():
        raise ValueError('screen completed recordings only')
    p=read_json(folder/'protocol.json');period=p['period_us']
    events=read_json(folder/'events.json');contacts={}
    for e in events:
        if e['kind']=='nutrient_contact' and e['energy']>0:
            key=(e['individual'],(e['time_us']+period-1)//period*period)
            contacts.setdefault(key,[]).append(e)
    history={};hits=[];last_hit={};windows=0
    for path in sorted((folder/'inputs').glob('*.arrow')):
        with memory_map(str(path),'r') as source:
            reader=ipc.open_file(source)
            for k in range(reader.num_record_batches):
                batch=reader.get_batch(k);nested=batch.column('inputs')
                rows=pc.list_flatten(nested)
                if not len(rows):continue
                lengths=pc.list_value_length(rows.field('raw')).to_numpy()
                if not np.all(lengths==26):raise ValueError('Ocean /3 physical sensory layout required')
                times=pc.take(batch.column('time_us'),pc.list_parent_indices(nested)).to_numpy()
                ids=rows.field('individual').to_numpy()
                raw=pc.list_flatten(rows.field('raw')).to_numpy().reshape(-1,26)
                actions=pc.list_flatten(rows.field('action')).to_numpy().reshape(-1,3)
                for identity in np.unique(ids):
                    identity=int(identity);mask=ids==identity
                    t,r,a=times[mask],raw[mask],actions[mask]
                    new_start=int(t[0])
                    if identity in history:
                        ot,orr,oa=history[identity]
                        t=np.concatenate((ot,t));r=np.concatenate((orr,r));a=np.concatenate((oa,a))
                    for at in np.flatnonzero((r[:,10]>0)&(t>=new_start)):
                        when=int(t[at])
                        if (identity,when) not in contacts or when-last_hit.get(identity,-WINDOW_US)<WINDOW_US:
                            continue
                        # Exclude the ingestion sample: the food has already
                        # disappeared from its sensory concentration field then.
                        start=np.searchsorted(t,when-WINDOW_US)
                        value=measure_window(t[start:at],r[start:at],a[start:at])
                        if value is None:continue
                        windows+=1
                        if value['passes']:
                            hits.append({'individual':identity,'time_us':when,'start_us':int(t[start]),
                                         'end_us':int(t[at-1]),'nutrient_events':contacts[identity,when],**value})
                            last_hit[identity]=when
                    keep=t>=t[-1]-WINDOW_US
                    history[identity]=(t[keep].copy(),r[keep].copy(),a[keep].copy())
                latest=int(times[-1])
                history={i:v for i,v in history.items() if latest-int(v[0][-1])<=WINDOW_US}
    counts=Counter(h['individual'] for h in hits)
    return {'schema':'threemind.ocean-turning-screen/1','case':str(folder.resolve()),
            'scope':'retrospective motor-turn-and-feeding candidates; not causal proof of learned food seeking',
            'window_us':WINDOW_US,'criteria':{'turn_degrees_min':30,'alignment_after_min':.7,
                'alignment_gain_min':.3,'relative_speed_m_s_min':.001,'turn_command_abs_min':.01,
                'turn_command_spin_product_positive':True,'collision_max':0},
            'evaluated_windows':windows,'passing_events':hits,
            'individual_counts':dict(counts),'inputs_changed':False,'core_advanced':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('recording',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=screen(a.recording);write_json(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='passing_events'},ensure_ascii=False))


if __name__=='__main__':main()
