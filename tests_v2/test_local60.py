"""Engineering fixtures for fixed-function addressing; no research subjects."""

import math
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import StateImage, Stimulus
from threemind_kernels.decay60 import CURVES
from threemind_kernels.local53 import Local53Config, Local53Engine
from threemind_kernels.local60 import KERNEL_ID, Local60Config, Local60Engine, node_address
from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel
from threemind_runtime import ArtifactCodec


def same(a, b, path=""):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for key in a:
            same(a[key], b[key], path + "/" + key)
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}/{i}")
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=3e-12, abs_tol=3e-14), (path, a, b)
    else:
        assert a == b, (path, a, b)


def make(config=None, backend="reference", state=None):
    return resolve_kernel(KERNEL_ID).create(config, state, backend=backend)


def inject_course(engine, codes=(0, 1, 2)):
    # First arrival creates 0,1,2 in that order, so historical and fixed IDs coincide.
    for t, pairs, intensity in (
        (0, ((0, 0.7), (1, 0.4), (2, 0.2)), 1),
        (0, ((0, 0.3), (1, 0.7)), 1),
        (50_000, ((1, 0.5), (2, 0.7)), 1),
        (110_000, ((0, 0.9), (2, 0.2)), 3),
        (411_337, ((1, 0.2),), 1),
        (900_000, ((0, 0.8), (1, 0.7)), 1),
    ):
        engine.inject(Stimulus(t, tuple((codes[i], v) for i, v in pairs), intensity))


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_fixed_address_is_order_independent_and_sparse(backend):
    codes = (0, 17, 2**31 + 9, 2**32 - 1)
    for ordering in (codes, tuple(reversed(codes))):
        e = make(backend=backend)
        for i, code in enumerate(ordering):
            e.inject(Stimulus(i, ((code, 0.6),)))
        e.advance_to(10)
        rows = e.capture_state().to_dict()["nodes"]
        assert {r["id"] for r in rows} == set(codes)
        assert all(r["id"] == r["channel"] for r in rows)
        assert len(rows) == 4
        saved = e.capture_state()
        assert "next_node" not in saved.to_dict()
        assert not hasattr(e, "receptors")
        e = make(backend=backend, state=saved)
        e.inject(Stimulus(11, ((codes[-1], 0.2),)))
        e.advance_to(11)
        assert len(e.capture_state().to_dict()["nodes"]) == 4


@pytest.mark.parametrize("code", (-1, 2**32, 1.5, True, "ABC"))
def test_address_rejects_out_of_contract_encoding(code):
    with pytest.raises(ValueError):
        node_address(code)


OPTIONS = [
    {},
    {"reception_mode": "unified", "arrival_mode": "coincident"},
    {"propagation_phase": "asynchronous"},
    {"spatial_embedding": True, "neighborhood_enabled": True},
    {"energy_simulation_enabled": True},
    {"retention_growth_enabled": True, "retention_relaxation_enabled": True},
    {"signal_threshold_enabled": False, "weight_gate_enabled": True},
    {"inhibitory_learning_enabled": False, "inhibition_sender_gate_enabled": True},
    {"reinforcement_age_policy": "reset"},
]


def comparable(image):
    value = image.to_dict()
    for key in ("schema", "dynamics", "definition", "definition_hash"):
        value.pop(key)
    if "next_node" in value:
        value["birth_count"] = value.pop("next_node")
    value["config"].pop("inflight_delivery", None)
    for row in value["nodes"]:
        row.pop("birth_serial", None)
    return value


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("options", OPTIONS)
def test_other_dynamics_match_53_when_node_addresses_match(curve, options):
    a = Local53Engine(Local53Config(decay_curve=curve, **options))
    b = Local60Engine(Local60Config(decay_curve=curve, **options))
    for engine in (a, b):
        inject_course(engine)
        if options.get("energy_simulation_enabled"):
            engine.supply_energy(20, time_us=20_000)
    for t in (0, 100_000, 110_000, 300_000, 1_000_000, 2_000_000):
        a.advance_to(t)
        b.advance_to(t)
        assert comparable(a.capture_state()) == comparable(b.capture_state())


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("options", OPTIONS)
def test_native_reference_parity_with_sparse_addresses(curve, options):
    c = Local60Config(decay_curve=curve, **options)
    a, b = make(c), make(c, "native")
    for e in (a, b):
        inject_course(e, (700, 2**32 - 1, 17))
        if options.get("energy_simulation_enabled"):
            e.supply_energy(20, time_us=20_000)
    for t in (0, 110_000, 311_337, 1_000_000, 2_000_000):
        a.advance_to(t)
        b.advance_to(t)
        same(a.capture_state().to_dict(), b.capture_state().to_dict())
    # Cross restore real pending queues, all per-object state, and configuration.
    a, b = make(state=b.capture_state()), make(backend="native", state=a.capture_state())
    for e in (a, b):
        e.inject(Stimulus(2_000_003, ((17, 0.9),)))
        e.advance_to(2_300_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("format", ("json", "tmind"))
def test_save_observation_split_time_and_artifact_roundtrip(backend, format):
    a, b = make(backend=backend), make(backend=backend)
    for e in (a, b):
        inject_course(e, (25, 0, 2**32 - 1))
    a.advance_to(2_000_000)
    for t in (0, 1, 50_000, 100_000, 110_000, 123_456, 900_000, 1_110_003, 2_000_000):
        b.advance_to(t)
        before = b.capture_state()
        b.graph()
        b.metrics()
        b.spatial_geometry()
        b.activations()
        assert b.capture_state() == before
        image = ArtifactCodec.decode(ArtifactCodec.encode(before, format))
        b = make(backend=backend, state=image)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_deleted_node_is_recreated_at_same_address_with_fresh_state(backend):
    e = make(backend=backend)
    e.inject(Stimulus(0, ((31, 0.8), (49, 0.7))))
    e.advance_to(300_000)
    old = {n["id"]: n for n in e.capture_state().to_dict()["nodes"]}[31]
    e.intervene(action="delete_nodes", nodes=[31])
    assert 31 not in dict(e.activations())
    e.inject(Stimulus(300_001, ((31, 0.1),)))
    e.advance_to(300_001)
    row = {n["id"]: n for n in e.capture_state().to_dict()["nodes"]}[31]
    assert row["birth_us"] == "300001" != old["birth_us"]
    assert row["touches"] == 1
    assert row["decay_age"] == 0
    assert not any(31 in (x["source"], x["target"]) for x in e.capture_state().to_dict()["edges"])


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_saved_address_and_version_validation(backend):
    e = make(backend=backend)
    e.inject(Stimulus(0, ((73, 0.5),)))
    e.advance_to(0)
    raw = e.capture_state().to_dict()
    raw["nodes"][0]["id"] = 74
    with pytest.raises(ValueError):
        make(backend=backend, state=StateImage.from_dict(raw))
    old = Local53Engine().capture_state()
    with pytest.raises(ValueError, match="identity|schema"):
        make(backend=backend, state=old)
    with pytest.raises(ValueError):
        resolve_kernel("threemind.continuous-memory/5.3").create(state=e.capture_state(), backend=backend)


def test_parameters_and_default_preserved():
    defaults = Local60Config().to_dict()
    assert defaults.pop("inflight_delivery") == "address"
    assert defaults == Local53Config().to_dict()
    assert DEFAULT_KERNEL == "threemind.continuous-memory/6.1"
    e = make()
    with pytest.raises(ValueError):
        e.reconfigure(replace(e.config, decay_curve="power-law"))
    from threemind_runtime.inheritance import birth

    assert birth(e.capture_state()).to_dict()["time_us"] == "0"


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_kernel_runs_when_53_imports_are_forbidden(backend):
    code = """
import importlib.abc, sys
class No53(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.rsplit('.',1)[-1] in ('local53', 'decay53', 'local53_native'):
            raise AssertionError('6.0 attempted to import '+fullname)
sys.meta_path.insert(0,No53())
from threemind_kernels.local60 import Local60Engine
from threemind_core import Stimulus
e=Local60Engine(); e.inject(Stimulus(0,((4294967295,.7),))); e.advance_to(100000)
assert e.activations()[0][0] == 4294967295
assert Local60Engine(state=e.capture_state()).capture_state()==e.capture_state()
"""
    if backend == "native":
        code = code.replace(
            "from threemind_kernels.local60 import Local60Engine",
            "from threemind_kernels.local60_native import NativeLocal60Engine as Local60Engine",
        )
    subprocess.run([sys.executable, "-X", "utf8", "-c", code], check=True, capture_output=True)


def test_owned_sources_do_not_import_previous_kernel_implementations():
    root = Path(__file__).resolve().parents[1]
    for filename in ("local60.py", "local60_config.py", "decay60.py", "local60_native.py"):
        text = (root / "src/threemind_kernels" / filename).read_text(encoding="utf-8")
        assert not any(
            f"from .{mod} import" in text for mod in ("local", "local5", "local51", "local52", "local53", "decay53")
        )
    for filename in ("local60.rs", "local60_transitions.rs"):
        text = (root / "crates/threemind-core/src" / filename).read_text(encoding="utf-8")
        assert "local53" not in text and "LocalEngine53" not in text


def test_lab_parameter_catalogue_and_validation_expose_60():
    from threemind_lab.configuration import catalogue, default_spec, validate_configuration

    catalog = catalogue(KERNEL_ID)
    assert any(k["kernel_id"] == KERNEL_ID for k in catalog["kernels"])
    shown = {
        f["path"]: f for f in catalog["fields"] if KERNEL_ID in f.get("kernels", ()) and f["path"].startswith("config.")
    }
    defaults = Local60Config().to_dict()
    assert all(f["default"] == defaults[path[7:]] for path, f in shown.items())
    assert shown["config.decay_curve"]["default"] == "inverse-logarithmic"
    assert len(shown["config.decay_curve"]["choices"]) == 4
    assert shown["config.inflight_delivery"]["default"] == "address"
    assert len(shown["config.inflight_delivery"]["choices"]) == 2
    current = default_spec(KERNEL_ID)
    assert validate_configuration(current)["valid"]
    requested = current | {"config": current["config"] | {"decay_curve": "power-law"}}
    assert validate_configuration(requested)["valid"]
    assert not validate_configuration(requested, current=current)["valid"]
    requested = current | {"config": current["config"] | {"inflight_delivery": "same-birth"}}
    assert validate_configuration(requested)["valid"]
    assert not validate_configuration(requested, current=current)["valid"]


def inflight_fixture(mode, backend="reference", *, recreate=True):
    """Real emissions, deletion and re-creation within one internal timestamp."""
    e = make(Local60Config(inflight_delivery=mode), backend)
    e.inject(Stimulus(100_000, ((11, 0.8), (22, 0.7))))
    e.advance_to(100_000)
    saved = e.capture_state().to_dict()
    assert {r["kind"] for r in saved["queue"]} == {"signal", "inhibition"}
    assert all(("birth_limit" in r) == (mode == "same-birth") for r in saved["queue"])
    e.intervene(action="delete_nodes", nodes=[22])
    if recreate:
        e.inject(Stimulus(100_000, ((22, 0.1),)))
        e.advance_to(100_000)
        new = {r["id"]: r for r in e.capture_state().to_dict()["nodes"]}[22]
        old = {r["id"]: r for r in saved["nodes"]}[22]
        assert new["birth_us"] == old["birth_us"]  # A timestamp cannot identify this lifetime.
        assert new["birth_serial"] > old["birth_serial"]
    return e


@pytest.mark.parametrize("mode", ("address", "same-birth"))
@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("format", (None, "json", "tmind"))
def test_old_excitation_and_inhibition_follow_selected_policy(mode, backend, format):
    e = inflight_fixture(mode, backend)
    if format:
        e = make(backend=backend, state=ArtifactCodec.decode(ArtifactCodec.encode(e.capture_state(), format)))
    e.advance_to(110_000)
    rows = {r["id"]: r for r in e.capture_state().to_dict()["nodes"]}
    assert rows[22]["touches"] == (2 if mode == "address" else 1)
    assert (rows[22]["associative"] > 0) == (mode == "address")
    assert (rows[22]["pending_inhibition"] > 0) == (mode == "address")
    # Deleting/recreating the sender must not recall what it sent to a surviving receiver.
    assert rows[11]["touches"] == 2
    assert rows[11]["associative"] > 0 and rows[11]["pending_inhibition"] > 0


@pytest.mark.parametrize("mode", ("address", "same-birth"))
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_old_arrivals_do_not_create_nodes_and_new_signals_still_arrive(mode, backend):
    e = inflight_fixture(mode, backend, recreate=False)
    e.advance_to(110_000)
    assert 22 not in dict(e.activations())
    e.inject(Stimulus(111_000, ((11, 0.7), (22, 0.8))))
    e.advance_to(200_000)
    restored = make(backend=backend, state=e.capture_state())
    before = {r["id"]: r for r in restored.capture_state().to_dict()["nodes"]}[22]["touches"]
    restored.advance_to(210_000)
    row = {r["id"]: r for r in restored.capture_state().to_dict()["nodes"]}[22]
    assert row["touches"] > before and row["associative"] > 0


@pytest.mark.parametrize("mode", ("address", "same-birth"))
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_wake_requires_original_endpoints_only_in_same_birth_mode(mode, backend):
    c = Local60Config(
        inflight_delivery=mode,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.001,
        edge_wake_threshold=0.001,
    )
    e = make(c, backend)
    e.inject(Stimulus(0, ((11, 0.8), (22, 0.7))))
    e.advance_to(0)
    # Isolated engineering fixture: put existing edges to sleep, then let the real emitter run.
    raw = e.capture_state().to_dict()
    for row in raw["edges"]:
        row["sleeping"] = True
    e = make(backend=backend, state=StateImage.from_dict(raw))
    e.advance_to(100_000)
    assert any(r["kind"] == "wake" for r in e.capture_state().to_dict()["queue"])
    e.intervene(action="delete_nodes", nodes=[22])
    e.inject(Stimulus(100_001, ((11, 0.2), (22, 0.2))))
    e.advance_to(100_001)
    raw = e.capture_state().to_dict()
    for row in raw["edges"]:
        row["sleeping"] = True
    e = make(backend=backend, state=ArtifactCodec.decode(ArtifactCodec.encode(StateImage.from_dict(raw), "tmind")))
    before = raw["audit"]["edges_awakened"]
    e.advance_to(110_000)
    saved = e.capture_state().to_dict()
    assert saved["audit"]["edges_awakened"] - before == (2 if mode == "address" else 0)
    assert all(r["sleeping"] == (mode == "same-birth") for r in saved["edges"])


@pytest.mark.parametrize("mode", ("address", "same-birth"))
def test_policy_cross_backend_restore_and_observation_are_identical(mode):
    a = inflight_fixture(mode)
    b = make(backend="native", state=a.capture_state())
    for t in (100_001, 109_999, 110_000, 111_337, 300_000):
        before = b.capture_state()
        b.graph()
        b.metrics()
        b.activations()
        assert b.capture_state() == before
        a.advance_to(t)
        b.advance_to(t)
        same(a.capture_state().to_dict(), b.capture_state().to_dict())
    b = make(state=b.capture_state())
    a.advance_to(600_000)
    b.advance_to(600_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize(
    "damage",
    (
        "missing_serial",
        "duplicate_serial",
        "future_serial",
        "missing_limit",
        "future_limit",
        "zero_limit",
        "bool_limit",
    ),
)
def test_birth_metadata_must_survive_complete_restore(backend, damage):
    raw = inflight_fixture("same-birth").capture_state().to_dict()
    if damage == "missing_serial":
        raw["nodes"][0].pop("birth_serial")
    elif damage == "duplicate_serial":
        raw["nodes"][0]["birth_serial"] = raw["nodes"][1]["birth_serial"]
    elif damage == "future_serial":
        raw["nodes"][0]["birth_serial"] = raw["birth_count"] + 1
    elif damage == "missing_limit":
        raw["queue"][0].pop("birth_limit")
    else:
        raw["queue"][0]["birth_limit"] = {"future_limit": raw["birth_count"] + 1, "zero_limit": 0, "bool_limit": True}[
            damage
        ]
    with pytest.raises(ValueError):
        make(backend=backend, state=StateImage.from_dict(raw))


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_delivery_policy_is_fixed_at_birth(backend):
    e = make(backend=backend)
    with pytest.raises(ValueError):
        e.reconfigure(replace(e.config, inflight_delivery="same-birth"))
    with pytest.raises(ValueError):
        Local60Config(inflight_delivery="unknown")


@pytest.mark.parametrize("mode", ("address", "same-birth"))
@pytest.mark.parametrize("format", ("json", "tmind"))
def test_standalone_runtime_restores_inflight_policy(tmp_path, mode, format):
    runtime = Path(
        os.environ.get(
            "THREEMIND_TEST_RUNTIME", Path(__file__).resolve().parents[1] / "target/release/threemind-runtime.exe"
        )
    )
    if not runtime.exists():
        pytest.skip("build independent runtime first")
    e = inflight_fixture(mode)
    source, output = tmp_path / f"pending.{format}", tmp_path / "after.tmind"
    source.write_bytes(ArtifactCodec.encode(e.capture_state(), format))
    subprocess.run(
        [str(runtime), "--model", str(source), "--clock", "unbounded", "--until-us", "110000", "--export", str(output)],
        check=True,
        capture_output=True,
    )
    e.advance_to(110_000)
    same(e.capture_state().to_dict(), ArtifactCodec.decode(output.read_bytes()).to_dict())
