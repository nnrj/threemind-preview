"""Bounded file/peer transfer, always read-only at the destination after import."""

import hashlib
import shutil
from pathlib import Path
from uuid import UUID

from .experiment_archive import CHUNK, ArchiveReader
from .operation_receipts import HEADER


def upload_file(client, project, path, request_id, *, progress=lambda value: None):
    project, request_id = str(UUID(str(project))), str(UUID(str(request_id)))
    path = Path(path)
    if not 0 < path.stat().st_size <= 8 * 1024**3:
        raise ValueError("experiment upload must be at most 8 GiB")
    with path.open("rb") as stream:
        # Only verified experiment archives can use this capability. This is not
        # a general host-file exfiltration endpoint for an MCP agent.
        reader = ArchiveReader(stream)
        try:
            reader.verify()
        finally:
            reader.close()
        stream.seek(0)
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        size = stream.tell()
        # file_digest may bypass buffering, so size comes from the descriptor.
        import os

        size = os.fstat(stream.fileno()).st_size
        base = f"/api/v2/projects/{project}/bundle-uploads"
        upload = client.request(
            "POST",
            base,
            body={"request_id": request_id, "name": path.name[:160], "bytes": size, "sha256": checksum},
            headers={HEADER: request_id},
        )
        target = base + "/" + str(UUID(upload["id"]))
        status = client.request("GET", target)
        present = {item["ordinal"]: item for item in status["chunks"]}
        stream.seek(0)
        ordinal, sent = 0, 0
        while raw := stream.read(CHUNK):
            sha = hashlib.sha256(raw).hexdigest()
            if ordinal in present:
                if present[ordinal]["sha256"] != sha or present[ordinal]["bytes"] != len(raw):
                    raise ValueError("local file changed or uploaded chunk differs")
            else:
                reply = client.request(
                    "PUT",
                    target + f"/chunks/{ordinal}",
                    content=raw,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if reply["sha256"] != sha:
                    raise ValueError("uploaded chunk checksum mismatch")
            sent += len(raw)
            ordinal += 1
            progress({"upload_id": upload["id"], "bytes": sent, "total": size})
        job = client.request("POST", target + "/complete")
    return {"upload_id": upload["id"], "job": job, "sha256": checksum, "mode": "read_only"}


def download_file(client, project, bundle_id, path, *, maximum=8 * 1024**3):
    base = f"/api/v2/projects/{UUID(str(project))}/bundles/{UUID(str(bundle_id))}"
    bundle = client.request("GET", base)
    if int(bundle["bytes"]) > maximum:
        raise ValueError("bundle exceeds download budget")
    # Publish the final path only after expected identity and inner hashes pass.
    path = Path(path)
    if path.exists():
        raise ValueError("output exists; evidence is never overwritten")
    if shutil.disk_usage(path.parent).free - int(bundle["bytes"]) < 15 * 1024**3:
        raise ValueError("download would breach the 15 GiB free-disk reserve")
    staged = path.with_name(path.name + ".verified-download")
    result = client.request("GET", base + "/download", output=staged, maximum=maximum)
    if result["sha256"] != bundle["sha256"] or result["bytes"] != int(bundle["bytes"]):
        raise ValueError("download checksum differs from the selected bundle; incomplete file retained")
    with staged.open("rb") as stream:
        reader = ArchiveReader(stream)
        try:
            reader.verify()
        finally:
            reader.close()
    import os

    os.link(staged, path)
    staged.unlink()
    return result | {"path": str(path.resolve()), "bundle_id": str(bundle_id), "verified": True}
