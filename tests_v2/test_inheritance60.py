"""New engineering subjects only; no historical experimental state is loaded."""

import json

import pytest

from threemind_core import StateImage, Stimulus
from threemind_kernels.decay60 import CURVES
from threemind_kernels.local60 import KERNEL_ID, Local60Config, Local60Engine
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.ecology import EcologyCoordinator, EcologySettings
from threemind_runtime.ecology_job import EcologyJob, parse_job
from threemind_runtime.inheritance import BIRTH_RULE, KERNEL60_BIRTH_RULE, birth, birth_metadata
from threemind_runtime.world_schema import default_world


def parent(curve="inverse-logarithmic", delivery="address", backend="reference", **options):
    config = Local60Config(decay_curve=curve, inflight_delivery=delivery, **options)
    e = resolve_kernel(KERNEL_ID).create(config, backend=backend)
    for t, values in ((0, ((17, .8), (2**32 - 1, .7))), (100000, ((17, .6), (301, .5)))):
        e.inject(Stimulus(t, values))
    e.inject(Stimulus(2000000, ((301, .7),)))
    e.advance_to(333337)
    return e


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("delivery", ("address", "same-birth"))
@pytest.mark.parametrize("age", ("preserve", "reset"))
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_persistent_birth_and_complete_cross_backend_continuation(curve, delivery, age, backend):
    e = parent(curve, delivery, backend)
    source = e.capture_state()
    projected = Local60Engine(state=source)
    child_image = birth(source, decay_age=age)
    child = child_image.to_dict()
    assert source.digest == e.capture_state().digest
    assert source.to_dict()["queue"]  # Future parental stimuli must not reach the child.
    assert child["time_us"] == "0" and child["life"] == "waiting"
    assert child["queue"] == child["active"] == child["silenced_nodes"] == child["silenced_edges"] == []
    assert child["sequence"] == child["next_event"] == 0
    assert not any(child["transport"].values()) and not any(child["audit"].values())
    assert child["config"] == source.to_dict()["config"]
    for row in child["nodes"]:
        expected = projected._project_node(projected.nodes[row["id"]], projected.time_us)
        assert row["id"] == row["channel"]
        for key in ("support", "stability", "local_plasticity", "touches", "half_life", "region", "sleeping"):
            assert row[key] == getattr(expected, key)
        assert row["decay_age"] == (expected.decay_age if age == "preserve" else 0)
        for key in ("activation", "inhibition", "trace", "direct", "associative", "fatigue", "salience",
                    "pending_inhibition", "generated_inhibition", "reserve"):
            assert row[key] == 0
        assert all(row[k] == "0" for k in row if k.endswith("_us"))
    for row in child["edges"]:
        expected = projected._project_edge(projected.edges[row["source"], row["target"]], projected.time_us)
        for key in ("weight", "stability", "touches", "half_life", "sleeping"):
            assert row[key] == getattr(expected, key)
        assert row["decay_age"] == (expected.decay_age if age == "preserve" else 0)
        assert row["eligibility"] == row["novelty_source"] == row["novelty_target"] == 0
        assert row["short_term"] is row["fast"] is row["novelty_deadline_us"] is None
        assert all(row[k] == "0" for k in row if k.endswith("_us") and row[k] is not None)
    assert child_image.digest == birth(child_image, decay_age=age).digest
    portable = ArtifactCodec.decode(ArtifactCodec.encode(child_image, "tmind"))
    left = resolve_kernel(KERNEL_ID).create(state=portable, backend="reference")
    right = resolve_kernel(KERNEL_ID).create(state=portable, backend="native")
    assert left.capture_state().digest == right.capture_state().digest == child_image.digest
    for engine in (left, right):
        engine.inject(Stimulus(7777, ((17, .4), (301, .6))))
        engine.advance_to(230007)
    from test_local60 import same
    same(left.capture_state().to_dict(), right.capture_state().to_dict())


def test_dormant_structure_is_not_lost_through_a_filtered_graph_query():
    e = parent(dormant_traces_enabled=True)
    raw = e.capture_state().to_dict()
    raw["edges"][0]["sleeping"] = True
    source = StateImage.from_dict(raw)
    projected = Local60Engine(state=source)
    assert len(projected.induced_edges(projected.nodes)) < len(raw["edges"])
    newborn = birth(source).to_dict()
    assert len(newborn["edges"]) == len(raw["edges"])
    assert newborn["edges"][0]["sleeping"]


@pytest.mark.parametrize("policy", ("preserve", "reset"))
def test_energy_configuration_and_damage_timers_survive_birth(policy):
    e = parent(energy_simulation_enabled=True, energy_starvation_damage_enabled=True)
    child = birth(e.capture_state(), decay_age=policy)
    for backend in ("reference", "native"):
        engine = resolve_kernel(KERNEL_ID).create(state=child, backend=backend)
        engine.advance_to(20000)
        assert engine.time_us == 20000


@pytest.mark.parametrize("kernel", ("5.2", "5.3"))
def test_undefined_historical_births_still_refuse(kernel):
    image = resolve_kernel("threemind.continuous-memory/" + kernel).create(backend="reference").capture_state()
    with pytest.raises(ValueError, match="not defined"):
        birth(image)


def test_invalid_policy_wrong_version_and_negative_age_are_rejected():
    image = parent().capture_state()
    with pytest.raises(ValueError, match="preserve or reset"):
        birth(image, decay_age="guess")
    with pytest.raises(ValueError, match="identity"):
        birth(image, rule=BIRTH_RULE)
    old = resolve_kernel("threemind.continuous-memory/5.1").create(backend="reference").capture_state()
    with pytest.raises(ValueError, match="only"):
        birth(old, decay_age="reset")
    for backend in ("reference", "native"):
        raw = birth(image).to_dict()
        raw["edges"][0]["decay_age"] = -1
        with pytest.raises(ValueError):
            resolve_kernel(KERNEL_ID).create(state=StateImage.from_dict(raw), backend=backend)
    assert birth_metadata(image) == {"inheritance_rule": KERNEL60_BIRTH_RULE, "inheritance_decay_age": "preserve"}
    assert birth_metadata(old) == {"inheritance_rule": BIRTH_RULE}


def ecological_settings(age):
    value = EcologySettings(inheritance_rule=KERNEL60_BIRTH_RULE, inheritance_decay_age=age).model_dump(mode="json")
    value["rules"].update(uptake_per_s=100, maintenance_per_s=0)
    value["rules"]["patches"] = [{"id": "food", "radius": 10, "capacity": 100, "initial": 100, "regeneration_per_s": 0}]
    value["rules"]["reproduction"].update(interval_us=20000, minimum_age_us=20000, cooldown_us=1000000,
                                         threshold=4, offspring_reserve=1, population_limit=6)
    return EcologySettings.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("age", ("preserve", "reset"))
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_ecology_births_energy_balance_and_exact_population_recovery(age, backend):
    settings, events = ecological_settings(age), []
    with EcologyCoordinator(default_world(), settings, kernel_id=KERNEL_ID, backend=backend, record=events.append) as world:
        world.advance_to(20000)
        checkpoint = world.checkpoint()
        births = [e for e in events if e["kind"] == "individual_born"]
        assert len(births) == 2
        for event in births:
            images = checkpoint[1]
            assert event["inheritance_rule"] == KERNEL60_BIRTH_RULE
            assert event["inheritance_decay_age"] == age
            assert images[event["individual"]].digest == birth(images[event["parent"]], decay_age=age).digest
        world.ledger.check_balance()
        with EcologyCoordinator(default_world(), settings, kernel_id=KERNEL_ID, backend=backend, checkpoint=checkpoint) as resumed:
            for target in (47000, 60000, 100000):
                world.advance_to(target)
                resumed.advance_to(target)
                a, ai = world.checkpoint()
                b, bi = resumed.checkpoint()
                assert a == b
                assert {k: v.digest for k, v in ai.items()} == {k: v.digest for k, v in bi.items()}
        assert world.ledger.check_balance()["spent"] > 0
        assert max(a.generation for a in world.ledger.accounts.values()) >= 2
        assert len(world.world.members) == 6


def test_founder_default_resolves_the_saved_kernel_before_building_the_world():
    images = [parent().capture_state()] * 2
    with EcologyCoordinator(default_world(), EcologySettings(), founders=images, backend="reference") as world:
        assert world.settings.inheritance_rule == KERNEL60_BIRTH_RULE
    with pytest.raises(ValueError, match="match"):
        EcologyCoordinator(default_world(), EcologySettings(inheritance_rule=BIRTH_RULE), founders=images,
                           backend="reference")


@pytest.mark.parametrize("age", ("preserve", "reset"))
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_kernel60_recovers_before_pending_physical_delivery_and_birth(age, backend):
    settings = ecological_settings(age)
    with EcologyCoordinator(default_world(), settings, kernel_id=KERNEL_ID, backend=backend) as original:
        original.advance_to(17000)
        checkpoint = original.checkpoint()
        assert checkpoint[0]["pending_end_us"] == 20000
        with EcologyCoordinator(default_world(), settings, kernel_id=KERNEL_ID, backend=backend,
                                checkpoint=checkpoint) as resumed:
            for target in (20000, 47000, 100000):
                original.advance_to(target)
                resumed.advance_to(target)
                a, ai = original.checkpoint()
                b, bi = resumed.checkpoint()
                assert a == b
                assert {k: v.digest for k, v in ai.items()} == {k: v.digest for k, v in bi.items()}


def test_portable_protocol_defaults_and_historical_wire_shape():
    legacy = EcologySettings().model_dump(mode="json")
    assert "inheritance_decay_age" not in legacy
    assert legacy["inheritance_rule"] == BIRTH_RULE
    job = EcologyJob(kernel_id=KERNEL_ID)
    assert job.ecology.inheritance_rule == KERNEL60_BIRTH_RULE
    assert parse_job(job.model_dump_json()).digest == job.digest
    reset = EcologyJob(kernel_id=KERNEL_ID, ecology=ecological_settings("reset"))
    assert parse_job(reset.model_dump_json()).digest == reset.digest
    assert reset.digest != job.digest
    with pytest.raises(ValueError, match="match"):
        EcologyJob(kernel_id=KERNEL_ID, ecology=EcologySettings(inheritance_rule=BIRTH_RULE))
    with pytest.raises(ValueError, match="requires"):
        EcologySettings(inheritance_decay_age="reset")


def test_development_protocols_record_the_actual_birth_rule():
    from uuid import uuid4

    from test_assessments import protocol as assessment_fixture
    from test_evolution_protocol import protocol as evolution_fixture

    from threemind_lab.assessment_protocol import AssessmentProtocol
    from threemind_lab.evolution_protocol import EvolutionProtocol

    ev = evolution_fixture()
    for name in ("development", "evaluation"):
        ev[name].update(kernel_id=KERNEL_ID, config={})
    ap = assessment_fixture(str(uuid4()))
    ap["evaluation"].update(kernel_id=KERNEL_ID, config={})
    for cls, payload in ((EvolutionProtocol, ev), (AssessmentProtocol, ap)):
        parsed = cls.model_validate_json(json.dumps(payload))
        assert parsed.inheritance_rule == KERNEL60_BIRTH_RULE
        assert cls.model_validate_json(parsed.model_dump_json()) == parsed
        with pytest.raises(ValueError, match="match"):
            cls.model_validate_json(json.dumps(payload | {"inheritance_rule": BIRTH_RULE}))
