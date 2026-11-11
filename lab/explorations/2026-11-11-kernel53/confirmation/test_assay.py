"""Confirmation apparatus checks; synthetic seeds never enter formal N."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from assay import Assay, cases as explore_cases
sys.path.insert(0,str(HERE))
from spec import cases


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


metrics=load_module('confirm_metrics',HERE/'analyze.py')


def test_all_sources_materials_and_pairing():
    rows=cases();assert len(rows)==5376 and len({r['key'] for r in rows})==5376
    assert len({r['seed'] for r in rows})==48
    assert {r['seed'] for r in rows}.isdisjoint(r['seed'] for r in explore_cases())
    for origin in range(48):
        sub=[r for r in rows if r['origin']==origin]
        assert len(sub)==112
        assert len({str(r['profile']) for r in sub})==1
        assert {r['delay'] for r in sub if r['course']=='weak'}=={30}


@pytest.mark.parametrize('curve',metrics.CURVES)
def test_continuity(curve):
    row=copy.deepcopy(next(r for r in cases() if r['curve']==curve and r['course']=='spaced' and r['delay']==300))
    row.update(seed=98765053,key='engineering')
    value=Assay(row,'native');value.teach();before=value.state()
    resumed=Assay.restore(before,'native')
    left=value.probe();right=resumed.probe()
    assert left==right and value.state()==resumed.state()
    assert len(left['response']['frames'])==20


def test_statistics_positive_negative_and_degenerate():
    plus=metrics.comparison([.2,.3,.4,.5]*12)
    minus=metrics.comparison([-.2,-.3,-.4,-.5]*12)
    zero=metrics.comparison([0.]*48)
    constant=metrics.comparison([.2]*48)
    assert plus['significant'] and plus['bonferroni_lower']>0
    assert not minus['significant'] and minus['p_one_sided']>.99
    assert not zero['significant'] and zero['method'].startswith('exact sign')
    assert constant['significant']
