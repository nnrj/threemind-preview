import copy
import pytest
from lab.tools.connection_controls import cross_domain_masks


def test_masks_are_disjoint_count_matched_and_read_only():
    image={'nodes':[{'id':i,'channel':i+10} for i in range(4)],'edges':[
        {'source':0,'target':1,'weight':.4},{'source':1,'target':0,'weight':.2},
        {'source':0,'target':2,'weight':.35},{'source':2,'target':3,'weight':.22},
        {'source':0,'target':3,'weight':.9}]}
    saved=copy.deepcopy(image);mask=cross_domain_masks(image,{10},{11})
    assert set(mask['target'])=={(0,1),(1,0)}
    assert set(mask['matched'])=={(0,2),(2,3)}
    assert mask['mean_weight_error']==pytest.approx(.035)
    assert not mask['topology_matched'] and image==saved


def test_unavailable_control_is_not_silently_smaller():
    image={'nodes':[{'id':0,'channel':10},{'id':1,'channel':11}],
           'edges':[{'source':0,'target':1,'weight':.4}]}
    assert cross_domain_masks(image,{10},{11}) is None
    with pytest.raises(ValueError):cross_domain_masks(image,{10},{10})
