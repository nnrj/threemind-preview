"""New-birth policy and saved-state isolation after the 2026-11-11 decision."""

import json
from pathlib import Path

import pytest

from threemind_core import Stimulus
from threemind_kernels.decay53 import CURVES
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import DEFAULT_KERNEL, kernel_catalog
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.platform_configuration import factory
from threemind_runtime import ArtifactCodec, create_engine


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_new_birth_defaults_and_rust_constructor_agree(backend):
    assert DEFAULT_KERNEL == KERNEL_ID
    engine = create_engine(backend=backend)
    state = engine.capture_state().to_dict()
    assert state["dynamics"] == KERNEL_ID
    assert state["config"]["decay_curve"] == "inverse-logarithmic"
    assert state["config"]["reinforcement_age_policy"] == "keep"
    assert not state["config"]["retention_growth_enabled"]
    assert not state["config"]["retention_relaxation_enabled"]
    rust = json.loads((Path(__file__).resolve().parents[1] /
                       "crates/threemind-core/src/local53-defaults.json").read_text())
    assert rust == Local53Config().to_dict() == state["config"]
    assert default_spec()["kernel_id"] == factory()["kernel_id"] == KERNEL_ID
    assert default_spec()["config"] == factory()["config"] == state["config"]


@pytest.mark.parametrize("version,curves,default", (
    ("5.2", CURVES[:3], "exponential"),
    ("5.3", CURVES, "inverse-logarithmic"),
))
def test_version_and_all_decay_options_are_exposed_and_valid(version, curves, default):
    identity = "threemind.continuous-memory/" + version
    catalog = catalogue(kernel_id=identity)
    assert catalog["defaults"]["config"]["decay_curve"] == default
    options = next(f for f in catalog["fields"] if f["path"] == "config.decay_curve"
                   and identity in f.get("kernels", ()))
    assert {row[0] for row in options["choices"]} == set(curves)
    assert [row["kernel_id"] for row in kernel_catalog() if row["default"]] == [KERNEL_ID]
    for curve in curves:
        spec = default_spec(identity)
        spec["config"]["decay_curve"] = curve
        result = validate_configuration(spec)
        assert result["valid"], result
        assert result["spec"]["config"]["decay_curve"] == curve


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("identity,curve", (
    ("threemind.continuous-memory/3", None),
    ("threemind.continuous-memory/5.1", None),
    ("threemind.continuous-memory/5.2", "exponential"),
    (KERNEL_ID, "power-law"),
    (KERNEL_ID, "power-exponential"),
))
def test_saved_individual_restores_its_own_version_and_curve(backend, identity, curve):
    configuration = {} if curve is None else {"decay_curve": curve}
    old = create_engine(configuration, kernel_id=identity, backend=backend)
    old.inject(Stimulus(0, ((1, 0.7), (2, 0.5))))
    old.advance_to(123456)
    saved = old.capture_state()
    # Restoration deliberately omits kernel_id, exercising identity detection.
    restored = create_engine(state=ArtifactCodec.decode(ArtifactCodec.encode(saved)), backend=backend)
    assert restored.capture_state().digest == saved.digest
    assert restored.capture_state().to_dict()["dynamics"] == identity
    if curve is not None:
        assert restored.config.decay_curve == curve
    old.advance_to(750000)
    restored.advance_to(750000)
    assert old.capture_state().digest == restored.capture_state().digest
