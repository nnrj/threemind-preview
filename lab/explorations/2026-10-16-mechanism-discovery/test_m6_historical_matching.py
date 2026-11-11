import copy,math
import pytest
from m6_historical_matching import FEATURES,edge_features,match_edges


def state():
    return {'definition':{'kernel_id':'threemind.continuous-memory/2'},'time_us':'3000000',
            'config':{'fast_enabled':True,'fast_gain':.1,'fast_tau_s':2.},
            'operator_state':{'fast':[{'source':0,'target':1,'state':{'value':.4,'time_us':'1000000'}}]},
            'nodes':[{'id':i,'activation':.2,'channel':100+i} for i in range(4)],
            'edges':[{'source':0,'target':1,'weight':.5,'birth_us':'0'}, {'source':2,'target':3,'weight':.5,'birth_us':'0'}]}


def row(a,b,weight):
    return {'key':[a,b],'features':dict(zip(FEATURES,[weight,weight,1,1,1,1,.2,.2]))}


def test_effective_weight_at_saved_time_and_no_mutation():
    s=state();before=copy.deepcopy(s);table=edge_features(s)
    assert table[0]['features']['effective_weight']==pytest.approx(.5+.04*math.exp(-1))
    assert table[1]['features']['effective_weight']==.5 and s==before


def test_disabled_fast_and_saturation():
    s=state();s['config']['fast_enabled']=False
    assert edge_features(s)[0]['features']['effective_weight']==.5
    s['config']['fast_enabled']=True;s['edges'][0]['weight']=.999
    assert edge_features(s)[0]['features']['effective_weight']==1.


def test_refuse_wrong_version_and_future_state():
    s=state();s['definition']['kernel_id']='threemind.continuous-memory/5.1'
    with pytest.raises(ValueError):edge_features(s)
    s=state();s['operator_state']['fast'][0]['state']['time_us']='4000000'
    with pytest.raises(ValueError):edge_features(s)


def test_matching_uses_global_cardinality_not_greedy():
    # t0 can use c0/c1; t1 can only use c0. Taking t0-c0 first loses a valid pair.
    table=[row(0,1,.5),row(0,2,.54),row(3,4,.51),row(5,6,.46)]
    result=match_edges(table,{0},2)
    assert result['valid'] and result['available_pairs']==2
    pairs={tuple(p['target']['key']):tuple(p['matched']['key']) for p in result['pairs']}
    assert pairs=={(0,1):(5,6),(0,2):(3,4)}


def test_matching_keeps_counts_calipers_and_is_order_invariant():
    table=[row(0,1,.5),row(0,2,.52),row(3,4,.5),row(5,6,.52)]
    r=match_edges(table,{0},2)
    assert r==match_edges(list(reversed(table)),{0},2)
    assert len({tuple(x['matched']['key']) for x in r['pairs']})==2
    assert r['maximum_normalized_residual']<=1


def test_insufficient_matching_does_not_relax_or_return_partial_operation():
    r=match_edges([row(0,1,.5),row(3,4,.9)],{0},1)
    assert not r['valid'] and r['pairs']==[] and r['available_pairs']==0
