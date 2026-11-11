import json
import math
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.store import SQLiteStore


@pytest.fixture(params=["reference", "native"])
def make_engine(request):
    return partial(create_engine, backend=request.param)


def test_spatial_default_preserves_frozen5_and_upgrade_keeps_live_modulators(make_engine):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal5-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        make_engine(state=before)


def test_developmental_coordinates_and_geometry_do_not_create_connections(make_engine):
    e = make_engine(Config(spatial_embedding=True, spatial_radius=0.1, inhibition=False))
    e.advance_to(20000)
    assert e.spatial_geometry()["nodes"] == []
    e.inject(Stimulus(20001, ((1, 0.9), (2, 0.7))))
    e.advance_to(20001)
    image = e.capture_state()
    geometry = e.spatial_geometry()
    assert geometry["nodes"][0]["position"] == [0.16660335147753358, -0.6203176029957831, 0.9635058753192425]
    assert geometry["neighbor_edges"] == 0 and geometry["clusters"] == 2
    assert geometry["edges"] == [] and image.digest == e.capture_state().digest
    geometry["nodes"][0]["position"][0] = 99
    assert e.spatial_geometry()["nodes"][0]["position"][0] != 99
    with pytest.raises(ValueError, match="immutable"):
        e.reconfigure(replace(e.config, seed=e.config.seed + 1))
    e.reconfigure(replace(e.config, spatial_dimensions=64))
    assert len(e.spatial_geometry()["nodes"][0]["position"]) == 64
    assert e.spatial_geometry()["nodes"][0]["position"][:3] == [
        0.16660335147753358,
        -0.6203176029957831,
        0.9635058753192425,
    ]
    e.reconfigure(replace(e.config, neighborhood_enabled=False))
    e.inject(Stimulus(e.time_us, ((1, 0.9), (2, 0.7))))
    e.advance_to(e.time_us)
    assert e.metrics()["edges"] == 2
    assert e.spatial_geometry()["neighbor_edges"] == 0  # topology exists beyond the selected radius
    restored = make_engine(state=e.capture_state())
    assert restored.spatial_geometry() == e.spatial_geometry()


def connected(make_engine, **updates):
    e = make_engine(Config(spatial_embedding=True, inhibition=False, spatial_radius=4))
    e.inject(Stimulus(0, ((1, 0.9), (2, 0.6))))
    e.advance_to(0)
    state = e.capture_state().to_dict()
    state["config"].update(plasticity=False, **updates)
    state["nodes"][0].update(activation=0.8, direct=0.8, associative=0)
    state["nodes"][1].update(activation=0.3, direct=0.3, associative=0)
    return state


def test_distance_controls_adaptation_and_excitatory_flux_but_not_topology_deletion(make_engine):
    state = connected(make_engine, activation_floor=0)  # isolate geometry from the restored per-edge cutoff
    e = make_engine(state=StateImage.from_dict(state))
    distance = e.spatial_geometry()["edges"][0]["distance"]
    whole, half, blocked = [make_engine(state=StateImage.from_dict(deepcopy(state))) for _ in range(3)]
    whole.reconfigure(replace(whole.config, neighborhood_enabled=False))
    half.reconfigure(replace(half.config, spatial_radius=2 * distance))
    blocked.reconfigure(replace(blocked.config, spatial_radius=distance / 2))
    for engine in (whole, half, blocked):
        assert engine.metrics()["edges"] == 2
        engine.advance_to(100000)

    def signals(engine):
        return next(q["payload"]["values"] for q in engine.capture_state().to_dict()["queue"] if q["kind"] == "signal")

    for (a, x), (b, y) in zip(signals(whole), signals(half), strict=True):
        assert a == b and y == pytest.approx(x * 0.5)
    assert all(q["kind"] != "signal" for q in blocked.capture_state().to_dict()["queue"])
    # Already emitted signals retain the original geometry's delivery and value.
    queue = half.capture_state().to_dict()["queue"]
    half.reconfigure(replace(half.config, spatial_radius=0.01))
    assert half.capture_state().to_dict()["queue"] == queue
    half.advance_to(110000)
    assert half.metrics()["activation"] > blocked.metrics()["activation"] * 0.5
    growing = make_engine(state=StateImage.from_dict(state))
    growing.reconfigure(replace(growing.config, spatial_radius=0.01, plasticity=True))
    before = growing.capture_state().to_dict()["edges"]
    growing.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    growing.advance_to(0)
    assert growing.capture_state().to_dict()["edges"] == before


def test_spatial_competition_uses_fixed_time_boundary_snapshot_and_keeps_inhibition_separate(make_engine):
    state = connected(make_engine, propagation_rate=0, neighborhood_enabled=False, spatial_competition_rate=2)
    e = make_engine(state=StateImage.from_dict(state))
    e.advance_to(10000)
    rows = e.capture_state().to_dict()["nodes"]
    assert rows[0]["activation"] == pytest.approx(0.8 * math.exp(-0.01 / e.config.activation_tau))
    assert rows[1]["activation"] == pytest.approx(0.3 * math.exp(-0.01 / e.config.activation_tau - 0.02))
    digest = e.capture_state().digest
    e.spatial_geometry()
    e.metrics()
    assert e.capture_state().digest == digest
    split = make_engine(state=StateImage.from_dict(state))
    for t in (4999, 5001, 7999, 10000):
        split.advance_to(t)
    assert split.capture_state().digest == digest
    state["config"].update(inhibition=True, spatial_competition_rate=0, neighborhood_enabled=True)
    state["nodes"][0]["inhibition"] = 0.7
    state["nodes"][1]["inhibition"] = 0.1
    state["config"]["spatial_radius"] = 0.01
    small = make_engine(state=StateImage.from_dict(state))
    state["config"]["spatial_radius"] = 4
    large = make_engine(state=StateImage.from_dict(state))
    for engine in (small, large):
        engine.advance_to(10000)
    assert small.capture_state().to_dict()["queue"] == large.capture_state().to_dict()["queue"]


def test_spatial_validation_and_closed_independent_ports(make_engine):
    for invalid in (
        {"spatial_dimensions": 0},
        {"spatial_dimensions": 65},
        {"spatial_dimensions": True},
        {"spatial_radius": 0},
        {"spatial_competition_rate": float("inf")},
        {"spatial_embedding": 1},
    ):
        with pytest.raises(ValueError):
            Config(**invalid)
    e = make_engine(Config(energy_simulation_enabled=True))
    e.inject(Stimulus(100000, ((1, 0.8),)))
    e.close_inputs()
    state = e.capture_state()
    with pytest.raises(ValueError):
        e.modulate_input(gain=0.5)
    with pytest.raises(ValueError):
        e.supply_energy(0.2)
    assert e.capture_state().digest == state.digest


def test_competition_chain_is_not_changed_by_edge_traversal_order(make_engine):
    engine = make_engine(Config(spatial_embedding=True, spatial_radius=4, inhibition=False))
    engine.inject(Stimulus(0, ((1, 0.9), (2, 0.6), (3, 0.5))))
    engine.advance_to(0)
    state = engine.capture_state().to_dict()
    state["config"].update(
        propagation_rate=0, plasticity=False, neighborhood_enabled=False, spatial_competition_rate=100
    )
    state["edges"] = [e for e in state["edges"] if (e["source"], e["target"]) in ((1, 2), (2, 3))]
    forward = make_engine(state=StateImage.from_dict(state))
    state["edges"].reverse()
    reverse = make_engine(state=StateImage.from_dict(state))
    for e in (forward, reverse):
        e.advance_to(10000)
    assert forward.capture_state().digest == reverse.capture_state().digest
    # The middle node remains a stronger source in the shared pre-competition snapshot,
    # even though the first edge makes it weaker than the last node during this step.
    last = forward.capture_state().to_dict()["nodes"][2]
    assert last["activation"] == pytest.approx(
        state["nodes"][2]["activation"] * math.exp(-0.01 / forward.config.activation_tau - 1)
    )


@pytest.mark.parametrize("runtime", ["rust", "python"])
@pytest.mark.parametrize("format", ["json", "tmind"])
def test_causal_geometry_portable_plastic_model_and_sqlite(tmp_path, runtime, format):
    from test_runtime_interop import RUNTIME

    e = create_engine(
        Config(spatial_embedding=True, spatial_dimensions=4, spatial_radius=2.5, spatial_competition_rate=0.2)
    )
    for i in range(8):
        e.inject(Stimulus(i * 11007, ((i % 4, 0.8), ((i + 1) % 4, 0.5))))
    e.advance_to(25003)
    source, output, store = tmp_path / f"source.{format}", tmp_path / "output.tmind", tmp_path / "local.sqlite"
    source.write_bytes(ArtifactCodec.encode(e.capture_state(), format))
    prefix = [str(RUNTIME)] if runtime == "rust" else [sys.executable, "-m", "threemind_runtime.cli"]
    result = subprocess.run(
        prefix
        + [
            "--model",
            str(source),
            "--store",
            str(store),
            "--clock",
            "unbounded",
            "--until-us",
            "65011",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    e.advance_to(65011)
    restored = create_engine(state=ArtifactCodec.decode(output.read_bytes()))
    assert restored.capture_state().digest == e.capture_state().digest
    assert restored.spatial_geometry() == e.spatial_geometry()
    assert SQLiteStore(store).load("default")[1].digest == e.capture_state().digest
