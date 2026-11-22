import copy
import json

import pytest

from threemind_core import StateImage, Stimulus
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.ecology import EcologyCoordinator, EcologySettings
from threemind_runtime.inheritance import birth
from threemind_runtime.population_participant import CoreParticipant, ParticipantConfig
from threemind_runtime.world_schema import default_world, digest


@pytest.fixture(autouse=True)
def historical_ecology_kernel(monkeypatch):
    # These legacy fixtures predate the selectable 5.3 constructor default.
    # Keep testing their original implementation instead of rebirthing 5.3.
    from threemind_kernels import registry
    monkeypatch.setattr(registry, "DEFAULT_KERNEL", registry.BASELINE_KERNEL)


def configuration(habitat="shared"):
    value = EcologySettings().model_dump(mode="json")
    value["rules"].update(habitat=habitat, uptake_per_s=100, maintenance_per_s=0)
    value["rules"]["patches"] = [{"id": "food", "radius": 10, "capacity": 100, "initial": 100, "regeneration_per_s": 0}]
    value["rules"]["reproduction"].update(
        interval_us=20000,
        minimum_age_us=20000,
        cooldown_us=1000000,
        threshold=4,
        offspring_reserve=1,
        population_limit=6,
    )
    return EcologySettings.model_validate_json(json.dumps(value))


def serialized(checkpoint):
    metadata, images = checkpoint
    return json.loads(json.dumps(metadata)), {
        key: StateImage.from_dict(image.to_dict()) for key, image in images.items()
    }


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_real_births_inherit_stimulus_formed_structure_and_reset_activity(backend, habitat):
    events = []
    with EcologyCoordinator(default_world(), configuration(habitat), backend=backend, record=events.append) as trainer:
        trainer.advance_to(20000)
        metadata, images = trainer.checkpoint()
        births = [e for e in events if e["kind"] == "individual_born"]
        assert len(births) == 2
        assert all(e["model_born"] and e["core_viability_checked"] for e in births)
        for event in births:
            parent, child = images[event["parent"]], images[event["individual"]]
            assert parent.to_dict()["nodes"] and parent.to_dict()["edges"]
            assert event["source_state_hash"] == parent.digest
            assert event["state_hash"] == child.digest == birth(parent).digest
            assert all(n["activation"] == n["trace"] == 0 for n in child.to_dict()["nodes"])
            assert child.to_dict()["time_us"] == "0" and not child.to_dict()["queue"]
            portable = create_engine(state=ArtifactCodec.decode(ArtifactCodec.encode(child, "tmind")), backend=backend)
            before = portable.metrics()["nodes"]
            portable.inject(Stimulus(1000, ((987654321, 0.8),)))
            portable.advance_to(3000)
            assert portable.metrics()["nodes"] > before
        trainer.advance_to(100000)
        assert max(a.generation for a in trainer.ledger.accounts.values()) >= 2
        assert len(trainer.world.members) == 6
        assert metadata["pending_end_us"] is None
        assert trainer.ledger.check_balance()["spent"] > 0


@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_mid_delivery_checkpoint_restores_all_brains_physics_and_pending_births(habitat):
    spec, settings = default_world(), configuration(habitat)
    with EcologyCoordinator(spec, settings) as uninterrupted:
        uninterrupted.advance_to(17000)
        checkpoint = serialized(uninterrupted.checkpoint())
        meta, images = checkpoint
        assert meta["time_us"] == 17000
        assert meta["world"]["time_us"] == meta["ledger"]["time_us"] == meta["pending_end_us"] == 20000
        assert meta["ledger"]["pending_reproduction_us"] == 20000
        assert all(image.to_dict()["time_us"] == "17000" for image in images.values())
        assert all(image.to_dict()["queue"] for image in images.values())
        with EcologyCoordinator(spec, settings, checkpoint=checkpoint) as resumed:
            assert uninterrupted.checkpoint()[0] == resumed.checkpoint()[0]
            for target in (20000, 47000, 60000, 87000, 100000):
                uninterrupted.advance_to(target)
                resumed.advance_to(target)
                left, left_images = uninterrupted.checkpoint()
                right, right_images = resumed.checkpoint()
                assert left == right
                assert {k: v.digest for k, v in left_images.items()} == {k: v.digest for k, v in right_images.items()}


def test_body_failure_closes_declared_sources_without_faking_death_or_removing_brain_evidence():
    settings = configuration()
    settings.rules.patches = []
    settings.rules.founder_reserve = 0.01
    settings.rules.maintenance_per_s = 1
    events, observations = [], []
    with EcologyCoordinator(
        default_world(),
        settings,
        record=events.append,
        participant_record=lambda identity, value: observations.append((identity, value)),
    ) as trainer:
        trainer.advance_to(20000)
        assert not trainer.world.members
        assert all(not body.alive for body in trainer.ledger.accounts.values())
        assert len(trainer.participants) == 2  # No false elimination of raw brain states.
        images = trainer.checkpoint()[1]
        assert all(not image.to_dict()["sources_open"] for image in images.values())
        assert all(e["core_death_observed"] is False for e in events if e["kind"] == "body_failed")
        assert all(image.to_dict()["nodes"] for image in images.values())
        saved = serialized(trainer.checkpoint())
        with EcologyCoordinator(default_world(), settings, checkpoint=saved) as resumed:
            trainer.advance_to(140000)
            resumed.advance_to(140000)
            assert trainer.checkpoint()[0] == resumed.checkpoint()[0]
        delivered = [value for _, value in observations if value["kind"] == "input_delivered"]
        assert len(delivered) == 2


def test_passive_tools_and_observer_changes_do_not_feed_back_into_core():
    world = default_world()
    settings = configuration()
    options = ParticipantConfig()
    options.acoustic_output = type(options.acoustic_output)(enabled=True)
    options.activation_projector = type(options.activation_projector)(enabled=True)
    quiet = copy.deepcopy(options)
    quiet.structural_readout = type(quiet.structural_readout)(enabled=False)
    quiet.temporal_readout = type(quiet.temporal_readout)(enabled=False)
    quiet.acoustic_output = type(quiet.acoustic_output)(enabled=False)
    quiet.activation_projector = type(quiet.activation_projector)(enabled=False)
    records = []
    with (
        EcologyCoordinator(
            world, settings, participant_options=options, participant_record=lambda i, e: records.append((i, e))
        ) as observed,
        EcologyCoordinator(world, settings, participant_options=quiet) as control,
    ):
        for target in (20000, 53000, 100000):
            observed.advance_to(target)
            control.advance_to(target)
            assert {k: v.digest for k, v in observed.checkpoint()[1].items()} == {
                k: v.digest for k, v in control.checkpoint()[1].items()
            }
        kinds = {e["kind"] for _, e in records}
        assert {"organ_output", "structural_readout", "input_scheduled", "input_delivered"} <= kinds
        raw = [e["payload"] for _, e in records if e["kind"] == "structural_readout"]
        assert any(value["raw_nodes"] for value in raw)
        assert all(
            value["raw_observation"]["complete"] and len(value["raw_nodes"]) == value["source_node_count"]
            for value in raw
        )


def test_a_failed_boundary_cannot_be_checkpointed_or_treated_as_natural_extinction():
    class Broken(CoreParticipant):
        def receive(self, frame, evidence):
            super().receive(frame, evidence)
            if self.identity == "n1":
                raise RuntimeError("injected participant failure")

    factory = lambda identity, image, state: Broken(identity, image, 20260724, state=state)
    with EcologyCoordinator(default_world(), configuration(), participant_factory=factory) as trainer:
        with pytest.raises(RuntimeError, match="injected"):
            trainer.advance_to(20000)
        assert trainer.failed
        with pytest.raises(ValueError, match="partially failed"):
            trainer.checkpoint()
        with pytest.raises(ValueError, match="restored"):
            trainer.advance_to(40000)


def test_nested_observer_mutation_cannot_change_inputs_or_other_consumers():
    settings = configuration()
    settings.rules.reproduction.enabled = False
    records, control_records = [], []

    def mutate(identity, event):
        for value in event.values():
            if isinstance(value, (dict, list)):
                value.clear()
        event.clear()

    with (
        EcologyCoordinator(default_world(), settings, participant_record=mutate) as observed,
        EcologyCoordinator(
            default_world(), settings, participant_record=lambda i, e: control_records.append((i, e))
        ) as control,
        EcologyCoordinator(default_world(), settings) as unsubscribed,
    ):
        for identity, participant in observed.participants.items():
            participant.output.subscribe("faithful", lambda event, key=identity: records.append((key, event)))
        for boundary in (17000, 20000, 47000, 100000):
            for population in (observed, control, unsubscribed):
                population.advance_to(boundary)
            expected, images = control.checkpoint()
            for population in (observed, unsubscribed):
                metadata, actual = population.checkpoint()
                assert metadata == expected
                assert {k: v.digest for k, v in actual.items()} == {k: v.digest for k, v in images.items()}
        assert records == control_records
        assert any(event["kind"] == "input_delivered" for _, event in records)
        assert any(event.get("payload", {}).get("raw_nodes") for _, event in records)


def test_checkpoint_rejects_missing_brains_time_mixtures_and_changed_protocols():
    world, settings = default_world(), configuration()
    with EcologyCoordinator(world, settings) as trainer:
        trainer.advance_to(17000)
        metadata, images = serialized(trainer.checkpoint())
    with pytest.raises(ValueError, match="missing a brain"):
        EcologyCoordinator(world, settings, checkpoint=(metadata, {"n0": images["n0"]}))
    changed = copy.deepcopy(metadata)
    changed["time_us"] = 16000
    changed["checkpoint_hash"] = digest({k: v for k, v in changed.items() if k != "checkpoint_hash"})
    with pytest.raises(ValueError, match="brain clock"):
        EcologyCoordinator(world, settings, checkpoint=(changed, images))
    with pytest.raises(ValueError, match="checksum"):
        EcologyCoordinator(world, settings, checkpoint=(metadata | {"time_us": 16000}, images))
    settings.senses.enabled = False
    with pytest.raises(ValueError, match="protocol changed"):
        EcologyCoordinator(world, settings, checkpoint=(metadata, images))
