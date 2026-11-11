import json
from pathlib import Path

import pytest
from kernel_witnesses import exercise

from threemind_core import Config, Engine, Stimulus

BASELINE = json.loads((Path(__file__).parent / "fixtures/causal9-baseline.json").read_text(encoding="utf-8"))


def assert_state_close(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_state_close(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            assert_state_close(left, right)
    elif isinstance(expected, float):
        # Preserve the existing Python/Rust libm tolerance, not a new threshold.
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-14)
    else:
        assert actual == expected


@pytest.mark.parametrize("name", BASELINE["cases"])
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_causal9_preserves_frozen_behavior(name, backend):
    if backend == "native":
        from threemind_runtime.host import NativeEngine

        factory = NativeEngine
    else:
        factory = Engine
    case = BASELINE["cases"][name]
    actual = exercise(case, config_type=Config, stimulus_type=Stimulus, factory=factory)
    assert_state_close(actual, case["snapshots"])
