"""Independent read-only audit of the 12 registered novelty-timing stages."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import novelty_followup as n
h=n.h;e=h.e;s=h.s
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import measurement_timescales as m

def analyze(work):
    n.check(work);assert h.read(work/'audit.json')['passed'] and h.read(work/'novelty-summary.json')['complete']==12
    assert not (work/'in-flight.json').exists()
    cases=h.read(work/'novelty-cases.json');records={};rows=[];nstates=0;ninputs=0
    norm=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
    for c in cases:
        folder=work/'cases'/c['key'];r=h.read(folder/'result.json')
        assert r['status']=='complete' and r['kernel']=='threemind.continuous-memory/'+c['version'] and r['life']=='active'
        images={k:e.base.image(folder/(k+'.tmind')) for k in ('initial','intervened','final')}
        for k,im in images.items():
            assert im.digest==r[k+'_sha256'] and im.to_dict()['dynamics']==r['kernel'];nstates+=1
        before,changed,final=[images[k].to_dict() for k in ('initial','intervened','final')]
        assert before['config']['novelty_mode']=='immediate'
        assert changed['config']==before['config']|c['patch']|c['cause_patch'] and final['config']==changed['config']
        assert int(before['time_us'])==int(changed['time_us'])==c['begin_us'] and int(final['time_us'])==c['end_us']
        change=h.read(folder/'intervention.json');assert change['advanced_us']==0 and change['changes']==e.support.x.differences(before,changed)
        if c['parent']:
            assert r['parent_sha256']==r['initial_sha256']==records[c['parent']]['final_sha256']
            assert e.unpacked(folder/'initial-observer.json.xz')==e.unpacked(work/'cases'/c['parent']/'observer.json.xz')
        inputs=e.unpacked(folder/'inputs.json.xz');assert inputs==e.material_frames(c,work/'materials')
        scheduled=e.unpacked(folder/'scheduled.json.xz');delivered=e.unpacked(folder/'delivered.json.xz')
        assert len(inputs)==len(scheduled)==len(delivered)==r['inputs'];ninputs+=len(inputs)
        by_event={}
        for a,b in zip(inputs,scheduled):
            assert a['enqueue_us']==b['enqueue_us'] and a['source']==b['receipt']['source']
            assert int(a['stimulus']['time_us'])==int(b['receipt']['scheduled_time_us'])
            by_event[b['receipt']['core_event_id']]=b['enqueue_us']
        assert Counter(norm({k:a[k] for k in ('stimulus','source','enqueue_us')}) for a in inputs)==Counter(
            norm({'stimulus':a['stimulus'],'source':a['source'],'enqueue_us':by_event[a['core_event_id']]}) for a in delivered)
        assert all(a['status']=='delivered' and not a.get('labels') and a['stimulus']['time_us']==a['scheduled_time_us']==a['delivered_time_us'] for a in delivered)
        assert e.unpacked(folder/'observer.json.xz')['input_bus']['pending']=={}
        with zipfile.ZipFile(folder/'milestones.zip') as archive:
            assert set(archive.namelist())=={k+'.tmind' for k in r['snapshots']}
            for k,digest in r['snapshots'].items():
                im=e.base.ArtifactCodec.decode(archive.read(k+'.tmind'));assert im.digest==digest and im.to_dict()['dynamics']==r['kernel'];nstates+=1
        if c['kind']=='probe':rows.append(m.process(c,e.unpacked(folder/'trajectory.json.xz')['points']))
        records[c['key']]=r
    summary=[]
    for variant in ('v2-immediate','v61-immediate'):
        blocks=[]
        for b in (0,1):
            margins=[r['signed_peak'] for r in rows if r['key'].startswith(f'{variant}/history/s{b}/')]
            assert len(margins)==2
            blocks.append({'block':b,'margins':margins,'passed':all(x>m.EPS for x in margins)})
        summary.append({'variant':variant,'blocks':blocks,'prefix_blocks':sum(b['passed'] for b in blocks)})
    s.base.original(work/'analysis-novelty.json',{'variants':summary,'process':rows,'stages':12,'material_blocks':2})
    s.base.original(work/'audit-novelty.json',{'passed':True,'stages':12,'complete_states':nstates,'inputs':ninputs,
        'maximum_arithmetic_error':max(r['arithmetic_error'] for r in rows),'apparatus':h.read(work/'novelty-apparatus.json')})
    print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();analyze(a.work)
