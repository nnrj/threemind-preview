import json
import subprocess
import sys

import pytest

from threemind_core import Config
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.host import create_engine
from threemind_runtime.profile import profile_from_spec
from threemind_runtime.sensory import TextSensor, TextSensorConfig
from threemind_runtime.store import SQLiteStore


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_cli_record_resume_and_explicit_cutoff_preserve_core(tmp_path, backend):
    config = Config(propagation_rate=0, activation_decay_enabled=False, inhibition_gain=0)
    source = create_engine(config, backend=backend)
    profile = profile_from_spec({"seed": config.seed, "text_sensor": {"encoding": "literal-character"}})
    model, carrier = tmp_path / "source.tmind", tmp_path / "cue.txt"
    model.write_bytes(ArtifactCodec.encode(source.capture_state(), profile=profile))
    original = model.read_bytes()
    carrier.write_text("甲。", encoding="utf-8")
    store = tmp_path / "recovery.sqlite"
    first, later, final = (tmp_path / p for p in ("first.jsonl", "later.jsonl", "final.tmind"))

    def run(*args, good=True):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "threemind_runtime.cli",
                "--clock",
                "unbounded",
                "--backend",
                backend,
                *map(str, args),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        if good:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0
        return result

    run("--model", model, "--text-input", carrier, "--store", store, "--until-us", 400000, "--readouts", first)
    records = [json.loads(line) for line in first.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["recoverable"] and records[-1]["open_windows"] == 1
    context = SQLiteStore(store).load("default", with_profile=True, with_context=True)[3]
    assert context["readouts"]["temporal"]["windows"]
    run("--resume", "--store", store, "--until-us", 2000000, "--readouts", later, "--export", final)
    records = [json.loads(line) for line in later.read_text(encoding="utf-8").splitlines()]
    windows = [r["payload"] for r in records if r["kind"] == "temporal_readout"]
    assert len(windows) == 1 and windows[0]["classification"] == "converged"
    assert windows[0]["chat"]["readable_labels"] == ["甲", "。"]
    for frame in TextSensor(profile["sensory_seed"], TextSensorConfig(**profile["text_sensor"])).frames("甲。"):
        source.inject(frame["stimulus"])
    source.advance_to(2000000)
    assert ArtifactCodec.decode(final.read_bytes()).digest == source.capture_state().digest
    assert model.read_bytes() == original
    saved = later.read_bytes()
    run("--model", model, "--readouts", later, good=False)
    assert later.read_bytes() == saved
    cutoff = tmp_path / "cutoff.jsonl"
    run("--model", model, "--text-input", carrier, "--until-us", 200000, "--readouts", cutoff)
    records = [json.loads(line) for line in cutoff.read_text(encoding="utf-8").splitlines()]
    window = next(r["payload"] for r in records if r["kind"] == "temporal_readout")
    assert window["classification"] == "censored" and window["reason"] == "run_ended"


def test_temporal_calibration_cli_inherits_the_model_source_policy(tmp_path):
    engine = create_engine()
    profile = profile_from_spec({"seed": engine.config.seed, "source_policies": {"cli_text_enabled": False}})
    model = tmp_path / "policy.tmind"
    model.write_bytes(ArtifactCodec.encode(engine.capture_state(), profile=profile))
    original = model.read_bytes()
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"mode": "temporal", "cues": ["甲。"]}, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "policy-evidence.zip"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "threemind_runtime.calibration_cli",
            "--model",
            str(model),
            "--protocol",
            str(protocol),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert evidence["source_policies"]["cli_text_enabled"] is False
    assert evidence["rows"][0]["reason"] == "input_source_disabled"
    assert evidence["rows"][0]["classification"] == "not_observed"
    assert model.read_bytes() == original
