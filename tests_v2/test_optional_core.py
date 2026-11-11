"""Scientific mechanism and frozen baseline controls, not cognitive claims."""

import json
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_core.spec import DYNAMICS, OPTIONAL_DEFAULTS
from threemind_lab.configuration import default_spec
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.store import SQLiteStore

CONTROL = json.loads((Path(__file__).parent / "fixtures/causal1-continuation.json").read_text())


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_frozen_legacy_resume_default_equivalence_and_versioned_reconfigure(backend):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal1-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        create_engine(state=before, backend=backend)


def settle(config, frames, until, backend):
    engine = create_engine(config, backend=backend)
    for time, channels in frames:
        engine.inject(Stimulus(time, tuple(channels)))
    engine.advance_to(until)
    return engine


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_temporal_birth_uses_real_touch_window_and_internal_delivery(backend):
    config = Config(inhibition=False, propagation_rate=0, forgetting_rate=0, association_window_us=20001)
    frames = [(0, [(4, 0.8)]), (20001, [(8, 0.7)])]
    assert not settle(config, frames, 20001, backend).capture_state().to_dict()["edges"]
    temporal = replace(config, edge_birth_policy="temporal-association")
    engine = settle(temporal, frames, 20001, backend)
    assert [(e["source"], e["target"]) for e in engine.capture_state().to_dict()["edges"]] == [(1, 2)]
    assert (
        not settle(temporal, [(0, [(4, 0.8)]), (20002, [(8, 0.7)])], 20002, backend).capture_state().to_dict()["edges"]
    )
    # Internal signal really reaches an existing node. It may form a temporal
    # association from another recently touched node, never an untouched identity.
    c = replace(temporal, association_window_us=500000, propagation_rate=4.2)
    active = settle(c, [(0, [(10, 0.8), (20, 0.5)]), (11001, [(30, 0.8)])], 19000, backend)
    resumed = create_engine(state=active.capture_state(), backend=backend)
    for t in (20000, 100000, 110000, 161001):
        active.advance_to(t)
    resumed.advance_to(161001)
    assert active.capture_state().digest == resumed.capture_state().digest
    s = active.capture_state().to_dict()
    assert any(e["source"] == 3 and e["target"] in (1, 2) for e in s["edges"])
    assert {n["channel"] for n in s["nodes"]} == {10, 20, 30}


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_optional_thresholds_caps_homeostasis_and_state_bounds(backend):
    base = Config(inhibition=False, propagation_rate=0, forgetting_rate=0)
    frames = [(0, [(1, 0.8), (2, 0.8)])]
    no_birth = settle(replace(base, edge_birth_activation_product_min=0.6), frames, 0, backend)
    assert not no_birth.capture_state().to_dict()["edges"]
    ordinary = settle(base, frames, 0, backend)
    capped = settle(replace(base, consolidation_cap=0), frames, 0, backend)
    assert (
        capped.capture_state().to_dict()["edges"][0]["weight"]
        < ordinary.capture_state().to_dict()["edges"][0]["weight"]
    )
    ordinary.reconfigure(replace(base, edge_birth_activation_product_min=1))
    previous = ordinary.capture_state().to_dict()["edges"][0]["weight"]
    # Keep both endpoints below saturation: a score of 1 would accidentally
    # pass the birth gate and conceal a gate wrongly applied to existing edges.
    ordinary.inject(Stimulus(10001, ((1, 0.01), (2, 0.01))))
    ordinary.advance_to(10001)
    assert ordinary.capture_state().to_dict()["edges"][0]["weight"] > previous  # threshold is birth-only
    inhibited = settle(Config(inhibition_saturation=3, inhibition_gain=20), frames, 100000, backend)
    assert max(n["inhibition"] for n in inhibited.capture_state().to_dict()["nodes"]) > 1
    create_engine(state=inhibited.capture_state(), backend=backend)
    inhibited.reconfigure(replace(inhibited.config, inhibition_saturation=0.2))
    assert all(n["inhibition"] <= 0.2 for n in inhibited.capture_state().to_dict()["nodes"])
    c = replace(base, homeostasis_enabled=True, target_total_activation=0.25)
    clamped = settle(c, frames + [(10001, [(1, 0.9), (2, 0.9)])], 10001, backend)
    assert clamped.metrics()["activation"] == pytest.approx(0.25)
    create_engine(state=clamped.capture_state(), backend=backend)  # activity components stay valid too
    flux_limited = settle(Config(propagation_rate=0, inhibition_propagation_min=1e6), frames, 100000, backend)
    assert max(n["inhibition"] for n in flux_limited.capture_state().to_dict()["nodes"]) > 0
    assert not flux_limited.capture_state().to_dict()["queue"]  # self-inhibition arrived; diffusion was suppressed
    # Suppressing emissions does not remove previously scheduled signals.
    emitting = settle(Config(inhibition=False), frames, 100000, backend)
    pending = emitting.capture_state().to_dict()["queue"]
    assert any(q["kind"] == "signal" for q in pending)
    emitting.reconfigure(replace(emitting.config, propagation_activation_min=1))
    assert emitting.capture_state().to_dict()["queue"] == pending
    emitting.advance_to(200000)
    assert not any(q["kind"] == "signal" for q in emitting.capture_state().to_dict()["queue"])


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_local_novelty_requires_existing_neighbourhood_and_nonzero_reentry(backend):
    common = Config(inhibition=False, forgetting_rate=0)

    def born(config, frames, until):
        return settle(config, frames, until, backend).capture_state().to_dict()["edges"]

    one = [(0, [(1, 0.6), (2, 0.6)])]
    assert born(common, one, 0) == born(replace(common, local_novelty_gain=0.2), one, 0)
    later = one + [(150001, [(1, 0.2), (3, 0.6)])]
    without = born(common, later, 150001)
    with_bonus = born(replace(common, local_novelty_gain=0.2), later, 150001)
    assert (
        next(e for e in with_bonus if e["source"] == 1 and e["target"] == 3)["weight"]
        > next(e for e in without if e["source"] == 1 and e["target"] == 3)["weight"]
    )
    no_reentry = replace(common, propagation_rate=0)
    assert born(no_reentry, later, 150001) == born(replace(no_reentry, local_novelty_gain=0.2), later, 150001)


def test_optional_reference_native_numerics_and_invalid_configuration():
    c = Config(
        edge_birth_policy="temporal-association",
        local_novelty_gain=0.018,
        inhibition_saturation=2,
        inhibition_propagation_min=0.0001,
        homeostasis_enabled=True,
        target_total_activation=1.4,
        consolidation_cap=0.08,
    )
    frames = [(i * 31007, [(i % 5, 0.8), ((i + 2) % 5, 0.4)]) for i in range(12)]
    a, b = [settle(c, frames, 1500013, backend).capture_state().to_dict() for backend in ("reference", "native")]
    assert a["config"] == b["config"] and a["dynamics"] == b["dynamics"] == DYNAMICS
    for collection in ("nodes", "edges"):
        for left, right in zip(a[collection], b[collection], strict=True):
            for key in left:
                if isinstance(left[key], float):
                    assert left[key] == pytest.approx(right[key], rel=1e-10, abs=1e-12)
                else:
                    assert left[key] == right[key]
    for key, value in [
        ("homeostasis_enabled", 1),
        ("edge_birth_policy", "invented"),
        ("association_window_us", 0),
        ("consolidation_cap", 1.1),
        ("inhibition_saturation", 0),
        ("novelty_touch_reference", 0),
        ("local_novelty_gain", float("nan")),
    ]:
        with pytest.raises(ValueError):
            Config(**{key: value})
    assert all(k in default_spec()["config"] for k in OPTIONAL_DEFAULTS)


@pytest.mark.parametrize("format", ["json", "tmind"])
def test_optional_model_rust_and_sqlite_roundtrip(tmp_path, format):
    from tests_v2.test_runtime_interop import RUNTIME

    config = Config(
        edge_birth_policy="temporal-association",
        inhibition_saturation=2,
        local_novelty_gain=0.018,
        homeostasis_enabled=True,
        target_total_activation=0.8,
    )
    e = settle(config, [(0, [(1, 0.7), (2, 0.8)]), (70003, [(2, 0.6), (3, 0.7)])], 10007, "native")
    original = e.capture_state()
    model = tmp_path / f"source.{format}"
    model.write_bytes(ArtifactCodec.encode(original, format))
    output = tmp_path / "result.tmind"
    store = tmp_path / "device.sqlite"
    result = subprocess.run(
        [
            str(RUNTIME),
            "--model",
            str(model),
            "--clock",
            "unbounded",
            "--until-us",
            "130009",
            "--export",
            str(output),
            "--store",
            str(store),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    e.advance_to(130009)
    assert ArtifactCodec.decode(output.read_bytes()).digest == e.capture_state().digest
    assert SQLiteStore(store).load("default")[1].digest == e.capture_state().digest
    assert ArtifactCodec.decode(model.read_bytes()).digest == original.digest


def test_optional_configuration_upgrade_is_audited_without_overwriting_old_checkpoint(database):
    from fastapi.testclient import TestClient

    from threemind_lab.api import create_app
    from threemind_lab.config import Settings

    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Optional core controls"}).json()["id"]
        spec = default_spec() | {"environment": "manual", "clock": "unbounded"}
        spec["config"] = CONTROL["before"]["config"]
        run = database.create_run(project, "Legacy control", spec)
        old = StateImage.from_dict(CONTROL["before"])
        cp = database.save_checkpoint(project, run["id"], old, expected_revision=0, status="paused")
        spec["config"] = asdict(
            replace(Config(**spec["config"]), edge_birth_policy="temporal-association", consolidation_cap=0.1)
        )
        base = f"/api/v2/projects/{project}/runs/{run['id']}"
        saved = client.put(
            f"{base}/configuration", json={"name": "Optional core", "spec": spec, "expected_revision": 1}
        )
        assert saved.status_code == 422 and "read-only" in saved.text
        image = database.load_checkpoint(project, run["id"])[1]
        assert image.digest == old.digest
        assert database.load_checkpoint(project, run["id"], cp["id"])[1].digest == old.digest
        assert client.get(f"{base}/events?kind=configuration_changed").json() == []
