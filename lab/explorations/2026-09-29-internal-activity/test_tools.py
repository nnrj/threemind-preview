"""Checks protect matched interventions and time-weighted analysis."""
import gzip
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from analyze import area
from experiment import edge_group, edge_keys, load_old, parents
from threemind_runtime import create_engine
from dataclasses import replace

def test_unequal_sampling_does_not_overweight_early_samples():
    rows=[{'relative_us':0,'v':1},{'relative_us':10_000,'v':2},
          {'relative_us':100_000,'v':3},{'relative_us':1_000_000,'v':999}]
    assert abs(area(rows,lambda r:r['v'],0,1_000_000)-2.89)<1e-12
    assert abs(area(rows,lambda r:r['v'],50_000,200_000)-.4)<1e-12

def test_noop_configuration_preserves_a_live_full_state():
    state=load_old(parents()[0])['image']
    engine=create_engine(state=state,backend='native')
    engine.reconfigure(replace(engine.config))
    assert engine.capture_state().digest==state.digest

def test_edge_silencing_keeps_nodes_and_structure_and_is_reversible():
    state=load_old(parents()[0])['image']
    engine=create_engine(state=state,backend='native')
    edges=edge_keys(state)
    first={e for e in edges if edge_group(e)==0}
    second={e for e in edges if edge_group(e)==1}
    assert first and second and first.isdisjoint(second) and first|second==set(edges)
    engine.intervene(edges=sorted(first),action='silence')
    middle=engine.capture_state().to_dict()
    assert middle['nodes']==state.to_dict()['nodes']
    assert middle['edges']==state.to_dict()['edges']
    assert set(map(tuple,middle['silenced_edges']))==first
    engine.intervene(edges=sorted(first),action='unsilence')
    restored=engine.capture_state().to_dict()
    original=state.to_dict()
    assert restored['sequence']==original['sequence']+2
    restored['sequence']=original['sequence']
    assert restored==original
