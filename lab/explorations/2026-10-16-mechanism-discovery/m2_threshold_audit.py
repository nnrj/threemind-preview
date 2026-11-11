"""File-only lineage, state-intervention, prediction and endpoint audit."""
import argparse,copy,gzip,hashlib,json
from pathlib import Path
import closure_audit as oldcheck
import m2_threshold_rig as spec
import pilot_m2 as m


def load(path):return json.loads(gzip.decompress(path.read_bytes()))


def intervention_check(parent,initial,receipt,selection):
    assert initial['branch']['parent_sha256']==m.digest(parent)
    expected=copy.deepcopy(parent);expected['branch']=initial['branch'];reference=copy.deepcopy(expected)
    name=receipt['arm'];keys={tuple(x['matched' if name.startswith('matched') else 'target']) for x in selection['pairs']}
    if name not in ('intact','restored'):
        for e in expected['model']['edges']:
            if (e['source'],e['target']) in keys:
                e['short_term']={'available':1. if name.endswith('full') else 0.,'active':0.,
                                'utilization':expected['model']['config']['stp_utilization'],'time_us':str(parent['time_us'])}
    assert initial==expected
    assert receipt['parent_sha256']==m.digest(parent) and receipt['reference_sha256']==m.digest(reference)
    assert receipt['Core_config_changed'] is False and receipt['persistent_weights_changed'] is False
    if name=='restored':assert receipt['restored_exact']
    if name!='intact':
        assert {tuple(x['edge']) for x in receipt['changed_short_term_bundles']}==keys
        for change in receipt['changed_short_term_bundles']:
            old=next(e for e in parent['model']['edges'] if (e['source'],e['target'])==tuple(change['edge']))
            assert change['before']==old['short_term']
            assert change['after']=={'available':1. if name.endswith('full') else 0.,'active':0.,
                                    'utilization':parent['model']['config']['stp_utilization'],'time_us':str(parent['time_us'])}


def unit_audit(folder,raw):
    baseline=load(folder/'baseline.json.gz');oldcheck.probe_check(baseline,raw['baseline'])
    assert baseline['time_us']==48500000
    birth=load(folder/'birth.json.gz');assert birth['time_us']==0 and birth['seed']==raw['case']['seed'] and not birth['model']['nodes']
    count={'whole_states':len(list(folder.glob('*.json.gz'))),'cultivation_probes':1,'diagnostics':0,'restorations':0}
    for h in raw['histories']:
        history=h['history'];initial=load(folder/f'h{history}-initial.json.gz')
        expected=copy.deepcopy(baseline);expected['branch']=initial['branch'];assert expected==initial
        assert initial['branch']['parent_sha256']==m.digest(baseline)
        for j,lesson in enumerate(h['lessons'],1):
            whole=load(folder/lesson['checkpoint']['path']);oldcheck.probe_check(whole,lesson['probe'])
            assert whole['time_us']==48500000+j*3500000 and lesson['lesson']==j
            assert hashlib.sha256((folder/lesson['checkpoint']['path']).read_bytes()).hexdigest()==lesson['checkpoint']['sha256']
            start=whole['time_us']-3500000
            taught=[r['values'] for r in whole['inputs'] if r['time_us']==start and set(r['values']) in ({'X','Y','A'},{'X','Y','B'})]
            assert taught==[dict.fromkeys('XYA' if history==0 else 'XYB',.4)]
            count['cultivation_probes']+=1
        parent=load(folder/f'h{history}-lesson16.json.gz')
        for delay in h['delays']:
            whole=load(folder/delay['checkpoint']['path']);d=delay['delay']
            assert whole['branch']['parent_sha256']==m.digest(parent) and whole['time_us']==104500000+d*1000000
            assert whole['inputs'][len(parent['inputs']):]==[{'time_us':104500000+t,'values':{'K':.2}} for t in range(500000,d*1000000+1,500000)]
            assert delay['selection']==spec.select(whole)
        assert len(h['tests'])==44
        for r in h['tests']:
            cohort=load(folder/f'h{history}-delay{r["delay"]}.json.gz')
            a=load(folder/r['initial']['path']);b=load(folder/r['checkpoint']['path'])
            selection=next(x['selection'] for x in h['delays'] if x['delay']==r['delay'])
            intervention_check(cohort,a,r['intervention'],selection)
            for key in ('initial','checkpoint'):
                assert hashlib.sha256((folder/r[key]['path']).read_bytes()).hexdigest()==r[key]['sha256']
            start=104500000+r['delay']*1000000;pr=r['probe']
            assert (a['time_us'],b['time_us'],pr['start_us'],pr['end_us'])==(start,start+150000,start,start+150000)
            assert b['inputs'][:len(a['inputs'])]==a['inputs']
            assert b['inputs'][len(a['inputs']):]==([{'time_us':start,'values':{'X':r['dose']}}] if r['dose'] else [])
            assert b['rows'][:len(a['rows'])]==a['rows']
            rows=b['rows'][len(a['rows']):]
            assert [x['time_us'] for x in rows]==list(range(start+1000,start+150001,1000))
            first=next(x['response'] for x in rows if x['time_us']==start+110000)
            assert first==pr['first'] and (int(first>1e-4)-int(first<-1e-4))==pr['direction']
            assert pr['trace_count']==150 and pr['final_sha256']==m.digest(b)
            label=r['initial']['path'].removesuffix('-initial.json.gz')
            pred=folder/(label+'-prediction.json')
            assert m.read(pred)==r['prediction'] and pred.stat().st_mtime_ns<=(folder/r['checkpoint']['path']).stat().st_mtime_ns
            assert r['prediction']['first_arrival_us']==start+110000
            assert r['novel']==(r['arm']=='intact' and r['dose'] in spec.NOVEL_DOSES)
            count['diagnostics']+=1;count['restorations']+=r['arm']=='restored'
    assert count=={'whole_states':217,'cultivation_probes':33,'diagnostics':88,'restorations':12}
    return count


def independent_goals(raw):
    alltests=[r for h in raw['histories'] for r in h['tests']]
    novel=[r for r in alltests if r['novel']]
    good=sum(r['prediction']['direction']==r['probe']['direction'] for r in novel)
    p1=good>=.95*len(novel) and any(r['probe']['direction']==0 for r in novel) and any(r['probe']['direction']!=0 for r in novel)
    p2=True
    for h in raw['histories']:
        v={(r['delay'],r['arm'],r['dose']):r['probe']['first'] for r in h['tests']};s=1-2*h['history']
        p2 &= s*v[0,'intact',.55]<=1e-4 and s*v[0,'target-full',.55]>1e-4 and abs(v[0,'matched-full',.55]-v[0,'intact',.55])<=1e-9
        p2 &= s*v[0,'intact',.8]>1e-4 and abs(v[0,'target-empty',.8])<=.25*abs(v[0,'intact',.8]) and abs(v[0,'matched-empty',.8]-v[0,'intact',.8])<=1e-9
        p2 &= all(abs(v[d,a,0.])<=1e-4 for d in spec.DELAYS for a in spec.ARMS)
        p2 &= all(abs(v[d,'restored',q]-v[d,'intact',q])<=1e-9 for d in spec.DELAYS for q in (.55,.8))
    return {'P1':bool(p1),'P2':bool(p2)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    m.frozen_check(w);assert not any((w/n).exists() for n in ('STOP','in-flight.json'))
    a=m.read(w/'analysis-v1.json');counts={};goals={'P1':0,'P2':0}
    for case in spec.cases():
        folder=w/'units'/f'o{case["origin"]}';raw=m.read(folder/'result.json');assert raw['case']==case
        for k,v in unit_audit(folder,raw).items():counts[k]=counts.get(k,0)+v
        for k,v in independent_goals(raw).items():
            goals[k]+=v;assert v==next(x[k] for x in a['units'] if x['origin']==case['origin'])
    assert all(a['goals'][k]['qualified']==v and a['goals'][k]['verdict']==('PASS' if v>=6 else 'FAIL') for k,v in goals.items())
    out={'schema':'threemind.m2-threshold-file-audit/1','passed':True,'counts':counts,'goals':goals,'Core_loaded':False,'simulation_advanced':False}
    m.original(w/'audit-v1.json',out);print(json.dumps(out))
