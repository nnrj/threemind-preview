"""Resource release and local expiry witnesses; no formal subject is modified."""
from dataclasses import replace
import hashlib

import pytest

from threemind_core import StateImage, Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local62 import KERNEL_ID, Local62Config, Local62Engine
from threemind_kernels.registry import resolve_kernel
from test_local60 import same


def make(config=None, state=None, backend="reference"):
    return resolve_kernel(KERNEL_ID).create(config, state, backend=backend)


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("decay", [True, False])
def test_weak_positive_input_expires_locally(backend, decay):
    config = Local62Config(activation_decay_enabled=decay, plasticity=False)
    e = make(config, backend=backend)
    e.inject(Stimulus(0, ((1, .0001),)))
    e.advance_to(0)
    before = e.capture_state()
    e.observation_nodes(); e.metrics()
    assert before.digest == e.capture_state().digest
    assert e.capture_state().to_dict()["active"] == [1]
    e = make(state=before, backend=backend)
    e.advance_to(300_000_000)
    d = e.capture_state().to_dict()
    assert d["life"] == "dead" and not d["active"]
    assert int(d["time_us"]) == config.quiescence_death_us + 1
    assert d["audit"]["scan_visits"] == 0
    with pytest.raises(ValueError):
        e.inject(Stimulus(e.time_us + 1, ((1, .1),)))


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_same_timestamp_weak_inputs_can_accumulate(backend):
    e = make(Local62Config(), backend=backend)
    for _ in range(100):
        e.inject(Stimulus(0, ((1, .0001),)))
    e.advance_to(1)
    d = e.capture_state().to_dict()
    assert d["active"] == [1] and d["nodes"][0]["activation"] > .004
    assert any(t[0] == 1 and int(t[3]) > 1 for t in d["timers"])


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_old_definition_keeps_old_release_and_lifecycle(backend):
    config = Local62Config(resource_precheck_enabled=False, subthreshold_expiry_enabled=False)
    original = make(config, backend=backend)
    original.inject(Stimulus(0, ((1, .0001),)))
    original.advance_to(0)
    doc = original.capture_state().to_dict()
    for key in ("resource_precheck_enabled", "subthreshold_expiry_enabled"):
        doc["config"].pop(key)
        doc["definition"]["config"].pop(key)
    doc["definition_hash"] = hashlib.sha256(canonical_bytes(doc["definition"])).hexdigest()
    restored = make(state=StateImage.from_dict(doc), backend=backend)
    assert not restored.config.resource_precheck_enabled
    assert not restored.config.subthreshold_expiry_enabled
    original.advance_to(300_000_000); restored.advance_to(300_000_000)
    same(original.capture_state().to_dict(), restored.capture_state().to_dict())
    assert restored.capture_state().to_dict()["life"] == "active"


@pytest.mark.parametrize("excitatory,inhibitory", [(2., 2.), (0., 2.), (2., 0.)])
def test_precheck_releases_only_if_one_signal_qualifies(excitatory, inhibitory):
    c = Local62Config(activation_signal_threshold=excitatory, inhibition_signal_threshold=inhibitory,
                      fast_enabled=False, local_novelty_gain=0)
    e = Local62Engine(c)
    e.inject(Stimulus(0, ((1, .4), (2, .3))))
    e.advance_to(0)
    e.nodes[1].inhibition = .2
    initial = e.capture_state()
    legacy = Local62Engine(state=initial)
    legacy.reconfigure(replace(c, resource_precheck_enabled=False))
    original_resource = e.edges[(1, 2)].short_term
    e._emit(1); legacy._emit(1)
    if excitatory == inhibitory == 2.:
        assert e.edges[(1, 2)].short_term == original_resource
        assert legacy.edges[(1, 2)].short_term != original_resource
    else:
        assert e.edges[(1, 2)].short_term == legacy.edges[(1, 2)].short_term
        transmitted = "transmitted_excitation" if excitatory == 0 else "transmitted_inhibition"
        assert e.transport[transmitted] > 0


@pytest.mark.parametrize("field", ["resource_precheck_enabled", "subthreshold_expiry_enabled"])
@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_switch_requires_boolean(field, value):
    with pytest.raises(ValueError, match="boolean"):
        Local62Config(**{field: value})


def test_new_switches_are_exposed_and_validated_by_catalogue():
    from threemind_lab.configuration import catalogue, default_spec, validate_configuration
    fields = {v['path']: v for v in catalogue(KERNEL_ID)['fields']}
    for name in ('resource_precheck_enabled', 'subthreshold_expiry_enabled'):
        assert fields['config.' + name]['default'] is True
        for value in (True, False):
            assert validate_configuration(default_spec(kernel_id=KERNEL_ID) | {'config': {name: value}})['valid']
        assert not validate_configuration(default_spec(kernel_id=KERNEL_ID) | {'config': {name: 'false'}})['valid']


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_repair_is_explicit_and_observation_does_not_apply_it(backend):
    e = make(Local62Config(subthreshold_expiry_enabled=False), backend=backend)
    e.inject(Stimulus(0, ((1, .0001),)))
    e.advance_to(0)
    before = e.capture_state()
    e.observation_nodes()
    assert before.digest == e.capture_state().digest
    e.reconfigure(replace(e.config, subthreshold_expiry_enabled=True))
    e.advance_to(300_000_000)
    assert e.capture_state().to_dict()["life"] == "dead"
