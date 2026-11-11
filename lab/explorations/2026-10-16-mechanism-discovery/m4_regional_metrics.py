"""Prospective M4 measurements: pure files/arrays, never advance a subject.

Selection is fit only to pre-training and development frames. Confirmation and
causal outcomes cannot update the fitted nuisance model, groups or edge lists.
"""
import math
from collections import Counter
import numpy as np
from scipy.optimize import linear_sum_assignment

GROUP_SIZE=4
EDGES_PER_NODE=4
RIDGE=1.
MIN_SELECTIVITY=.5
MIN_GAIN=.5
CALIPERS={'effective_weight':.02,'degree':2,'activity':.01}
BACKGROUND=('acceleration_x_m_s2','acceleration_y_m_s2','air_temperature_K',
            'body_temperature_K','motor_power_W','relative_humidity','wind_x_m_s','wind_y_m_s')


def channel_classes(channels,vision_width):
    assert len(channels)==vision_width+42
    kinds=['vision']*vision_width+['body']*8+['weather']*20+['contact']*4+['eye']*10
    return {int(ch):kind for ch,kind in zip(channels,kinds)}


def reduce_trial(task,rows,classes):
    channels=sorted(classes);index={c:i for i,c in enumerate(channels)}
    values=[];common=[];regions={};ids={}
    for i,r in enumerate(rows):
        a=np.zeros((len(channels),4))
        for n in r['activity']['nodes']:
            c=int(n['channel'])
            if c in index:
                a[index[c]]=[n[k] for k in ('activation','inhibition','direct','associative')]
                regions[c]=int(n['region']);ids[c]=int(n['id'])
        ob=r['observation'];p=ob['pointer'];b=ob['physical_background']
        common.append([(i+1)/len(rows),ob['time_s'],*task['xy'],*ob['eye_angle_rad'],*ob['eye_velocity_rad_s'],
                       p['x'],p['y'],p['vx'],p['vy'],*[b[k] for k in BACKGROUND]])
        values.append(a.tolist())
    return {'id':task['id'],'mode':task['mode'],'channels':channels,'classes':classes,
            'regions':regions,'node_ids':ids,'values':values,'common':common,'frames':len(rows)}


def _data(trials,phase,channels):
    for r in trials:assert r['channels']==channels and len(r['values'])==r['frames']==60
    values=np.concatenate([r['values'] for r in trials],axis=0)
    common=np.concatenate([r['common'] for r in trials],axis=0)
    return values,np.column_stack([np.full(len(values),phase),common])


def _design(values,common,j,channels,classes,regions):
    c=channels[j];sameclass=[k for k,x in enumerate(channels) if classes[x]==classes[c]]
    sameregion=[k for k,x in enumerate(channels) if regions.get(x)==regions.get(c)]
    return np.column_stack([common,values[:,j,2],values[:,sameclass,2].mean(axis=1),values[:,sameregion,2].mean(axis=1)])


def _means(residual,trials):
    return np.array([residual[i*60:(i+1)*60].mean(axis=0) for i in range(len(trials))])


def _contrast(means,trials,early=None):
    use=list(range(len(trials)))
    if early is not None:use=use[:6] if early else use[6:]
    eye=[i for i in use if trials[i]['mode']=='eye'];hand=[i for i in use if trials[i]['mode']=='hand']
    assert len(eye)==len(hand) and eye
    return means[eye].mean(axis=0)-means[hand].mean(axis=0)


def fit_groups(pre,development,classes):
    assert len(pre)==len(development)==12
    classes={int(k):v for k,v in classes.items()};channels=sorted(classes)
    regions={int(k):v for r in development for k,v in r['regions'].items()}
    ids={int(k):v for r in development for k,v in r['node_ids'].items()}
    pv,pc=_data(pre,0,channels);dv,dc=_data(development,1,channels)
    values=np.concatenate([pv,dv]);common=np.concatenate([pc,dc]);residual=np.zeros(values.shape[:2]);fits=[]
    for j,c in enumerate(channels):
        if c not in regions:
            fits.append(None);continue
        x=_design(values,common,j,channels,classes,regions);mu=x.mean(axis=0);scale=np.maximum(x.std(axis=0),1e-8)
        x=np.column_stack([np.ones(len(x)),(x-mu)/scale]);y=values[:,j,3]
        ym=float(y.mean());ys=max(float(y.std()),1e-5)
        penalty=np.eye(x.shape[1])*RIDGE;penalty[0,0]=0
        coef=np.linalg.solve(x.T@x+penalty,x.T@((y-ym)/ys))
        residual[:,j]=(y-ym)/ys-x@coef
        fits.append({'mean':mu.tolist(),'scale':scale.tolist(),'coef':coef.tolist(),'y_mean':ym,'y_scale':ys})
    before=_contrast(_means(residual[:len(pv)],pre),pre)
    after=_contrast(_means(residual[len(pv):],development),development)
    gain=after-before;groups={}
    for name,sign in (('eye',1),('hand',-1)):
        eligible=[j for j,c in enumerate(channels) if fits[j] is not None and dv[:,j,3].mean()>=1e-5
                  and sign*after[j]>=MIN_SELECTIVITY and sign*gain[j]>=MIN_GAIN]
        chosen=sorted(eligible,key=lambda j:(-sign*gain[j],channels[j]))[:GROUP_SIZE]
        groups[name]={'channels':[channels[j] for j in chosen],'nodes':[ids[channels[j]] for j in chosen],
                      'eligible':len(eligible),'complete':len(chosen)==GROUP_SIZE}
    return {'schema':'threemind.m4-regional-selection/1','channels':channels,'classes':classes,'regions':regions,
            'fits':fits,'pre_contrast':before.tolist(),'development_contrast':after.tolist(),'gain':gain.tolist(),
            'mean_activation':dv[:,:,0].mean(axis=0).tolist(),'groups':groups,
            'fit_sources':'pre and development only; no confirmation or causal outcomes'}


def confirm_groups(selection,trials):
    channels=selection['channels'];classes={int(k):v for k,v in selection['classes'].items()}
    regions={int(k):v for k,v in selection['regions'].items()};v,c=_data(trials,1,channels);residual=np.zeros(v.shape[:2])
    for j,f in enumerate(selection['fits']):
        if f is None:continue
        x=_design(v,c,j,channels,classes,regions)
        x=np.column_stack([np.ones(len(x)),(x-np.array(f['mean']))/np.array(f['scale'])])
        residual[:,j]=(v[:,j,3]-f['y_mean'])/f['y_scale']-x@np.array(f['coef'])
    means=_means(residual,trials);contrast=_contrast(means,trials);early=_contrast(means,trials,True);late=_contrast(means,trials,False)
    out={}
    for name,sign in (('eye',1),('hand',-1)):
        g=selection['groups'][name];indices=[channels.index(ch) for ch in g['channels']]
        def avg(a):return float(sign*np.mean(np.asarray(a)[indices])) if indices else None
        result={'complete':g['complete'],'selectivity':avg(contrast),'gain_over_pre':avg(contrast-np.array(selection['pre_contrast'])),
                'early':avg(early),'late':avg(late)}
        result['qualified']=bool(g['complete'] and result['selectivity']>=.5 and result['gain_over_pre']>=.5 and result['early']>=.25 and result['late']>=.25)
        out[name]=result
    return {'groups':out,'qualified':all(x['qualified'] for x in out.values()),'fixed_fit':True}


def edge_table(graph,config,time_us,selection):
    nodes={int(n['id']):n for n in graph['nodes']};degrees=Counter()
    for e in graph['edges']:degrees[(e['source'],'out')]+=1;degrees[(e['target'],'in')]+=1
    channels=selection['channels'];activity=dict(zip(channels,selection['mean_activation']))
    classes={int(k):v for k,v in selection['classes'].items()};table=[]
    for e in graph['edges']:
        s,t=e['source'],e['target'];sn,tn=nodes[s],nodes[t];sc,tc=int(sn['channel']),int(tn['channel'])
        if sc not in classes or tc not in classes:continue
        fast=e.get('fast');eff=float(e['weight'])
        if config['fast_enabled'] and fast:
            eff=min(1.,eff+config['fast_gain']*fast['value']*math.exp(-(time_us-int(fast['time_us']))/1e6/config['fast_tau_s']))
        table.append({'key':[s,t],'effective_weight':eff,'degrees':[degrees[(s,'in')],degrees[(s,'out')],degrees[(t,'in')],degrees[(t,'out')]],
                      'activity':[activity.get(sc,0.),activity.get(tc,0.)],
                      'parent_activity':[float(sn['activation']),float(tn['activation'])],
                      'stratum':[classes[sc],classes[tc],int(sn['region']),int(tn['region'])]})
    return table


def residual(a,b):
    return {'effective_weight':abs(a['effective_weight']-b['effective_weight']),
            'degrees':[abs(x-y) for x,y in zip(a['degrees'],b['degrees'])],
            'activity':[abs(x-y) for x,y in zip(a['activity'],b['activity'])],
            'parent_activity':[abs(x-y) for x,y in zip(a['parent_activity'],b['parent_activity'])],
            'same_stratum':a['stratum']==b['stratum']}


def within(r):
    return r['same_stratum'] and r['effective_weight']<=.02 and max(r['degrees'])<=2 and max(r['activity'])<=.01 and max(r['parent_activity'])<=.01


def select_edges(table,selection):
    forbidden={n for g in selection['groups'].values() for n in g['nodes']};chosen={};targets=[]
    for name in ('eye','hand'):
        keys=[]
        for node in selection['groups'][name]['nodes']:
            candidates=[e for e in table if e['key'][1]==node and e['key'][0] not in forbidden]
            top=sorted(candidates,key=lambda e:(-e['effective_weight']*e['activity'][0]*e['activity'][1],e['key']))[:EDGES_PER_NODE]
            keys.extend(top)
        chosen[name]=keys;targets.extend(keys)
    if any(len(chosen[k])!=16 for k in ('eye','hand')):
        return {'valid':False,'reason':'not four nodes and sixteen target edges per group','groups':{}}
    candidates=[e for e in table if not set(e['key'])&forbidden]
    if len(candidates)<len(targets):return {'valid':False,'reason':'insufficient control edges','groups':{}}
    cost=np.full((len(targets),len(candidates)),1e9)
    for i,a in enumerate(targets):
        for j,b in enumerate(candidates):
            if a['stratum']!=b['stratum']:continue
            r=residual(a,b)
            if within(r):cost[i,j]=r['effective_weight']/.02+sum(r['degrees'])/2+(sum(r['activity'])+sum(r['parent_activity']))/.01
    rr,cc=linear_sum_assignment(cost)
    if len(rr)!=32 or np.any(cost[rr,cc]>=1e9):return {'valid':False,'reason':'caliper matching unavailable; no relaxation','groups':{}}
    pairs=[{'target':targets[i],'control':candidates[j],'residual':residual(targets[i],candidates[j])} for i,j in zip(rr,cc)]
    return {'valid':True,'groups':{'eye':pairs[:16],'hand':pairs[16:]},'calipers':CALIPERS,
            'selection_phase':'development; lists frozen before confirmation'}


def recheck_edges(chosen,table):
    if not chosen['valid']:return {'valid':False,'reason':chosen['reason']}
    bykey={tuple(x['key']):x for x in table};res=[]
    for group,pairs in chosen['groups'].items():
        for p in pairs:
            a=bykey.get(tuple(p['target']['key']));b=bykey.get(tuple(p['control']['key']))
            if a is None or b is None:return {'valid':False,'reason':'previously selected edge missing'}
            r=residual(a,b);res.append({'group':group,'target':a['key'],'control':b['key'],**r})
    return {'valid':all(within(r) for r in res),'residuals':res,'new_edges_selected':False}


def behavior(results):
    out={}
    for mode in ('eye','hand','joint'):
        rows=[r for r in results if r['mode']==mode];assert len(rows)==4
        result={'successes':sum(r['joint_success'] for r in rows),'n':4,'new':{}}
        for organ in (('eye',) if mode=='eye' else ('hand',) if mode=='hand' else ('eye','hand')):
            key='eye_initially_inside' if organ=='eye' else 'hand_initially_arrived'
            fresh=[r for r in rows if not r[key]];k=sum(r[organ+'_success'] for r in fresh)
            result['new'][organ]={'successes':k,'n':len(fresh),'qualified':len(fresh)>=2 and k/len(fresh)>=.75}
        result['qualified']=result['successes']>=3 and all(x['qualified'] for x in result['new'].values())
        out[mode]=result
    return {'modes':out,'qualified':all(x['qualified'] for x in out.values())}


def causal(arms,restoration_exact):
    def cost(name,organ):
        return float(np.mean([r[organ+'_target_cost'] for r in arms[name] if r['mode']==organ]))
    baseline={organ:cost('sham',organ) for organ in ('eye','hand')};out={}
    for group,other in (('eye','hand'),('hand','eye')):
        own=cost(group,group)-baseline[group];cross=cost(group,other)-baseline[other]
        control=cost('matched-'+group,group)-baseline[group]
        result={'target_cost_increase':own,'other_cost_increase':cross,'matched_increase':control,
                'restoration_exact':restoration_exact[group]}
        result['qualified']=own>=.5 and abs(cross)<=.25 and abs(control)<=.25 and own-cross>=.5 and own-control>=.5 and restoration_exact[group]
        out[group]=result
    return {'groups':out,'qualified':all(x['qualified'] for x in out.values()),'sham_cost':baseline}
