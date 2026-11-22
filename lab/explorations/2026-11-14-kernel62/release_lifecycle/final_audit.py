"""Verify the supplementary tails and preservation of the interrupted attempt."""
import argparse
import importlib.util
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t10_final_recovery',HERE/'recovery.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
s=r.s


def audit(work):
    s.check(work)
    assert not any((work/n).exists() for n in ('in-flight.json','STOP','final-audit.json'))
    original=s.s.read(work/'audit.json');assert original['passed'] and original['stages']==92
    assert s.s.read(work/'tail-birth-summary.json')['stages']==8
    frozen=s.s.read(work/'tail-birth-frozen.json')
    for rel,h in frozen['sources'].items():assert s.s.sha(s.ROOT/rel)==h
    rows=[];states=0
    for key,h in frozen['parents'].items():
        folder=work/'birth-tails'/key;q=s.s.read(folder/'result.json')
        parent=s.get(work/'cases'/key/'final.rstate.gz')
        initial=s.get(folder/'initial.rstate.gz');final=s.get(folder/'final.rstate.gz')
        assert parent.digest==initial.digest==h==q['initial_sha256']==q['parent_sha256']
        assert final.digest==q['final_sha256'] and q['no_reconfigure']
        assert initial.to_dict()['config']==final.to_dict()['config']==q['config']
        for image in (initial,final):
            assert s.engine(state=image).capture_state().digest==image.digest;states+=1
        previous=None
        for p in q['points']:
            image=s.get(folder/f"tail-{p['requested_seconds']}.rstate.gz");d=image.to_dict()
            assert image.digest==p['sha256'] and int(d['time_us'])==p['time_us']
            assert d['life']==p['life'] and d['active']==p['active'] and d['transport']==p['transport']
            e=s.engine(state=image);before=e.capture_state().digest
            assert e.observation_nodes()==p['nodes']
            assert before==e.capture_state().digest
            if previous:assert p['time_us']>=previous['time_us']
            previous=p;states+=1
        zero=next((p for p in q['points'] if max((n['activation'] for n in p['nodes']),default=0)==0),None)
        last=q['points'][-1]
        row={'parent':key,'block':int(key.split('/')[2]),
             'precheck':q['config']['resource_precheck_enabled'],'repair':q['config']['subthreshold_expiry_enabled'],
             'life':last['life'],'actual_seconds':last['actual_seconds'],'remaining_active':len(last['active']),
             'first_zero_sample_seconds':zero['actual_seconds'] if zero else None,
             'maximum_final_activation':max((n['activation'] for n in last['nodes']),default=0),
             'transmission_after_first_zero':None if zero is None else
                 sum(last['transport'][k]-zero['transport'][k] for k in ('transmitted_excitation','transmitted_inhibition'))}
        if last['life']=='dead':
            assert not last['active'] and row['maximum_final_activation']==0
            assert last['time_us']-int(last['quiet_since_us'])==q['config']['quiescence_death_us']
        row['stale_label']=last['life']=='active' and row['maximum_final_activation']==0 and bool(last['active'])
        rows.append(row)
    old=Path(s.s.read(work/'recovery-authorization.json')['old_work'])
    manifest=s.s.read(old/'interruption-manifest.json')
    r.verify_pack(old/'interruption-evidence.zip',manifest)
    r.verify_pack(work/'prior-attempt/interruption-evidence.zip',manifest)
    for member in manifest['members']:assert s.s.sha(old/member['path'])==member['sha256'],member['path']
    for p in (work/'prior-attempt').iterdir():
        source=old/('interruption-publication/receipt.json' if p.name=='receipt.json' else p.name)
        assert s.s.sha(p)==s.s.sha(source)
    assert s.get(old/'cases'/r.KEY/'final.rstate.gz').digest==r.PARENT
    assert s.get(work/'cases'/r.KEY/'final.rstate.gz').digest==r.PARENT
    assert (old/'STOP').exists() and (old/'in-flight.json').exists()
    plan=s.s.read(work/'plan.json')
    stage=next(p for p in plan if p['key']=='persistent/p0-f0/0/original/wait')
    background=s.load_inputs(work,stage)
    assert len(background)==300 and all(p['source_policy']['category']=='background' for p in background)
    assert not any(ch in s.TARGETS for p in background for ch,a in p['stimulus']['channels'])
    analysis=s.s.read(work/'analysis.json')
    result={'passed':True,'scientific_stop':any(p['repair'] and p['stale_label'] for p in rows),
            'main_stages':92,'supplementary_tails':8,'material_blocks':2,
            'main_complete_states_checked':original['complete_states_checked'],
            'supplementary_complete_states_checked':states,
            'old_interrupted_members_unchanged':len(manifest['members']),
            'old_markers_preserved':True,'reused_teaching_sha256':r.PARENT,
            'waiting_background_inputs':300,'waiting_task_inputs':0,
            'max_repair_process_difference':max(p['max_activity_difference'] for p in analysis['repair_pairs']),
            'lifecycle_rows':rows,
            'main_tail_interpretation':'Configuration intervention settles all nodes even when the repair remains disabled; birth-flag tails isolate the repair without this intervention.'}
    s.s.write(work/'final-audit.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
