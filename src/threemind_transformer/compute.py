"""Optional device policy. Does not import torch until explicitly probing a tool host.

The Core solver and sensory mapping do not use this module. Allocation limits are
best-effort process budgets, not an OS sandbox. CUDA tests remain a separate gate.
"""

import os
import platform
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

MIB = 1024 * 1024


class DeviceFailure(RuntimeError):
    def __init__(self, reason, evidence=None):
        super().__init__(reason)
        self.evidence = evidence or {}


def device_fault(error):
    """Never relabel invalid data, nonfinite loss or general logic errors as GPU failure."""
    if isinstance(error, DeviceFailure):
        return True
    import torch

    return isinstance(error, torch.cuda.OutOfMemoryError) or (
        isinstance(error, RuntimeError)
        and any(
            marker in str(error).lower()
            for marker in (
                "cuda error: initialization error",
                "cuda error: unknown error",
                "cuda error: device is lost",
                "cuda error: device lost",
                "cuda error: out of memory",
                "cuda driver initialization failed",
                "no kernel image is available",
                "not compiled with cuda",
                "found no nvidia driver",
                "cuda-capable device(s) is/are busy or unavailable",
            )
        )
    )


def probe():
    result = {
        "schema": "threemind.compute-capabilities/1",
        "platform": platform.system(),
        "scope": "current_tool_process",
        "cpu": True,
        "cuda_available": False,
        "devices": [],
        "real_gpu_validation": "not_run",
        "kernels_device": "cpu",
        "driver_version": None,
    }
    try:
        import torch

        result.update(torch_version=str(torch.__version__), cuda_runtime=torch.version.cuda)
        import shutil
        import subprocess

        binary = shutil.which("nvidia-smi")
        if binary:
            try:
                output = subprocess.run(
                    [binary, "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if output.returncode == 0:
                    result["driver_version"] = output.stdout.decode(errors="replace")[:200].strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        if not torch.cuda.is_available():
            result["reason"] = "cpu_torch_build" if torch.version.cuda is None else "cuda_unavailable"
            return result
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            free, total = torch.cuda.mem_get_info(index)
            result["devices"].append(
                {
                    "index": index,
                    "name": props.name,
                    "free_bytes": free,
                    "total_bytes": total,
                    "compute_capability": [props.major, props.minor],
                }
            )
        result.update(cuda_available=bool(result["devices"]), reason="device_discovered_not_benchmarked")
    except (ImportError, OSError, RuntimeError, AssertionError) as exc:
        result.update(reason="optional_dependency_unavailable", detail=f"{type(exc).__name__}: {exc}"[:400])
    return result


@contextmanager
def gpu_slot():
    """One cooperating Transformer CUDA process per host/user; crash releases OS lock."""
    root = Path(os.environ.get("THREEMIND_COMPUTE_LOCK_DIR", tempfile.gettempdir()))
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / "threemind-gpu-0.lock").open("a+b")
    acquired = False
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def stable_speedup(cpu, gpu):
    # Each pair includes model placement and transfers. No optimistic mean hiding slow samples.
    return len(cpu) == len(gpu) == 3 and all(c > 0 and g > 0 and c / g >= 1.2 for c, g in zip(cpu, gpu))


@contextmanager
def device_session(policy, benchmark=None):
    """Resolve once; hold the slot for this attempt. A failed CUDA context is not reused."""
    evidence = {
        "requested": policy.compute_device,
        "resolved": "cpu",
        "dtype": "float32",
        "reason": "explicit_cpu",
        "peak_vram_bytes": 0,
        "benchmark": None,
        "memory_budget_mib": policy.gpu_memory_mib,
        "headroom_mib": policy.gpu_headroom_mib,
    }
    if policy.compute_device == "cpu":
        yield evidence, lambda: None
        return
    capability = probe()
    evidence["capability"] = capability
    if not capability["cuda_available"]:
        evidence["reason"] = capability["reason"]
        yield evidence, lambda: None
        return
    with gpu_slot() as acquired:
        if not acquired:
            evidence["reason"] = "gpu_busy"
            yield evidence, lambda: None
            return
        import torch

        device = capability["devices"][0]
        allowance = min(policy.gpu_memory_mib * MIB, device["free_bytes"] - policy.gpu_headroom_mib * MIB)
        if allowance < 128 * MIB:
            evidence["reason"] = "insufficient_free_vram"
            yield evidence, lambda: None
            return
        evidence["allocation_limit_bytes"] = allowance
        old_matmul, old_cudnn = torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32
        try:
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            torch.cuda.set_per_process_memory_fraction(allowance / device["total_bytes"], 0)
            torch.cuda.reset_peak_memory_stats(0)

            def check():
                evidence["peak_vram_bytes"] = max(evidence["peak_vram_bytes"], torch.cuda.max_memory_reserved(0))
                free, _ = torch.cuda.mem_get_info(0)
                if evidence["peak_vram_bytes"] > allowance or free < policy.gpu_headroom_mib * MIB:
                    raise DeviceFailure("vram_budget", evidence)

            if policy.compute_device == "auto":
                if benchmark is None:
                    evidence["reason"] = "no_representative_benchmark"
                    yield evidence, lambda: None
                    return
                timings = benchmark(check)
                evidence["benchmark"] = timings
                if not stable_speedup(timings["cpu_seconds"], timings["cuda_seconds"]):
                    evidence["reason"] = "cpu_faster_or_gpu_gain_below_20_percent"
                    yield evidence, lambda: None
                    return
            evidence.update(
                resolved="cuda", reason="explicit_gpu" if policy.compute_device == "cuda" else "measured_speedup"
            )
            yield evidence, check
            check()
        except (RuntimeError, AssertionError) as exc:
            if device_fault(exc):
                evidence["failure"] = str(exc)[:500]
                raise DeviceFailure(str(exc), evidence | getattr(exc, "evidence", {})) from exc
            raise
        finally:
            torch.backends.cuda.matmul.allow_tf32 = old_matmul
            torch.backends.cudnn.allow_tf32 = old_cudnn


def representative_benchmark(factory, operation, check):
    """Three cold-placement, three-step measurements; uses independent disposable models."""
    import torch

    times = {
        "cpu_seconds": [],
        "cuda_seconds": [],
        "steps_per_sample": 3,
        "includes": "placement, batch transfer, computation and synchronized completion",
    }
    for _ in range(3):
        for device in ("cpu", "cuda"):
            check()
            model = factory()
            if device == "cuda":
                torch.cuda.synchronize(0)
            start = time.perf_counter()
            model = model.to(device)
            operation(model, 3)
            if device == "cuda":
                torch.cuda.synchronize(0)
            times[device + "_seconds"].append(time.perf_counter() - start)
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
            check()
    return times
