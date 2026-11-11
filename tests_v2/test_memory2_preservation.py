"""/2 behavior frozen before /3 and /4, using anonymous engineering inputs."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("memory2_audit", ROOT / "tools/audit_memory2_preservation.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
FROZEN = json.loads((ROOT / "tests_v2/fixtures/memory2-preservation-hashes.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def python_witnesses():
    return AUDIT.collect()


@pytest.fixture(scope="module")
def native_witnesses():
    return AUDIT.collect("native")


def test_memory2_factory_defaults_remain_the_calibrated_pre3_values(python_witnesses):
    assert AUDIT.digest(python_witnesses["default"]) == FROZEN["default_sha256"]


@pytest.mark.parametrize("name", FROZEN["cases"])
def test_memory2_matches_independent_historical_complete_state_hash(name, python_witnesses):
    expected = FROZEN["cases"][name]
    case = AUDIT.cases()[name]
    assert case["config"] == expected["config"]
    assert AUDIT.digest(case) == expected["scenario_sha256"]
    states = python_witnesses["cases"][name]
    assert len(states) == expected["snapshot_count"]
    # Frozen hashes come from pre-/3 source, not from the implementation under test.
    # A failure requires historical comparison; do not auto-update this fixture.
    assert AUDIT.digest(states) == expected["state_sha256"]


@pytest.mark.parametrize("name", FROZEN["cases"])
def test_memory2_native_keeps_historical_decisions_and_numeric_tolerance(name, python_witnesses, native_witnesses):
    assert AUDIT.close(python_witnesses["cases"][name], native_witnesses["cases"][name])
