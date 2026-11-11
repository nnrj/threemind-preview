import json
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from threemind_lab import input_client
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.host import create_engine
from threemind_runtime.sensory import TextSensor, TextSensorConfig


@pytest.mark.parametrize("dose", [None, 0.0, 0.5, 0.9])
@pytest.mark.parametrize("readouts", [False, True])
def test_runtime_cli_intensity_matches_sensor_and_preserves_default(tmp_path, dose, readouts):
    carrier, model = tmp_path / "carrier.txt", tmp_path / "result.tmind"
    carrier.write_text("甲是松子", encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "threemind_runtime.cli",
        "--clock",
        "unbounded",
        "--text-input",
        str(carrier),
        "--until-us",
        "20000",
        "--export",
        str(model),
    ]
    if dose is not None:
        args += ["--text-intensity", str(dose)]
    if readouts:
        args += ["--readouts", str(tmp_path / "readouts.jsonl")]
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    expected = create_engine()
    for frame in TextSensor(expected.config.seed, TextSensorConfig()).frames("甲是松子", 1 if dose is None else dose):
        expected.inject(frame["stimulus"])
    expected.advance_to(20000)
    assert ArtifactCodec.decode(model.read_bytes()).digest == expected.capture_state().digest


@pytest.mark.parametrize("dose", [None, 0.0, 0.5, 0.9])
def test_api_client_preserves_omission_or_sends_explicit_intensity(tmp_path, monkeypatch, dose):
    requests = []

    from threemind_lab.operations_client import OperationsClient

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"spec": {}} if request.method == 'GET' else {"accepted": True})

    monkeypatch.setattr(input_client, "client_from_arguments",
                        lambda _: OperationsClient(transport=httpx.MockTransport(respond)))
    carrier = tmp_path / "input.txt"
    carrier.write_text("甲是松子", encoding="utf-8")
    args = SimpleNamespace(
        url="http://127.0.0.1:8877",
        project=uuid4(),
        run=uuid4(),
        file=carrier,
        username=None,
        delay_us=0,
        intensity=dose,
    )
    input_client.submit_text(args, uuid4())
    payload = json.loads(requests[-1].content)["payload"]
    assert payload == ({"text": "甲是松子"} | ({"intensity": dose} if dose is not None else {}))


@pytest.mark.parametrize("dose", [float("nan"), float("inf"), -0.1, 100.1])
def test_invalid_client_intensity_rejected_before_network(dose):
    with pytest.raises(ValueError, match="刺激强度"):
        input_client.submit_text(SimpleNamespace(intensity=dose), uuid4())
