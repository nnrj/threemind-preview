"""The accepted shortage-damage mechanism never decides life/death itself."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth


@pytest.fixture(params=["reference", "native"])
def backend(request):
    return lambda *args, **kwargs: create_engine(*args, **kwargs, backend=request.param)


def test_causal8_energy_artifact_is_read_only_and_losslessly_exportable(backend):
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/causal8-energy-before-unification.json").read_text(encoding="utf-8")
    )
    image = StateImage.from_dict(fixture["state"])
    assert image.digest == fixture["hash"]
    for format in ("json", "tmind"):
        restored = ArtifactCodec.decode(ArtifactCodec.encode(image, format))
        assert restored.digest == fixture["hash"]
        with pytest.raises(ValueError, match="read-only"):
            backend(state=restored)
        with pytest.raises(ValueError, match="read-only"):
            birth(restored)


def test_zero_reserve_keeps_activity_and_events_while_shortage_erodes_structure(backend):
    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0,
        energy_direct_cost=0,
        direct_gain=1,
        inhibition=False,
        propagation_rate=0,
        activation_decay_enabled=False,
        support_decay_enabled=False,
    )
    e = backend(c)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    e.advance_to(0)
    e.reconfigure(replace(c, plasticity=False))
    e.inject(Stimulus(92_000_000, ((1, 0.8),)))
    before = e.capture_state()
    resumed = backend(state=before)
    control = backend(state=before)
    control.reconfigure(replace(c, plasticity=False, energy_starvation_damage_enabled=False))
    no_erosion = backend(state=before)
    no_erosion.reconfigure(replace(c, plasticity=False, energy_starvation_structural_decay=0))
    for when in (7001, 900003, 90_000_001, 91_000_000):
        e.advance_to(when)
    resumed.advance_to(91_000_000)
    control.advance_to(91_000_000)
    no_erosion.advance_to(91_000_000)
    state = e.capture_state().to_dict()
    assert e.capture_state().digest == resumed.capture_state().digest
    assert state["life"] == "active" and state["quiet_since_us"] is None
    assert state["energy"]["reserve"] == 0 and state["energy"]["death_us"] is None
    assert state["energy"]["starved_since_us"] == "0"
    assert state["sources_open"] is True
    assert state["queue"] == before.to_dict()["queue"]
    assert [n["activation"] for n in state["nodes"]] == [0.8, 0.6]
    assert 0 < state["edges"][0]["weight"] < before.to_dict()["edges"][0]["weight"]
    assert state["nodes"][0]["support"] < before.to_dict()["nodes"][0]["support"]
    assert control.capture_state().to_dict()["edges"] == before.to_dict()["edges"]
    assert no_erosion.capture_state().to_dict()["edges"] == before.to_dict()["edges"]
    assert no_erosion.metrics()["energy"]["last_maintenance_deficit"] == 1
    e.supply_energy(0.2, time_us=91_000_001)
    e.advance_to(91_000_001)
    assert e.life == "active" and e.metrics()["energy"]["starved_since_us"] is None


def test_arrival_at_activity_deadline_revives_activity_without_energy_reserve(backend):
    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.01,
        inhibition=False,
        propagation_rate=0,
        activation_tau=0.0001,
        quiescence_death_us=7001,
    )
    e = backend(c)
    e.inject(Stimulus(0, ((1, 0.8),)))
    e.advance_to(10000)
    state = e.capture_state().to_dict()
    assert state["quiet_since_us"] == "10000" and state["energy"]["reserve"] == 0
    state["next_event"] += 1
    # An already paid, in-flight excitation arrives exactly at the death boundary.
    state["queue"] = [
        {"time_us": "17001", "id": state["next_event"], "kind": "signal", "payload": {"values": [[1, 0.5]]}}
    ]
    e = backend(state=StateImage.from_dict(state))
    e.advance_to(17001)
    assert e.life == "active" and e.metrics()["activation"] == pytest.approx(0.5)
    assert e.capture_state().to_dict()["quiet_since_us"] is None
    assert e.metrics()["energy"]["reserve"] == 0


def test_unactivated_energy_starved_receptor_remains_waiting(backend):
    e = backend(Config(energy_simulation_enabled=True, energy_starvation_damage_enabled=True, energy_initial_reserve=0))
    e.inject(Stimulus(0, ((1, 0.8),)))
    e.advance_to(2_000_000)
    assert e.life == "waiting" and e.metrics()["activation"] == 0
    assert e.metrics()["nodes"] == 1 and e.metrics()["energy"]["death_us"] is None


def test_removed_forced_death_parameters_cannot_be_saved_or_silently_reinterpreted():
    fields = {f["path"]: f for f in catalogue()["fields"]}
    assert fields["config.energy_starvation_damage_enabled"]["default"] is False
    for key, value in (("irreversible_energy_death_enabled", True), ("energy_starvation_death_us", 1)):
        assert f"config.{key}" not in fields
        result = validate_configuration(default_spec() | {"config": {key: value}})
        assert not result["valid"]
