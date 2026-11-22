"""6.2 isolated engineering witnesses, not formal research subjects."""
import copy
import json
import math
from dataclasses import replace

import pytest
from test_local60 import inject_course, same
from test_local61 import OPTIONS

from threemind_core import StateImage, Stimulus
from threemind_kernels.local61 import Local61Config
from threemind_kernels.local62 import KERNEL_ID, Local62Config
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import birth


def make(config=None, backend="reference", state=None):
    return resolve_kernel(KERNEL_ID).create(config, state, backend=backend)


def image(doc):
    return StateImage(json.dumps(doc).encode())


def comparable(doc):
    doc = copy.deepcopy(doc)
    for k in ("schema", "dynamics", "definition", "definition_hash"):
        doc.pop(k, None)
    for k in ("activation_signal_threshold", "inhibition_signal_threshold", "stability_growth_enabled", "stability_relaxation_enabled", "activation_weight_reinforcement_enabled", "inhibition_weight_reinforcement_enabled", "resource_precheck_enabled", "subthreshold_expiry_enabled"):
        doc["config"].pop(k, None)
    for k in ("separate_inhibition", "separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning", "inhibition_updates_usage"):
        doc["config"].pop(k, None)
    return doc


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("options", OPTIONS)
def test_61_compatibility(backend, options):
    c = Local61Config(quiescence_death_us=10**12, **options)
    old = resolve_kernel("threemind.continuous-memory/6.1").create(c, backend=backend)
    new = make(Local62Config(**c.to_dict(), resource_precheck_enabled=False, subthreshold_expiry_enabled=False,
                            inhibition_updates_usage=True), backend)
    for e in (old, new):
        inject_course(e)
    for t in (0, 110000, 900000, 2100000, 10000000):
        old.advance_to(t)
        new.advance_to(t)
        assert comparable(old.capture_state().to_dict()) == comparable(new.capture_state().to_dict())


@pytest.mark.parametrize("mode", ("adaptive-half-life", "stability"))
@pytest.mark.parametrize("novelty", ("immediate", "arrival-window"))
@pytest.mark.parametrize("options", (
    {}, {"deletion_strategy": "global-scan"},
    {"stability_growth_enabled": False}, {"stability_relaxation_enabled": False},
    {"activation_signal_threshold": 0}, {"inhibition_signal_threshold": 0.004},
    {"activation_signal_threshold": 0.003, "inhibition_signal_threshold": 0.001},
    {"signal_threshold_enabled": False, "weight_gate_enabled": True},
    {"stp_facilitation_tau_s": 0.1}, {"energy_simulation_enabled": True},
    {"propagation_phase": "asynchronous"}, {"inflight_delivery": "same-birth"},
    {"activation_weight_reinforcement_enabled": False}, {"inhibition_weight_reinforcement_enabled": False},
    {"activation_weight_reinforcement_enabled": False, "inhibition_weight_reinforcement_enabled": False},
))
def test_python_rust_restore_observation_and_birth(mode, novelty, options):
    c = Local62Config(consolidation_mode=mode, novelty_mode=novelty, quiescence_death_us=10**12, **options)
    p, r = make(c), make(c, "native")
    inject_course(p)
    inject_course(r)
    for t in (0, 100000, 110000, 700000, 1800000, 10000000):
        p.advance_to(t)
        r.advance_to(t)
        same(p.capture_state().to_dict(), r.capture_state().to_dict())
        before = p.capture_state()
        p.activations()
        p.observation_nodes()
        p.metrics()
        assert before.payload == p.capture_state().payload
        p = make(state=before)
        r = make(backend="native", state=r.capture_state())
    child = birth(p.capture_state())
    same(make(state=child).capture_state().to_dict(), make(backend="native", state=child).capture_state().to_dict())
    assert child.to_dict()["time_us"] == "0"


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_signal_fallback_and_equal_override(backend):
    base = make(Local62Config(signal_threshold=.003), backend)
    explicit = make(Local62Config(signal_threshold=.009, activation_signal_threshold=.003, inhibition_signal_threshold=.003), backend)
    for e in (base, explicit):
        inject_course(e)
        e.advance_to(2000000)
    a, b = [e.capture_state().to_dict() for e in (base, explicit)]
    assert b["config"]["activation_signal_threshold"] == .003
    for d in (a, b):
        for k in ("config", "definition", "definition_hash"):
            d.pop(k)
    assert a == b


def test_optional_threshold_resolution():
    c = Local62Config(signal_threshold=.004, activation_signal_threshold=0)
    assert c.signal_threshold_for(False) == 0
    assert c.signal_threshold_for(True) == .004
    assert replace(c, inhibition_signal_threshold=.1).signal_threshold_for(True) == .1


@pytest.mark.parametrize("value", (-1, True, "0.1", float("inf"), float("nan")))
@pytest.mark.parametrize("field", ("activation_signal_threshold", "inhibition_signal_threshold"))
def test_invalid_thresholds(value, field):
    with pytest.raises(ValueError):
        Local62Config(**{field: value})


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("relax", (False, True))
def test_stability_decay_is_local_and_exact(backend, relax):
    c = Local62Config(consolidation_mode="stability", propagation_rate=0, inhibition=False,
                     local_novelty_gain=0, stability_relaxation_enabled=relax, quiescence_death_us=10**12)
    e = make(c, backend)
    e.inject(Stimulus(0, ((1, .3), (2, .3))))
    e.advance_to(0)
    saved = e.capture_state().to_dict()
    edge = saved["edges"][0]
    e.advance_to(c.propagation_interval_us)
    new = e.capture_state().to_dict()
    actual = new["edges"][0]
    dt = c.propagation_interval_us / 1e6
    eligibility = edge["eligibility"] * math.exp(-dt/c.eligibility_tau)
    stability = max(0, edge["stability"] - dt/c.stability_tau * (1 - eligibility)) if relax else edge["stability"]
    assert actual["eligibility"] == pytest.approx(eligibility)
    assert actual["stability"] == pytest.approx(stability)
    assert actual["weight"] == pytest.approx(edge["weight"] * (1-.1*c.forgetting_rate*(1-(.08+.92*stability)))**(dt/.1))
    assert new["audit"]["scan_visits"] == 0
    assert any(t[0] == 7 for t in new["timers"])
    new["timers"] = [t for t in new["timers"] if t[0] != 7]
    with pytest.raises(ValueError, match="stability deadline"):
        make(backend=backend, state=image(new))


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_growth_off_preserves_weight_reinforcement(backend):
    c = Local62Config(consolidation_mode="stability", stability_growth_enabled=False)
    e = make(c, backend)
    inject_course(e)
    e.advance_to(900000)
    rows = e.capture_state().to_dict()["edges"]
    assert rows and all(r["stability"] == 0 for r in rows)
    assert max(r["weight"] for r in rows) > c.birth_weight


def test_presets_and_api_metadata():
    from threemind_lab.configuration import catalogue
    from threemind_runtime.stimulus_presets import research_presets
    data = catalogue()
    fields = {f["path"]: f for f in data["fields"] if KERNEL_ID in f.get("kernels", ())}
    assert fields["config.activation_signal_threshold"]["nullable"]
    assert fields["config.activation_signal_threshold"]["default"] is None
    assert ["stability", "稳定度保持"] in fields["config.consolidation_mode"]["choices"]
    for p in research_presets():
        resolve_kernel(p["kernel_id"]).configuration(p["config"])


def test_stability_rejects_unstudied_hybrid():
    with pytest.raises(ValueError, match="H"):
        Local62Config(consolidation_mode="stability", retention_growth_enabled=True)


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("exc,inh", ((0,100),(100,0),(100,100)))
def test_independent_thresholds_control_delivered_signal_kinds(backend,exc,inh):
    e=make(Local62Config(activation_signal_threshold=exc,inhibition_signal_threshold=inh),backend)
    e.inject(Stimulus(0,((1,.7),(2,.7))))
    e.advance_to(100000)
    kinds={r['kind'] for r in e.capture_state().to_dict()['queue']}
    assert ('signal' in kinds) == (exc==0)
    assert ('inhibition' in kinds) == (inh==0)


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_stability_deletion_grid_and_reinforcement_at_deletion(backend):
    c=Local62Config(consolidation_mode='stability', stability_growth_enabled=False,
                   local_novelty_gain=0,propagation_rate=0,inhibition=False,
                   forgetting_rate=.8,quiescence_death_us=10**12)
    local,scan=make(c,backend),make(replace(c,deletion_strategy='global-scan'),backend)
    for e in (local,scan):
        e.inject(Stimulus(0,((1,.1),(2,.1))))
        e.advance_to(0)
    original=local.capture_state()
    cutoff=None
    for t in range(100000,10000001,100000):
        local.advance_to(t);scan.advance_to(t)
        a,b=local.capture_state().to_dict(),scan.capture_state().to_dict()
        assert a['edges']==b['edges']
        assert [n['id'] for n in a['nodes']]==[n['id'] for n in b['nodes']]
        # Local and global settlement timestamps differ; compare values projected
        # to the same observation time, not the lazy storage timestamps.
        same(local.observation_nodes(),scan.observation_nodes())
        if not a['edges']:
            cutoff=t;break
    assert cutoff and a['audit']['scan_visits']==0
    # An explicitly declared test branch supplies input at that deletion instant.
    revived=make(backend=backend,state=original)
    revived.inject(Stimulus(cutoff,((1,1.),(2,1.))))
    revived.advance_to(cutoff)
    assert len(revived.capture_state().to_dict()['edges'])==2


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("mode", ('stability','adaptive-half-life'))
def test_observer_pause_codec_and_advance_partition(backend,mode):
    import time
    c=Local62Config(consolidation_mode=mode,quiescence_death_us=10**12)
    a,b=make(c,backend),make(c,backend)
    inject_course(a);inject_course(b)
    a.advance_to(3000000)
    for t in (10000,100000,199999,200000,900000,1000001,3000000):
        b.advance_to(t)
        saved=b.capture_state()
        b.observation_nodes();b.graph();b.metrics();time.sleep(.001)
        assert saved.digest==b.capture_state().digest
        encoded=ArtifactCodec.encode(saved)
        b=make(backend=backend,state=ArtifactCodec.decode(encoded))
    assert a.capture_state().digest==b.capture_state().digest


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_stability_pause_plasticity_and_resume(backend):
    e=make(Local62Config(consolidation_mode='stability',quiescence_death_us=10**12),backend)
    inject_course(e);e.advance_to(1000000)
    e.reconfigure(replace(e.config,plasticity=False))
    assert not any(t[0]==7 for t in e.capture_state().to_dict()['timers'])
    e.advance_to(2000000)
    e=make(backend=backend,state=e.capture_state())
    e.reconfigure(replace(e.config,plasticity=True,stability_relaxation_enabled=False))
    assert any(t[0]==7 for t in e.capture_state().to_dict()['timers'])
    e.advance_to(2100000)
    make(backend=backend,state=e.capture_state())


@pytest.mark.parametrize("mode", ('stability','adaptive-half-life'))
@pytest.mark.parametrize("format", ('tmind','json'))
def test_independent_rust_runtime_round_trip(tmp_path,mode,format):
    import os
    import subprocess
    from pathlib import Path
    runtime_path=os.environ.get('THREEMIND_TEST_RUNTIME')
    if not runtime_path:
        pytest.skip('set THREEMIND_TEST_RUNTIME to test the separately built Rust executable')
    runtime=Path(runtime_path)
    e=make(Local62Config(consolidation_mode=mode,activation_signal_threshold=0,inhibition_signal_threshold=.004))
    inject_course(e);e.advance_to(100000)
    source=tmp_path/('source.'+format);out=tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(e.capture_state(),format))
    subprocess.run([str(runtime),'--model',str(source),'--clock','unbounded','--until-us','2100000','--export',str(out)],
                   check=True,capture_output=True)
    e.advance_to(2100000)
    saved=ArtifactCodec.decode(out.read_bytes())
    same(e.capture_state().to_dict(),saved.to_dict())


def test_delivered_defaults_and_independent_runtime(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    from threemind_kernels.registry import DEFAULT_KERNEL

    config = Local62Config()
    assert DEFAULT_KERNEL == 'threemind.continuous-memory/6.1'
    assert config.novelty_mode == 'arrival-window'
    assert config.consolidation_mode == 'adaptive-half-life'
    assert config.decay_curve == 'inverse-logarithmic'
    root = Path(__file__).resolve().parents[1]
    assert json.loads((root/'crates/threemind-core/src/local62-defaults.json').read_bytes()) == config.to_dict()
    runtime_path = os.environ.get('THREEMIND_TEST_RUNTIME')
    if not runtime_path:
        pytest.skip('set THREEMIND_TEST_RUNTIME to check standalone executable defaults')
    out = tmp_path/'new62.json'
    subprocess.run([runtime_path, '--kernel', KERNEL_ID, '--clock', 'unbounded',
                    '--until-us', '0', '--export', str(out)], check=True, capture_output=True)
    state = ArtifactCodec.decode(out.read_bytes()).to_dict()
    assert state['dynamics'] == KERNEL_ID
    assert state['config'] == config.to_dict()
