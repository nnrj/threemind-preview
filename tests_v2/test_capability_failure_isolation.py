import json
import subprocess

import pytest

from threemind_runtime import capabilities


def test_native_optional_exceptions_are_reported_without_hiding_interrupts():
    class NativeFatalError(Exception):
        pass

    def fail():
        raise NativeFatalError("missing graphics context")

    result = capabilities.check("optional", fail)
    assert result["state"] == "unavailable" and "NativeFatalError" in result["reason"]
    with pytest.raises(KeyboardInterrupt):
        capabilities.check("interrupt", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))


@pytest.mark.parametrize("failure", ["crash", "hang", "malformed", "missing"])
def test_renderer_failure_does_not_remove_other_worker_capabilities(monkeypatch, failure):
    def run(command, **kwargs):
        assert command[-1] == "threemind_runtime.capability_render" and kwargs["timeout"] == 20
        assert kwargs["stdin"] == subprocess.DEVNULL
        if failure == "hang":
            raise subprocess.TimeoutExpired(command, 20)
        if failure == "missing":
            raise OSError("process could not start")
        return subprocess.CompletedProcess(command, -11 if failure == "crash" else 0, "{}", "driver failed")

    monkeypatch.setattr(capabilities.subprocess, "run", run)
    monkeypatch.setattr(capabilities, "engine_probe", lambda backend: {"backend": backend})
    monkeypatch.setattr(capabilities, "physics_probe", dict)
    monkeypatch.setattr(capabilities, "world_probe", dict)
    report = capabilities.probe_worker("native")["features"]
    assert report["worker.world_rgb_v1"]["state"] == "unavailable"
    assert all(report[key]["state"] == "available" for key in ("worker.core", "worker.mujoco", "worker.world_v1"))


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_renderer_child_result_keeps_missing_and_available_states(monkeypatch, state):
    monkeypatch.setattr(
        capabilities.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"schema": "threemind.render-probe/1", "result": {"state": state, "reason": "measured"}}),
            "",
        ),
    )
    result = capabilities.check("RGB", capabilities.world_rgb_probe)
    assert result["state"] == state and result["isolated_process"]


def test_idle_worker_rechecks_failed_renderer_without_touching_other_capabilities(monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace

    from threemind_lab import worker as module

    reports, checked = [], []
    clock = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module, "capture_implementation", lambda backend: {})
    backend = SimpleNamespace(announce_worker=lambda name, report: reports.append(deepcopy(report)))
    worker = module.Worker(backend)
    worker.capabilities = {
        "features": {"worker.core": {"state": "available"}, "worker.world_rgb_v1": {"state": "unavailable"}}
    }

    def probe():
        checked.append(clock[0])
        return {"state": "unavailable" if len(checked) == 1 else "available", "reason": "independent fixture"}

    monkeypatch.setattr(capabilities, "world_rgb_probe", probe)
    worker.refresh_optional_capabilities()
    assert not checked
    clock[0] = 60
    worker.refresh_optional_capabilities()
    clock[0] = 119
    worker.refresh_optional_capabilities()
    assert checked == [60]
    clock[0] = 120
    worker.refresh_optional_capabilities()
    assert reports[-1]["features"]["worker.world_rgb_v1"]["state"] == "available"
    assert reports[-1]["features"]["worker.core"] == {"state": "available"}
    clock[0] = 180
    worker.refresh_optional_capabilities()
    assert checked == [60, 120]  # No repeated probing once available.
