"""Exercise the 53-founder checkpoint in an isolated directory, including segment analysis."""

import hashlib
from pathlib import Path
import shutil
import sys
from tempfile import mkdtemp
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worldio
from execution import checked_metrics, encoded
from habitat import make_world
from outcomes import case_outcome
from paths import CONTROL, EXPECTED, SECOND, exclusive_json, sha


def qualify():
    work = Path(mkdtemp(prefix="checkpoint-test-", dir=CONTROL))
    initial = work / "initial.zip"
    original = EXPECTED / "evidence/cases/world-0-reference/initial.zip"
    shutil.copyfile(original, initial)
    restored = worldio.restore(initial)
    independently_created = make_world(0, 1)
    assert worldio.state_bytes(restored.capture()) == worldio.state_bytes(independently_created.capture())
    assert set(restored.engines) == set(independently_created.engines) and len(restored.engines) == 53
    for i, engine in independently_created.engines.items():
        assert engine.capture_state().payload == restored.engines[i].capture_state().payload
    with ZipFile(initial) as archive:
        import json
        saved = json.loads(archive.read("world.json"))["context"]
    assert encoded(restored.capture()) != encoded(saved)
    assert worldio.state_bytes(restored.capture()) == encoded(saved)
    compare_inputs = []
    compare_events = []

    def collect(row):
        compare_inputs.append(hashlib.sha256(encoded(row)).hexdigest())

    # A fresh reference takes the same 50 ticks without pausing.
    for _ in range(50):
        compare_events.append(independently_created.step(collect))
    ticks = []
    events = []
    for _ in range(50):
        events.append(restored.step(lambda row: ticks.append(hashlib.sha256(encoded(row)).hexdigest())))
    assert compare_inputs == ticks and len(ticks) == 50 and encoded(compare_events) == encoded(events)
    assert worldio.state_bytes(restored.capture()) == worldio.state_bytes(independently_created.capture())
    for i, engine in independently_created.engines.items():
        assert engine.capture_state().payload == restored.engines[i].capture_state().payload

    # Only workspace admission is replaced. Seal and reload two ordinary segments, then run the real analysis.
    class TestStorage:
        def guard(self, *args, **kwargs):
            return work

    replay = worldio.restore(initial)
    with patch.object(worldio, "pool", return_value=TestStorage()), patch.object(worldio, "guard"):
        worldio.segment(replay, work, work, 0, SECOND // 2)
        half = worldio.restore_end(work / "seg-0000.zip")
        worldio.segment(half, work, work, 1, SECOND)
    finished = worldio.restore_end(work / "seg-0001.zip")
    assert worldio.state_bytes(finished.capture()) == worldio.state_bytes(independently_created.capture())
    for i, engine in independently_created.engines.items():
        assert engine.capture_state().payload == finished.engines[i].capture_state().payload
    stats = checked_metrics(finished)
    exclusive_json(work / "result.json", dict(time_us=finished.time_us, extinct=False,
                                              members=stats["members"], totals=stats["totals"]))
    assert case_outcome(work)["seconds"] == 1
    checks = dict(initial_sha256=sha(initial), individual_cores=53, initial_internal_us=0,
                  uninterrupted_ticks=50, period_us=20000, same_inputs_actions_and_events=True,
                  same_uninterrupted_and_restored_world_and_cores=True, sealed_and_analyzed_segments=2)
    exclusive_json(CONTROL / "checkpoint-qualification.json", checks)
    return checks


if __name__ == "__main__":
    print(qualify())
