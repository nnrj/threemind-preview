"""Read-only independent verification and functional scoring of R51t3."""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal,localcontext
import importlib.util
import json
import math
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import body as h
e=h.e;s=h.s
spec=importlib.util.spec_from_file_location('r51t3_integrals',HERE.parent/'body_transfer/analyze.py')
oldmath=importlib.util.module_from_spec(spec);spec.loader.exec_module(oldmath)

def analyze(work):
    h.check(work);assert h.read(work/'summary.json')['complete']==296 and not (work/'in-flight.json').exists()
    table=h.read(work/'cases.json');static={};body=[];settled={};nstates=0;ninputs=0;maxerr=0.
    for i,c in enumerate(table):
        f=work/'cases'/c['key'];r=h.read(f/'result.json');assert r['status']=='complete'
        images={k:e.base.image(f/(k+'.tmind')) for k in ('initial','intervened','final')}
        for k,im in images.items():assert im.digest==r[k+'_sha256'] and im.to_dict()['dynamics']==r['kernel'];nstates+=1
        assert images['initial'].digest==e.base.image(h.parent_dir(work,c)/'final.tmind').digest
        a,b,z=[images[k].to_dict() for k in ('initial','intervened','final')]
        assert b['config']==a['config']|{'signal_threshold':c['threshold']} and z['config']==b['config']
        assert int(a['time_us'])==int(b['time_us'])==r['begin_us'] and int(z['time_us'])==r['end_us']
        same=deepcopy(b);same.pop('config');same.pop('definition_hash');same['definition'].pop('config');key=(c['seed'],c['mode'])
        assert b['definition']['config']==b['config'] and z['definition']['config']==z['config']
        if key in settled:assert settled[key]==same,('post-settlement states differ',key)
        else:settled[key]=same
        inputs=e.unpacked(f/'inputs.json.xz');delivered=e.unpacked(f/'delivered.json.xz');assert len(inputs)==len(delivered)==r['inputs'];ninputs+=len(inputs)
        normal=lambda x:json.dumps({k:x[k] for k in ('stimulus','source')},sort_keys=True,separators=(',',':'))
        assert Counter(normal(x) for x in inputs)==Counter(normal(x) for x in delivered)
        assert all(x['stimulus']['time_us']==x['scheduled_time_us']==x['delivered_time_us'] and not x.get('labels') for x in delivered)
        forbidden={h.mapping(c['seed'])[v] for v in ('A','B')}
        assert not any(ch in forbidden for x in inputs for ch,val in x['stimulus']['channels'])
        assert e.unpacked(f/'observer.json.xz')['input_bus']['pending']=={}
        points=e.unpacked(f/'trajectory.json.xz')
        if c['kind']=='static':
            assert [p['time_us']-r['begin_us'] for p in points]==list(range(0,5600001,100000))
            ids=[h.mapping(c['seed'])[v] for v in ('A','B')]
            curve={p['time_us']-r['begin_us']:{field:[next((n.get(field,0.) for n in p['nodes'] if n['channel']==ch),0.) for ch in ids] for field in h.FIELDS} for p in points}
            static[(c['seed'],c['mode'],c['threshold'],c['sign'])]=curve
        else:
            assert [p['time_us']-r['begin_us'] for p in points]==list(range(0,8000001,10000))
            physical=[p for p in points if 'q' in p];assert len(physical)==401
            start=e.unpacked(f/'body-initial.json.xz');end=e.unpacked(f/'body-final.json.xz')
            assert start['core_sha256']==r['intervened_sha256'] and end['core_sha256']==r['final_sha256']
            assert end['body']['elapsed_us']==8000000 and end['elapsed_core_us']==8000000
            assert end['observer']==e.unpacked(f/'observer.json.xz')
            vals=[p['q']**2 for p in physical[:-1]];angle=math.sqrt(math.fsum(vals)/400)
            with localcontext() as ctx:
                ctx.prec=45;independent=(sum(Decimal(str(p['q']))**2 for p in physical[:-1])/400).sqrt()
            maxerr=max(maxerr,abs(angle-float(independent)));assert maxerr<1e-10
            body.append({**c,'angle_rms':angle,'speed_rms':math.sqrt(math.fsum(p['velocity']**2 for p in physical[:-1])/400),
                'last_second_error':math.sqrt(math.fsum(p['q']**2 for p in physical[-51:-1])/50),
                'absolute_torque':math.fsum(abs(p['command'])*.02 for p in physical[:-1]),
                'switches':sum(a['command']*b['command']<0 for a,b in zip(physical,physical[1:])),
                'success':all(abs(p['q'])<.1 and abs(p['velocity'])<.2 for p in physical[-51:])})
        if (i+1)%40==0:print('audited body',i+1,flush=True)
    static_scores=[]
    for seed in h.SEEDS:
        for mode in h.MODES:
            for threshold in (.0004,.004):
                blank=static[(seed,mode,threshold,0)]
                for sign in (1,-1):
                    values,error=oldmath.process(static[(seed,mode,threshold,sign)],blank,600000,5600000);maxerr=max(maxerr,error)
                    static_scores.append({'seed':seed,'mode':mode,'threshold':threshold,'sign':sign,
                        'direction':oldmath.direction(values['activation'],int(sign<0)),'fields':values})
    inversions=[]
    for seed in h.SEEDS:
        get=lambda mode,t:[r['direction'] for r in static_scores if r['seed']==seed and r['mode']==mode and r['threshold']==t]
        passed=get('full',.0004)==['correct']*2 and get('full',.004)==['opposite']*2 and all(get('no_imu',t)==['correct']*2 for t in (.0004,.004))
        inversions.append({'seed':seed,'passed':passed,'low_full':get('full',.0004),'high_full':get('full',.004),'low_joint':get('no_imu',.0004),'high_joint':get('no_imu',.004)})
    contrasts=[]
    for seed in h.SEEDS:
        for mode in h.MODES:
            for polarity in (1,-1):
                rows=[r for r in body if r['controller']=='core' and r['seed']==seed and r['mode']==mode and r['polarity']==polarity]
                averages={str(t):{metric:math.fsum(r[metric] for r in rows if r['threshold']==t)/2 for metric in ('angle_rms','speed_rms','last_second_error','absolute_torque')} for t in (.0004,.004)}
                change={metric:1-averages['0.004'][metric]/averages['0.0004'][metric] if averages['0.0004'][metric] else None for metric in averages['0.0004']}
                contrasts.append({'seed':seed,'mode':mode,'polarity':polarity,'means':averages,'relative_improvement_high_threshold':change})
    result={'stages':296,'material_blocks':4,'same_post_teaching_state_verified':True,'static':static_scores,
        'inversions':inversions,'inversion_passed_blocks':sum(r['passed'] for r in inversions),'body':body,'contrasts':contrasts,
        'maximum_arithmetic_error':maxerr,'defaults_changed':False,'campaign_paused':True}
    s.base.original(work/'analysis.json',result);s.base.original(work/'audit.json',{'passed':True,'stages':296,'complete_states':nstates,
        'inputs':ninputs,'maximum_arithmetic_error':maxerr,'same_post_teaching_state_verified':True,'analysis_revision':'v2: normalize duplicated configuration metadata and its hash only; Core state equality remains exact','apparatus':h.read(work/'apparatus.json')})
    print(json.dumps({'inversions':inversions,'full_body_contrasts':[r for r in contrasts if r['mode']=='full']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();analyze(a.work)
