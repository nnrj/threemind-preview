from collections import Counter
import inspect
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import closure_rig as g
import m1_confirm_probe as p
import m1_confirm_spec as s
from m1_confirm_audit import check_matching


def test_sources_strata_and_order_balanced_before_data():
    cases = s.cases()
    assert len({c['seed'] for c in cases}) == 48
    assert set(Counter((c['teaching_dose'], c['delay_s'], c['seed'] % 2) for c in cases).values()) == {4}
    assert not {c['seed'] for c in cases} & set(range(1016100, 1016108))


def test_unseen_mixtures_preserve_total_dose_and_use_no_answer_channel():
    for cue in s.CUES:
        v = s.cue_values(cue)
        assert sum(v.values()) == pytest.approx(.88)
        assert not set(v) & {'A', 'B'}
    assert s.cue_values('XN')['X'] == pytest.approx(.88*.85)
    assert 'goal' not in inspect.signature(p.probe).parameters


def test_whole_state_observation_restore_and_pause_equivalence():
    subject = g.Rig('threemind', 1076004)
    g.teaching(subject, 0, .42, delay=2); g.settle(subject)
    saved = subject.save(); hashes = []
    for mode in ('plain', 'observed', 'restored', 'paused'):
        child = g.Rig.restore(saved)
        result = p.probe(child, 'XN', observed=mode == 'observed', restore_mid=mode == 'restored', pause_mid=mode == 'paused')
        hashes.append(result['final_sha256'])
        assert child.time == saved['time_us']+1_500_000
    assert len(set(hashes)) == 1
    assert subject.save() == saved


def test_matching_audit_recomputes_topology_and_teaching_residual():
    import copy
    subject = g.Rig('threemind', 1076004)
    records = g.teaching(subject, 0, .42, delay=2); g.settle(subject)
    matching = g.matching(subject, records)
    check_matching(subject.save(), matching, records)
    corrupt = copy.deepcopy(matching)
    corrupt['rows']['XY'][0]['degrees'][0][0] += 1
    with pytest.raises(AssertionError):
        check_matching(subject.save(), corrupt, records)
