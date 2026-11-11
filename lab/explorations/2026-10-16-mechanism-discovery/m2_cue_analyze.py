"""Read-only frozen diagnostic endpoints; no simulation."""
import argparse
import gzip
import json
from pathlib import Path
from scipy.stats import beta
import m2_cue_rig as spec
import pilot_m2 as m


def scores(result, folder):
    summaries=[]
    for h in (0,1):
        sign=1 if h==0 else -1
        cells={(r['arm'],r['cue']):r for r in result['diagnostics'] if r['history']==h}
        def first(arm,cue):return cells[arm,cue]['probe']['first']
        strong=first('intact','strong');weak=first('intact','weak')
        conditions={'weak_endpoint_failure':sign*weak<=1e-4,
                    'strong_expression':sign*strong>1e-4,
                    'paired_dose_gain':sign*(strong-weak)>1e-4,
                    'blank_absent':abs(first('intact','blank'))<=1e-4,
                    'untaught_absent':abs(first('untaught','strong'))<=1e-4,
                    'connection_dependence':abs(first('silenced','strong'))<=.25*abs(strong),
                    'rescue_exact':abs(first('restored','strong')-strong)<=1e-9}
        traces={}
        for cue in ('blank','weak','strong'):
            row=cells['intact',cue];whole=json.loads(gzip.decompress((folder/row['checkpoint']['path']).read_bytes()))
            start=row['probe']['start_us']
            values=[r for r in whole['rows'] if start<r['time_us']<=start+1_500_000]
            assert len(values)==1500
            peak=max(sign*r['response'] for r in values)
            traces[cue]={'signed_peak':peak,
                         'first_directional_us':next((r['time_us']-start for r in values if sign*r['response']>1e-4),None),
                         'early_integral':row['probe']['early_integral'], 'late_integral':row['probe']['late_integral']}
        temporal=('endpoint-correct' if sign*weak>1e-4 else
                  'endpoint-missed-window-response' if traces['weak']['signed_peak']>1e-4 else 'no-expression-in-window')
        summaries.append({'history':h,'conditions':conditions,'passed':all(conditions.values()),
                          'signed_weak':sign*weak,'signed_strong':sign*strong,
                          'paired_gain':sign*(strong-weak),'temporal_class':temporal,'traces':traces})
    return {'origin':result['origin'],'histories':summaries,'passed':all(r['passed'] for r in summaries)}


def evaluate(units):
    assert len(units)==spec.N and {u['origin'] for u in units}==set(range(spec.N))
    k=sum(u['passed'] for u in units);n=len(units)
    classes={}
    for u in units:
        for h in u['histories']:classes[h['temporal_class']]=classes.get(h['temporal_class'],0)+1
    return {'schema':'threemind.m2-cue-diagnostic-analysis/1','valid':True,'verdict':'PASS' if k>=6 else 'FAIL',
            'independent_origins':n,'D1_qualifying_origins':k,
            'qualification_exact95':[0 if k==0 else float(beta.ppf(.025,k,n-k+1)),1 if k==n else float(beta.ppf(.975,k+1,n-k))],
            'D2_history_counts':classes,'D2_source_counts':{c:sum(any(h['temporal_class']==c for h in u['histories']) for u in units) for c in classes},
            'units':units,'study_phase':'exploratory fixed-parent expression diagnosis; not savings confirmation'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);work=p.parse_args().work
    assert m.read(work/'status.json')['state']=='awaiting-analysis'
    units=[]
    for case in spec.cases():
        folder=work/'units'/f'o{case["origin"]}';raw=m.read(folder/'result.json');assert raw['case']==case
        units.append(scores(raw,folder))
    result=evaluate(units);m.original(work/'analysis-v1.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='units'}))
