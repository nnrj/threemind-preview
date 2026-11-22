"""Read-only historical and synthetic checks; never creates a subject."""
import copy,gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import materials_timescales as mat
import measurement_timescales as m

def check():
    rows=[]
    for c in mat.inventory():
        if c['kind']!='probe':continue
        old=mat.read(mat.OLD/'cases'/c['key']/'result.json')['extra']
        target='C' if c['cue'] in ('A','AB') else 'E'
        if c['swap']:target='E' if target=='C' else 'C'
        other='E' if target=='C' else 'C'
        r={'key':c['key'],'signed_peak':old['post_cue'][target]['peak']-old['post_cue'][other]['peak']}
        if c['key'].startswith('sustain/'):
            with gzip.open(mat.OLD/'cases'/c['key']/'trajectory.jsonl.gz','rb') as f:points=[json.loads(line) for line in f]
            amps=[(p['relative_us'],max((n['activation'] for n in p['nodes'] if n['channel'] in mat.TOKENS.values()),default=0)) for p in points]
            r['task_activity']={'first':amps[0][1],'end':amps[-1][1],'maximum':max(v for _,v in amps),
                'minimum':min(v for _,v in amps),'last_positive_us':max((t for t,v in amps if v>0),default=None)}
        rows.append(r)
    old=m.decide(rows);assert not old['scientific_stop']
    checks={}
    for name in ('retention','test_L_off','prefix','sustained'):
        changed=copy.deepcopy(rows)
        for row in changed:
            key=row['key']
            if name=='retention' and key.startswith('retention/') and '/101/paired/d30/' in key:row['signed_peak']=0.
            if name=='test_L_off' and key.startswith('readout/') and '/101/paired/d30/' in key:row['signed_peak']=0.
            if name=='prefix' and key.startswith(('short/','history/')) and '/101/' in key:row['signed_peak']=0.
            if name=='sustained' and key.startswith('sustain/'):row['task_activity']['end']=0.
        checks[name]=m.decide(changed)['scientific_stop'];assert checks[name]
    c={'key':'synthetic','probe_start_us':0,'gap_s':1,'cue':'A','swap':False}
    points=[{'time_us':t,'nodes':[{'channel':mat.TOKENS[symbol],**{field:value for field in m.FIELDS}} for symbol,value in [('C',1.),('E',.2)]]} for t in [0]+list(range(0,15000001,10000))]
    positive=m.process(c,points)
    assert abs(positive['signed_area']-12)<1e-12 and positive['signed_peak']==.8
    assert m.process(c|{'swap':True},points)['signed_peak']==-.8
    assert m.process(c|{'cue':'B'},points)['measures']['C']['activation']['area']==14
    zero=[{'time_us':p['time_us'],'nodes':[]} for p in points]
    assert m.process(c,zero)['signed_area']==m.process(c,zero)['signed_peak']==0
    result={'passed':True,'created_engines':0,'historical_stop':old['scientific_stop'],
        'negative_outcomes_detected':checks,'synthetic_cases':4,'maximum_arithmetic_error':positive['arithmetic_error'],
        'measurement_source_sha256':mat.sha(Path(m.__file__))}
    return result

if __name__=="__main__":
    print(json.dumps(check()))
