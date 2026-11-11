import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_analyze as a
import m5_rig as g


def test_inference_has_no_label_or_metadata_channel_and_does_not_learn():
    reader = g.Reader()
    rows = [{'features': [1., 0.]+[0.]*10, 'label': 1}, {'features': [0., 1.]+[0.]*10, 'label': -1}]
    reader.learn(rows); before = reader.save()
    assert reader.infer(rows[0]['features'])['answer'] == 1
    assert reader.infer(rows[1]['features'])['answer'] == -1
    assert reader.save() == before
    with pytest.raises(ValueError): reader.infer([0.]*13)


def test_continued_learning_preserves_old_sufficient_statistics_and_scale():
    r = g.Reader(); r.learn([{'features': [1.]+[0.]*11, 'label': 1}])
    before = copy.deepcopy(r.save())
    r.learn([{'features': [0., 1.]+[0.]*10, 'label': -1}])
    assert r.updates == 2 and r.save()['samples'][0] == before['samples'][0]
    assert r.save()['scale'] == before['scale']
    assert np.allclose(r.gram, np.asarray(before['gram'])+np.diag([0., 1.]+[0.]*10))
    assert g.Reader(r.save()).save() == r.save()


def test_whole_restoration_and_output_ports_are_individual_interfaces():
    s = g.Subject(1056004); s.tick(0, [{'K': .2}]); s.advance(1_000_000)
    saved = s.save()
    assert g.Subject.restore(saved).save() == saved
    features = list(range(12)); projected = s.port_features(features)
    indices = [sorted(s.channels.values()).index(s.channels[k]) for k in 'AB']
    assert all(projected[i] == (features[i] if i in indices else 0) for i in range(12))
    assert s.save() == saved


def test_opposite_new_histories_share_old_labels_and_change_new_targets():
    for cue in g.NEW: assert g.label(cue, 0) == -g.label(cue, 1)
    for cue in g.OLD: assert g.label(cue, 0) == g.label(cue, 1)


def test_joint_cues_cannot_rescue_registered_singleton_denominator():
    rows = [{'cue': cue, 'group': 'new', 'label': 1, 'response': {'answer': 0 if len(cue) == 1 else 1}}
            for cue in g.NEW]
    assert a.accuracy(rows, 'full', 'new') == {'correct': 0, 'n': 4, 'rate': 0.}
    assert a.accuracy(rows, 'full', 'new', form='joint') == {'correct': 2, 'n': 2, 'rate': 1.}
