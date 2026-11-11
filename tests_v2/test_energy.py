import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_core.energy import Energy, supply_payload
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.store import SQLiteStore

BACKENDS = ["reference", "native"]


def balance(ledger):
    consumed = sum(ledger[f"consumed_{kind}"] for kind in ("direct", "associative", "inhibition", "maintenance"))
    assert ledger["initial_total"] + ledger["supplied_total"] == pytest.approx(
        ledger["reserve"] + consumed + ledger["discarded_total"], rel=1e-11, abs=1e-13
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_disabled_energy_preserves_frozen_causal3_evolution_and_explicit_upgrade(backend):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal3-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        create_engine(state=before, backend=backend)


@pytest.mark.parametrize("backend", BACKENDS)
def test_energy_has_no_hidden_recovery_and_supply_does_not_create_activity(backend):
    c = Config(
        inhibition=False,
        propagation_rate=0,
        energy_simulation_enabled=True,
        energy_initial_reserve=0.05,
        energy_direct_cost=0.1,
    )
    e = create_engine(c, backend=backend)
    e.supply_energy(0.02, time_us=0, source="explicit-reservoir")
    records = []
    e.advance_to(0, records.append, inputs_only=True)
    assert e.metrics()["activation"] == 0 and e.metrics()["nodes"] == 0
    assert records[0]["kind"] == "energy" and records[0]["payload"]["accepted"] == 0.02
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(0)
    assert e.metrics()["activation"] == pytest.approx(0.7)
    assert e.metrics()["energy"]["reserve"] == 0
    e.advance_to(15001)
    assert e.metrics()["energy"]["reserve"] == 0
    balance(e.metrics()["energy"])
    assert e.metrics()["energy"]["unserved_total"] > 0
    with pytest.raises(ValueError):
        e.supply_energy(0.1, time_us=0)
    with pytest.raises(ValueError):
        e.reconfigure(replace(c, energy_initial_reserve=0.9))


@pytest.mark.parametrize("backend", BACKENDS)
def test_energy_pause_toggle_supply_rejection_and_capacity_discard_are_explicit(backend):
    c = Config(energy_simulation_enabled=True, energy_direct_cost=1, inhibition=False, propagation_rate=0)
    e = create_engine(c, backend=backend)
    e.inject(Stimulus(0, ((1, 0.5),)))
    e.supply_energy(0.3, time_us=20000)
    e.advance_to(5001)
    snapshot = e.capture_state()
    e.reconfigure(c)
    assert e.capture_state().digest == snapshot.digest
    e.reconfigure(replace(c, energy_simulation_enabled=False))
    remaining = e.metrics()["energy"]["reserve"]
    records = []
    e.advance_to(30000, records.append, inputs_only=True)
    assert records[-1]["payload"]["status"] == "disabled" and records[-1]["payload"]["accepted"] == 0
    e.reconfigure(c)
    assert e.metrics()["energy"]["reserve"] == remaining
    e.reconfigure(replace(c, energy_capacity=0.2))
    assert e.metrics()["energy"]["reserve"] == 0.2
    balance(e.metrics()["energy"])
    assert create_engine(state=e.capture_state(), backend=backend).capture_state().digest == e.capture_state().digest


@pytest.mark.parametrize("backend", BACKENDS)
def test_maintenance_charges_actual_existence_and_observer_partition_is_inert(backend):
    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_direct_cost=0,
        energy_maintenance_cost_per_node=2,
        energy_maintenance_cost_per_edge=0,
        inhibition=False,
        propagation_rate=0,
        energy_starvation_structural_decay=0.1,
    )
    e = create_engine(c, backend=backend)
    e.inject(Stimulus(5000, ((1, 0.8),)))
    e.advance_to(10000)
    assert e.metrics()["energy"]["consumed_maintenance"] == pytest.approx(0.01)
    saved = e.capture_state()
    resumed = create_engine(state=saved, backend=backend)
    for t in (11001, 15003, 17003, 19001, 23011, 33331):
        e.advance_to(t)
        image = e.capture_state()
        e.metrics()
        assert e.capture_state().digest == image.digest
    resumed.advance_to(33331)
    assert e.capture_state().digest == resumed.capture_state().digest
    balance(e.metrics()["energy"])


@pytest.mark.parametrize("backend", BACKENDS)
def test_supply_alone_cannot_cancel_quiescence_death_and_inputs_cannot_resurrect(backend):
    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.01,
        energy_direct_cost=0.01,
        activation_tau=0.0001,
        quiescence_death_us=7001,
        inhibition=False,
    )
    e = create_engine(c, backend=backend)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    e.advance_to(10000)
    saved = e.capture_state()
    assert saved.to_dict()["quiet_since_us"] == "10000"
    a = create_engine(state=saved, backend=backend)
    a.supply_energy(0.2, time_us=17001)
    a.advance_to(30000)
    assert a.life == "dead" and a.metrics()["energy"]["reserve"] > 0
    assert a.metrics()["energy"]["starved_since_us"] is None
    e.inject(Stimulus(17001, ((1, 0.8),)))  # Real input with no affordable activation.
    e.inject(Stimulus(20000, ((1, 0.8),)))
    e.advance_to(17000)
    assert e.life == "active"
    e.advance_to(30000)
    assert e.time_us == 17001 and e.life == "dead" and e.metrics()["activation"] == 0
    state = e.capture_state().to_dict()
    assert state["energy"]["death_us"] == "17001"
    assert len(state["nodes"]) == 2 and len(state["edges"]) == 2
    assert len(state["queue"]) == 1  # No destruction of already recorded events.
    assert state["sources_open"] is True
    with pytest.raises(ValueError):
        e.supply_energy(0.2)
    with pytest.raises(ValueError):
        e.inject(Stimulus(17001, ((1, 0.8),)))
    assert create_engine(state=e.capture_state(), backend=backend).capture_state().digest == e.capture_state().digest
    balance(a.metrics()["energy"])


def test_energy_payload_and_ledger_validation():
    for value in (-1, True, float("inf"), 1e13):
        with pytest.raises(ValueError):
            supply_payload(value)
    for patch in ({"energy_simulation_enabled": 1}, {"energy_capacity": 0}, {"energy_starvation_damage_enabled": 1}):
        with pytest.raises(ValueError):
            Config(**patch)
    original = Energy.initial(Config()).to_dict()
    for patch in (
        {"reserve": 2},
        {"last_settlement_us": "01"},
        {"since_us": "2"},
        {"consumed_direct": -1},
        {"starved_since_us": "0"},
    ):
        with pytest.raises(ValueError):
            Energy.restore(original | patch, 1, Config())


def test_energy_reference_native_combination_and_inhibition_conservation():
    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.05,
        energy_capacity=0.4,
        energy_direct_cost=0.05,
        energy_maintenance_cost_per_node=0.01,
        energy_maintenance_cost_per_edge=0.003,
        edge_birth_policy="temporal-association",
        propagation_limit=4,
        edge_adaptation_limit=5,
        max_nodes=6,
        max_edges=10,
    )
    models = []
    for backend in BACKENDS:
        e = create_engine(c, backend=backend)
        for i in range(12):
            e.supply_energy(0.013, time_us=i * 19001, source="bounded-external-fixture")
            e.inject(Stimulus(i * 21001, ((i % 7, 0.8), ((i + 2) % 7, 0.4), ((i + 4) % 7, 0.6))))
        e.advance_to(150003)
        saved = e.capture_state()
        resumed = create_engine(state=saved, backend=backend)
        e.advance_to(500019)
        resumed.advance_to(500019)
        assert e.capture_state().digest == resumed.capture_state().digest
        ledger = e.metrics()["energy"]
        balance(ledger)
        assert all(ledger[f"consumed_{k}"] > 0 for k in ("direct", "associative", "inhibition", "maintenance"))
        models.append(e.capture_state().to_dict())
    a, b = models
    assert a["resources"] == b["resources"]
    for left, right in [
        (a["energy"], b["energy"]),
        *zip(a["nodes"], b["nodes"], strict=True),
        *zip(a["edges"], b["edges"], strict=True),
    ]:
        for key in left:
            assert (
                left[key] == pytest.approx(right[key], rel=1e-10, abs=1e-12)
                if isinstance(left[key], float)
                else left[key] == right[key]
            )


@pytest.mark.parametrize("runtime", ["rust", "python"])
@pytest.mark.parametrize("format", ["json", "tmind"])
def test_energy_portable_external_supply_and_terminal_sqlite_state(tmp_path, runtime, format):
    from tests_v2.test_runtime_interop import RUNTIME
    from threemind_lab.worker import birth

    c = Config(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.01,
        activation_tau=0.0001,
        quiescence_death_us=7001,
        inhibition=False,
    )
    e = create_engine(c)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    model = tmp_path / f"source.{format}"
    model.write_bytes(ArtifactCodec.encode(e.capture_state(), format))
    supplies = tmp_path / "supply.jsonl"
    supplies.write_text(
        json.dumps({"time_us": "6001", "amount": 0.2, "source": "external-test-reservoir"}) + "\n", encoding="utf-8"
    )
    prefix = [str(RUNTIME)] if runtime == "rust" else [sys.executable, "-m", "threemind_runtime.cli"]
    output, store = tmp_path / "supplied.tmind", tmp_path / "supplied.sqlite"
    result = subprocess.run(
        prefix
        + [
            "--model",
            str(model),
            "--energy-input",
            str(supplies),
            "--clock",
            "unbounded",
            "--until-us",
            "35007",
            "--store",
            str(store),
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    e.supply_energy(0.2, time_us=6001, source="external-test-reservoir")
    e.advance_to(35007)
    assert ArtifactCodec.decode(output.read_bytes()).digest == e.capture_state().digest
    assert SQLiteStore(store).load("default")[1].digest == e.capture_state().digest
    inherited = birth(e.capture_state())
    assert inherited.to_dict()["energy"] == Energy.initial(c).to_dict()
    # Natural decay, then the quiescence grace: terminal state must still be persisted.
    dead_store = tmp_path / "dead.sqlite"
    result = subprocess.run(
        prefix + ["--model", str(model), "--clock", "unbounded", "--until-us", "50000", "--store", str(dead_store)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    dead = SQLiteStore(dead_store).load("default")[1].to_dict()
    assert dead["life"] == "dead" and dead["time_us"] == "17001"
    assert dead["energy"]["death_us"] == "17001"
