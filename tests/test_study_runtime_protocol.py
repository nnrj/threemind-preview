"""Physical study protocols are explicit and cannot silently alter Core/readers."""

import pytest

from lab.tools.service_study import case_run_spec
from threemind_lab.protocols import RunSpec

READERS = {
    "structural_readout": {"enabled": False},
    "temporal_readout": {"enabled": True},
    "activity_readout": {"enabled": True},
}
KERNEL = "threemind.continuous-memory/2"


def test_existing_replay_protocol_is_identical():
    actual = case_run_spec(KERNEL, 71, {}, READERS, False)
    original = RunSpec(
        kernel_id=KERNEL,
        environment="replay",
        clock="unbounded",
        seed=71,
        config={},
        structural_readout={"enabled": False},
        temporal_readout={"enabled": False},
        activity_readout={"enabled": False},
    )
    assert actual.model_dump() == original.model_dump()


def test_physical_input_requires_real_time():
    with pytest.raises(ValueError, match="实时"):
        case_run_spec(KERNEL, 71, {}, READERS, False, {"host_telemetry": {"enabled": True}})
    spec = case_run_spec(
        KERNEL, 71, {}, READERS, False, {"clock": "realtime", "host_telemetry": {"enabled": True, "intensity": 0.2}}
    )
    assert spec.host_telemetry.enabled and spec.host_telemetry.intensity == 0.2
    assert spec.config == {} and not spec.activity_readout.enabled


def test_runtime_override_cannot_change_dynamics_or_observers():
    for key in ("config", "kernel_id", "activity_readout", "seed"):
        with pytest.raises(ValueError, match="unsupported"):
            case_run_spec(KERNEL, 71, {}, READERS, False, {key: {}})


def test_study_worker_lock_rejects_overlap_and_releases(tmp_path):
    from lab.tools.study_lock import worker_lock

    first = worker_lock(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="another simulation"):
            worker_lock(tmp_path)
    finally:
        first.close()
    worker_lock(tmp_path).close()
