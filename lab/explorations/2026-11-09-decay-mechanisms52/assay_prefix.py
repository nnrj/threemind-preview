"""Read-only validation of a complete R46 prefix, including a taught next case."""
from pathlib import Path


def validate(work,cases,load,sha,digest):
    work=Path(work).resolve();completed=boundaries=0;last=None;resume=None;rows=[];gap=False
    for i,case in enumerate(cases):
        key='subjects/'+case['key'];folder=work/key;birth=folder/'birth.json.gz'
        has_birth=birth.exists()
        present=[(folder/phase/'complete.json').exists() for phase in ('teaching','probe')]
        if gap:
            assert not has_birth and not any(present),'future case exists beyond current prefix'
            continue
        assert not present[1] or present[0],'probe without teaching'
        assert not any(present) or has_birth,'complete operation without birth'
        if not has_birth:
            resume=dict(index=i,phase='birth',state_file=None);gap=True;continue
        before=load(birth)
        assert int(before['core']['time_us'])==0
        assert before['identity']=='R46a-'+case['key']
        for phase,exists in zip(('teaching','probe'),present):
            if not exists:
                resume=dict(index=i,phase=phase,state_file=key+('/birth.json.gz' if phase=='teaching' else '/teaching/whole.json.gz'))
                gap=True;break
            row=load(folder/phase/'complete.json')
            for field in ('state_file','result_file'):
                (work/row[field]).resolve().relative_to(work)
            assert row['state_file']==key+'/'+phase+'/whole.json.gz'
            assert row['result_file']==key+'/'+phase+'/result.json.gz'
            assert sha(work/row['state_file'])==row['sha256']
            assert sha(work/row['result_file'])==row['result_sha256']
            after=load(work/row['state_file'])
            assert digest(before)==row['before_sha256'] and digest(after)==row['after_sha256']
            assert int(before['core']['time_us'])==int(row['start_us'])
            assert int(after['core']['time_us'])==int(row['end_us'])>=int(row['start_us'])
            assert after['identity']==before['identity'] and after['mapping']==before['mapping']
            assert after['core']['dynamics']=='threemind.continuous-memory/5.2'
            assert after['core']['config']==before['core']['config']
            assert after['core']['config']['decay_curve']==case['curve']
            assert after['core']['config']['retention_relaxation_enabled']==case['relaxation']
            last=dict(unit=key+'/'+phase,state_file=row['state_file'],sha256=row['sha256'],time_us=int(row['end_us']))
            rows.append(dict(unit=last['unit'],state=row['sha256'],result=row['result_sha256']))
            before=after;boundaries+=1
        if present[1]:completed+=1
    assert last is not None,'no completed boundary to resume'
    current=load(work/'current.json')
    assert current==last,'current pointer differs from latest complete operation'
    assert load(work/'status.json')['sequences_completed']==completed
    assert completed<len(cases) and resume is not None,'finished batch cannot be resumed'
    return dict(sequences=completed,boundaries=boundaries,current=current,resume=resume,
        verified_chain_sha256=digest(rows))
