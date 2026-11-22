"""Saved-process scoring without constructing a scientific subject."""
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('r63i_shared_integrals',HERE.parent/'body_transfer/analyze.py')
maths=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(maths)

def read(p):
    b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)

def curves(folder):
    result=read(folder/'result.json');points=read(folder/'trajectory.json.gz')['points'];targets=result['targets']
    curve={p['time_us']-result['begin_us']:{field:[next((n.get(field,0.) for n in p['nodes'] if n['channel']==ch),0.)
            for ch in targets] for field in maths.FIELDS} for p in points}
    assert sorted(curve)==list(range(0,5600001,100000))
    return curve

def scores(work,subject,arm='intact'):
    base=work/'subjects'/subject['key'];blank=curves(base/f'{arm}-0');out=[]
    for sign in (1,-1):
        folder=base/f'{arm}-{sign}';cued=curves(folder);r=read(folder/'result.json');windows={}
        zero={t:{field:[0.,0.] for field in maths.FIELDS} for t in cued}
        for name,lo,hi,reference in [('post_input',600000,5600000,blank),('input',0,600000,blank),
                                    ('common_blank_window',600000,5000000,blank),('raw_post',600000,5600000,zero)]:
            q,error=maths.process(cued,reference,lo,hi)
            windows[name]={'fields':q,'direction':maths.direction(q['activation'],int(sign<0)),
                           'maximum_Decimal_error':error}
        out.append({k:r[k] for k in ('subject','variant','kernel','seed','preset','mode','sign','arm','queue_policy')}|{'windows':windows})
    return out

def block_summary(rows,variant,arm='intact'):
    out=[]
    for seed in (930101,930102,930103,930104):
        r=[x for x in rows if x['variant']==variant and x['seed']==seed and x['arm']==arm]
        full=[x['windows']['post_input']['direction'] for x in r if x['mode']=='full']
        joint=[x['windows']['post_input']['direction'] for x in r if x['mode']=='no_imu']
        assert len(full)==len(joint)==4
        out.append({'seed':seed,'full_correct':full.count('correct'),'full_opposite':full.count('opposite'),
            'full_unmeasurable':full.count('no-measurable-direction'),'joint_correct':joint.count('correct'),
            'old_relation':full.count('opposite')>=3 and joint.count('correct')>=3,
            'taught_relation':full.count('correct')>=3 and joint.count('correct')>=3})
    return {'variant':variant,'arm':arm,'blocks':out,'independent_material_blocks':4,
        'old_relation_blocks':sum(x['old_relation'] for x in out),'taught_relation_blocks':sum(x['taught_relation'] for x in out)}

def baseline_check(work):
    rows=[]
    for subj in read(work/'subjects.json'):
        if subj['variant'] in ('v2','v63','v2-prequeue','v63-prequeue'):rows+=scores(work,subj)
    groups=[block_summary(rows,v) for v in ('v2','v63','v2-prequeue','v63-prequeue')]
    passed=groups[0]['old_relation_blocks']>=3 and groups[3]['taught_relation_blocks']>=3
    return {'passed':passed,'groups':groups,'registered_gates':['v2 stream old relation >=3/4','v63 prequeue taught relation >=3/4'],
            'Core_engines_loaded':0}
