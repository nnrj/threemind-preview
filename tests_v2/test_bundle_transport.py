import hashlib
import io
import json
import sys

import pytest

from threemind_lab import bundle_oci
from threemind_lab.experiment_archive import ArchiveWriter


def archive():
    out = io.BytesIO()
    writer = ArchiveWriter(out, {"test": True})
    writer.json("notes.json", {"content": "read only"})
    writer.finish()
    writer.close()
    return out.getvalue()


def test_oci_pull_verifies_content_without_extracting_or_executing(tmp_path, monkeypatch):
    raw = archive()
    sha = hashlib.sha256(raw).hexdigest()
    metadata = {
        "artifactType": bundle_oci.TYPE,
        "layers": [{"mediaType": bundle_oci.TYPE, "digest": "sha256:" + sha, "size": len(raw)}],
    }

    def transfer(args, output, **kw):
        body = json.dumps(metadata).encode() if args[1] == "manifest" else raw
        output.write(body)
        return {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}

    monkeypatch.setattr(bundle_oci, "command", lambda: "oras")
    monkeypatch.setattr(bundle_oci, "bounded_process", transfer)
    path = tmp_path / "copy.tmexperiment"
    result = bundle_oci.pull("registry.example/test:one", path)
    assert result["mode"] == "file_only" and path.read_bytes() == raw
    with pytest.raises(ValueError, match="exists"):
        bundle_oci.pull("registry.example/test:one", path)
    metadata["layers"][0]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="checksum"):
        bundle_oci.pull("registry.example/test:one", tmp_path / "bad.tmexperiment")
    assert not (tmp_path / "bad.tmexperiment").exists()


def test_oci_subprocess_is_bounded_by_bytes_and_time():
    with pytest.raises(ValueError, match="byte budget"):
        bundle_oci.bounded_process([sys.executable, "-c", "print('x'*4096)"], io.BytesIO(), maximum=10)
    with pytest.raises(ValueError, match="wall-clock"):
        bundle_oci.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(5)"], io.BytesIO(), maximum=10, timeout=0.1
        )


def test_oci_push_freezes_and_checks_receipt(tmp_path, monkeypatch):
    raw = archive()
    file = tmp_path / "experiment.tmexperiment"
    file.write_bytes(raw)
    observed = {}
    monkeypatch.setattr(bundle_oci, "command", lambda: "oras")

    def transfer(args, output, **kw):
        if args[1] == "push":
            from pathlib import Path

            file.write_bytes(b"concurrent edit")
            observed["raw"] = (Path(kw["cwd"]) / "experiment.tmexperiment").read_bytes()
        else:
            output.write(
                json.dumps(
                    {
                        "artifactType": bundle_oci.TYPE,
                        "layers": [{"size": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest()}],
                    }
                ).encode()
            )

    monkeypatch.setattr(bundle_oci, "bounded_process", transfer)
    result = bundle_oci.push("registry.example/test:one", file)
    assert observed["raw"] == raw and result["sha256"] == hashlib.sha256(raw).hexdigest()
