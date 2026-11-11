"""Independent file and arithmetic checks of whole parents/copies and timelines."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import closure_audit as check
import m2_cue_rig as spec
import pilot_m2 as m
from pilot_m1 import differences


def load(path):return json.loads(gzip.decompress(path.read_bytes()))


def unit_audit(folder,result):
    counts={'diagnostics':0,'cultivation_probes':1,'whole_snapshots':0,'restorations':0}
    baseline=load(folder/'baseline.json.gz');check.probe_check(baseline,result['baseline'])
    assert baseline['time_us']==48_500_000
    assert result['baseline']['start_us']==47_000_000
    for role,rows in result['cultivation'].items():
        assert len(rows)==16
        for j,row in enumerate(rows,1):
            path=folder/row['checkpoint']['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['checkpoint']['sha256']
            whole=load(path);check.probe_check(whole,row['probe'])
            start=48_500_000+(j-1)*3_500_000
            assert row['lesson']==j and row['start_us']==start and row['end_us']==whole['time_us']==start+3_500_000
            frames=[x['values'] for x in whole['inputs'] if x['time_us']==start]
            # Previous probe maintenance K at this same boundary remains in history.
            taught=[v for v in frames if set(v) in ({'X','Y','A'},{'X','Y','B'})]
            assert taught==([] if role=='untaught' else [dict.fromkeys('XYA' if role=='h0' else 'XYB',.4)])
            counts['cultivation_probes']+=1
    assert len(result['diagnostics'])==24
    for row in result['diagnostics']:
        h,name,cue=row['history'],row['arm'],row['cue']
        parent=load(folder/(('untaught' if name=='untaught' else f'h{h}')+'-lesson16.json.gz'))
        initial=load(folder/row['initial']['path']);final=load(folder/row['checkpoint']['path'])
        for key in ('initial','checkpoint'):
            assert hashlib.sha256((folder/row[key]['path']).read_bytes()).hexdigest()==row[key]['sha256']
        assert initial['time_us']==104_500_000 and final['time_us']==106_000_000
        assert initial['branch']['parent_sha256']==m.digest(parent)
        expected=copy.deepcopy(parent);expected['branch']=initial['branch']
        paths=differences(expected,initial)
        if name=='silenced':
            assert paths and set(paths)<={'model.silenced_edges'}
            assert {tuple(e) for e in initial['model']['silenced_edges']} == {
                tuple(e) for e in parent['model']['silenced_edges']} | {
                (e['source'],e['target']) for e in parent['model']['edges']}
        else:assert initial==expected
        if name=='restored':assert row['intervention']['restored_exact'];counts['restorations']+=1
        new=final['inputs'][len(initial['inputs']):]
        expected_inputs=[] if cue=='blank' else [{'time_us':104_500_000,'values':{'X':row['dose']}}]
        expected_inputs += [{'time_us':104_500_000+t,'values':{'K':.2}} for t in (500_000,1_000_000,1_500_000)]
        assert new==expected_inputs
        check.probe_check(final,row['probe']);counts['diagnostics']+=1
    files=list(folder.glob('*.json.gz'));assert len(files)==102
    counts['whole_snapshots']=len(files)
    return counts


def independently_qualifies(result):
    for history in (0,1):
        sign=1-2*history
        cells={(r['arm'],r['cue']):r['probe']['first'] for r in result['diagnostics'] if r['history']==history}
        weak=sign*cells['intact','weak'];strong=sign*cells['intact','strong']
        if weak>1e-4 or strong<=1e-4 or strong-weak<=1e-4:return False
        if abs(cells['intact','blank'])>1e-4 or abs(cells['untaught','strong'])>1e-4:return False
        if abs(cells['silenced','strong'])>.25*abs(strong):return False
        if abs(cells['restored','strong']-cells['intact','strong'])>1e-9:return False
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);work=p.parse_args().work
    m.frozen_check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json'))
    counts={};qualifications=[]
    analysis=m.read(work/'analysis-v1.json')
    for case in spec.cases():
        folder=work/'units'/f'o{case["origin"]}';raw=m.read(folder/'result.json');assert raw['case']==case
        for k,v in unit_audit(folder,raw).items():counts[k]=counts.get(k,0)+v
        passed=independently_qualifies(raw);qualifications.append(passed)
        assert passed==next(u['passed'] for u in analysis['units'] if u['origin']==case['origin'])
    assert sum(qualifications)==analysis['D1_qualifying_origins']
    assert analysis['verdict']==('PASS' if sum(qualifications)>=6 else 'FAIL')
    out={'schema':'threemind.m2-cue-file-audit/1','passed':True,'counts':counts,'Core_loaded':False,'simulation_advanced':False}
    m.original(work/'audit-v1.json',out);print(json.dumps(out))
