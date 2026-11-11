"""Engineering witnesses for the original frame runtime's lossless container."""

import hashlib
import io
import json
import zipfile

import pytest

from threemind_core import Engine, StateImage, Stimulus
from threemind_kernels.legacy.unified.frames import SensoryFrame
from threemind_kernels.legacy.unified_adapter import UnifiedConfig, UnifiedEngine
from threemind_lab.checkpoints import apply_delta, encode
from threemind_runtime import ArtifactCodec
from threemind_runtime.codec import FORMAT, UNIFIED_PAYLOAD


def original_image():
    engine = UnifiedEngine(UnifiedConfig(node_payload="labeled", sensory_encoding="legacy-labeled"))
    epoch = engine.config.step_us
    engine.inject_frame(SensoryFrame("manual", {2**64 - 9: 0.8, 3: 0.7}), time_us=0)
    engine.advance_to(epoch)
    engine.inject_frame(SensoryFrame("manual", {2**64 - 3: 0.75}), time_us=epoch * 3)
    state = engine.capture_state().to_dict()
    state["package"]["state"]["historical_extra"] = {"value": -0.0, "unsigned": 2**64 - 1, "note": "原始资料"}
    return StateImage.from_dict(state)


def container(parts):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_unified_artifact_and_checkpoint_keep_original_fields_and_continuation():
    image = original_image()
    raw = ArtifactCodec.encode(image)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {"manifest.json", "state.json"}
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == FORMAT and manifest["payload_format"] == UNIFIED_PAYLOAD
        assert manifest["kernel_id"] == "unified-associative"
    for kind in ("tmind", "json"):
        restored = ArtifactCodec.decode(ArtifactCodec.encode(image, kind))
        assert restored.payload == image.payload and restored.digest == image.digest
        assert restored.to_dict()["package"]["state"]["historical_extra"]["unsigned"] == 2**64 - 1
        assert any(int(channel) > 2**63 for _, _, frame, _ in restored.to_dict()["pending"]
                   for channel in frame["channels"])
        original, resumed = UnifiedEngine(state=image), UnifiedEngine(state=restored)
        target = original.config.step_us * 4
        original.advance_to(target)
        resumed.advance_to(target)
        assert original.capture_state().digest == resumed.capture_state().digest
        assert resumed.capture_state().to_dict()["package"]["state"]["historical_extra"] == image.to_dict()["package"]["state"]["historical_extra"]
    raw, storage, depth, patch = encode(image.to_dict(), image.digest,
                                       ({"state_hash": image.digest, "delta_depth": 0}, image.to_dict()))
    assert (storage, depth, patch) == ("tmind/2", 0, None)
    assert ArtifactCodec.decode(raw).digest == image.digest
    with pytest.raises(ValueError, match="full original package"):
        apply_delta(b"not a valid delta", image)


@pytest.mark.parametrize("fault", ["kernel", "schema", "payload", "missing-payload", "extra", "logical-checksum"])
def test_unified_container_rejects_mismatched_identity_and_corruption(fault):
    image = original_image()
    with zipfile.ZipFile(io.BytesIO(ArtifactCodec.encode(image))) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(parts["manifest.json"])
    if fault == "kernel":
        manifest["kernel_id"] = "threemind.causal/9"
    elif fault == "schema":
        manifest["state_schema"] = "threemind.state/7"
    elif fault == "payload":
        manifest["payload_format"] = "unknown-payload/1"
    elif fault == "missing-payload":
        del manifest["payload_format"]
    elif fault == "extra":
        parts["nodes.arrow"] = b"must not be interpreted as a modern graph"
    else:
        state = json.loads(parts["state.json"])
        state["package"]["state"]["historical_extra"]["unsigned"] -= 1
        parts["state.json"] = json.dumps(state).encode()
        manifest["files"]["state.json"] = {
            "bytes": len(parts["state.json"]), "sha256": hashlib.sha256(parts["state.json"]).hexdigest()}
    parts["manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError):
        ArtifactCodec.decode(container(parts))


def test_unified_compressed_expansion_budget_and_modern_container_unchanged():
    state = original_image().to_dict()
    state["package"]["state"]["historical_extra"]["large"] = "0" * 100_000
    image = StateImage.from_dict(state)
    raw = ArtifactCodec.encode(image)
    assert len(raw) < 100_000
    with pytest.raises(ValueError, match="expanded"):
        ArtifactCodec.decode(raw, max_bytes=len(raw) + 1)
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.4), (2, 0.6))))
    engine.advance_to(10000)
    modern = engine.capture_state()
    with zipfile.ZipFile(io.BytesIO(ArtifactCodec.encode(modern))) as archive:
        assert set(archive.namelist()) == {"manifest.json", "state.json", "nodes.arrow", "edges.arrow"}
        assert "payload_format" not in json.loads(archive.read("manifest.json"))
    assert ArtifactCodec.decode(ArtifactCodec.encode(modern)).digest == modern.digest
