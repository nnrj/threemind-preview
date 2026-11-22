"""Independent read-only state, schedule and arithmetic audit for R51t2."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as h
e=h.e;s=h.s
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m

def analyze(work):
    h.check(work);assert h.read(work/'summary.json')['complete']==110 and not (work/'in-flight.json').exists()
    records={};rows=[];waits={};nstates=0;ninputs=0
    norm=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
    for i,c in enumerate(h.read(work/'cases.json')):
        folder=work/'cases'/c['key'];r=h.read(folder/'result.json')
        assert r['status']=='complete' and r['kernel']=='threemind.continuous-memory/6.1'
        states={k:e.base.image(folder/(k+'.tmind')) for k in ('initial','intervened','final')}
        for k,im in states.items():
            assert im.digest==r[k+'_sha256'] and im.to_dict()['dynamics']==r['kernel'];nstates+=1
        before,changed,final=[states[k].to_dict() for k in ('initial','intervened','final')]
        assert changed['config']==before['config']|c['patch']|c['cause_patch'] and final['config']==changed['config']
        assert int(before['time_us'])==int(changed['time_us'])==c['begin_us'] and int(final['time_us'])==c['end_us']
        assert final['config']['inhibition'] is True
        if c['parent']:
            external=c['parent'].startswith('external:')
            parent=h.old(work)/'cases'/c['parent'].removeprefix('external:') if external else work/'cases'/c['parent']
            pr=h.read(parent/'result.json')
            assert r['parent_sha256']==r['initial_sha256']==pr['final_sha256']
            assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(parent/'observer.json.xz')
        changes=h.read(folder/'intervention.json')
        assert changes['advanced_us']==0 and changes['changes']==e.support.x.differences(before,changed)
        inputs=e.unpacked(folder/'inputs.json.xz');assert inputs==e.material_frames(c,work/'materials')
        scheduled=e.unpacked(folder/'scheduled.json.xz');delivered=e.unpacked(folder/'delivered.json.xz')
        assert len(inputs)==len(scheduled)==len(delivered)==r['inputs'];ninputs+=len(inputs)
        lookup={b['receipt']['core_event_id']:b['enqueue_us'] for b in scheduled}
        assert Counter(norm({k:a[k] for k in ('stimulus','source','enqueue_us')}) for a in inputs)==Counter(
            norm({'stimulus':a['stimulus'],'source':a['source'],'enqueue_us':lookup[a['core_event_id']]}) for a in delivered)
        assert all(not x.get('labels') and x['stimulus']['time_us']==x['scheduled_time_us']==x['delivered_time_us'] for x in delivered)
        assert e.unpacked(folder/'observer.json.xz')['input_bus']['pending']=={}
        with zipfile.ZipFile(folder/'milestones.zip') as z:
            for k,digest in r['snapshots'].items():
                im=e.base.ArtifactCodec.decode(z.read(k+'.tmind'));assert im.digest==digest and im.to_dict()['dynamics']==r['kernel'];nstates+=1
        points=e.unpacked(folder/'trajectory.json.xz')['points']
        if c['kind']=='probe':
            row=m.process(c,points);vals=[n['activation'] for p in points for n in p['nodes']]
            row.update(variant=c['variant'],group=c['group'],block=c['block'],saturation_fraction=sum(v>=.95 for v in vals)/len(vals) if vals else 0)
            rows.append(row)
        elif c['kind']=='readout_wait':
            waits[c['variant']+':'+str(c['block'])]=max(((p['time_us']-c['begin_us'])/1e6 for p in points if any(n['activation']>0 for n in p['nodes'])),default=0.)
        records[c['key']]=r
        if (i+1)%20==0:print('audited',i+1,flush=True)
    summary=[]
    for name in dict.fromkeys(r['variant'] for r in rows):
        rr=[r for r in rows if r['variant']==name];group=rr[0]['group'];blocks=[]
        for b in (0,1):
            rs=[r for r in rr if r['block']==b]
            if group=='persistent':
                assert len(rs)==1;v=rs[0]
                blocks.append({'block':b,'passed':v['task_activity']['minimum']>m.EPS,'last_positive_seconds':waits[name+':'+str(b)],
                    'activity':v['task_activity'],'saturation_fraction':v['saturation_fraction']})
            else:
                assert len(rs)==2
                blocks.append({'block':b,'passed':all(x['signed_peak']>m.EPS for x in rs),
                    'peak_margins':[r['signed_peak'] for r in rs],'area_margins':[r['signed_area'] for r in rs]})
        summary.append({'variant':name,'group':group,'blocks':blocks,'passed_blocks':sum(x['passed'] for x in blocks)})
    result={'variants':summary,'process':rows,'material_blocks':2,'stages':110,'defaults_changed':False,
        'scientific_stop':False,'campaign_paused':True,'maximum_arithmetic_error':max(r['arithmetic_error'] for r in rows)}
    s.base.original(work/'analysis.json',result)
    s.base.original(work/'audit.json',{'passed':True,'stages':110,'complete_states':nstates,'inputs':ninputs,
        'maximum_arithmetic_error':result['maximum_arithmetic_error'],'apparatus':h.read(work/'apparatus.json')})
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();analyze(a.work)
