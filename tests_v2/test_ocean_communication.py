import copy
import json

import numpy as np
import pytest

from lab.tools.ocean_communication import CommunicationOcean, CommunicationProtocol, JointCommunicationOcean
from lab.tools.ocean_coverage import CoverageOcean, CoverageProtocol


def world(**kwargs):
    p = CommunicationProtocol(founders=2, population_limit=7, nutrient_initial=8,
                              reproduction=False, **kwargs)
    w = CommunicationOcean(p.model_dump(by_alias=True))
    w.configure({0: 'a', 1: 'b'}, {'a': 'core', 'b': 'core'}, cross_only=True)
    w.bodies[0].position = [.3, .3]
    w.bodies[1].position = [.4, .3]
    return w


def joint_copy(w):
    state = w.capture()
    protocol = w.p.model_dump(by_alias=True) | {'schema': 'threemind.ocean-communication/2'}
    state['schema'] = JointCommunicationOcean.state_schema
    state['coverage']['material']['enclosure']['group']['community']['world']['protocol'] = protocol
    return JointCommunicationOcean(protocol, state=state,
                                   images={i: e.capture_state() for i, e in w.engines.items()})


def test_common_body_sample_preserves_values_and_allows_cross_sensory_edges():
    separate = world()
    joint = joint_copy(separate)
    records = []
    for w in (separate, joint):
        w.output.publish({'individual': 0, 'organ': {'voices': [{'frequency_hz': 220., 'amplitude': .5}]}})
        rows = []
        w.step(rows.append)
        records.append(next(v for v in rows[0]['inputs'] if v['individual'] == 1))
    a, b = records
    expected = sorted(a['stimulus']['channels'] + a['heard']['stimulus']['channels'])
    assert b['stimulus']['channels'] == expected
    assert a['raw'] == b['raw']
    for w, expected_cross in ((separate, False), (joint, True)):
        state = w.engines[1].capture_state().to_dict()
        receptors = {n['id'] for n in state['nodes'] if n['channel'] in w.hearing_channels(1)}
        assert any((e['source'] in receptors) != (e['target'] in receptors) for e in state['edges']) == expected_cross


def test_joint_snapshot_restores_without_changing_legacy_protocol():
    legacy = world()
    joint = joint_copy(legacy)
    for _ in range(7):
        joint.step()
    restored = JointCommunicationOcean(joint.p.model_dump(by_alias=True), state=joint.capture(),
                                       images={i: e.capture_state() for i, e in joint.engines.items()})
    joint.step()
    restored.step()
    assert joint.capture() == restored.capture()
    assert legacy.p.schema_id == 'threemind.ocean-communication/1'
    assert restored.p.schema_id == 'threemind.ocean-communication/2'


@pytest.mark.parametrize('joint', [False, True])
def test_species_export_and_replacement_rebind_input_bus(tmp_path, joint):
    from lab.tools.ocean_contact_cli import save
    from lab.tools.ocean_species import save_candidate, seed_founders

    source = world()
    if joint:
        source = joint_copy(source)
    source.step()
    save(source, tmp_path / 'source')
    bundle = tmp_path / 'candidate.tmspecies'
    manifest = save_candidate(tmp_path / 'source', 0, bundle, name='test candidate', evidence=[])
    assert manifest['environment_protocol']['schema'] == source.p.schema_id
    target = joint_copy(world()) if joint else world()
    discarded = target.engines[1]
    seed_founders(target, bundle.read_bytes(), [1])
    assert 1 not in target.input_buses
    target.step()
    assert 1 in target.input_buses
    assert target.engines[1].time_us == target.time_us
    assert discarded.time_us == 0


def test_cli_recording_and_portable_viewer_preserve_world_evolution(tmp_path):
    import base64
    import gzip
    import re
    from lab.tools.ocean_communication_cli import run_recorded
    from lab.tools.ocean_communication_view import build

    recorded, plain = world(), world()
    folder = tmp_path / 'case'
    result = run_recorded(recorded, folder, .4, trajectory_interval_us=200000,
                          activity_interval_us=1000000)
    for _ in range(20):
        plain.step()
    assert result['status'] == 'horizon_paused'
    assert recorded.capture() == plain.capture()
    for identity in plain.engines:
        assert recorded.engines[identity].capture_state().to_dict() == plain.engines[identity].capture_state().to_dict()
    with gzip.open(folder / 'communication.jsonl.gz', 'rt', encoding='utf-8') as f:
        rows = [json.loads(line) for line in f]
    assert any(r['received'] for r in rows)
    assert any(r['emitted'] for r in rows)
    build([folder], tmp_path / 'replay.html')
    html = (tmp_path / 'replay.html').read_text(encoding='utf-8')
    packed = json.loads(re.search(r'const packed=("[^"]+");', html).group(1))
    data = json.loads(gzip.decompress(base64.b64decode(packed)))
    assert data[0]['name'] == 'case'
    assert len(data[0]['frames'][0]['members']) == 2


def test_receiver_gets_only_anonymous_band_values_after_physical_delay():
    w = world()
    w.output.publish({'individual': 0, 'organ': {'voices': [{'frequency_hz': 220., 'amplitude': .5}]}})
    q = next(p for p in w.packets if p['receiver'] == 1)
    assert q['arrival_us'] > w.time_us
    assert w._hearing(1) is None
    w.time_us = q['arrival_us']
    row = w._hearing(1)
    stimulus = row['stimulus']
    assert {i for i, _ in stimulus['channels']} <= w.hearing_channels(1)
    assert 'sender' not in stimulus and 'cohort' not in stimulus
    assert max(v for _, v in stimulus['channels']) < w.p.hearing_gain
    assert w.bodies[0].storage < w.p.initial_body_energy


def test_muting_others_retains_own_sound_and_scrambling_retains_power():
    outputs = {}
    for mode in ('live', 'muted', 'scrambled'):
        w = world(hearing_mode=mode)
        for i, freq in ((0, 220.), (1, 880.)):
            w.output.publish({'individual': i, 'organ': {'voices': [{'frequency_hz': freq, 'amplitude': .5}]}})
        w.time_us = w.p.period_us
        outputs[mode] = w._hearing(1)
    assert np.sum(outputs['live']['power']) == pytest.approx(np.sum(outputs['scrambled']['power']))
    assert 0 < np.sum(outputs['muted']['power']) < np.sum(outputs['live']['power'])
    assert outputs['live']['power'] != outputs['scrambled']['power']


def test_restore_retains_queued_sound_buses_energy_and_behavior():
    w = world()
    for _ in range(11):
        w.step()
    w._emit()  # May leave an in-flight packet, explicitly saved below as well.
    w.output.publish({'individual': 0, 'organ': {'voices': [{'frequency_hz': 220., 'amplitude': .3}]}})
    z = CommunicationOcean(w.p.model_dump(by_alias=True), state=json.loads(json.dumps(w.capture())),
                           images={i: e.capture_state() for i, e in w.engines.items()})
    for _ in range(12):
        w.step()
        z.step()
    assert w.capture() == z.capture()
    assert abs(w.metrics()['energy_balance_error']) < 1e-6
    assert all(bus.pending_count() == 0 for bus in w.input_buses.values())


def test_inaudible_free_sound_preserves_existing_core_and_body_behavior():
    p = CommunicationProtocol(founders=2, nutrient_initial=8, reproduction=False,
                              intake_share_fraction=0., hearing_gain=0., voice_cost_per_s=0.)
    old = {k: v for k, v in p.model_dump(by_alias=True).items() if k == 'schema' or k in CoverageProtocol.model_fields}
    old['schema'] = 'threemind.ocean-enclosure/3'
    a, b = CoverageOcean(old), CommunicationOcean(p.model_dump(by_alias=True))
    for w in (a, b):
        w.configure({0: 'a', 1: 'b'}, {'a': 'core', 'b': 'core'}, cross_only=True)
        for _ in range(50):
            w.step()
    assert [e.capture_state().digest for e in a.engines.values()] == [e.capture_state().digest for e in b.engines.values()]
    assert [v.position for v in a.bodies.values()] == [v.position for v in b.bodies.values()]


def test_species_labels_cannot_change_hearing_and_same_species_cannot_predate():
    w = world()
    w.cohorts = {0: 'a', 1: 'a'}
    w.group_controls = {'a': 'core'}
    assert w._protected_pair(0, 1, 1000000000)
    w.output.publish({'individual': 0, 'organ': {'voices': [{'frequency_hz': 220., 'amplitude': .5}]}})
    before = copy.deepcopy(w.packets)
    w.packets = []
    w.cohorts = {0: 'red', 1: 'blue'}
    w.output.publish({'individual': 0, 'organ': {'voices': [{'frequency_hz': 220., 'amplitude': .5}]}})
    assert before == w.packets


def test_sharing_is_physical_lossy_and_not_a_free_cooperation_reward():
    w = world()
    w.cohorts = {0: 'a', 1: 'a'}
    w.group_controls = {'a': 'core'}
    w.associations = {(0, 1): 0}
    w.time_us = w.p.association_dwell_us
    w.intake = {0: 10.}
    before = sum(b.storage for b in w.bodies.values())
    w._share_intake()
    assert w.bodies[1].share_received == pytest.approx(10 * .25 * .9)
    assert before - sum(b.storage for b in w.bodies.values()) == pytest.approx(10 * .25 * .1)
