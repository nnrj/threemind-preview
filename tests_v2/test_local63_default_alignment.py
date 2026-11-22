"""/6.1 compatibility, default local expiry and pre-edit /6.3 restoration."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from test_local60 import same
from test_local63 import make, numerical
from threemind_core import StateImage, Stimulus
from threemind_kernels.local61_config import Local61Config
from threemind_kernels.local63_config import Local63Config
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec

ROOT = Path(__file__).resolve().parents[1]
WITNESSES = ROOT / '.work/kernel63-default-alignment/witnesses'


@pytest.mark.parametrize('backend', ['reference', 'native'])
@pytest.mark.parametrize('course', ['grouped', 'weak', 'same-time', 'ordered'])
def test_compatible_63_follows_61_at_every_boundary(backend, course):
    old = resolve_kernel('threemind.continuous-memory/6.1').create(backend=backend)
    new = make(Local63Config(subthreshold_expiry_enabled=False), backend=backend)
    frames = {
        'grouped': [(0, ((1, .8), (2, .3))), (300000, ((2, .4), (3, .2))), (900000, ((1, .2),))],
        'weak': [(0, ((1, .0001),))],
        'same-time': [(0, ((1, .0001),))] * 100,
        'ordered': [(i*100000, ((1+i%3, .2+(i%4)*.1),)) for i in range(20)],
    }[course]
    for e in (old, new):
        for when, channels in frames: e.inject(Stimulus(when, channels))
    for when in (0, 1, 100000, 110000, 300000, 900000, 2100000, 10000000, 300000000):
        old.advance_to(when); new.advance_to(when)
        same(numerical(old.capture_state()), numerical(new.capture_state()))
        state = new.capture_state()
        new.graph(); new.metrics(); new.observation_nodes()
        assert new.capture_state().digest == state.digest
        new = make(state=state, backend=backend)
    if course == 'weak':
        # This legacy scheduling artifact is deliberately retained, not repaired silently.
        assert new.capture_state().to_dict()['life'] == 'active'
        assert new.observation_nodes()[0]['activation'] == 0


@pytest.mark.parametrize('backend', ['reference', 'native'])
@pytest.mark.parametrize('expiry', [False, True])
def test_expiry_is_optional_and_keeps_the_quiet_period(backend, expiry):
    c = Local63Config(subthreshold_expiry_enabled=expiry, plasticity=False)
    e = make(c, backend=backend); e.inject(Stimulus(0, ((1, .0001),))); e.advance_to(0)
    assert e.capture_state().to_dict()['active'] == [1]
    e.advance_to(300000000)
    d = e.capture_state().to_dict()
    if expiry:
        assert d['life'] == 'dead' and d['active'] == []
        assert int(d['time_us']) == c.quiescence_death_us+1
    else:
        assert d['life'] == 'active' and d['quiet_since_us'] is None


@pytest.mark.parametrize('backend', ['reference', 'native'])
def test_expiry_does_not_remove_activation_above_existing_floor(backend):
    e = make(Local63Config(subthreshold_expiry_enabled=True, activation_decay_enabled=False,
                          plasticity=False), backend=backend)
    e.inject(Stimulus(0, ((1, .1),))); e.advance_to(300000000)
    assert e.capture_state().to_dict()['life'] == 'active'
    assert e.observation_nodes()[0]['activation'] > e.config.activation_floor


def test_defaults_match_python_rust_and_api_catalogue():
    from _threemind_native import NativeLocal63
    from threemind_lab.configuration import catalogue
    config = Local63Config().to_dict()
    for key, value in Local61Config().to_dict().items(): assert config[key] == value
    assert json.loads(NativeLocal63('{}', None).config_json()) == config
    fields = {v['path']: v for v in catalogue('threemind.continuous-memory/6.3')['fields']}
    for key, value in {'resource_precheck_enabled': False, 'subthreshold_expiry_enabled': True,
                       'inhibition_updates_usage': True, 'inhibition_bypasses_resources': False}.items():
        assert config[key] is value and fields['config.'+key]['default'] is value


@pytest.mark.parametrize('backend', ['reference', 'native'])
def test_remaining_default_difference_is_observable_and_declared(backend):
    old = resolve_kernel('threemind.continuous-memory/6.1').create(backend=backend)
    new = make(backend=backend)
    for engine in (old, new):
        engine.inject(Stimulus(0, ((1, .0001),)))
        engine.advance_to(300000000)
        assert sum(n['activation'] for n in engine.observation_nodes()) == 0
    assert old.capture_state().to_dict()['life'] == 'active'
    assert new.capture_state().to_dict()['life'] == 'dead'
    assert new.time_us == new.config.quiescence_death_us + 1


@pytest.mark.parametrize('backend', ['reference', 'native'])
@pytest.mark.parametrize('name', ['old-default', 'old-stability', 'old-independent', 'old-proportional', 'old-weak'])
def test_saved_63_defaults_are_not_overwritten(backend, name):
    if not WITNESSES.exists(): pytest.skip('pre-edit local engineering witnesses')
    before = StateImage.from_dict(json.loads((WITNESSES/(name+'-before.json')).read_text('utf8')))
    after = StateImage.from_dict(json.loads((WITNESSES/(name+'-after.json')).read_text('utf8')))
    e = make(state=before, backend=backend)
    assert e.config.resource_precheck_enabled is True
    assert e.config.subthreshold_expiry_enabled is True
    assert e.config.inhibition_updates_usage is False
    assert e.config.inhibition_bypasses_resources is (name != 'old-independent')
    e.advance_to(300000000 if name == 'old-weak' else 2100000)
    same(e.capture_state().to_dict(), after.to_dict())


def test_frozen_historical_sources_and_witnesses_unchanged():
    if not WITNESSES.exists(): pytest.skip('pre-edit local manifest')
    manifest = json.loads((WITNESSES/'manifest.json').read_text('utf8'))
    for path, expected in manifest['historical_sources'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
    for path, expected in manifest['witnesses'].items():
        assert hashlib.sha256((WITNESSES/path).read_bytes()).hexdigest() == expected, path


def test_standalone_birth_uses_current_defaults(tmp_path):
    runtime = ROOT / 'target/release/threemind-runtime.exe'
    destination = tmp_path / 'born.json'
    subprocess.run([str(runtime), '--kernel', 'threemind.continuous-memory/6.3',
                    '--clock', 'unbounded', '--until-us', '0', '--export', str(destination)],
                   check=True, capture_output=True)
    state = ArtifactCodec.decode(destination.read_bytes())
    assert state.to_dict()['config'] == Local63Config().to_dict()
    same(state.to_dict(), make().capture_state().to_dict())


@pytest.mark.parametrize('format', ['json', 'tmind'])
def test_standalone_keeps_previous_default_configuration(tmp_path, format):
    if not WITNESSES.exists(): pytest.skip('pre-edit engineering witnesses')
    before = StateImage.from_dict(json.loads((WITNESSES/'old-default-before.json').read_text('utf8')))
    after = StateImage.from_dict(json.loads((WITNESSES/'old-default-after.json').read_text('utf8')))
    source, target = tmp_path/('initial.'+format), tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(before, format))
    subprocess.run([str(ROOT/'target/release/threemind-runtime.exe'), '--model', str(source),
                    '--clock', 'unbounded', '--until-us', '2100000', '--export', str(target)],
                   check=True, capture_output=True)
    same(ArtifactCodec.decode(target.read_bytes()).to_dict(), after.to_dict())
