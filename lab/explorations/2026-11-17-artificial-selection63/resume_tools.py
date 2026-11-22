"""Resume a declared, fully saved stage without discarding its past activity."""
import math
from pathlib import Path
import time

import ring as r

ORIGINAL_EXECUTE = r.execute


def continue_execute(folder, key, seed, *, whole=None, parent=None, position=None, blank_control=False,
                     seconds=60, mode="normal", backend="native", guard=None):
    folder = Path(folder)
    if (folder / "result.json").exists() or not folder.exists():
        return ORIGINAL_EXECUTE(folder, key, seed, whole=whole, parent=parent, position=position,
                                blank_control=blank_control, seconds=seconds, mode=mode,
                                backend=backend, guard=guard)
    assert mode == "normal"
    initial = r.read(folder / "initial.json.gz")
    saved = r.read(folder / "interrupted.json.gz")
    trace = r.read(folder / "interrupted-trace.json.gz")
    ancestry = r.read(folder / "ancestry.json")
    begin = int(initial["core"]["time_us"])
    current = int(saved["core"]["time_us"])
    end = begin + round(seconds*1e6)
    assert saved["kernel"] == initial["kernel"] == r.KERNEL
    assert saved["seed"] == initial["seed"] == seed
    assert saved["next_motor"] == current and begin <= current < end
    assert len(trace["rows"]) == (current-begin)//100000
    assert all(row["time_us"] == begin+i*100000 for i, row in enumerate(trace["rows"]))
    # Resume only a boundary captured before the next complete physical/Core step.
    if trace["rows"]:
        last = trace["rows"][-1]
        v, u = last["body"]["v"], last["control"]
        terminal = .3*u/.8
        dx = terminal*.1+(v-terminal)*(1-math.exp(-.8*.1))/.8
        assert abs(saved["body"]["x"]-(last["body"]["x"]+dx)%1) <= 1e-12
        assert abs(saved["body"]["v"]-(terminal+(v-terminal)*math.exp(-.8*.1))) <= 1e-12
    obj = r.Ring(key, seed, whole=saved, backend=backend)
    assert obj.snapshot() == saved
    obj.origin, obj.ancestry = initial, ancestry
    obj.rows.extend(trace["rows"])
    obj.events.extend(trace["events"])
    obj.inputs.extend(trace["inputs"])
    resume_start = time.time()
    r.save(folder / "continuation-v2.json", {"schema": "artificial-selection63/continuation/1",
        "initial_whole_hash": r.digest(initial), "resumed_whole_hash": r.digest(saved),
        "resume_at_us": current, "end_us": end, "prior_rows_retained": len(trace["rows"]),
        "birth_called": False, "positioning_repeated": False, "resume_wall_epoch": resume_start})
    try:
        result = obj.run((end-current)/1e6, guard=guard)
    except BaseException:
        r.save(folder / "interrupted-v2.json.gz", obj.snapshot())
        r.save(folder / "interrupted-trace-v2.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
        raise
    result.update(begin_us=begin, seconds=seconds)
    distance = 0.
    for row in obj.rows:
        terminal = .3*row["control"]/.8
        distance += abs(terminal*.1 + (row["body"]["v"]-terminal)*(1-math.exp(-.8*.1))/.8)
    result["travel_distance"] = distance
    result["continuation"] = {"schema": "artificial-selection63/continuation/1",
                              "at_us": current, "previous_rows": len(trace["rows"]),
                              "wall_seconds_covers": "post-pause segment only"}
    final = obj.snapshot()
    assert len(obj.rows) == round(seconds*10)
    assert r.digest(final) == result["final_whole_hash"]
    r.save(folder / "final.json.gz", final)
    assert r.read(folder / "final.json.gz") == final
    r.save(folder / "trajectory.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
    r.save(folder / "result.json", result)
    return result, final


def apparatus(work):
    folder = work / "continuation-v2/apparatus"
    assert not folder.exists()
    key = "continuation-apparatus"
    reference, expected = ORIGINAL_EXECUTE(folder / "continuous", key, r.INSTRUMENT_SEED,
                                           position=.125, seconds=3)
    calls = 0
    def stop_at_boundary():
        nonlocal calls
        calls += 1
        if calls == 13:
            raise RuntimeError("declared instrument pause at step boundary")
    try:
        ORIGINAL_EXECUTE(folder / "paused", key, r.INSTRUMENT_SEED, position=.125, seconds=3, guard=stop_at_boundary)
    except RuntimeError as exc:
        assert str(exc) == "declared instrument pause at step boundary"
    else:
        raise AssertionError("instrument pause did not occur")
    resumed, actual = continue_execute(folder / "paused", key, r.INSTRUMENT_SEED, position=.125, seconds=3)
    assert actual == expected
    assert r.read(folder / "continuous/trajectory.json.gz") == r.read(folder / "paused/trajectory.json.gz")
    for field in ("region1", "travel_distance", "samples", "initial_core_hash", "final_core_hash",
                  "initial_whole_hash", "final_whole_hash", "begin_us", "planned_end_us", "life"):
        assert resumed[field] == reference[field], field
    r.save(work / "continuation-v2/apparatus.json", {"passed": True, "pause_at_us": 1200000,
        "entire_trajectory_identical": True, "complete_final_state_identical": True,
        "final_whole_hash": r.digest(actual)})
    print("Exact stage continuation passed")


if __name__ == "__main__":
    import study
    apparatus(study.DEFAULT_WORK)
