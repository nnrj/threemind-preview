"""Optional ORAS transport; one content-addressed archive blob, never image execution."""

import hashlib
import io
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .experiment_archive import ArchiveReader, strict_json

TYPE = "application/vnd.threemind.experiment-bundle.v1+zip"


def reference(value):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:/_@-]{1,500}", value) or "/" not in value or ".." in value.split("/"):
        raise ValueError("provide a registry/repository:tag or registry/repository@sha256:digest")
    return value


def command():
    binary = shutil.which("oras")
    if not binary:
        raise ValueError("ORAS CLI is optional; install ORAS and log in locally before OCI transfer")
    return binary


def bounded_process(arguments, stream, *, maximum, timeout=600, cwd=None, reserve_disk=False):
    """Drain stdout with backpressure; neither output nor wall time is unbounded."""
    messages, stopping = queue.Queue(maxsize=4), threading.Event()
    process = subprocess.Popen(
        arguments,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    def read():
        try:
            while not stopping.is_set():
                raw = process.stdout.read(1024**2)
                while not stopping.is_set():
                    try:
                        messages.put(raw, timeout=0.1)
                        break
                    except queue.Full:
                        continue
                if not raw:
                    return
        finally:
            process.stdout.close()

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    deadline, size, sha = time.monotonic() + timeout, 0, hashlib.sha256()
    try:
        while True:
            if time.monotonic() >= deadline:
                raise ValueError("OCI transfer exceeded wall-clock budget")
            try:
                raw = messages.get(timeout=0.25)
            except queue.Empty:
                continue
            if not raw:
                break
            size += len(raw)
            if size > maximum:
                raise ValueError("OCI transfer exceeded byte budget")
            if reserve_disk and shutil.disk_usage(Path(stream.name).parent).free < 15 * 1024**3:
                raise ValueError("OCI transfer reached disk reserve")
            stream.write(raw)
            sha.update(raw)
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
        if process.returncode:
            raise ValueError("ORAS transfer failed; check registry address, local login and connectivity")
        return {"bytes": size, "sha256": sha.hexdigest()}
    finally:
        stopping.set()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        thread.join(timeout=5)


def pull(target, path, *, maximum=8 * 1024**3):
    target, path = reference(target), Path(path)
    if path.exists():
        raise ValueError("output exists; evidence is never overwritten")
    buffer = io.BytesIO()
    bounded_process([command(), "manifest", "fetch", target], buffer, maximum=4 * 1024**2, timeout=60)
    manifest_bytes = buffer.getvalue()
    manifest = strict_json(manifest_bytes)
    if manifest.get("artifactType") != TYPE or len(manifest.get("layers", [])) != 1:
        raise ValueError("OCI artifact is not a single ThreeMind experiment bundle")
    manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    if "@" in target and target.rsplit("@", 1)[1] != manifest_digest:
        raise ValueError("OCI manifest digest mismatch")
    layer = manifest["layers"][0]
    if layer.get("mediaType") != TYPE or type(layer.get("size")) is not int or not 0 < layer["size"] <= maximum:
        raise ValueError("OCI layer type/size is outside budget")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", layer.get("digest", "")):
        raise ValueError("unsupported OCI layer digest")
    repository = target.split("@", 1)[0]
    if ":" in repository.rsplit("/", 1)[-1]:
        repository = repository.rsplit(":", 1)[0]
    partial = path.with_name(path.name + ".partial")
    with partial.open("xb") as output:
        result = bounded_process(
            [command(), "blob", "fetch", "--output", "-", repository + "@" + layer["digest"]],
            output,
            maximum=layer["size"],
            reserve_disk=True,
        )
    if "sha256:" + result["sha256"] != layer["digest"] or result["bytes"] != layer["size"]:
        raise ValueError("OCI blob checksum mismatch")
    with partial.open("rb") as stream:
        reader = ArchiveReader(stream)
        try:
            reader.verify()
        finally:
            reader.close()
    os.link(partial, path)
    partial.unlink()
    return result | {
        "path": str(path.resolve()),
        "manifest_digest": manifest_digest,
        "reference": target,
        "mode": "file_only",
    }


def push(target, path):
    target, path = reference(target), Path(path).resolve()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", path.name) or path.name.startswith("-"):
        raise ValueError("OCI export filename must use letters, digits, dot, underscore or hyphen")
    # Freeze a verified copy so edits to the caller's file cannot race publication.
    size = path.stat().st_size
    if not 0 < size <= 8 * 1024**3 or shutil.disk_usage(path.parent).free - size < 15 * 1024**3:
        raise ValueError("OCI publication exceeds file/disk budget")
    with tempfile.TemporaryDirectory(prefix="tm-oci-", dir=path.parent) as temp:
        frozen = Path(temp) / "experiment.tmexperiment"
        checksum, copied = hashlib.sha256(), 0
        with path.open("rb") as source, frozen.open("xb") as output:
            while raw := source.read(4 * 1024**2):
                copied += len(raw)
                if copied > size or shutil.disk_usage(temp).free < 15 * 1024**3:
                    raise ValueError("OCI source changed or disk reserve reached")
                output.write(raw)
                checksum.update(raw)
        if copied != size:
            raise ValueError("OCI source changed while freezing")
        sha = checksum.hexdigest()
        with frozen.open("rb") as stream:
            reader = ArchiveReader(stream)
            try:
                reader.verify()
            finally:
                reader.close()
        bounded_process(
            [command(), "push", "--artifact-type", TYPE, "--concurrency", "1", target, frozen.name + ":" + TYPE],
            io.BytesIO(),
            maximum=1024**2,
            cwd=temp,
        )
        receipt = io.BytesIO()
        bounded_process([command(), "manifest", "fetch", target], receipt, maximum=4 * 1024**2, timeout=60)
        metadata = strict_json(receipt.getvalue())
        layers = metadata.get("layers", [])
        if (
            metadata.get("artifactType") != TYPE
            or len(layers) != 1
            or layers[0].get("digest") != "sha256:" + sha
            or layers[0].get("size") != size
        ):
            raise ValueError(
                "publication result is uncertain: registry manifest differs; inspect the remote reference before retrying"
            )
        return {
            "reference": target,
            "manifest_digest": "sha256:" + hashlib.sha256(receipt.getvalue()).hexdigest(),
            "sha256": sha,
            "bytes": size,
            "action": "published_experiment_bundle",
        }
