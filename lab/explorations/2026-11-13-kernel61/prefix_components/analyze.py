"""Read-only state, input, intervention and arithmetic audit for R51t6."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import components_study as h
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m
e=h.e;s=h.s

def analyze(work):
    h.check(work);assert h.read(work/'summary.json')['complete']==70 and not (work/'in-flight.json').exists()
    rows=[];states=0;inputs=0;training=[]
    for c in h.read(work/'cases.json'):
        folder=work/'cases'/c['key'];r=h.read(folder/'result.json')
        assert r['status']=='complete' and r['kernel']==h.research.KERNEL_ID
        a=e.storage.image(folder/'initial.rstate');v=e.storage.image(folder/'intervened.rstate');z=e.storage.image(folder/'final.rstate');states+=3
        assert (a.digest,v.digest,z.digest)==(r['initial_sha256'],r['intervened_sha256'],r['final_sha256'])
        da,dv,dz=a.to_dict(),v.to_dict(),z.to_dict()
        assert int(da['time_us'])==c['begin_us'] and int(dz['time_us'])==c['end_us']
        assert da['dynamics']==dv['dynamics']==dz['dynamics']==h.research.KERNEL_ID
        assert dv['config']==da['config']|c['patch']|c['cause_patch'] and dz['config']==dv['config']
        allowed={'config','definition','definition_hash'}
        if c.get('weight_donor'):
            allowed.add('edges');donor=e.storage.image(work/'cases'/c['weight_donor']/'final.rstate').to_dict()
            donors={(x['source'],x['target']):x for x in donor['edges']}
            for before,after in zip(da['edges'],dv['edges']):
                supplied=donors[before['source'],before['target']]
                assert before['state_us']==supplied['state_us']
                assert after==before|{'weight':supplied['weight']}
        assert all(da[k]==dv[k] for k in da if k not in allowed)
        if c['parent']:
            parent=work/'cases'/c['parent'];assert a.digest==e.storage.image(parent/'final.rstate').digest
            assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(parent/'observer.json.xz')
        original=e.unpacked(folder/'inputs.json.xz');delivered=e.unpacked(folder/'delivered.json.xz')
        assert original==e.material_frames(c,work/'materials') and len(original)==len(delivered)==r['inputs'];inputs+=len(original)
        norm=lambda x:json.dumps({'stimulus':x['stimulus'],'source':x['source']},sort_keys=True)
        assert Counter(norm(x) for x in original)==Counter(norm(x) for x in delivered)
        assert all(x['stimulus']['time_us']==x['scheduled_time_us']==x['delivered_time_us'] and not x.get('labels') for x in delivered)
        assert e.unpacked(folder/'observer.json.xz')['input_bus']['pending']=={}
        with zipfile.ZipFile(folder/'milestones.zip') as zz:
            for k,digest in r['snapshots'].items():assert e.storage.Codec.decode(zz.read(k+'.rstate')).digest==digest;states+=1
        if c['kind']=='probe':
            q=m.process(c,e.unpacked(folder/'trajectory.json.xz')['points'])
            q.update(variant=c['variant'],block=c['block'],comparison=c['comparison']);rows.append(q)
        else:
            channels={n['id']:n['channel'] for n in dz['nodes']};names={v:k for k,v in e.materials.TOKENS.items()}
            edges=[{'source':names[channels[x['source']]],'target':names[channels[x['target']]],
                    **{k:x[k] for k in ('weight','stability','eligibility','touches','last_pass_us')}}
                    for x in dz['edges'] if channels[x['source']] in names and channels[x['target']] in names]
            training.append({'variant':c['variant'],'block':c['block'],'edges':edges,'total_edges':len(dz['edges'])})
    matrix=[]
    for variant in dict.fromkeys(c['variant'] for c in h.read(work/'cases.json')):
        rr=[r for r in rows if r['variant']==variant];assert len(rr)==4
        blocks=[{'block':b,'passed':all(r['signed_peak']>m.EPS for r in rr if r['block']==b),
                 'margins':{r['cue']:r['signed_peak'] for r in rr if r['block']==b}} for b in (0,1)]
        matrix.append({'variant':variant,'blocks':blocks,'passed_blocks':sum(x['passed'] for x in blocks)})
    assert next(x for x in matrix if x['variant']=='reference')['passed_blocks']==2,'reference recovery not reproduced'
    assert next(x for x in matrix if x['variant']=='window')['passed_blocks']==0,'window comparison not reproduced'
    error=max(r['arithmetic_error'] for r in rows)
    result={'matrix':matrix,'process':rows,'training':training,'material_blocks':2,'stages':70,'maximum_arithmetic_error':error,
            'production_changed':False,'main_campaign_paused':True,'research_identity':h.research.KERNEL_ID}
    s.base.original(work/'analysis.json',result)
    s.base.original(work/'audit.json',{'passed':True,'complete_states':states,'inputs':inputs,'stages':70,
        'maximum_arithmetic_error':error,'apparatus':h.read(work/'apparatus.json'),'research_identity':h.research.KERNEL_ID})
    print(json.dumps(matrix),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();analyze(a.work)
