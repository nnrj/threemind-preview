"""Synthetic causal/nuisance adversaries; no subject is simulated here."""
import copy
from collections import Counter
import numpy as np
import m4_balanced_course as course
import m4_regional_metrics as r


def synthetic(phase,seed=1):
    rng=np.random.default_rng(seed);channels=list(range(8));trials=[]
    for j in range(12):
        mode=('eye','hand','joint')[j%3];a=np.zeros((60,8,4));a[:,:,0]=.1;a[:,:,2]=.01
        a[:,:,3]=.03+rng.uniform(0,.002,(60,8))
        if phase:
            if mode=='eye':a[:,:4,3]+=.05
            if mode=='hand':a[:,4:,3]+=.05
        trials.append({'id':str(j),'mode':mode,'channels':channels,'frames':60,
                       'regions':dict.fromkeys(channels,0),'node_ids':dict(zip(channels,channels)),
                       'values':a.tolist(),'common':rng.normal(size=(60,4)).tolist()})
    return trials


def test_development_only_selection_generalizes_and_rejects_lost_contrast():
    s=r.fit_groups(synthetic(0),synthetic(1,2),dict.fromkeys(range(8),'vision'))
    assert set(s['groups']['eye']['channels'])==set(range(4))
    assert set(s['groups']['hand']['channels'])==set(range(4,8))
    before=copy.deepcopy(s)
    assert r.confirm_groups(s,synthetic(1,3))['qualified']
    assert not r.confirm_groups(s,synthetic(0,4))['qualified']
    assert s==before


def test_no_group_from_fixed_direct_sensory_difference():
    pre=synthetic(1,5);dev=synthetic(1,6)
    # Identical selection before teaching does not demonstrate acquired division.
    s=r.fit_groups(pre,dev,dict.fromkeys(range(8),'vision'))
    assert not all(x['complete'] for x in s['groups'].values())


def edge(key):
    return {'key':key,'effective_weight':.05,'degrees':[16]*4,'activity':[.1,.1],
            'parent_activity':[.1,.1],'stratum':['vision','vision',0,0]}


def test_exact_unique_caliper_matching_and_final_recheck():
    s={'groups':{'eye':{'nodes':list(range(4))},'hand':{'nodes':list(range(4,8))}}}
    table=[edge([100+j,n]) for n in range(8) for j in range(4)]+[edge([200+j,300+j]) for j in range(32)]
    chosen=r.select_edges(table,s);assert chosen['valid']
    controls=[tuple(p['control']['key']) for group in chosen['groups'].values() for p in group]
    assert len(set(controls))==32
    assert r.recheck_edges(chosen,table)['valid']
    modified=copy.deepcopy(table)
    for e in modified:
        if tuple(e['key'])==controls[0]:e['parent_activity'][0]+=.011
    assert not r.recheck_edges(chosen,modified)['valid']
    for e in table:
        if e['key'][0]>=200:e['stratum'][-1]=1
    assert not r.select_edges(table,s)['valid']


def results():
    return [{'mode':mode,'joint_success':True,'eye_success':True,'hand_success':True,
             'eye_initially_inside':False,'hand_initially_arrived':False,
             'eye_target_cost':.1,'hand_target_cost':.1} for mode in course.MODES for _ in range(4)]


def test_holding_is_not_new_arrival_and_causal_selectivity_requires_controls():
    rows=results();assert r.behavior(rows)['qualified']
    for x in rows:x['eye_initially_inside']=True;x['hand_initially_arrived']=True
    assert not r.behavior(rows)['qualified']
    arms={k:results() for k in ('sham','eye','hand','matched-eye','matched-hand')}
    for k in ('eye','hand'):
        for x in arms[k]:
            if x['mode']==k:x[k+'_target_cost']+=1
    exact={'eye':True,'hand':True};assert r.causal(arms,exact)['qualified']
    arms['matched-eye']=copy.deepcopy(arms['eye']);assert not r.causal(arms,exact)['qualified']


def test_physical_materials_are_balanced_between_diagnostic_tasks():
    for origin in range(8):
        for phase in ('pre','development','confirmation'):
            bank=course.bank(origin)[phase]
            count=[Counter((tuple(x['xy']),tuple(x['item'])) for x in bank if x['mode']==mode) for mode in course.MODES]
            assert count[0]==count[1]==count[2]
