"""The instrument must validate identity sidecars, never discard them."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m2_fusion_v2 as v2


def whole(mix):
    cfg = {'context_mix': mix, 'fixed': 1.}
    definition = {'config': cfg, 'kernel_id': v2.m.KERNEL}
    return {'core': {'config': cfg, 'definition': definition,
                     'definition_hash': v2.m.StateImage.from_dict(definition).digest,
                     'nodes': [{'id': 1, 'activation': 0.}]}}


def test_correct_sidecar_changes_are_verified():
    assert v2.intervention_identity_valid(whole(1.), whole(0.))


def test_stale_definition_or_forged_hash_is_rejected():
    a, b = whole(1.), whole(0.)
    b['core']['definition_hash'] = a['core']['definition_hash']
    assert not v2.intervention_identity_valid(a, b)
    b = whole(0.)
    b['core']['definition'] = copy.deepcopy(a['core']['definition'])
    assert not v2.intervention_identity_valid(a, b)


def test_any_biological_state_change_is_still_rejected():
    a, b = whole(1.), whole(0.)
    b['core']['nodes'][0]['activation'] = .001
    assert not v2.intervention_identity_valid(a, b)


def test_scientific_design_is_unchanged_and_paths_are_distinct():
    import pilot_m2_fusion as v1
    assert v2.parents() == v1.parents()
    assert v2.CUES == v1.CUES and v2.ARMS == v1.ARMS
    assert v2.WORK != v1.WORK and v2.NS != v1.NS
