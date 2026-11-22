"""Separate signal weights/resources: causal witnesses and complete-state parity."""
import hashlib
from dataclasses import replace

import pytest
from test_local60 import inject_course, same
from threemind_core import StateImage, Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local62 import KERNEL_ID, Local62Config, Local62Engine
from threemind_kernels.registry import resolve_kernel
from threemind_runtime.inheritance import birth
from threemind_runtime import ArtifactCodec

KEYS = ("separate_inhibition", "separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning")


def make(config=None, state=None, backend="reference"):
    return resolve_kernel(KERNEL_ID).create(config, state, backend=backend)


@pytest.mark.parametrize("weights,resources,learning", [(False, False, False), (True, False, False), (False, True, False), (True, True, False), (True, False, True), (True, True, True)])
@pytest.mark.parametrize("mode", ["adaptive-half-life", "stability"])
@pytest.mark.parametrize("options", [{}, {"novelty_mode": "immediate"}, {"reinforcement_age_policy": "reset"},
    {"retention_growth_enabled": False, "deletion_strategy": "global-scan"},
    {"stp_facilitation_tau_s": .1, "resource_precheck_enabled": False},
    {"depletion_enabled": False, "inhibitory_learning_enabled": False},
    {"weight_gate_enabled": True, "weight_gate": .2},
    {"energy_simulation_enabled": True, "energy_starvation_damage_enabled": True}])
def test_cross_backend_continuity_and_observation(weights, resources, learning, mode, options):
    c = Local62Config(separate_inhibition_weights=weights, separate_inhibition_resources=resources, separate_inhibition_learning=learning,
                      consolidation_mode=mode, quiescence_death_us=10**12, **options)
    p, r = make(c), make(c, backend="native")
    for e in (p, r):
        inject_course(e)
    for t in (0, 110000, 900000, 2100000, 10000000):
        p.advance_to(t); r.advance_to(t)
        same(p.capture_state().to_dict(), r.capture_state().to_dict())
        before = p.capture_state()
        assert ArtifactCodec.decode(ArtifactCodec.encode(before)).digest == before.digest
        p.graph(); p.metrics(); p.observation_nodes()
        assert before.digest == p.capture_state().digest
        p = make(state=before)
        r = make(state=r.capture_state(), backend="native")
    original = p.capture_state()
    for age in ("preserve", "reset"):
        child = birth(original, decay_age=age)
        same(make(state=child).capture_state().to_dict(), make(state=child, backend="native").capture_state().to_dict())
        if weights:
            for row in child.to_dict()["edges"]:
                assert row["inhibition_weight"] is not None
        assert all("inhibition_short_term" not in row for row in child.to_dict()["edges"])
    assert original.digest == p.capture_state().digest


@pytest.mark.parametrize("positive", [False, True])
@pytest.mark.parametrize("separated", [False, True])
def test_each_transmission_learns_own_weight_and_resource(positive, separated):
    c = Local62Config(separate_inhibition_weights=separated, separate_inhibition_resources=True,
                      signal_threshold_enabled=False, strong_fatigue_enabled=False, fast_enabled=False)
    e = Local62Engine(c)
    e.inject(Stimulus(0, ((1, .4), (2, .3)))); e.advance_to(0)
    n = e.nodes[1]
    n.activation = .5 if positive else 0
    n.inhibition = 0 if positive else .5
    n.pending_inhibition = n.generated_inhibition = 0
    before = e.edges[1, 2].weight
    e._emit(1)
    edge = e.edges[1, 2]
    if positive:
        assert edge.weight > before
        if separated:
            assert edge.inhibition_weight == before
        assert edge.short_term is not None and edge.inhibition_short_term is None
    else:
        assert edge.weight == before if separated else edge.weight > before
        if separated:
            assert edge.inhibition_weight > before
        assert edge.inhibition_short_term is not None and edge.short_term is None
    assert e.config.inhibitory_learning_enabled


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_separation_is_a_birth_choice_and_old_artifacts_remain_shared(backend):
    e = make(backend=backend)
    inject_course(e); e.advance_to(2100000)
    d = e.capture_state().to_dict()
    for key in KEYS:
        d["config"].pop(key); d["definition"]["config"].pop(key)
    d["definition_hash"] = hashlib.sha256(canonical_bytes(d["definition"])).hexdigest()
    old = make(state=StateImage.from_dict(d), backend=backend)
    old.advance_to(10000000); e.advance_to(10000000)
    same(old.capture_state().to_dict(), e.capture_state().to_dict())
    for key in KEYS:
        with pytest.raises(ValueError):
            old.reconfigure(replace(old.config, **{key: True}))


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_deletion_requires_both_weights_below_threshold(backend):
    c = Local62Config(separate_inhibition_weights=True, propagation_rate=0, inhibition=False,
                      local_novelty_gain=0, quiescence_death_us=10**12)
    e = make(c, backend=backend)
    e.inject(Stimulus(0, ((1, .4), (2, .3)))); e.advance_to(0)
    d = e.capture_state().to_dict()
    for edge in d["edges"]:
        edge["inhibition_weight"] = edge["weight"]
        edge["weight"] = .00001
    e = make(state=StateImage.from_dict(d), backend=backend)
    e.advance_to(1000000)
    assert len(e.capture_state().to_dict()["edges"]) == 2


@pytest.mark.parametrize("key", KEYS)
def test_catalogue_and_validation(key):
    from threemind_lab.configuration import catalogue, default_spec, validate_configuration
    field = next(f for f in catalogue(KERNEL_ID)["fields"] if f["path"] == "config." + key)
    assert field["default"] is (False if key == "separate_inhibition" else None) and field["immutable"]
    for value in (True, False):
        patch = {key: value}
        if key == "separate_inhibition_learning":
            patch["separate_inhibition_weights"] = True
        assert validate_configuration(default_spec(kernel_id=KERNEL_ID) | {"config": patch})["valid"]
    for value in (0, 1, "false"):
        with pytest.raises(ValueError):
            Local62Config(**{key: value})


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_master_and_child_precedence(backend):
    automatic = make(Local62Config(separate_inhibition=True), backend=backend)
    explicit = make(Local62Config(separate_inhibition_weights=True, separate_inhibition_resources=True,
                                  separate_inhibition_learning=True), backend=backend)
    override = make(Local62Config(separate_inhibition=True, separate_inhibition_weights=False,
                                  separate_inhibition_resources=False, separate_inhibition_learning=False), backend=backend)
    shared = make(Local62Config(), backend=backend)
    for e in (automatic, explicit, override, shared):
        inject_course(e);e.advance_to(2000000)
    for left,right in ((automatic,explicit),(override,shared)):
        docs=[e.capture_state().to_dict() for e in (left,right)]
        for doc in docs:
            for k in ("config","definition","definition_hash"):doc.pop(k)
        same(*docs)
    with pytest.raises(ValueError):
        make(Local62Config(separate_inhibition=True,separate_inhibition_weights=False),backend=backend)


@pytest.mark.parametrize('updates',[False,True])
def test_full_learning_separation_prevents_inhibition_from_refreshing_excitation(updates):
    c=Local62Config(separate_inhibition=True,signal_threshold_enabled=False,inhibition_updates_usage=updates)
    e=Local62Engine(c);e.inject(Stimulus(0,((1,.4),(2,.3))));e.advance_to(100000)
    n=e.nodes[1];n.activation=0;n.inhibition=.5;n.pending_inhibition=n.generated_inhibition=0
    edge=e._settle_edge((1,2));before={k:getattr(edge,k) for k in e._LEARNING_FIELDS}
    weight=edge.weight; inhibitory_weight=edge.inhibition_weight
    e._emit(1);edge=e.edges[1,2]
    assert edge.weight==weight
    assert before=={k:getattr(edge,k) for k in e._LEARNING_FIELDS}
    assert edge.inhibition_learning["last_pass_us"]==(str(e.time_us) if updates else '0')
    assert edge.inhibition_weight>inhibitory_weight


@pytest.mark.parametrize("weights,resources,learning", [(False,False,False),(False,True,False),
    (True,False,False),(True,True,False),(True,False,True),(True,True,True)])
@pytest.mark.parametrize("format", ["json","tmind"])
def test_standalone_runtime_preserves_separated_state(tmp_path,weights,resources,learning,format):
    import os
    import subprocess
    from pathlib import Path
    runtime=os.environ.get('THREEMIND_TEST_RUNTIME')
    if not runtime:pytest.skip('set THREEMIND_TEST_RUNTIME for standalone round-trip')
    e=make(Local62Config(separate_inhibition_weights=weights,separate_inhibition_resources=resources,
                         separate_inhibition_learning=learning,consolidation_mode='stability'))
    inject_course(e);e.advance_to(100000)
    source=tmp_path/('source.'+format);target=tmp_path/('final.'+format)
    source.write_bytes(ArtifactCodec.encode(e.capture_state(),format))
    subprocess.run([str(Path(runtime)),'--model',str(source),'--clock','unbounded','--until-us','2100000',
                    '--export',str(target)],check=True,capture_output=True)
    e.advance_to(2100000)
    same(e.capture_state().to_dict(),ArtifactCodec.decode(target.read_bytes()).to_dict())
