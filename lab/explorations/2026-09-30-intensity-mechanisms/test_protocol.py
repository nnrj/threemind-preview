"""Validate factor isolation and representation invariance before research."""

import itertools
import runpy
from pathlib import Path

import pytest

from threemind_core import Stimulus
from threemind_kernels.mechanisms import ShortTermConfig, ShortTermState
from threemind_kernels.novelty import NoveltyConfig
from threemind_runtime import create_engine

SCRIPT = runpy.run_path(str(Path(__file__).with_name("experiment.py")))


def test_factorial_does_not_disable_unrelated_dynamics():
    original = NoveltyConfig().to_dict()
    for factors in itertools.product((0, 1), repeat=3):
        patch = SCRIPT["factor_config"](*factors)
        actual = NoveltyConfig(**patch).to_dict()
        assert all(actual[k] == v for k, v in original.items() if k not in patch)
        assert actual["inhibition"] and actual["depletion_enabled"] and actual["plasticity"]
        assert actual["forgetting_rate"] == 0.025


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_equal_incident_representation_only_separates_with_explicit_bonus(backend):
    for gain in (0.0, 0.075):
        states = []
        for value, intensity in ((1.0, 1.0), (0.25, 4.0)):
            e = create_engine({"intensity_gain": gain}, kernel_id=SCRIPT["KERNEL"], backend=backend)
            e.inject(Stimulus(0, ((1, value), (2, value)), intensity))
            e.advance_to(500000)
            states.append(e.capture_state())
        assert (states[0].digest == states[1].digest) == (gain == 0)


def test_facilitation_changes_utilization_without_inventing_resources():
    outcomes = []
    for tau in (0.0, 1.0):
        config = ShortTermConfig(facilitation_tau_s=tau)
        state, first = ShortTermState().release(0, config)
        state, second = state.release(100000, config)
        assert first == 0.5
        assert state.available + state.active <= 1.0
        outcomes.append((state.utilization, second))
    assert outcomes[1][0] > outcomes[0][0]
    assert outcomes[1][1] > outcomes[0][1]


def test_training_quantity_and_last_input_are_matched():
    histories = SCRIPT["HISTORIES"]
    assert sum(dose for _, dose in histories["repeat"]) == pytest.approx(4.0)
    assert histories["single4"][-1][0] == histories["repeat"][-1][0] == histories["single1"][-1][0]
