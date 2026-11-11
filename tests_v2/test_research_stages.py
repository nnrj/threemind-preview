from uuid import uuid4

import pytest
from test_api import client_for
from test_research_operations import fixture
from test_research_plans import start

from threemind_lab import research_plans
from threemind_lab.database import LOCAL_USER
from threemind_lab.inputs import digest
from threemind_lab.research_commands import ResearchProtocol, StageProtocol, parse_protocol
from threemind_lab.worker import Worker


def protocol(repeats=12):
    return StageProtocol(
        stages=[
            {
                "name": "Repeated anonymous input",
                "repeat": repeats,
                "steps": [
                    {
                        "command": "stimulus.frames",
                        "parameters": {
                            "frames": [{"time_us": "0", "channels": [[91, 0.8], [92, 0.4]], "intensity": 1.0}]
                        },
                    },
                    {"command": "runtime.wait", "parameters": {"duration_us": 1000}},
                ],
            },
            {"name": "Record", "steps": [{"command": "observe.summary", "parameters": {}}]},
        ]
    )


def test_compact_protocol_expands_counts_not_memory_and_preserves_v2_serialization():
    p = protocol(500)
    assert p.step_count == 1001 and p.totals()["stimuli"] == 500
    assert p.totals()["channels"] == 1000
    assert p.cursor_at(999)["repetition"] == 499
    assert p.cursor_at(1000)["name"] == "Record"
    assert p.cursor_at(1001)["completed"]
    assert p.step_at(998).command == "stimulus.frames"
    assert len(p.model_dump()["stages"]) == 2 and "steps" not in p.model_dump()
    old = {
        "schema_version": "threemind.research-plan/2",
        "mode": "confirm",
        "limits": {"max_steps": 100, "max_stimuli": 20, "max_text_chars": 20000, "max_wait_us": 60000000},
        "steps": [{"command": "runtime.wait", "parameters": {"duration_us": 123}}],
    }
    assert parse_protocol(old).model_dump() == old
    assert digest(parse_protocol(old).model_dump()) == digest(old)
    with pytest.raises(ValueError, match="预算"):
        StageProtocol.model_validate(protocol().model_dump() | {"limits": {"max_stimuli": 5}})
    with pytest.raises(ValueError, match="research-plan/3"):
        ResearchProtocol(steps=[protocol().step_at(0)])


def test_stage_resume_does_not_repeat_stimulation_or_time(database, monkeypatch):
    with client_for(database) as http:
        project, run, _, _ = fixture(database, http)
        frozen = protocol(12)
        plan = research_plans.create(
            database,
            project,
            run,
            LOCAL_USER,
            name="staged",
            protocol=frozen.model_dump(),
            request_id=uuid4(),
            expected_revision=1,
        )
        start(database, project, run, plan)
        worker = Worker(database)
        save = database.save_checkpoint
        calls = []

        def stop_after_first(*args, **kwargs):
            result = save(*args, **kwargs)
            calls.append(1)
            worker.stopping = True
            return result

        monkeypatch.setattr(database, "save_checkpoint", stop_after_first)
        assert worker.once()
        with database.tx(project) as db:
            paused = research_plans.get(db, run, plan["id"])
        assert paused["status"] == "paused"
        monkeypatch.setattr(database, "save_checkpoint", save)
        worker.stopping = False
        start(database, project, run, paused)
        assert worker.once()
        url = f"/api/v2/projects/{project}/runs/{run}/research/plans/{plan['id']}"
        result = http.get(url).json()
        assert result["status"] == "completed", result
        assert result["cursor"]["completed"]
        assert database.get_run(project, run)["time_us"] == "12000"
        with database.tx(project) as db:
            carriers = db.execute(
                "SELECT count(*) n,sum(delivered_count) delivered FROM input_envelopes "
                "WHERE run_id=%s AND adapter_id='anonymous-frames'",
                (run,),
            ).fetchone()
        assert carriers["n"] == 12 and int(carriers["delivered"]) == 12
        listing = http.get(url.rsplit("/", 1)[0]).json()
        assert listing["rows"][0]["step_count"] == 25
