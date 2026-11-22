"""Read-only supplemental comparisons. Does not create or advance an engine."""
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import study_resources as x
s=x.s
from threemind_kernels.local62_config import Local62Config
from threemind_kernels.mechanisms import ShortTermState


def run(work):
    assert s.read(work/'final-audit.json')['passed']
    pairs=(('stable-g0-r8','stable-g0-r8-exc0'),('stable-g0-r8-inh0','stable-g0-r8-sources0'))
    comparisons=[]
    for left,right in pairs:
        for block in (0,1):
            for cue in ('train','AB','DB'):
                a=x.state_at(x.folder(work,left,block,cue),'final').to_dict()
                b=x.state_at(x.folder(work,right,block,cue),'final').to_dict()
                config_differences={k:[a['config'].get(k),b['config'].get(k)] for k in a['config'] if a['config'].get(k)!=b['config'].get(k)}
                assert set(config_differences)=={'activation_send_threshold'}
                for value in (a,b):
                    for k in ('config','definition','definition_hash'):value.pop(k,None)
                comparisons.append({'a':left,'b':right,'block':block,'cue':cue,
                    'config_differences':config_differences,'complete_state_equal_except_config_identity':a==b})
    cfg=Local62Config();operators=[]
    for tau in (.8,.08):
        setting=replace(cfg,stp_recovery_tau_s=tau).short_term();state=ShortTermState(time_us=0)
        for i in range(1,1001):state,released=state.release(i*cfg.propagation_interval_us,setting)
        operators.append({'recovery_tau_s':tau,'release_interval_us':cfg.propagation_interval_us,'utilization':cfg.stp_utilization,
            'released_fraction_after_1000_fixed_interval_operations':released,'pre_resource_amount_for_threshold_0_0004':.0004/released})
    output={'status':'retrospective read-only interpretation; no change to primary scores',
        'activation_threshold_comparisons':comparisons,'resource_operator_example':operators,
        'apparatus_scope':{'native_reference_comparisons':24,'python_only_isolated_conditions':3,
            'clarification':'The three historical-inhibition conditions use the same Python research engine for both backend arguments; they are not Rust comparisons.'}}
    s.write(work/'mechanism-notes.json',output)
    print(json.dumps({'activation_gate_changes_state':any(not q['complete_state_equal_except_config_identity'] for q in comparisons),
        'compared_pairs':len(comparisons),'operators':operators}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
