import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import closure_rig as g
import m3_confirm_spec as spec
from m3_confirm_driver_v2 import declared_sham_equal


@pytest.mark.parametrize('kind',spec.KINDS)
def test_sham_lineage_is_required_but_no_other_field_can_change(kind):
    parent=g.Rig(kind,spec.TEST_SEED);rows=g.teaching(parent,0)
    selection=g.rnn_selection(parent,rows) if kind=='fixed-rnn-reader' else None
    original=parent.save()
    sham,_=g.intervene(parent,'sham',selection)
    restored,_=g.intervene(parent,'restored',selection)
    assert declared_sham_equal(parent,sham)
    assert restored.save()==original==parent.save()
    wrong=copy.deepcopy(sham.save());wrong['body']['x']+=.1
    view=type('SavedView',(),{'save':lambda self:wrong})()
    assert not declared_sham_equal(parent,view)
    wrong['body']=original['body'];wrong['branch']['label']='intact'
    assert not declared_sham_equal(parent,view)
