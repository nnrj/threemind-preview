"""Independent backend witnesses; all organisms here are synthetic fixtures."""

import hashlib
from dataclasses import replace

import pytest

from threemind_core import Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local import LocalConfig
from threemind_kernels.local5 import Local5Config, Local5Engine
from threemind_kernels.local5_native import NativeLocal5Engine
from threemind_kernels.local_native import NativeLocalEngine

native = pytest.importorskip("_threemind_native")
pytestmark = pytest.mark.skipif(not hasattr(native, "NativeLocal5"), reason="memory/5 native binding is required")


def assert_equivalent(left, right, path="state"):
    if isinstance(left, dict):
        assert left.keys() == right.keys(), path
        for key, value in left.items():
            assert_equivalent(value, right[key], f"{path}.{key}")
    elif isinstance(left, list):
        assert len(left) == len(right), path
        for index, (a, b) in enumerate(zip(left, right)):
            assert_equivalent(a, b, f"{path}[{index}]")
    elif isinstance(left, float):
        assert left == pytest.approx(right, abs=1e-14, rel=1e-12), path
    else:
        assert left == right, path


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("source", ["legacy-source", "unified"])
@pytest.mark.parametrize("arrival", ["sequential", "coincident"])
@pytest.mark.parametrize("phase", ["aligned", "asynchronous"])
def test_five_configurations_preserve_cross_backend_trajectory_and_restore(mode, source, arrival, phase):
    config = Local5Config(
        consolidation_mode=mode,
        reception_mode=source,
        arrival_mode=arrival,
        propagation_phase=phase,
        quiescence_death_us=10**12,
    )
    py, rust = Local5Engine(config), NativeLocal5Engine(config)
    for time, channels in (
        (0, ((1, 0.8), (2, 0.7))),
        (70000, ((1, 0.5), (3, 0.5))),
        (80000, ((1, 0.1),)),
        (110000, ((1, 0.6), (4, 0.7))),
        (611337, ((1, 0.6), (3, 0.7))),
    ):
        for engine in (py, rust):
            engine.inject(Stimulus(time, channels))
            engine.advance_to(time)
        assert_equivalent(py.capture_state().to_dict(), rust.capture_state().to_dict())
    # Restoring the other backend's complete current boundary preserves identity.
    py_state, rust_state = py.capture_state(), rust.capture_state()
    py, rust = Local5Engine(state=rust_state), NativeLocal5Engine(state=py_state)
    for engine in (py, rust):
        before = engine.capture_state().payload
        engine.metrics()
        engine.graph()
        engine.activations()
        assert before == engine.capture_state().payload
        engine.advance_to(2000000)
    assert_equivalent(py.capture_state().to_dict(), rust.capture_state().to_dict())


@pytest.mark.parametrize(
    "options",
    [
        {"local_novelty_gain": 0.0},
        {"energy_simulation_enabled": True, "energy_model": "global-ledger", "energy_initial_reserve": 0.04},
        {"energy_simulation_enabled": True, "energy_model": "local-field", "energy_region_count": 1},
        {"spatial_embedding": True, "neighborhood_enabled": False},
        {"spatial_embedding": True, "neighborhood_enabled": True},
    ],
)
def test_optional_features_and_same_time_completion_match_native(options):
    config = Local5Config(**options, quiescence_death_us=10**12)
    py, rust = Local5Engine(config), NativeLocal5Engine(config)
    for when, channels, intensity in (
        (0, ((1, 0.8), (2, 0.6)), 2.0),
        (100000, ((1, 0.4), (2, 0.2)), 1.0),
        (100000, ((1, 0.3), (3, 0.4)), 1.0),
        (100000, ((3, 0.002),), 1.0),
    ):
        for engine in (py, rust):
            engine.advance_to(when)
            engine.inject(Stimulus(when, channels, intensity=intensity))
            engine.advance_to(when)
        assert_equivalent(py.capture_state().to_dict(), rust.capture_state().to_dict())
    for engine in (py, rust):
        engine.reconfigure(replace(config, plasticity=False))
        engine.advance_to(1000000)
        engine.reconfigure(config)
        engine.advance_to(2000000)
    assert_equivalent(py.capture_state().to_dict(), rust.capture_state().to_dict())


# Independently captured using the installed pre-change Rust extension.
FROZEN_NATIVE4 = {
    "adaptive-half-life": (
        "f9207940af6b465e97899abd109d98bad1306f0c09c6fbeea482efab78040318",
        "3c0b424378629c7c05ce9ff4fb1a87d5e7a804c433dd42c5293228740d7ab0e8",
        "800f615a9730038e641576d134b54b60b25df79d78c378730952c38a8a4e0522",
        "00ac7125885a5ea82a2c130e943ee821d5af262b493ad409aa24df510aadb0e1",
    ),
    "legacy-stability": (
        "8705785d68b0476995ef5f8f24e1c3ef6b952cfdac8fa11288f9ed28f4037f2c",
        "d5021d026bd8e5da5fd4fb0ad19768c60423c92136a4875ca38cffabe9bd97e5",
        "dff7679ebd71d8cde11f48d93b48f50f48795b4f1e9c35aea279e43f307fa764",
        "7ec9edf417203c5995b8bda6f2d58d9bbe4f5c3022293d9a708d0df453a86f36",
    ),
}


@pytest.mark.parametrize("mode", FROZEN_NATIVE4)
def test_previous_native_memory4_snapshots_are_unchanged(mode):
    e = NativeLocalEngine(LocalConfig(consolidation_mode=mode, quiescence_death_us=10**12))
    for index, when in enumerate((0, 73000, 180000, 610000, 1200000)):
        e.inject(Stimulus(when, ((10, 0.8), (11, 0.6), (20 + index % 2, 0.4))))
    for when, digest in zip((0, 180000, 611337, 2000000), FROZEN_NATIVE4[mode]):
        e.advance_to(when)
        assert hashlib.sha256(canonical_bytes(e.capture_state().to_dict())).hexdigest() == digest
