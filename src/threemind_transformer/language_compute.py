"""Bounded child execution; strict decoding gets its own request without user text."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining, ScratchTraining
from .process_guard import OwnedProcessTree
from .supervisor import ComputeExecutionError, executable


def compute(operation, payload, policy=None, *, head=None, checkpoint=None):
    import psutil

    policy = policy or LanguageCompute()
    if operation not in ("encode", "train", "decode", "decode_many", "scratch_train"):
        raise ValueError("unknown language compute operation")
    attempts, started = [], time.monotonic()
    cache = Path(os.environ.get("THREEMIND_COMPUTE_TEMP", ".work/compute-temp")).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="language-", dir=cache) as temporary:
        folder = Path(temporary)
        model_input = folder / "head.safetensors"
        checkpoint_input = folder / "checkpoint.safetensors"
        if checkpoint is not None:
            if len(checkpoint) > 64 * 2**20:
                raise ValueError("scratch checkpoint exceeds 64 MiB")
            checkpoint_input.write_bytes(checkpoint)
        if head is not None:
            if len(head) > 64 * 2**20:
                raise ValueError("head exceeds 64 MiB")
            model_input.write_bytes(head)
        for ordinal in range(2):
            effective = policy.model_copy(update={"compute_device": "cpu"}) if ordinal else policy
            request, report, model_output = (
                folder / f"request{ordinal}.json",
                folder / f"result{ordinal}.json",
                folder / f"output{ordinal}.safetensors",
            )
            request.write_text(
                json.dumps(
                    {
                        "operation": operation,
                        "payload": payload,
                        "compute": effective.model_dump(),
                        "head": str(model_input) if head is not None else None,
                        "checkpoint": str(checkpoint_input) if checkpoint is not None else None,
                        "output": str(model_output),
                    },
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            with (
                (folder / f"stderr{ordinal}.log").open("wb") as err,
                (folder / f"stdout{ordinal}.log").open("wb") as out,
            ):
                child = subprocess.Popen(
                    [executable(), "-m", "threemind_transformer.language_compute", "child", str(request), str(report)],
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    env=os.environ
                    | {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"},
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                process = OwnedProcessTree(child.pid)
                peak, stopped = 0, None
                try:
                    while child.poll() is None:
                        if time.monotonic() - started > policy.wall_seconds:
                            stopped = "wall_budget"
                        peak = max(peak, process.sample())
                        if peak > policy.memory_mib * 2**20:
                            stopped = "memory_budget"
                        if psutil.virtual_memory().available < 2 * 2**30:
                            stopped = "host_memory_headroom"
                        if stopped:
                            process.stop()
                            break
                        time.sleep(0.1)
                    child.wait(timeout=10)
                finally:
                    process.stop()
                    child.wait(timeout=10)
            if stopped:
                raise ComputeExecutionError(
                    stopped, {"attempts": attempts, "peak_memory_bytes": peak, "stopped": stopped}
                )
            if not report.is_file() or report.stat().st_size > 16 * 2**20:
                detail = (folder / f"stderr{ordinal}.log").read_text(encoding="utf-8", errors="replace")[-2000:]
                raise ComputeExecutionError("language child failed", {"attempts": attempts, "detail": detail})
            result = json.loads(report.read_text(encoding="utf-8"))
            attempts.append(
                {
                    "device": effective.compute_device,
                    "status": result.get("status"),
                    "compute": result.get("compute"),
                    "peak_memory_bytes": peak,
                    "reason": result.get("reason"),
                }
            )
            if child.returncode == 0:
                result.update(
                    compute_attempts=attempts,
                    elapsed_seconds=time.monotonic() - started,
                    fallback_from_initial_conditions=bool(ordinal),
                )
                return result, model_output.read_bytes() if operation in ("train", "scratch_train") else None
            if child.returncode != 86 or ordinal or effective.compute_device == "cpu":
                raise ComputeExecutionError(result.get("reason", "language computation failed"), {"attempts": attempts})
    raise AssertionError("unreachable")


def child(request, report):
    import torch

    from .compute import device_fault, device_session
    from .language_model import decode, encode, train

    value = json.loads(request.read_text(encoding="utf-8"))
    policy = LanguageCompute.model_validate(value["compute"])
    torch.set_num_threads(policy.threads)
    result = {}
    try:
        with device_session(policy) as (evidence, check):
            operation, payload = value["operation"], value["payload"]
            checkpoint = Path(value["checkpoint"]) if value.get("checkpoint") else None
            protocol = LanguageProtocol.model_validate(payload["protocol"])
            model = protocol.input_model if operation == "encode" else protocol.output_model
            evidence["dtype"] = "float16" if evidence["resolved"] == "cuda" and model == "qwen" else "float32"
            if operation == "encode":
                if set(payload) != {"texts", "protocol"} or not 1 <= len(payload["texts"]) <= 512:
                    raise ValueError("invalid encoding request")
                result = encode(payload["texts"], protocol, evidence["resolved"], check, checkpoint)
            elif operation == "train":
                result = train(
                    LanguageTraining.model_validate(payload),
                    Path(value["output"]),
                    evidence["resolved"],
                    check,
                    checkpoint,
                )
            elif operation == "scratch_train":
                from .scratch_language import train as scratch_train

                result = scratch_train(
                    ScratchTraining.model_validate(payload),
                    Path(value["output"]),
                    evidence["resolved"],
                    check,
                    checkpoint,
                )
            elif operation == "decode_many":
                from .language_model import decode_many

                if set(payload) != {"windows", "protocol"}:
                    raise ValueError("undeclared batch decoder information")
                result = decode_many(
                    payload["windows"],
                    protocol,
                    Path(value["head"]) if value["head"] else None,
                    evidence["resolved"],
                    check,
                    checkpoint=checkpoint,
                )
            else:
                if not set(payload) <= {"features", "protocol", "assistance"}:
                    raise ValueError("undeclared decoder information")
                result = decode(
                    payload["features"],
                    LanguageProtocol.model_validate(payload["protocol"]),
                    Path(value["head"]) if value["head"] else None,
                    evidence["resolved"],
                    check,
                    assistance=payload.get("assistance"),
                    checkpoint=checkpoint,
                )
            result.update(status="completed", compute=evidence)
        report.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        return 0
    except Exception as error:  # noqa: BLE001 -- child failure is returned with evidence, never retried as success
        gpu_failure = device_fault(error)
        report.write_text(
            json.dumps(
                {
                    "status": "device_failed" if gpu_failure else "failed",
                    "reason": str(error),
                    "compute": getattr(error, "evidence", {}),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return 86 if gpu_failure else 1


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "child":
        raise SystemExit("internal isolated child only")
    raise SystemExit(child(Path(sys.argv[2]), Path(sys.argv[3])))
