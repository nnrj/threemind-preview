"""Read-only supplement verification and combined audit receipt."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import study_resources as x
import supplement_high as h
import audit_resources as a
s=x.s


def run(work):
    x.check(work)
    assert s.read(work/'audit.json')['passed']
    assert not any((work/p).exists() for p in ('in-flight.json','STOP','supplement-audit.json'))
    frozen=s.read(work/'supplement-frozen.json')
    for rel,digest in frozen['sources'].items():assert s.sha(x.ROOT/rel)==digest
    summary=s.read(work/'supplement-summary.json');assert summary['stages']==len(summary['results'])==24
    index=s.read(work/'cases.json');states=[];matrix=[];errors=[]
    # Derive answers independently from the exchanged curricula, not from the scorer's target field.
    label_checks=0
    for category in ('cases','controls'):
        for path in (work/category).glob('*/*/*/result.json'):
            cue=path.parent.name
            if cue not in ('AB','DB'):continue
            block=int(path.parent.parent.name);q=s.read(path)
            target='C' if (cue=='AB') != bool(block) else 'E'
            assert q['target']==target and q['other']==('E' if target=='C' else 'C')
            assert q['cue']==cue and q['block']==block
            assert index[f'history/s{block}/101/d1/{cue}']['swap']==bool(block)
            label_checks+=1
    x.VARIANTS.update(h.CONDITIONS)
    for name,item in h.CONDITIONS.items():
        blocks=[]
        for block in (0,1):
            parent=None;margins=[];teaching=None;seconds=0.
            for cue in ('train','AB','DB'):
                folder=x.folder(work,name,block,cue);q=s.read(folder/'result.json');assert q in summary['results']
                before=x.state_at(folder,'initial');after=x.state_at(folder,'final')
                assert before.digest==q['initial_sha256'] and after.digest==q['final_sha256']
                assert x.create(name,state=after).capture_state().digest==after.digest
                assert int(after.to_dict()['time_us'])==q['time_us']
                for k,v in item['patch'].items():assert after.to_dict()['config'][k]==v
                seconds+=q['wall_seconds']
                if cue=='train':
                    assert int(before.to_dict()['time_us'])==0 and q['time_us']==212200000
                    assert q['parent_sha256'] is None;parent=after
                    teaching=a.trace_measures(folder/'teaching.jsonl.gz',before)
                else:
                    assert q['parent_sha256']==parent.digest
                    clone=x.create(name,state=parent)
                    clone.reconfigure(replace(clone.config,**(index[f'history/s{block}/101/d1/{cue}']['patch']|item['patch'])))
                    assert clone.capture_state().digest==before.digest
                    margin,error=a.score(folder,q);margins.append(margin);errors.append(error)
                states.append({'folder':folder.relative_to(work).as_posix(),'initial':before.digest,'final':after.digest})
            blocks.append({'block':block,'AB':margins[0],'DB':margins[1],'passed':all(z>1e-6 for z in margins),
                'wall_seconds':seconds,'teaching':teaching})
        matrix.append({'variant':name,'blocks':blocks,'passed_blocks':sum(b['passed'] for b in blocks)})
    s.write(work/'supplement-analysis.json',{'stages':24,'matrix':matrix,
        'scientific_wall_seconds':sum(q['wall_seconds'] for q in summary['results']),
        'maximum_arithmetic_error':max(errors),'prospective_registration':frozen})
    s.write(work/'supplement-audit.json',{'passed':True,'states':48,'processes':16,
        'maximum_arithmetic_error':max(errors),'state_hashes':states})
    primary=s.read(work/'audit.json')
    s.write(work/'final-audit.json',{'passed':True,'primary_sha256':s.sha(work/'audit.json'),
        'supplement_sha256':s.sha(work/'supplement-audit.json'),'states':primary['states']+48,
        'processes':primary['processes']+16,'maximum_arithmetic_error':max(primary['maximum_arithmetic_error'],max(errors)),
        'production_source_freeze_verified':True,'curriculum_label_checks':label_checks})
    print(json.dumps({'passed':True,'matrix':[{'variant':q['variant'],'passed_blocks':q['passed_blocks'],
        'margins':[[b['AB'],b['DB']] for b in q['blocks']]} for q in matrix]}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);args=p.parse_args();run(args.work)
