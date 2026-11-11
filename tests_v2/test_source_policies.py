import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_core.spec import SPATIAL_DYNAMICS
from threemind_runtime import create_engine
from threemind_runtime.source_policies import CATEGORIES, SOURCES, SourcePolicies


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_per_frame_bypass_keeps_modulation_and_simultaneous_frames_independent(backend):
    engine = create_engine(Config(attention_competition_enabled=True, attention_budget=1), backend=backend)
    engine.modulate_input(time_us=0, source="gain", gain=0.5)
    first = Stimulus(0, ((1, 0.9), (2, 0.7), (3, 0.4)))
    engine.inject(first)
    engine.inject(Stimulus(0, ((4, 0.9), (5, 0.7), (6, 0.4)), bypass_attention=True))
    engine.inject(Stimulus(0, ((7, 0.9), (8, 0.7), (9, 0.4))))
    events = []
    engine.advance_to(0, events.append, inputs_only=True)
    decisions = [e["input_gate"] for e in events if e["kind"] == "stimulus"]
    assert [d["passed_channels"] for d in decisions] == [1, 3, 1]
    assert [d["effective_stimulus"]["intensity"] for d in decisions] == [0.5] * 3
    assert [d.get("competition_bypassed", False) for d in decisions] == [False, True, False]
    assert {n["channel"] for n in engine.capture_state().to_dict()["nodes"]} == {1, 4, 5, 6, 7}
    attention = engine.capture_state().to_dict()["attention"]
    assert attention["passed_channels"] == "5" and attention["suppressed_channels"] == "4"
    # A queued bypass is a property of that frame; later parameter changes cannot erase it.
    engine.inject(Stimulus(50000, ((11, 0.9), (12, 0.4)), bypass_attention=True))
    engine.reconfigure(replace(engine.config, attention_budget=0))
    before = engine.capture_state()
    restored = create_engine(state=before, backend=backend)
    left, right = [], []
    engine.advance_to(50123, left.append, inputs_only=True)
    restored.advance_to(50123, right.append, inputs_only=True)
    assert left == right and engine.capture_state().digest == restored.capture_state().digest
    assert left[-1]["input_gate"]["passed_channels"] == 2
    assert before.to_dict()["queue"][-1]["payload"]["bypass_attention"] is True


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_bypass_does_not_override_zero_gain_closed_inputs_or_dead_instance(backend):
    engine = create_engine(Config(attention_competition_enabled=True), backend=backend)
    engine.modulate_input(time_us=0, source="zero", gain=0)
    engine.inject(Stimulus(0, ((1, 1.0),), bypass_attention=True))
    events = []
    engine.advance_to(0, events.append, inputs_only=True)
    assert events[-1]["input_gate"]["passed_channels"] == 0
    assert not engine.capture_state().to_dict()["nodes"]
    engine.close_inputs()
    before = engine.capture_state()
    with pytest.raises(ValueError):
        engine.inject(Stimulus(1000, ((2, 1.0),), bypass_attention=True))
    assert engine.capture_state().digest == before.digest


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_frozen_causal6_continuation_and_explicit_bypass_upgrade(backend):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal6-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        create_engine(state=before, backend=backend)


def test_bypass_boolean_wire_contract_and_legacy_schema_rejection():
    frame = Stimulus(0, ((1, 0.5),))
    assert "bypass_attention" not in frame.to_dict()
    assert Stimulus.from_dict(frame.to_dict() | {"bypass_attention": False}) == frame
    for value in (1, 0, "false", None):
        with pytest.raises(ValueError):
            Stimulus.from_dict(frame.to_dict() | {"bypass_attention": value})
    for backend in ("reference", "native"):
        engine = create_engine(backend=backend)
        engine.inject(frame)
        for value in (True, False):
            saved = engine.capture_state().to_dict() | {"dynamics": SPATIAL_DYNAMICS}
            saved["queue"][0]["payload"]["bypass_attention"] = value
            with pytest.raises(ValueError, match="read-only"):
                create_engine(state=StateImage.from_dict(saved), backend=backend)


def test_source_identity_category_precedence_and_portable_contract():
    from threemind_lab.configuration import default_spec, validate_configuration
    from threemind_runtime.bus import InputBus
    from threemind_runtime.profile import profile_from_spec, validate_profile

    defaults = SourcePolicies()
    contract = json.loads(Path("crates/threemind-runtime/src/source-policy-contract.json").read_text(encoding="utf-8"))
    assert contract == asdict(defaults)
    for key, _, category, aliases in SOURCES:
        for source in aliases:
            assert defaults.resolve(source)["key"] == key
            assert not replace(defaults, **{category + "_enabled": False}).resolve(source)["enabled"]
            assert not replace(defaults, **{key + "_enabled": False}).resolve(source)["enabled"]
            assert replace(defaults, **{category + "_bypass_attention": True}).resolve(source)["bypass_attention"]
    for category, _ in CATEGORIES:
        assert replace(defaults, **{category + "_bypass_attention": True}).to_dict()[category + "_bypass_attention"]
    assert defaults.resolve("remote:123")["key"] == "remote"
    for value in ("false", 1, None):
        spec = default_spec() | {"source_policies": {"ui_text_enabled": value}}
        assert not validate_configuration(spec)["valid"]
    profile = profile_from_spec(default_spec())
    assert validate_profile(profile) == profile
    del profile["source_policies"]["ui_text_enabled"]
    with pytest.raises(ValueError):
        validate_profile(profile)
    engine = create_engine()
    bus = InputBus(engine, policies=defaults)
    bus.schedule(Stimulus(1000, ((1, 1.0),), bypass_attention=True), {"source": "manual-anonymous"})
    assert "bypass_attention" not in engine.capture_state().to_dict()["queue"][0]["payload"]
    # Restoring a frozen promise must not reapply the host's current policy.
    allowed = InputBus(engine, policies=SourcePolicies(ui_text_bypass_attention=True))
    allowed.schedule(Stimulus(2000, ((2, 1.0),)), {"source": "manual-text"})
    restored = InputBus(engine, allowed.capture(), policies=SourcePolicies(ui_text_enabled=False))
    restored.verify(engine.capture_state().to_dict())
    with pytest.raises(ValueError, match="disabled"):
        restored.schedule(Stimulus(3000, ((3, 1.0),)), {"source": "manual-text"})
    assert engine.capture_state().to_dict()["queue"][-1]["payload"]["bypass_attention"]


def test_disabled_telemetry_never_constructs_or_calls_physical_probe(monkeypatch):
    from threemind_lab.protocols import RunSpec
    from threemind_lab.telemetry import RuntimeTelemetry
    from threemind_runtime import telemetry_probe

    def forbidden():
        raise AssertionError("disabled source acquired physical counters")

    monkeypatch.setattr(telemetry_probe, "SystemTelemetryProbe", forbidden)
    spec = RunSpec(
        environment="manual",
        host_telemetry={"enabled": True},
        process_telemetry={"enabled": True},
        runtime_telemetry={"enabled": True},
        source_policies={"background_enabled": False},
    )
    telemetry = RuntimeTelemetry(spec, uuid4())
    assert telemetry.configs == {} and telemetry.probe is None
    telemetry.measured(1, 1, 1)
    telemetry.poll(None, forbidden, source_enabled=True)


@pytest.mark.parametrize("entry", ["python", "rust"])
def test_independent_runtime_enforces_policies_and_keeps_exported_profile(tmp_path, entry):
    from test_runtime_interop import RUNTIME

    from threemind_runtime.codec import ArtifactCodec
    from threemind_runtime.profile import profile_from_spec
    from threemind_runtime.store import SQLiteStore

    profile = profile_from_spec({"seed": 23, "source_policies": {"anonymous_bypass_attention": True}})
    engine = create_engine(Config(attention_competition_enabled=True, attention_budget=1))
    source, output, store = tmp_path / "source.tmind", tmp_path / "output.tmind", tmp_path / "recovery.sqlite"
    source.write_bytes(ArtifactCodec.encode(engine.capture_state(), profile=profile))
    carrier = tmp_path / "carrier.jsonl"
    carrier.write_text(json.dumps(Stimulus(0, ((1, 0.8), (2, 0.7), (3, 0.6))).to_dict()), encoding="utf-8")
    prefix = [sys.executable, "-X", "utf8", "-m", "threemind_runtime.cli"] if entry == "python" else [str(RUNTIME)]
    command = prefix + ["--model", str(source), "--input", str(carrier), "--clock", "unbounded", "--until-us", "1"]
    result = subprocess.run(
        command + ["--export", str(output), "--store", str(store)], capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    state, saved = ArtifactCodec.decode(output.read_bytes(), with_profile=True)
    assert len(state.to_dict()["nodes"]) == 3 and saved == profile
    assert SQLiteStore(store).load("default", with_profile=True)[2] == profile
    profile["source_policies"]["anonymous_enabled"] = False
    source.write_bytes(ArtifactCodec.encode(engine.capture_state(), profile=profile))
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0


def test_independent_text_cli_uses_text_sensor_and_its_own_policy(tmp_path):
    from threemind_runtime.codec import ArtifactCodec
    from threemind_runtime.profile import profile_from_spec

    profile = profile_from_spec(
        {"seed": 23, "source_policies": {"ui_text_enabled": False, "cli_text_bypass_attention": True}}
    )
    source, text, output = tmp_path / "source.tmind", tmp_path / "text.txt", tmp_path / "out.json"
    engine = create_engine(Config(attention_competition_enabled=True, attention_budget=0))
    source.write_bytes(ArtifactCodec.encode(engine.capture_state(), profile=profile))
    text.write_text("汉字 AB", encoding="utf-8")
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "threemind_runtime.cli",
        "--model",
        str(source),
        "--text-input",
        str(text),
        "--clock",
        "unbounded",
        "--until-us",
        "1",
    ]
    result = subprocess.run(command + ["--export", str(output)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    state, actual = ArtifactCodec.decode(output.read_bytes(), with_profile=True)
    assert state.to_dict()["nodes"] and actual == profile
    profile["source_policies"]["cli_text_enabled"] = False
    source.write_bytes(ArtifactCodec.encode(engine.capture_state(), profile=profile))
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
