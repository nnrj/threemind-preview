import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import READERS
from experiment import AGES, FORGETTING, SEEDS, background, old_memory, schedule, warm

from threemind_runtime.host import create_engine
from threemind_runtime.readout_config import ActivityReadoutConfig, TemporalReadoutConfig


def test_schedule_dose_and_readouts():
    assert sum(v for _, v in schedule("massed")) == sum(v for _, v in schedule("spaced"))
    assert schedule("single_4") == [(128, 4)]
    assert schedule("spaced")[-1][0] == 128
    assert AGES == (1, 10, 30, 100, 300)
    ActivityReadoutConfig(**READERS["activity_readout"])
    TemporalReadoutConfig(**READERS["temporal_readout"])
    assert FORGETTING["slow_off"] == {
        "forgetting_rate": 0.0,
        "stability_decay_enabled": False,
        "support_decay_enabled": False,
    }


def test_novelty_probe_call_contract(monkeypatch):
    import inspect

    import experiment

    signature = inspect.signature(experiment.probe)
    calls = []
    monkeypatch.setattr(experiment, "done", lambda *args: {"seed": SEEDS[0]})

    def record(*args, **kwargs):
        calls.append(signature.bind(*args, **kwargs))

    monkeypatch.setattr(experiment, "probe", record)
    experiment.novelty(None)
    assert len(calls) == 72


def test_historical_parents_restore_without_conversion_and_telemetry_coverage():
    for seed in SEEDS:
        for parent in (warm(seed), old_memory(seed, "none"), old_memory(seed, "spaced_ordinary")):
            engine = create_engine(state=parent["image"], backend="native")
            assert engine.capture_state().digest == parent["image"].digest
            assert engine.config.inhibition and engine.config.plasticity and engine.config.stp_enabled
            assert engine.config.depletion_enabled and engine.config.stp_facilitation_tau_s > 0
            assert engine.config.energy_simulation_enabled
            assert background(seed)[1][-1] > engine.time_us + 650_000_000
