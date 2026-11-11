"""Instrument/statistical validation only; no registered scientific origins."""
from collections import Counter
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_confirm_spec as s
import m5_confirm_analyze as a
import m5_rig as g


def test_new_sources_and_balanced_conditions_have_no_order_confound():
    cases = s.cases()
    assert len(cases) == len({c['seed'] for c in cases}) == 48
    assert not {c['seed'] for c in cases} & set(range(1056100, 1056108))
    assert set(Counter((c['dose'], c['delay_s']) for c in cases).values()) == {8}
    assert set(Counter((c['dose'], c['delay_s'], c['seed'] % 2) for c in cases).values()) == {4}


def test_zero_spread_is_not_zero_population_uncertainty():
    r = a.inference([1.]*48, 9)
    assert r['p_two_sided'] == 2.**-47
    assert 0 < r['positive_fraction_exact_95'][0] < 1
    assert r['paired_standardized_effect'] is None
    z = a.inference([0.]*48, 9)
    assert z['p_two_sided'] == 1 and z['p_signflip_sensitivity'] == 1


def test_holm_stepdown_controls_registered_family():
    assert a.holm({'a': .01, 'b': .02, 'c': .2}) == pytest.approx({'a': .03, 'b': .04, 'c': .2})


def test_registered_delay_is_explicit_experience_and_save_is_inert():
    subject = g.Subject(1066004)
    subject.tick(0, [{'K': .2}])
    before = subject.save()
    assert subject.save() == before
    subject.advance(subject.time+2_000_000)
    after = subject.save()
    assert after['time_us']-before['time_us'] == 2_000_000
    assert all(row['values'] == {'K': .2} for row in after['inputs'])
    assert g.Subject.restore(after).save() == after
