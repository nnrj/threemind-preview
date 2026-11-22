"""Audit lifecycle labels against saved activity and transmission, without advancing a Core."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import study_resources as x
s=x.s


def run(work):
    results=s.read(work/'tails.json')['results'];rows=[]
    for q in results:
        folder=work/'tails'/q['variant']/str(q['block'])
        initial=x.state_at(folder,'initial');final=x.state_at(folder,'final');d=final.to_dict()
        assert initial.digest==q['parent_sha256'] and final.digest==q['final_sha256']
        records=q['rows'];last=records[-1];begin=records[0]['time_us']
        assert last['state_sha256']==final.digest
        first_zero=next((v for v in records if all(n['activation']==0 for n in v['nodes'])),None)
        after_zero=[v for v in records if first_zero is not None and v['time_us']>=first_zero['time_us']]
        unchanged=bool(after_zero) and all(
            all(v['transport'][key]==after_zero[0]['transport'][key] for key in
                ('transmitted_excitation','transmitted_inhibition')) for v in after_zero)
        by_id={n['id']:n for n in d['nodes']};stale=[]
        timers=d['timers']
        for nid in d['active']:
            n=by_id[nid]
            observed=next(v for v in last['nodes'] if v['id']==nid)
            if observed['activation']==0:
                stale.append({'id':nid,'stored_activation':n['activation'],'stored_time_us':n['state_us'],
                    'below_activation_floor':0<n['activation']<d['config']['activation_floor'],
                    'has_activation_expiry':any(v[0]==1 and v[1]==nid for v in timers),
                    'has_sending_timer':any(v[0]==0 and v[1]==nid for v in timers)})
        rows.append({'variant':q['variant'],'block':q['block'],'life':last['life'],
            'observed_internal_seconds':(last['time_us']-begin)/1e6,
            'first_record_with_zero_activation_seconds':None if first_zero is None else (first_zero['time_us']-begin)/1e6,
            'transmission_unchanged_after_first_zero_record':unchanged,
            'final_projected_active_nodes':sum(n['activation']>0 for n in last['nodes']),
            'stored_active_ids':d['active'],'stale_active_entries':stale,'quiet_since_us':d['quiet_since_us']})
    out={'status':'New read-only finding; no change to primary scores or original states',
        'lifecycle_label_valid_as_activity_duration':False,
        'primary_score_uses_recorded_activation_not_lifecycle_label':True,
        'finding':'Lifecycle active label can persist without activation or further transmission. Sub-floor positive arrivals can enter the active set while neither an activation-expiry nor sending timer is scheduled.',
        'source_functions':{'python':'src/threemind_kernels/local62.py: _touch, _node_timers, _pulse, _settle_node',
                            'rust':'crates/threemind-core/src/local62_transitions.rs: touch, node_timers, pulse, settle_node'},
        'rows':rows}
    out['prior_edition']='tail-status-audit.json'
    out['prior_sha256']=s.sha(work/out['prior_edition'])
    out['edition_note']='Adds explicit measurement-validity fields; earlier analysis and all original states remain unchanged.'
    s.write(work/'tail-status-audit-v2.json',out)
    print(json.dumps({'rows':len(rows),'active_labels_with_zero_activation':sum(q['life']=='active' and q['final_projected_active_nodes']==0 for q in rows),
                      'lifecycle_duration_valid':False,'prior_preserved':True}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
