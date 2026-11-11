"""Secondary, read-only explanation of completed R46a primary outcomes.

Specified while the batch was running, before full-batch outcomes. Does not
replace any registered metric. Endpoint absence is a state classification,
not a claim about which deletion happened first.
"""
from pathlib import Path
import gzip
import hashlib
import json
import math
import statistics

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')
FIELDS=('activation','inhibition','direct','associative')

def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rms(xs):return math.sqrt(math.fsum(x*x for x in xs)/len(xs))

def coordinate_range(vectors):
    """Largest coordinate range, or None when structures are not comparable."""
    if not vectors or len({len(v) for v in vectors})!=1:return None
    return max((max(column)-min(column) for column in zip(*vectors)),default=0.)


def numeric_outcome(row):
    def edges(values):
        return sorted((e['source_symbol'],e['target_symbol'],e['weight'],e['half_life']) for e in values)
    return dict(formed=row['formed'],surviving=row['surviving'],
        initial=edges(row['initial_connections']),current=edges(row['current_connections']),
        forecast=row['forecast_30days'],response=row['response_vector'])


def variation(items):
    """Keep exact diversity and its magnitude; rounding noise is not a new context."""
    outcomes=[item['numeric'] for item in items]
    result={key:coordinate_range([o[key] for o in outcomes]) for key in ('response','forecast')}
    for stage in ('initial','current'):
        structures={tuple((e[0],e[1]) for e in o[stage]) for o in outcomes}
        result[stage+'_structures']=len(structures)
        for name,index in (('weight',2),('timescale',3)):
            result[stage+'_'+name]=(coordinate_range([[e[index] for e in o[stage]] for o in outcomes])
                if len(structures)==1 else None)
    return result


def contrast(lookup,origin,curve,relaxation,course,delay):
    parts={}
    for h in (0,1):
        a=lookup[origin,curve,relaxation,course,h,delay,True]['response_vector']
        b=lookup[origin,curve,relaxation,course,h,delay,False]['response_vector']
        parts[h]=[x-y for x,y in zip(a,b)]
    return [b-a for a,b in zip(parts[0],parts[1])]

def main():
    assert load(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json'))
    audit=load(WORK/'independent-audit-v1.json')
    assert audit['passed'] and audit['complete_boundaries']==3840
    primary=load(WORK/'analysis-v1.json');lookup={};loss=[];fields=[]
    for row in primary['rows']:
        c=row['case']
        lookup[c['origin'],c['curve'],c['relaxation'],c['course'],c['history'],c['delay'],c['cue']]=row
        if c['delay']!=300 or not c['cue']:continue
        root=WORK/'subjects'/c['key']
        result=load(root/'probe/result.json.gz')
        before=result['before']
        endpoints={n['id'] for n in before['nodes']}
        initial=row['initial_connections']
        current={(e['source'],e['target']) for e in row['current_connections']}
        missing=[e for e in initial if (e['source'],e['target']) not in current]
        loss.append(dict(case=c,formed=row['formed'],surviving=row['surviving'],
            missing_edges_with_both_endpoints=sum(e['source'] in endpoints and e['target'] in endpoints for e in missing),
            missing_edges_with_missing_endpoint=sum(e['source'] not in endpoints or e['target'] not in endpoints for e in missing),
            missing_endpoint_does_not_identify_deletion_order=True,
            taught_timescales=[e['half_life'] for e in initial],
            surviving_timescales=[e['half_life'] for e in row['current_connections']]))
    for origin in range(8):
        for condition in primary['conditions']:
            curve,relaxation=condition['curve'],condition['relaxation']
            for course in ('weak','ordinary','strong','massed','spaced'):
                early=contrast(lookup,origin,curve,relaxation,course,1)
                late=contrast(lookup,origin,curve,relaxation,course,300)
                measurements={}
                for k,field in enumerate(FIELDS):
                    a,b=early[k::4],late[k::4]
                    ra,rb=rms(a),rms(b)
                    measurements[field]=dict(early_rms=ra,late_rms=rb,
                        ratio=rb/ra if ra else None,
                        cosine=math.fsum(x*y for x,y in zip(a,b))/(len(a)*ra*rb) if ra and rb else None,
                        early_by_frame=[a[i:i+2] for i in range(0,len(a),2)],
                        late_by_frame=[b[i:i+2] for i in range(0,len(b),2)])
                fields.append(dict(origin=origin,curve=curve,relaxation=relaxation,course=course,fields=measurements))
    # The fixture has a fixed course and disables energy consumption. Distinct
    # births/remapped channel IDs need not generate distinct numeric paths.
    # Count this explicitly rather than interpret a degenerate bootstrap as
    # population-level precision.
    origin_groups={}
    for row in primary['rows']:
        c=row['case'];key=(c['curve'],c['relaxation'],c['course'],c['history'],c['delay'],c['cue'])
        numeric=numeric_outcome(row)
        fp=hashlib.sha256(json.dumps(numeric,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        origin_groups.setdefault(key,[]).append(dict(origin=c['origin'],fingerprint=fp,numeric=numeric))
    diversity=[]
    for key,items in origin_groups.items():
        assert len(items)==8 and {x['origin'] for x in items}==set(range(8))
        diversity.append(dict(condition=dict(zip(('curve','relaxation','course','history','delay','cue'),key)),
            births=8,distinct_numeric_outcomes=len({x['fingerprint'] for x in items}),
            maximum_coordinate_ranges=variation(items),
            origins=[{k:v for k,v in item.items() if k!='numeric'} for item in items]))
    summary=[]
    for condition in primary['conditions']:
        curve,relaxation=condition['curve'],condition['relaxation']
        for course in ('weak','ordinary','strong','massed','spaced'):
            selected=[r for r in loss if r['case']['curve']==curve and r['case']['relaxation']==relaxation and r['case']['course']==course]
            assert len(selected)==16
            taught_h=[h for r in selected for h in r['taught_timescales']]
            summary.append(dict(curve=curve,relaxation=relaxation,course=course,histories=16,
                original_edges=sum(len(r['taught_timescales']) for r in selected),
                surviving_edges=sum(r['surviving'] for r in selected),
                missing_edges_with_both_endpoints=sum(r['missing_edges_with_both_endpoints'] for r in selected),
                missing_edges_with_missing_endpoint=sum(r['missing_edges_with_missing_endpoint'] for r in selected),
                taught_timescale_range=[min(taught_h),max(taught_h)] if taught_h else None,
                taught_timescale_median=statistics.median(taught_h) if taught_h else None))
    out=dict(schema='threemind.decay-assay-secondary/1',
        status='secondary descriptive analysis; primary criteria unchanged',
        independent_origins=8,source_sha256=digest(Path(__file__)),
        primary_sha256=digest(WORK/'analysis-v1.json'),summary=summary,endpoint_states=loss,field_processes=fields,
        origin_diversity=diversity,
        fixed_course_identity_remapping_note='Independent births do not imply diverse numeric trajectories. Report actual diversity.')
    with (WORK/'secondary-diagnostics-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(secondary_complete=True,condition_courses=len(summary),origin_courses=len(fields))))

if __name__=='__main__':main()
