"""Synthetic checkpoint-chain checks; no Core is loaded or advanced."""
import gzip
import hashlib
import json
import pytest
from assay_prefix import validate

def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(encoded(x)).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(gzip.compress(encoded(x)) if p.suffix=='.gz' else encoded(x))

def fixture(work,next_phase):
    cases=[dict(key=f'o0/c{i}',curve='exponential',relaxation=True) for i in range(3)]
    last=None
    for i,steps in ((0,2),(1,next_phase)):
        if steps<0:continue
        c=cases[i];key='subjects/'+c['key']
        before=dict(identity='R46a-'+c['key'],mapping={'cue':11,'out':12},
            core=dict(time_us='0',dynamics='threemind.continuous-memory/5.2',
                config=dict(decay_curve='exponential',retention_relaxation_enabled=True)))
        save(work/key/'birth.json.gz',before)
        for j,phase in enumerate(('teaching','probe')[:steps]):
            after=json.loads(encoded(before));after['core']['time_us']=str((128+j)*1_000_000)
            state_file=key+'/'+phase+'/whole.json.gz';result_file=key+'/'+phase+'/result.json.gz'
            save(work/state_file,after);save(work/result_file,{'engineering_fixture':True})
            receipt=dict(state_file=state_file,result_file=result_file,sha256=sha(work/state_file),
                result_sha256=sha(work/result_file),before_sha256=digest(before),after_sha256=digest(after),
                start_us=before['core']['time_us'],end_us=int(after['core']['time_us']))
            save(work/key/phase/'complete.json',receipt)
            last=dict(unit=key+'/'+phase,state_file=state_file,sha256=receipt['sha256'],time_us=receipt['end_us'])
            before=after
    save(work/'current.json',last);save(work/'status.json',{'sequences_completed':1})
    return cases

@pytest.mark.parametrize('steps,phase',[(-1,'birth'),(0,'teaching'),(1,'probe')])
def test_current_complete_stage_is_preserved(tmp_path,steps,phase):
    cases=fixture(tmp_path,steps)
    row=validate(tmp_path,cases,load,sha,digest)
    assert row['sequences']==1 and row['boundaries']==2+max(steps,0)
    assert row['resume']['index']==1 and row['resume']['phase']==phase
    if phase=='probe':assert row['resume']['state_file'].endswith('/teaching/whole.json.gz')

def test_changed_original_is_rejected(tmp_path):
    cases=fixture(tmp_path,0)
    p=tmp_path/'subjects/o0/c0/probe/whole.json.gz'
    value=load(p);value['mapping']['cue']=999;save(p,value)
    with pytest.raises(AssertionError):validate(tmp_path,cases,load,sha,digest)

def test_stale_pointer_is_not_a_resume_point(tmp_path):
    cases=fixture(tmp_path,1);value=load(tmp_path/'current.json');value['time_us']=0
    save(tmp_path/'current.json',value)
    with pytest.raises(AssertionError):validate(tmp_path,cases,load,sha,digest)

def test_hole_is_rejected(tmp_path):
    cases=fixture(tmp_path,-1)
    save(tmp_path/'subjects/o0/c2/birth.json.gz',{})
    with pytest.raises(AssertionError):validate(tmp_path,cases,load,sha,digest)

def test_wrong_completed_count_is_rejected(tmp_path):
    cases=fixture(tmp_path,1);save(tmp_path/'status.json',{'sequences_completed':2})
    with pytest.raises(AssertionError):validate(tmp_path,cases,load,sha,digest)
