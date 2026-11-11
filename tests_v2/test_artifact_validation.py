"""Reject malformed interchange before it can become a running instance."""

import hashlib
import io
import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from threemind_core import Engine, Stimulus
from threemind_runtime import ArtifactCodec

RUNTIME = (
    Path(__file__).resolve().parents[1]
    / "target/release"
    / ("threemind-runtime.exe" if sys.platform == "win32" else "threemind-runtime")
)


def malformed(case):
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.6), (2, 0.7))))
    engine.advance_to(10000)
    image = engine.capture_state()
    if case == "duplicate-json":
        raw = ArtifactCodec.encode(image, "json")
        return b'{"format":"duplicate",' + raw.lstrip()[1:]
    if case == "logical-checksum":
        value = json.loads(ArtifactCodec.encode(image, "json"))
        value["state"]["nodes"][0]["activation"] += 0.01
        return json.dumps(value).encode()
    with zipfile.ZipFile(io.BytesIO(ArtifactCodec.encode(image))) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    if case == "unexpected-member":
        parts["../outside.txt"] = b"not a model member"
    elif case == "compressed-expansion":
        # A valid IPC envelope with a forged inner Zstd expanded length. The outer
        # ZIP and manifest are valid, so byte-count and SHA checks alone cannot help.
        payload = bytearray(parts["nodes.arrow"])
        frame = payload.find(b"\x28\xb5\x2f\xfd")
        assert frame >= 8
        struct.pack_into("<q", payload, frame - 8, 2**31)
        parts["nodes.arrow"] = bytes(payload)
        manifest = json.loads(parts["manifest.json"])
        manifest["files"]["nodes.arrow"]["sha256"] = hashlib.sha256(payload).hexdigest()
        parts["manifest.json"] = json.dumps(manifest).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in parts.items():
            archive.writestr(name, raw)
    return result.getvalue()


@pytest.mark.parametrize("case", ["duplicate-json", "logical-checksum", "unexpected-member", "compressed-expansion"])
def test_lab_and_device_reject_invalid_models(tmp_path, case):
    raw = malformed(case)
    with pytest.raises(ValueError) as rejected:
        ArtifactCodec.decode(raw)
    if case == "compressed-expansion":
        assert "expanded" in str(rejected.value)
    if not RUNTIME.exists():
        pytest.skip("build independent Runtime to also verify the device importer")
    source, output = tmp_path / "invalid.tmind", tmp_path / "should-not-exist.tmind"
    source.write_bytes(raw)
    result = subprocess.run(
        [str(RUNTIME), "--model", str(source), "--until-us", "20000", "--export", str(output)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert not output.exists()
    assert source.read_bytes() == raw
    if case == "compressed-expansion":
        assert "expanded" in result.stderr
