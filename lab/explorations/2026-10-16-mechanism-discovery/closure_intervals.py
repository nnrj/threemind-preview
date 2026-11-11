"""Describe origin-cluster uncertainty without changing frozen verdicts."""
import argparse
import json
import statistics as st
from pathlib import Path

from closure_analyze import interval
from pilot_m2 import original

p = argparse.ArgumentParser()
p.add_argument('--work', type=Path, required=True)
w = p.parse_args().work
a = json.loads((w/'analysis-v1.json').read_bytes())
out = {'schema':'threemind.closure-descriptive-intervals/1',
       'role':'postprocessing descriptive intervals, no change to frozen endpoints or verdicts',
       'sampling':'10000 origin-cluster bootstrap draws; seed 16102026; no p-value or significance selection',
       'X3':{}, 'X2':{}}
for kind, item in a['X3']['systems'].items():
    os = item['origins']
    out['X3'][kind] = {
        'C1_absolute_contrast':interval([abs(o['C1_contrast']) for o in os]),
        'C2_minimum_target_effect_across_histories':interval([min(h['target'] for h in o['C2']) for o in os]),
        'C3_maximum_interaction_effect_across_histories':interval([max(h['effect'] for h in o['C3']) for o in os]),
        'C4_maximum_environment_effect_across_directions':interval([max(o['C4_effects']) for o in os])}
for delay,c in a['X2']['cohorts'].items():
    out['X2'][delay] = {
        cue:interval([st.mean(abs(h['tests'][cue]['first']) for h in o['histories']) for o in c['origins']])
        for cue in ('weak','strong','joint','none')}
original(w/'descriptive-intervals-v1.json',out)
print(json.dumps({k:{name:{'mean':v['mean'],'ci95':v['ci95']} for name,v in values.items()} for k,values in out['X3'].items()}))
