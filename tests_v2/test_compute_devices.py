import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from threemind_transformer.compute import device_fault, device_session, gpu_slot, stable_speedup
from threemind_transformer.protocol import Prediction, Training
from threemind_transformer.supervisor import run_attempts


def test_legacy_defaults_and_new_choices_are_explicit():
    assert Training(sequences=[[1, 2]]).compute_device == "cpu"
    assert Prediction(tokens=[1]).compute_device == "cpu"
    for value in ("cpu", "auto", "cuda"):
        assert Prediction(tokens=[1], compute_device=value).compute_device == value
    with pytest.raises(ValueError):
        Prediction(tokens=[1], compute_device="gpu")


def test_auto_requires_stable_material_speedup():
    assert stable_speedup([2, 2, 2], [1, 1, 1])
    assert not stable_speedup([2, 2, 2], [1, 1, 2])
    assert not stable_speedup([], [])
    assert not stable_speedup([1, 1, 1], [0, 0, 0])


def test_missing_gpu_resolves_once_to_cpu(monkeypatch):
    from threemind_transformer import compute

    monkeypatch.setattr(compute, "probe", lambda: {"cuda_available": False, "reason": "cpu_torch_build"})
    for requested in ("auto", "cuda"):
        with device_session(Prediction(tokens=[1], compute_device=requested)) as (evidence, guard):
            guard()
            assert evidence["resolved"] == "cpu" and evidence["requested"] == requested
            assert evidence["reason"] == "cpu_torch_build"


def test_slot_is_released_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEMIND_COMPUTE_LOCK_DIR", str(tmp_path))
    with pytest.raises(ValueError), gpu_slot() as first:
        assert first
        with gpu_slot() as second:
            assert not second
        raise ValueError("test failure")
    with gpu_slot() as again:
        assert again


def test_gpu_failure_restarts_frozen_protocol_once_in_new_cpu_process(tmp_path):
    calls = []
    protocol = Training(sequences=[[1, 2, 3]], steps=9, compute_device="cuda", wall_seconds=30.0)

    def runner(command, **options):
        args = json.loads(Path(command[-3]).read_text())
        calls.append(args)
        report = Path(command[-1])
        if len(calls) == 1:
            assert args["compute_device"] == "cuda"
            report.write_text(
                json.dumps(
                    {
                        "status": "device_failed",
                        "reason": "test: lost device",
                        "compute": {"resolved": "cuda", "steps_completed": 3, "loss_history": [{"step": 3, "loss": 2}]},
                    }
                )
            )
            return SimpleNamespace(returncode=86)
        assert args["compute_device"] == "cpu"
        report.write_text(json.dumps({"status": "completed", "steps_completed": 9, "compute": {"resolved": "cpu"}}))
        return SimpleNamespace(returncode=0)

    result, _ = run_attempts("train", protocol, tmp_path, runner=runner)
    assert len(calls) == 2
    for name in ("sequences", "architecture", "steps", "batch_size", "learning_rate"):
        assert calls[0][name] == calls[1][name] == protocol.model_dump()[name]
    assert calls[1]["wall_seconds"] <= calls[0]["wall_seconds"] <= 30
    assert result["protocol"] == protocol.model_dump()
    assert result["compute_attempts"][0]["compute"]["steps_completed"] == 3
    assert result["compute_attempts"][0]["steps_completed"] == 3
    assert result["fallback_from_initial_conditions"]


def test_nonfinite_and_logic_errors_do_not_trigger_device_retry(tmp_path):
    pytest.importorskip("torch")
    assert not device_fault(ValueError("nonfinite loss"))
    assert not device_fault(RuntimeError("matrix dimensions do not match"))
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stderr=b"nonfinite loss; model was not published")

    with pytest.raises(ValueError, match="nonfinite"):
        run_attempts("train", Training(sequences=[[1, 2]], compute_device="cuda"), tmp_path, runner=runner)
    assert len(calls) == 1


def test_fallback_failure_retains_both_attempts(tmp_path):
    from threemind_transformer.supervisor import ComputeExecutionError

    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            Path(command[-1]).write_text(
                json.dumps({"status": "device_failed", "reason": "lost GPU", "compute": {"steps_completed": 2}})
            )
            return SimpleNamespace(returncode=86)
        return SimpleNamespace(returncode=1, stderr=b"CPU process failed")

    with pytest.raises(ComputeExecutionError) as error:
        run_attempts("train", Training(sequences=[[1, 2]], compute_device="cuda"), tmp_path, runner=runner)
    report = error.value.report
    assert len(report["compute_attempts"]) == 2
    assert report["compute_attempts"][0]["compute"]["steps_completed"] == 2
    assert report["compute_attempts"][0]["steps_completed"] == 2
    assert report["compute_attempts"][1]["status"] == "failed"


def test_real_cpu_child_training_and_inference_are_portable(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    from threemind_transformer.model import decode
    from threemind_transformer.protocol import Architecture
    from threemind_transformer.supervisor import predict_file, train_file

    monkeypatch.delenv("THREEMIND_TRANSFORMER_PYTHON", raising=False)
    protocol = Training(
        architecture=Architecture(vocabulary=4, context=4, width=8, heads=2, layers=1),
        sequences=[[1, 2, 3]],
        steps=3,
        wall_seconds=30.0,
        compute_device="cpu",
    )
    path = tmp_path / "model.tmt"
    result = train_file(protocol, path)
    model, metadata = decode(path.read_bytes())
    assert result["steps_completed"] == 3
    assert metadata["compute"]["resolved"] == "cpu"
    assert metadata["protocol"] == protocol.model_dump()
    response = predict_file(path, Prediction(tokens=[1, 2]))
    assert response["probabilities"] == model.predict([1, 2])
    assert response["compute_attempts"][0]["compute"]["resolved"] == "cpu"
