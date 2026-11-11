import copy
import threading

import pytest

from threemind_core import Engine, StateImage, Stimulus
from threemind_lab.checkpoints import CheckpointWriter, apply_delta, encode
from threemind_lab.database import LOCAL_USER, Conflict


def populated():
    engine = Engine()
    engine.inject(Stimulus(0, tuple((i, 0.5) for i in range(12))))
    engine.advance_to(0)
    return engine.capture_state()


def test_delta_preserves_float_bits_and_future_events():
    image = populated()
    state = image.to_dict()
    changed = copy.deepcopy(state)
    changed["nodes"][0]["inhibition"] = -0.0
    changed["nodes"][1]["activation"] = 0.012345678901234567
    changed["edges"].reverse()  # Valid imported tables need not arrive in key order.
    changed["queue"].append(
        {
            "id": 999,
            "kind": "stimulus",
            "time_us": "12345678901234567890",
            "payload": {"time_us": "12345678901234567890", "channels": [[88, 0.3]], "intensity": 1.0},
        }
    )
    changed["next_event"] = 999
    expected = StateImage.from_dict(changed)
    raw, kind, depth, patch = encode(changed, expected.digest, ({"state_hash": image.digest}, state))
    assert (kind, depth) == ("row-delta/1", 1)
    assert len(patch["nodes"]["upsert"]) == 2
    assert apply_delta(raw, image).digest == expected.digest
    with pytest.raises(ValueError, match="base checksum"):
        apply_delta(raw, Engine().capture_state())
    with pytest.raises(ValueError, match="incomplete"):
        apply_delta(raw[:-8], image)


def test_delta_lineage_projection_removals_anchor_and_corruption(database):
    project = database.create_project({"id": LOCAL_USER}, "Delta recovery")
    run = database.create_run(project["id"], "Incremental", {})
    image = populated()
    cp = database.save_checkpoint(project["id"], run["id"], image, expected_revision=0)
    original = cp
    for revision in range(1, 11):
        before = image.to_dict()
        state = copy.deepcopy(before)
        state["nodes"][0]["activation"] = revision / 20
        state["edges"] = state["edges"][1:]
        image = StateImage.from_dict(state)
        cp = database.save_checkpoint(
            project["id"], run["id"], image, expected_revision=revision, previous=(cp, before)
        )
        assert cp["storage_format"] == ("tmind/2" if revision == 9 else "row-delta/1")
        assert database.load_checkpoint(project["id"], run["id"])[1].digest == image.digest
        assert len(database.query_graph(project["id"], run["id"], table="edges", limit=1000)["rows"]) == len(
            state["edges"]
        )
    assert database.load_checkpoint(project["id"], run["id"], original["id"])[1].digest == populated().digest
    with pytest.raises(Conflict, match="base differs"):
        database.save_checkpoint(project["id"], run["id"], image, expected_revision=11, previous=(original, before))
    with database.tx(project["id"]) as db:
        db.execute("UPDATE state_chunks SET body=%s WHERE checkpoint_id=%s", (b"broken", cp["id"]))
    with pytest.raises(ValueError, match="chunk checksum"):
        database.load_checkpoint(project["id"], run["id"])


def test_writer_is_bounded_ordered_and_propagates_failure():
    entered, release = threading.Event(), threading.Event()
    calls = []

    class SlowDatabase:
        def save_checkpoint(self, project, run, image, **kwargs):
            entered.set()
            assert release.wait(5)
            calls.append((kwargs["expected_revision"], image.digest))
            return {"revision": kwargs["expected_revision"] + 1, "state_hash": image.digest}

    engine = Engine()
    first = engine.capture_state()
    with CheckpointWriter(SlowDatabase(), "p", "r", 0) as writer:
        writer.submit(first)
        assert entered.wait(5)
        engine.inject(Stimulus(0, ((1, 0.8),)))
        engine.advance_to(10000)  # Simulation can advance while the writer waits.
        assert first.digest != engine.capture_state().digest
        assert writer.revision == 0
        release.set()
        writer.submit(engine.capture_state())
        writer.drain()
        assert writer.revision == 2
    assert calls == [(0, first.digest), (1, engine.capture_state().digest)]

    class FailingDatabase:
        def save_checkpoint(self, *args, **kwargs):
            raise Conflict("expired generation")

    with (
        pytest.raises(Conflict, match="expired generation"),
        CheckpointWriter(FailingDatabase(), "p", "r", 0) as writer,
    ):
        writer.submit(first)
        writer.drain()
    assert writer.revision == 0
