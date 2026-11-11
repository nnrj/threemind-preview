"""Probe the actual configured Transformer child, never infer remote worker hardware from the API host."""

import json
import subprocess

from threemind_transformer.supervisor import executable


def probe_tool():
    try:
        child = subprocess.run(
            [executable(), "-m", "threemind_transformer.cli", "compute"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if child.returncode or len(child.stdout) > 65536:
            raise ValueError("compute probe child failed")
        result = json.loads(child.stdout)
        if result.get("schema") != "threemind.compute-capabilities/1":
            raise ValueError("unexpected compute probe version")
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {
            "schema": "threemind.compute-capabilities/1",
            "cpu": False,
            "cuda_available": False,
            "devices": [],
            "reason": "probe_failed",
            "detail": str(exc)[:400],
            "real_gpu_validation": "not_run",
            "kernels_device": "cpu",
        }


def worker_feature():
    capability = probe_tool()
    return {
        "state": "available" if capability.get("torch_version") else "unavailable",
        "name": "本地 Transformer 对照",
        "reason": "独立计算子进程；GPU 不可用时使用 CPU，不自动回灌内核。",
        "compute": capability,
    }
