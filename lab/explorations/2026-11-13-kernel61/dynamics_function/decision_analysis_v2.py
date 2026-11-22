"""R51t4 read-only continuity, truth-isolation and independent arithmetic checks."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal,localcontext
import json
import math
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import decision as h
d=h.d;e=h.e;s=h.s

def analyze(work):
    h.check(work);assert h.read(work/'summary.json')['complete']==64 and not (work/'in-flight.json').exists()
    answers=[];counts={'systems':0,'states':0,'phases':0,'inputs':0};maxerr=0.;subjectstats=[]
    for c in h.read(work/'cases.json'):
        folder=work/'cases'/c['key'];r=h.read(folder/'result.json');assert r['status']=='complete' and r['phases']==24
        ids,_=d.mapping(c['seed']);born=e.base.image(folder/'initial.tmind');last=born.digest;clock=0
        assert born.digest==r['initial_sha256'] and born.to_dict()['config']==e.base.resolve_kernel('threemind.continuous-memory/6.1').configuration(r['config']).to_dict()
        phases=['00-teaching','01-review']+[name for i in range(4) for name in (f'02-dev{i}',f'03-correction{i}')]+[f'04-final{i:02d}' for i in range(14)]
        saturation=0;denom=0;previous_ob=None
        for name in phases:
            f=folder/name;pr=h.read(f/'result.json');a=e.base.image(f/'initial.tmind');z=e.base.image(f/'final.tmind')
            assert a.digest==last==pr['initial_sha256'] and z.digest==pr['final_sha256']
            assert int(a.to_dict()['time_us'])==clock==pr['begin_us'] and int(z.to_dict()['time_us'])==pr['end_us']
            assert a.to_dict()['dynamics']==z.to_dict()['dynamics']=='threemind.continuous-memory/6.1'
            assert z.to_dict()['config']==born.to_dict()['config']
            first_ob=e.unpacked(f/'initial-observer.json.xz');ob=e.unpacked(f/'observer.json.xz')
            if previous_ob is not None:assert first_ob==previous_ob
            assert ob['input_bus']['pending']=={};previous_ob=ob
            inputs=e.unpacked(f/'inputs.json.xz');delivered=e.unpacked(f/'delivered.json.xz')
            assert len(inputs)==len(delivered)==pr['inputs']
            normal=lambda stim:json.dumps({'time_us':int(stim['time_us']),'channels':stim['channels'],'intensity':stim['intensity']},sort_keys=True)
            assert Counter((normal(x),x['source']) for x in inputs)==Counter((normal(x['stimulus']),x['source']) for x in delivered)
            assert all(int(x['stimulus']['time_us'])==int(x['scheduled_time_us'])==int(x['delivered_time_us']) and not x.get('labels') for x in delivered)
            points=e.unpacked(f/'trajectory.json.xz')
            assert points[0]['time_us']==clock and points[-1]['time_us']==pr['end_us']
            assert [p['time_us'] for p in points]==list(range(clock,pr['end_us']+1,50000))
            assert all(set(n)=={'channel',*d.FIELDS} for p in points for n in p['nodes'])
            counts['states']+=2;counts['phases']+=1;counts['inputs']+=len(inputs)
            if name.startswith('04-final'):
                qi=int(name[-2:]);q=c['tests'][qi];assert pr['question']==q
                forbidden={ids['C'],ids['E']}
                assert all(not any(ch in forbidden for ch,val in x['channels']) for x in inputs)
                pulses,duration,origin=d.question(c,q);assert duration==pr['end_us']-clock
                actual=[(x['time_us']-clock,x['channels'],x['intensity']) for x in inputs if x['source']=='test-cue']
                assert actual==[(t,[[ids[k],1.] for k in names],strength) for t,names,strength in pulses]
                window=[p for p in points if p['time_us']>=pr['end_us']-500000]
                fields={}
                for field in d.FIELDS:
                    fields[field]={}
                    for label in ('C','E'):
                        with localcontext() as ctx:
                            ctx.prec=45
                            area=sum((Decimal(str(next((n[field] for n in aa['nodes'] if n['channel']==ids[label]),0.)))+
                                Decimal(str(next((n[field] for n in bb['nodes'] if n['channel']==ids[label]),0.))))*
                                Decimal(bb['time_us']-aa['time_us'])/Decimal(2000000) for aa,bb in zip(window,window[1:]))
                        fields[field][label]=float(area)
                delta=fields['activation']['C']-fields['activation']['E'];ans=pr['answer']
                maxerr=max(maxerr,abs(delta-ans['margin_C_minus_E']));assert maxerr<1e-11
                choice=('C' if delta>0 else 'E') if abs(delta)>1e-6 else 'WAIT'
                assert choice==ans['choice'] and ans['expected']==d.expected(c,q['cue']) and ans['correct']==(choice==ans['expected'])
                category='blank' if q['cue'] is None else 'distractor' if q['distractor'] else 'short' if q['delay']<=3 else 'long'
                sat=sum(n['activation']>=.95 for p in points for n in p['nodes'] if n['channel'] in {ids[k] for k in 'ABCDE'})
                total=len(points)*5;saturation+=sat;denom+=total
                answers.append({k:c[k] for k in ('key','block','seed','task','swap','profile')}|{'question_index':qi,'category':category,
                    **q,**ans,'process_integrals':fields,'saturated':sat,'observations':total})
            last=z.digest;clock=pr['end_us']
        assert e.base.image(folder/'final.tmind').digest==last==r['final_sha256'] and clock==r['end_us']
        assert e.unpacked(folder/'observer.json.xz')==previous_ob
        counts['states']+=2;counts['systems']+=1
        subjectstats.append({k:c[k] for k in ('block','task','swap','profile')}|{'saturation_fraction':saturation/denom})
        if counts['systems']%8==0:print('audited decision',counts['systems'],flush=True)
    blocks=[]
    for block in range(4):
        for task in ('pair','prefix'):
            for profile in d.PROFILES:
                rows=[r for r in answers if (r['block'],r['task'],r['profile'])==(block,task,profile)]
                row={'block':block,'task':task,'profile':profile}
                for cat in ('short','long','distractor','blank'):
                    rr=[r for r in rows if r['category']==cat];row[cat]={'correct':sum(r['correct'] for r in rr),'total':len(rr),'accuracy':sum(r['correct'] for r in rr)/len(rr)}
                row['saturation_fraction']=sum(r['saturated'] for r in rows)/sum(r['observations'] for r in rows)
                row['prefix_recovery']=task=='prefix' and all(all(r['correct'] for r in rows if r['category']=='short' and r['swap']==swap)
                    and sum(r['correct'] for r in rows if r['category']=='long' and r['swap']==swap)>=3 for swap in (0,1))
                blocks.append(row)
    benefits=[]
    for task in ('pair','prefix'):
        for profile in ('short-inhibition','prefix-candidate'):
            passed=[]
            for b in range(4):
                get=lambda p:next(r for r in blocks if (r['block'],r['task'],r['profile'])==(b,task,p))
                a,z=get('reference'),get(profile)
                passed.append(z['long']['accuracy']-a['long']['accuracy']>=.1-1e-12 and z['long']['accuracy']>=.75 and
                    z['short']['accuracy']>=a['short']['accuracy']-.05 and z['saturation_fraction']<=.1)
            benefits.append({'task':task,'profile':profile,'passed_blocks':sum(passed),'functional_benefit':sum(passed)>=3})
    summary={'counts':counts,'material_blocks':4,'answers':answers,'blocks':blocks,'benefits':benefits,'subject_saturation':subjectstats,
        'maximum_arithmetic_error':maxerr,'defaults_changed':False,'campaign_paused':True}
    s.base.original(work/'analysis.json',summary);s.base.original(work/'audit.json',{'passed':True,**counts,
        'maximum_arithmetic_error':maxerr,'apparatus':h.read(work/'apparatus.json')})
    print(json.dumps({'counts':counts,'benefits':benefits}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();analyze(a.work)
