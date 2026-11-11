"""CPU fallback runs in a new process, starting from the same frozen inputs and weights."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from .protocol import MODEL_SCHEMA, canonical, digest


class ComputeExecutionError(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def replace_metadata(raw, metadata):
    """Preserve the child's numeric arrays byte-for-byte; parent needs no torch."""
    if len(raw) > 64 * 1024**2:
        raise ValueError("numeric model exceeds budget")
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        infos = source.infolist()
        if (
            len(infos) > 256
            or len({i.filename for i in infos}) != len(infos)
            or sum(i.file_size for i in infos) > 64 * 1024**2
        ):
            raise ValueError("invalid numeric model archive")
        manifest = json.loads(source.read("manifest.json"))
        if manifest.get("schema") != MODEL_SCHEMA:
            raise ValueError("unsupported numeric model schema")
        rows = manifest["arrays"]
        if {i.filename for i in infos} != {"manifest.json", *(f"{i}.npy" for i in range(len(rows)))}:
            raise ValueError("unexpected numeric model members")
        for index, row in enumerate(rows):
            if row["file"] != f"{index}.npy":
                raise ValueError("invalid numeric array name")
            data = source.read(row["file"])
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("numeric array checksum mismatch")
            target.writestr(row["file"], data)
        manifest["metadata"] = metadata
        target.writestr("manifest.json", canonical(manifest))
    if output.tell() > 64 * 1024**2:
        raise ValueError("numeric model exceeds budget")
    return output.getvalue()


def executable():
    value = os.environ.get("THREEMIND_TRANSFORMER_PYTHON")
    if not value:
        return sys.executable
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("THREEMIND_TRANSFORMER_PYTHON must name an existing absolute Python executable")
    return str(path)


def run_attempts(operation, protocol, folder, model_source=None, *, runner=subprocess.run):
    started = time.monotonic()
    budget = protocol.wall_seconds if operation == "train" else 30
    attempts = []
    original = protocol.model_dump()

    def failure(message):
        return ComputeExecutionError(
            message,
            {
                "schema": "threemind.compute-failure/1",
                "status": "failed",
                "reason": message,
                "compute_attempts": list(attempts),
                "protocol_hash": digest(original),
                "requested_compute_device": protocol.compute_device,
                "elapsed_seconds": time.monotonic() - started,
            },
        )

    for ordinal in range(2):
        remaining = budget - (time.monotonic() - started)
        if remaining <= 0:
            raise failure("compute wall budget exhausted; no additional fallback attempt was started")
        effective = dict(original)
        if operation == "train":
            effective["wall_seconds"] = remaining
        if ordinal:
            effective["compute_device"] = "cpu"
        source = folder / f"attempt-{ordinal}.json"
        report = folder / f"result-{ordinal}.json"
        model = folder / f"model-{ordinal}.tmt" if operation == "train" else model_source
        source.write_text(json.dumps(effective, allow_nan=False), encoding="utf-8")
        command = [executable(), "-m", "threemind_transformer.attempt", operation, str(source), str(model), str(report)]
        tick = time.monotonic()
        try:
            child = runner(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=remaining,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            attempts.append(
                {
                    "ordinal": ordinal,
                    "status": "timeout",
                    "steps_completed": None,
                    "elapsed_seconds": time.monotonic() - tick,
                    "protocol_hash": digest(effective),
                }
            )
            raise failure("compute wall budget exhausted; child was stopped") from exc
        if child.returncode not in (0, 86):
            reason = child.stderr.decode("utf-8", errors="replace")[-2000:] or "compute attempt failed"
            attempts.append(
                {
                    "ordinal": ordinal,
                    "status": "failed",
                    "reason": reason,
                    "steps_completed": None,
                    "elapsed_seconds": time.monotonic() - tick,
                    "protocol_hash": digest(effective),
                }
            )
            raise failure(reason)
        from .cli import read

        result = json.loads(read(report, 4 * 1024 * 1024))
        attempts.append(
            {
                "ordinal": ordinal,
                "status": result.get("status", "completed"),
                "elapsed_seconds": time.monotonic() - tick,
                "compute": result.get("compute", {}),
                "reason": result.get("reason"),
                "steps_completed": result.get("steps_completed", result.get("compute", {}).get("steps_completed", 0)),
                "protocol_hash": digest(effective),
            }
        )
        if child.returncode == 0:
            result.update(
                compute_attempts=attempts,
                requested_compute_device=protocol.compute_device,
                total_wall_seconds=time.monotonic() - started,
                fallback_from_initial_conditions=bool(ordinal),
            )
            if operation == "train":
                # The public protocol is the user's frozen scientific request, not a reduced retry timeout.
                result.update(protocol=original, protocol_hash=digest(original))
            return result, model
        if result.get("status") != "device_failed" or ordinal or protocol.compute_device == "cpu":
            raise failure("compute failed; no further CPU retry is permitted")
    raise AssertionError("unreachable")


def train_file(protocol, output, *, runner=subprocess.run):
    if output.exists():
        raise ValueError("output already exists; existing evidence is not overwritten")
    with tempfile.TemporaryDirectory(prefix="threemind-compute-") as temporary:
        result, model_path = run_attempts("train", protocol, Path(temporary), runner=runner)
        from .cli import read

        raw = replace_metadata(read(model_path, 64 * 1024**2), result)
        with output.open("xb") as stream:
            stream.write(raw)
        return {k: v for k, v in result.items() if k != "protocol"} | {"model_sha256": hashlib.sha256(raw).hexdigest()}


def predict_file(model, query, *, runner=subprocess.run):
    with tempfile.TemporaryDirectory(prefix="threemind-compute-") as temporary:
        # Freeze the input bytes so changing an external file between attempts cannot change the model.
        from .cli import read

        frozen = Path(temporary) / "input.tmt"
        frozen.write_bytes(read(model, 64 * 1024 * 1024))
        return run_attempts("predict", query, Path(temporary), frozen, runner=runner)[0]
