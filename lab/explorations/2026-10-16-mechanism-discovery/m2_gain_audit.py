"""Independent file/lineage arithmetic; never instantiates a subject."""
import argparse,copy,gzip,hashlib,json
from pathlib import Path
import closure_audit as oldcheck
import m2_gain_rig as spec
from m2_gain_predictor import predict
from m2_threshold_predictor import predict as old_predict
import pilot_m2 as m


def load(p):return json.loads(gzip.decompress(p.read_bytes()))


def unit_audit(folder,raw):
    baseline=load(folder/'baseline.json.gz');oldcheck.probe_check(baseline,raw['baseline'])
    assert baseline['time_us']==48500000
    birth=load(folder/'birth.json.gz');assert birth['time_us']==0 and birth['seed']==raw['case']['seed'] and not birth['model']['nodes']
    count=0;correct=0;error=0.;classes=set()
    for h in raw['histories']:
        history=h['history'];initial=load(folder/f'h{history}-initial.json.gz')
        expected=copy.deepcopy(baseline);expected['branch']=initial['branch'];assert initial==expected
        assert initial['branch']['parent_sha256']==m.digest(baseline)
        for j,r in enumerate(h['lessons'],1):
            p=folder/r['checkpoint']['path'];s=load(p);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['checkpoint']['sha256']
            oldcheck.probe_check(s,r['probe']);assert s['time_us']==48500000+j*3500000
            start=s['time_us']-3500000
            taught=[v['values'] for v in s['inputs'] if v['time_us']==start and set(v['values']) in ({'X','Y','A'},{'X','Y','B'})]
            assert taught==[dict.fromkeys('XYA' if history==0 else 'XYB',.4)]
        parent=load(folder/f'h{history}-lesson16.json.gz')
        for d in h['delays']:
            s=load(folder/d['checkpoint']['path']);wait=int(d['delay']*1e6)
            assert s['branch']['parent_sha256']==m.digest(parent) and s['time_us']==104500000+wait
            assert s['inputs'][len(parent['inputs']):]==[{'time_us':104500000+t,'values':{'K':.2}} for t in range(500000,wait+1,500000)]
        assert {(r['delay'],r['dose']) for r in h['tests']}=={(d,q) for d in spec.DELAYS for q in spec.DOSES}
        for r in h['tests']:
            a=load(folder/r['initial']['path']);b=load(folder/r['checkpoint']['path'])
            parent=load(folder/f'h{history}-delay{r["delay"]}.json.gz')
            expected=copy.deepcopy(parent);expected['branch']=a['branch'];assert a==expected and a['branch']['parent_sha256']==m.digest(parent)
            for key in ('initial','checkpoint'):assert hashlib.sha256((folder/r[key]['path']).read_bytes()).hexdigest()==r[key]['sha256']
            start=104500000+int(r['delay']*1e6)
            assert (a['time_us'],b['time_us'])==(start,start+150000)
            assert b['inputs'][:len(a['inputs'])]==a['inputs'] and b['inputs'][len(a['inputs']):]==([{'time_us':start,'values':{'X':r['dose']}}] if r['dose'] else [])
            assert b['rows'][:len(a['rows'])]==a['rows']
            rows=b['rows'][len(a['rows']):];assert [x['time_us'] for x in rows]==list(range(start+1000,start+150001,1000))
            actual=next(v['response'] for v in rows if v['time_us']==start+110000)
            direction=int(actual>1e-4)-int(actual<-1e-4)
            assert actual==r['probe']['first'] and direction==r['probe']['direction'] and m.digest(b)==r['probe']['final_sha256']
            assert r['prediction']==predict(a,r['dose']) and r['comparison']==old_predict(a,r['dose'])
            label=r['initial']['path'].removesuffix('-initial.json.gz');p=folder/(label+'-prediction.json')
            assert m.read(p)=={'gain_aware':r['prediction'],'original':r['comparison']}
            assert p.stat().st_mtime_ns<=(folder/r['checkpoint']['path']).stat().st_mtime_ns
            count+=1;correct+=direction==r['prediction']['direction'];error=max(error,abs(actual-r['prediction']['endpoint']))
            if r['dose']>0:classes.add(abs(actual)<=1e-4)
    wholes=len(list(folder.glob('*.json.gz')))
    assert wholes==81 and count==20
    return {'whole_states':wholes,'cultivation_probes':33,'diagnostics':count},correct==20 and error<=1e-6 and len(classes)==2


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);w=p.parse_args().work
    m.frozen_check(w);a=m.read(w/'analysis-v1.json');counts={};qualified=0
    assert not any((w/n).exists() for n in ('STOP','in-flight.json'))
    for case in spec.cases():
        folder=w/'units'/f'o{case["origin"]}';raw=m.read(folder/'result.json');assert raw['case']==case
        c,q=unit_audit(folder,raw);qualified+=q
        assert next(r['qualified'] for r in a['units'] if r['origin']==case['origin'])==q
        for k,v in c.items():counts[k]=counts.get(k,0)+v
    assert qualified==a['qualified'] and a['verdict']==('PASS' if qualified>=6 else 'FAIL')
    out={'schema':'threemind.m2-gain-file-audit/1','passed':True,'counts':counts,'qualified':qualified,'Core_loaded':False,'simulation_advanced':False}
    m.original(w/'audit-v1.json',out);print(json.dumps(out))
