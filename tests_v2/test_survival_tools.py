import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from lab.tools.granular_protocol import SurvivalProtocol
from lab.tools.granular_session import SurvivalSession
from lab.tools.survival import FoodConfig, TaskFood, select_survivors
from threemind_runtime import create_engine
from threemind_runtime.playground_assets import installed


def test_physical_food_is_idempotent_timed_and_has_a_closed_ledger():
    engine = create_engine(
        {"energy_simulation_enabled": True, "energy_initial_reserve": 2.0, "energy_capacity": 12.0},
        kernel_id="threemind.continuous-memory/2",
    )
    food = TaskFood(FoodConfig(energy_per_unit=3.0, interval_us=1000000))
    assert food.credit(sequence=0, time_us=20000, units=2.0)
    assert not food.credit(sequence=0, time_us=20000, units=2.0)
    with pytest.raises(ValueError, match="changed"):
        food.credit(sequence=0, time_us=20000, units=3.0)
    assert food.settle(engine, 20000) is None
    assert engine.metrics()["energy"]["reserve"] == 2
    restored = TaskFood(food.config, state=json.loads(json.dumps(food.capture())))
    offer = restored.settle(engine, 1000000)
    assert offer["amount"] == 6
    assert restored.settle(engine, 1000000) is None
    engine.advance_to(1000000)
    assert engine.metrics()["energy"]["reserve"] == 8
    assert engine.metrics()["energy"]["supplied_total"] == 6
    restored.credit(sequence=1, time_us=1020000, units=3)
    restored.settle(engine, 2000000)
    engine.advance_to(2000000)
    assert engine.metrics()["energy"]["reserve"] == 12
    assert engine.metrics()["energy"]["offered_total"] == 15
    assert engine.metrics()["energy"]["supplied_total"] == 10
    assert restored.capture()["offered"] == 15
    corrupt = restored.capture()
    corrupt["pending"] = 1
    with pytest.raises(ValueError, match="balance"):
        TaskFood(restored.config, state=corrupt)


def test_selection_never_revives_dead_or_promotes_censored_living_candidates():
    rows = [
        {"id": "dead-rich", "life": "dead", "energy_reserve": 100, "horizon_reached": True, "failed": False},
        {"id": "censored", "life": "active", "energy_reserve": 100, "horizon_reached": False, "failed": False},
        {"id": "living-a", "life": "active", "energy_reserve": 3, "horizon_reached": True, "failed": False},
        {"id": "living-b", "life": "active", "energy_reserve": 5, "horizon_reached": True, "failed": False},
    ]
    before = copy.deepcopy(rows)
    choice = select_survivors(rows, parent_count=1, offspring_count=4)
    assert rows == before
    assert choice["parents"] == ["living-b"]
    assert {r["parent"] for r in choice["offspring"]} == {"living-b"}
    assert set(choice["paused_alive"]) == {"censored", "living-a"}
    assert not choice["extinct"]
    dead = select_survivors(rows[:1], parent_count=1, offspring_count=4)
    assert dead["extinct"] and dead["no_eligible_parent"] and not dead["offspring"]
    censored = select_survivors(rows[1:2], parent_count=1, offspring_count=4)
    assert not censored["extinct"] and censored["no_eligible_parent"]


def test_task_parameters_refuse_silent_clock_or_mechanical_changes():
    protocol = SurvivalProtocol().model_dump(mode="json", by_alias=True)
    for patch in ({"period_us": 21000}, {"force_limits": [100.0] * 8}, {"grains": 13}, {"unknown": 1}):
        wrong = copy.deepcopy(protocol)
        wrong["world"].update(patch)
        with pytest.raises(ValueError):
            SurvivalProtocol.model_validate(wrong)
    wrong = copy.deepcopy(protocol)
    wrong["core"]["energy_simulation_enabled"] = False
    with pytest.raises(ValueError, match="finite"):
        SurvivalProtocol.model_validate(wrong)


@pytest.mark.skipif(not installed(), reason="requires explicitly installed pinned Panda assets")
def test_extracted_loop_preserves_frozen_physics_inputs_core_and_continuation():
    folder = Path(__file__).resolve().parents[1] / "lab/explorations/2026-10-02-survival-transfer"
    spec = importlib.util.spec_from_file_location("e27_physical", folder / "physical.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = sys.modules.get("physical")
    sys.modules["physical"] = module
    try:
        spec = importlib.util.spec_from_file_location("e27_session", folder / "session.py")
        previous = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(previous)
    finally:
        if old is None:
            sys.modules.pop("physical", None)
        else:
            sys.modules["physical"] = old
    protocol = SurvivalProtocol().model_dump(mode="json", by_alias=True)
    with previous.SurvivalSession(protocol) as baseline, SurvivalSession(protocol) as current:
        a, b = [], []
        for _ in range(8):
            baseline.step(a.append)
            current.step(b.append)
        assert a == b
        assert baseline.context() == current.context()
        assert baseline.engine.capture_state().digest == current.engine.capture_state().digest
        image, context = current.engine.capture_state(), current.context()
        with SurvivalSession(protocol, image=image, context=context) as recovered:
            a, b = [], []
            for _ in range(4):
                current.step(a.append)
                recovered.step(b.append)
            assert a == b
            assert current.context() == recovered.context()
            assert current.engine.capture_state().digest == recovered.engine.capture_state().digest


@pytest.mark.skipif(not installed(), reason="requires explicitly installed pinned Panda assets")
def test_video_replay_is_verified_against_raw_inputs_and_does_not_change_source(tmp_path):
    import gzip

    from lab.tools.granular_replay import replay, replay_core
    from lab.tools.granular_survival import run

    protocol = SurvivalProtocol().model_dump(mode="json", by_alias=True)
    source, output = tmp_path / "individual", tmp_path / "video"
    run(protocol, source, 0.12)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    evidence = replay(source, output, 0.1)
    assert evidence["rows"] == 6
    assert evidence["raw_measurements_match"] and evidence["final_physics_match"]
    assert not evidence["core_reexecuted"]
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}
    assert (output / "behavior.mp4").stat().st_size > 0
    assert (output / "sequence.png").exists()
    core = replay_core(source, tmp_path / "core-replay")
    assert core["final_state_matches"] and core["all_recorded_pre_action_activity_matches"]
    # Explicitly corrupted test fixture: strict mode must reject even one pixel;
    # the opt-in physical-only mode must disclose it, never claim exact senses.
    with gzip.open(source / "events.jsonl.gz", "rt", encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]
    records[0]["physical"]["luminance"][0] += 1
    with gzip.open(source / "events.jsonl.gz", "wt", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="sensory"):
        replay(source, tmp_path / "strict", 0.1)
    disclosed = replay(source, tmp_path / "physical-only", 0.1, allow_pixel_variation=True)
    assert not disclosed["raw_measurements_match"] and disclosed["physical_measurements_match"]
    assert disclosed["rendered_pixel_variation"]["maximum_absolute_difference"] == 1
