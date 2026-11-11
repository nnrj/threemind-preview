import pytest
from assay_study import cases
from analyze_assay import vector,retained,forecast_weight,cue_history_difference
from retention_assay import FIELDS


def test_nested_units_and_opposite_histories():
    rows=cases()
    assert len(rows)==len({x['key'] for x in rows})==1920
    assert len({x['seed'] for x in rows})==8
    assert all(sum(x['origin']==o for x in rows)==240 for o in range(8))


def test_natural_activity_change_is_removed_by_matched_cue_omission():
    parts={(h,1,q):{'response_vector':[.3*h+.1]*160} for h in (0,1) for q in (True,False)}
    assert cue_history_difference(parts,1)==[0.]*160
    parts[0,1,True]['response_vector'][7]+=.2
    parts[1,1,True]['response_vector'][2]+=.4
    result=cue_history_difference(parts,1)
    assert result[7]==pytest.approx(-.2) and result[2]==pytest.approx(.4)
    assert sum(x!=0 for x in result)==2


def test_inhibition_and_event_timing_are_in_primary_measure():
    frame={f'out{k}':dict.fromkeys(FIELDS,0.) for k in (0,1)}
    import copy
    result={'baseline':{'raw':[copy.deepcopy(frame) for _ in range(20)]},
            'response':{'raw':[copy.deepcopy(frame) for _ in range(20)]}}
    result['response']['raw'][0]['out1']['inhibition']=.2
    early=vector(result)
    assert len(early)==160 and retained(early,early)['passed']
    result['response']['raw'][0]['out1']['inhibition']=0.
    result['response']['raw'][19]['out1']['inhibition']=.2
    assert not retained(early,vector(result))['passed']
    assert not retained([0.]*160,[0.]*160)['passed']


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
def test_fixed_scale_first_half_is_matched(curve):
    state={'core':{'time_us':'0','config':{'decay_curve':curve,'retention_relaxation_enabled':False,
        'memory_half_life_min_s':30.,'memory_half_life_decay_rate':.125}}}
    row={'state_us':'0','half_life':30.,'weight':.8,'decay_contributions':[(.8,0.)]}
    assert forecast_weight(row,state,30)==pytest.approx(.4)


def test_original_boundaries_and_failed_units_are_preserved(monkeypatch):
    from pathlib import Path
    import tempfile
    import assay_study as e
    from retention_assay import Assay
    monkeypatch.setattr(e,'boundary',lambda work:None)
    with tempfile.TemporaryDirectory(prefix='assay-unit-',dir=Path('.work')) as folder:
        work=Path(folder)
        assert work.resolve().is_relative_to(Path('.work').resolve())
        s=Assay(26110994,'exponential',True,'engineering-boundary')
        e.save(work/'birth.json.gz',s.state())
        e.unit(work,'teaching',s,lambda:s.teach('ordinary',False,0))
        taught=e.load(work/'teaching/whole.json.gz')
        assert Assay.restore(taught).state()==taught
        e.unit(work,'probe',s,lambda:s.first_probe(1))
        assert not (work/'in-flight.json').exists()
        receipt=e.load(work/'probe/complete.json')
        assert receipt['before_sha256']==e.base.digest(taught)
        assert receipt['after_sha256']==e.base.digest(s.state())
        def failure():raise RuntimeError('synthetic interrupted operation')
        with pytest.raises(RuntimeError,match='synthetic'):
            e.unit(work,'failed',s,failure)
        assert e.load(work/'in-flight.json')['key']=='failed'
        assert e.load(work/'current.json')['unit']=='probe'
        assert not (work/'failed/complete.json').exists()
