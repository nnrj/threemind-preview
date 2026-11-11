"""Version selection and tool/storage boundaries on fresh engineering subjects."""
import copy
from dataclasses import fields
from unittest.mock import patch

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import Stimulus
from threemind_kernels.local5 import KERNEL_ID, Local5Edge, Local5Node
from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.host import Runtime
from threemind_runtime.inheritance import birth
from threemind_runtime.readout_session import ReadoutSession


def feed(engine):
    for t, values in ((0, ((1, .8), (2, .7))), (73123, ((1, .4), (3, .5))),
                      (311337, ((2, .6), (3, .8)))):
        engine.inject(Stimulus(t, values))


def test_creation_defaults_and_immutable_research_options():
    assert DEFAULT_KERNEL == 'threemind.continuous-memory/3'
    spec = default_spec(kernel_id=KERNEL_ID)
    assert spec['config']['reception_mode'] == 'legacy-source'
    assert spec['config']['arrival_mode'] == 'sequential'
    assert spec['config']['propagation_phase'] == 'aligned'
    assert resolve_kernel('threemind.continuous-memory/4').configuration().reception_mode == 'unified'
    catalog = catalogue(kernel_id=KERNEL_ID)
    shown = {row['path']: row for row in catalog['fields']}
    for key in ('reception_mode', 'arrival_mode', 'propagation_phase'):
        assert shown['config.' + key]['default'] == spec['config'][key]
        assert shown['config.' + key]['immutable']
        changed = copy.deepcopy(spec)
        changed['config'][key] = {'reception_mode': 'unified', 'arrival_mode': 'coincident', 'propagation_phase': 'asynchronous'}[key]
        assert validate_configuration(changed)['valid']
        assert not validate_configuration(changed, current=spec)['valid']


@pytest.mark.parametrize('backend', ['reference', 'native'])
@pytest.mark.parametrize('format', ['json', 'tmind'])
def test_object_clocks_survive_codec_and_new_birth_is_explicit(backend, format):
    engine = create_engine(kernel_id=KERNEL_ID, backend=backend)
    feed(engine)
    engine.advance_to(411337)
    image = engine.capture_state()
    restored_image = ArtifactCodec.decode(ArtifactCodec.encode(image, format))
    assert restored_image.digest == image.digest
    restored = create_engine(state=restored_image, backend=backend)
    engine.advance_to(733771)
    restored.advance_to(733771)
    assert_state_close(engine.capture_state().to_dict(), restored.capture_state().to_dict())
    child = birth(image).to_dict()
    assert child['dynamics'] == KERNEL_ID and child['time_us'] == '0'
    assert child['queue'] == []
    assert all(row['last_emit_us'] == '0' for row in child['nodes'])
    assert all(row['completed_period_us'] == '0' for row in child['edges'])
    assert child['nodes'] and child['edges']
    assert set(child['nodes'][0]) == {f.name for f in fields(Local5Node)}
    assert set(child['edges'][0]) == {f.name for f in fields(Local5Edge)}
    with pytest.raises(ValueError, match='identity|schema'):
        resolve_kernel('threemind.continuous-memory/4').create(state=image, backend=backend)


@pytest.mark.parametrize('backend', ['reference', 'native'])
@pytest.mark.parametrize('mode', ['adaptive-half-life', 'legacy-stability'])
def test_readout_boundaries_and_wall_clock_delays_cannot_change_core(backend, mode):
    config = resolve_kernel(KERNEL_ID).configuration({'consolidation_mode': mode})
    control = create_engine(config, kernel_id=KERNEL_ID, backend=backend)
    observed = create_engine(config, kernel_id=KERNEL_ID, backend=backend)
    session = ReadoutSession(observed, record=lambda _: None, config={
        'structural_readout': {'enabled': True, 'interval_us': 11357},
        'temporal_readout': {'enabled': True, 'interval_us': 17311},
        'activity_readout': {'enabled': True, 'interval_us': 19877}})
    for engine in (control, observed):
        feed(engine)
    control.advance_to(1001337)
    session.advance_to(1001337)
    assert control.capture_state().digest == observed.capture_state().digest
    before = observed.capture_state().digest
    for _ in range(3):
        observed.graph()
        observed.metrics()
        session.host.observe(observed, force=True)
        session.capture()
    now = [0]
    with patch('threemind_runtime.host.time.monotonic_ns', side_effect=lambda: now[0]), \
            patch('threemind_runtime.host.time.sleep'):
        host = Runtime(observed, clock='realtime')
        host.pace(observed.time_us + 20000)
        now[0] += 100_000_000_000
        host.pace(observed.time_us + 20000)
    assert observed.capture_state().digest == before
