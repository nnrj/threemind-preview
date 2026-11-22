"""Locate recorded direct-history differences without restoring a subject."""
from pathlib import Path
import argparse
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from compare import read, s


def main(work):
    old = work.parent/'stimulus61-v1'
    changed = 0; absent = 0; present_max = 0.; peak = None
    for c in read(work/'cases.json'):
        a = {p['time_us']:p for p in read(work/'cases'/c['key']/'trajectory.json.gz')['points']}
        b = {p['time_us']:p for p in read(old/'cases'/c['key']/'trajectory.json.gz')['points']}
        for t in a.keys() & b.keys():
            an = {n['channel']:n for n in a[t]['nodes']}; bn = {n['channel']:n for n in b[t]['nodes']}
            for channel in an.keys() | bn.keys():
                delta = abs(an.get(channel,{}).get('direct',0.)-bn.get(channel,{}).get('direct',0.))
                if delta:
                    changed += 1
                    if channel not in an or channel not in bn: absent += 1
                    else: present_max = max(present_max, delta)
                    if peak is None or delta > peak['difference']:
                        peak = {'case':c['key'],'time_us':t,'channel':channel,'difference':delta,
                                'new_node_present':channel in an,'old_node_present':channel in bn}
    aa, bb = read(work/'analysis.json'),read(old/'analysis.json')
    converged = lambda d:{p['key'] for p in d['patterns'] if p['detected']}
    result = {'different_samples':changed,'samples_with_absent_node':absent,
              'both_nodes_present_max_difference':present_max,'maximum':peak,
              'same_converged_conditions':converged(aa)==converged(bb),
              'converged':len(converged(aa)),
              'censored_conditions':[p['key'] for p in aa['patterns'] if p['censored']],
              'Core_engines_loaded':0,'simulation_advanced':False}
    s.base.original(work/'direct-history-audit.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    main(p.parse_args().work.resolve())
