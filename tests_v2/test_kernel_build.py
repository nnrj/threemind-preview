import json
import os
import subprocess

import pytest

from threemind_kernels.build import build_runtime
from threemind_kernels.definition import KernelDefinition
from threemind_runtime import ArtifactCodec


def test_build_does_not_overwrite_output_or_accept_arbitrary_definition(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("retained")
    with pytest.raises(ValueError, match="exists"):
        build_runtime(KernelDefinition.default(), output)
    assert marker.read_text() == "retained"
    bad = KernelDefinition(b'{"eval":"arbitrary"}')
    with pytest.raises(ValueError):
        build_runtime(bad, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


@pytest.mark.skipif(os.environ.get("THREEMIND_TEST_STANDALONE_BUILD") != "1", reason="explicit native build acceptance")
def test_real_compiled_constructor_stays_plastic_and_refuses_other_kernel(tmp_path):
    definition = KernelDefinition.default("threemind.lif/1", {"input_gain_na": 5.0})
    output = tmp_path / "device"
    manifest = build_runtime(definition, output)
    runtime = str(output / manifest["binary"])
    inspected = subprocess.run([runtime, "--inspect-definition"], capture_output=True, check=True, timeout=15)
    assert KernelDefinition.parse(inspected.stdout).digest == definition.digest
    stimuli = tmp_path / "stimuli.jsonl"
    stimuli.write_text(json.dumps({"time_us": "0", "channels": [[1, 0.8], [2, 0.6]]}) + "\n")
    model = tmp_path / "after.json"
    result = subprocess.run(
        [runtime, "--input", str(stimuli), "--clock", "unbounded", "--until-us", "10000", "--export", str(model)],
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    state = ArtifactCodec.decode(model.read_bytes()).to_dict()
    assert state["membranes"][0]["spikes"] > 0 and state["synapses"]
    override = subprocess.run([runtime, "--kernel", "threemind.causal/9"], capture_output=True, check=False, timeout=15)
    assert override.returncode != 0
    old = tmp_path / "old.json"
    old.write_bytes(ArtifactCodec.encode(KernelDefinition.default().create().capture_state(), "json"))
    restore = subprocess.run([runtime, "--model", str(old)], capture_output=True, check=False, timeout=15)
    assert restore.returncode != 0
