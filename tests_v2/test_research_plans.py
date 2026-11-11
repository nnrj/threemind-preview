import json
from uuid import uuid4

import pytest
from test_api import client_for
from test_research_operations import fixture

from threemind_lab import research_plans
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.inputs import submit
from threemind_lab.research_commands import ResearchProtocol, template
from threemind_lab.worker import Worker


def step(command, **parameters):
    return {"command": command, "parameters": parameters}


def new_plan(database, project, run, steps, mode="confirm"):
    return research_plans.create(
        database,
        project,
        run,
        LOCAL_USER,
        name="Controlled experiment",
        protocol={"steps": steps, "mode": mode},
        request_id=uuid4(),
        expected_revision=1,
    )


def start(database, project, run, plan, request_id=None):
    return research_plans.control(
        database,
        project,
        run,
        plan["id"],
        LOCAL_USER,
        action="start",
        request_id=request_id or uuid4(),
        expected_step=plan["next_step"],
        expected_revision=plan["expected_revision"],
    )


def test_command_registry_strict_limits_templates():
    for name in ("free", "repeat", "association", "forgetting", "order"):
        value = ResearchProtocol.model_validate(template(name))
        assert value.totals()["steps"] == len(value.steps)
    for bad in (
        step("shell", text="anything"),
        step("runtime.wait", duration_us="10"),
        step("runtime.wait", duration_us=True),
        step("stimulus.send", text=" "),
        step("observe.graph", url="http://unknown"),
        step("runtime.resume"),
        step("stimulus.send", text="a", intensity=float("nan")),
    ):
        with pytest.raises(ValueError):
            ResearchProtocol.model_validate({"steps": [bad]})
    with pytest.raises(ValueError, match="刺激数"):
        ResearchProtocol.model_validate({"limits": {"max_stimuli": 0}, "steps": [step("stimulus.send", text="x")]})


def test_single_worker_plan_real_input_receipts_retry_and_subject_lock(database):
    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        steps = [
            step("observe.summary"),
            step("stimulus.send", text="A"),
            step("runtime.wait", duration_us=3700),
            step("history.tail", limit=4),
            step("snapshot.capture", label="First result"),
            step("experiment.note", text="Human note"),
        ]
        plan = new_plan(database, project, run, steps)
        request_id = uuid4()
        control = start(database, project, run, plan, request_id)
        assert start(database, project, run, plan, request_id)["control"]["id"] == control["control"]["id"]
        with pytest.raises(Conflict, match="受控"):
            submit(
                database,
                project,
                run,
                {"id": LOCAL_USER},
                adapter_id="text-sensor",
                payload={"text": "outside"},
                request_id=uuid4(),
            )
        with pytest.raises(Conflict, match="受控"):
            database.command(project, run, "resume", {})
        worker = Worker(database, max_active=1)
        assert worker.once()
        with database.tx(project) as db:
            done = research_plans.get(db, run, plan["id"])
            operations = db.execute(
                "SELECT * FROM research_operations WHERE plan_id=%s AND plan_step IS NOT NULL ORDER BY plan_step",
                (plan["id"],),
            ).fetchall()
            carriers = db.execute(
                "SELECT * FROM input_envelopes WHERE run_id=%s AND source='manual-text'", (run,)
            ).fetchall()
        assert done["status"] == "completed", done["error"]
        assert len(operations) == len(steps) and len(carriers) == 1
        assert carriers[0]["delivered_count"] == 1
        assert operations[1]["result"]["envelope_id"] == str(carriers[0]["id"])
        assert operations[3]["result"]["operations"]
        assert database.get_run(project, run)["time_us"] == "3700"
        revision = database.get_run(project, run)["revision"]
        # Confirmation lost after ALL steps, and process retry after receipt:
        # neither may create a second carrier or advance the completed plan.
        assert start(database, project, run, plan, request_id)["control"]["id"] == control["control"]["id"]
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET status='pending',attempts=0 WHERE id=%s", (done["job_id"],))
        assert worker.once()
        assert database.get_run(project, run)["revision"] == revision
        export = client.get(f"/api/v2/projects/{project}/runs/{run}/research/plans/{plan['id']}/export")
        lines = [json.loads(line) for line in export.text.splitlines()]
        assert lines[0]["value"]["protocol_hash"] == plan["protocol_hash"] and len(lines) == len(steps) + 2


def test_manual_plan_pause_resume_and_changed_boundary_refusal(database):
    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        plan = new_plan(
            database,
            project,
            run,
            [step("runtime.wait", duration_us=3700), step("runtime.wait", duration_us=6300)],
            mode="manual",
        )
        start(database, project, run, plan)
        worker = Worker(database, max_active=1)
        assert worker.once()
        with database.tx(project) as db:
            paused = research_plans.get(db, run, plan["id"])
        assert paused["status"] == "paused" and paused["next_step"] == 1
        assert database.get_run(project, run)["time_us"] == "3700"
        submit(
            database,
            project,
            run,
            {"id": LOCAL_USER},
            adapter_id="text-sensor",
            payload={"text": "outside"},
            request_id=uuid4(),
        )
        with pytest.raises(Conflict, match="边界"):
            start(database, project, run, paused)


def test_interrupted_wait_continues_original_absolute_target(database, monkeypatch):
    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        plan = new_plan(database, project, run, [step("runtime.wait", duration_us=57000), step("observe.summary")])
        start(database, project, run, plan)
        worker = Worker(database)
        original_save = database.save_checkpoint

        def interrupt(*args, **kwargs):
            saved = original_save(*args, **kwargs)
            if kwargs.get("status") == "running" and int(saved["time_us"]) >= 10000:
                worker.stopping = True
            return saved

        monkeypatch.setattr(database, "save_checkpoint", interrupt)
        assert worker.once()
        with database.tx(project) as db:
            paused = research_plans.get(db, run, plan["id"])
        assert paused["status"] == "paused" and paused["next_step"] == 0
        assert paused["wait_target_us"] == "57000" and paused["step_attempt"] == 1
        assert 0 < int(database.get_run(project, run)["time_us"]) < 57000
        monkeypatch.setattr(database, "save_checkpoint", original_save)
        worker.stopping = False
        start(database, project, run, paused)
        assert worker.once()
        assert database.get_run(project, run)["time_us"] == "57000"
        with database.tx(project) as db:
            done = research_plans.get(db, run, plan["id"])
            attempts = db.execute(
                "SELECT status,parameters FROM research_operations WHERE plan_id=%s AND plan_step=0 ORDER BY plan_attempt",
                (plan["id"],),
            ).fetchall()
        assert done["status"] == "completed", done["error"]
        assert [row["status"] for row in attempts] == ["interrupted", "completed"]
        assert {row["parameters"]["target_us"] for row in attempts} == {"57000"}


def test_plan_process_loss_after_step_commit_reuses_exact_receipt(database, monkeypatch):
    class ProcessGone(BaseException):
        pass

    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        plan = new_plan(
            database, project, run, [step("runtime.wait", duration_us=3700), step("runtime.wait", duration_us=6300)]
        )
        started = start(database, project, run, plan)
        worker = Worker(database, max_active=1)
        original_run = worker.run

        def lost(job):
            original_run(job)
            raise ProcessGone()

        monkeypatch.setattr(worker, "run", lost)
        with pytest.raises(ProcessGone):
            worker.once()
        assert database.get_run(project, run)["time_us"] == "3700"
        with database.tx(project) as db:
            assert research_plans.get(db, run, plan["id"])["next_step"] == 0
            db.execute(
                "UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (started["plan"]["job_id"],)
            )
        assert Worker(database, max_active=1).once()
        assert database.get_run(project, run)["time_us"] == "10000"
        with database.tx(project) as db:
            assert research_plans.get(db, run, plan["id"])["status"] == "completed"
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM research_operations WHERE plan_id=%s AND plan_step IS NOT NULL",
                    (plan["id"],),
                ).fetchone()["n"]
                == 2
            )


def test_boundary_pause_resume_and_business_refusal_finish_without_lease_loop(database):
    with client_for(database) as client:
        project, run, cp, _image = fixture(database, client)
        plan = new_plan(
            database,
            project,
            run,
            [
                step("runtime.wait", duration_us=1000),
                step("runtime.pause"),
                step("snapshot.capture", label="After resume"),
            ],
        )
        start(database, project, run, plan)
        worker = Worker(database, max_active=1)
        assert worker.once()
        with database.tx(project) as db:
            paused = research_plans.get(db, run, plan["id"])
        assert paused["status"] == "paused" and paused["next_step"] == 2
        start(database, project, run, paused)
        assert worker.once()
        with database.tx(project) as db:
            assert research_plans.get(db, run, plan["id"])["status"] == "completed"
        fork = client.post(
            f"/api/v2/projects/{project}/runs/{run}/forks",
            json={"name": "No new background", "checkpoint_id": str(cp["id"]), "paused": True, "background": "suspend"},
        ).json()
        assert fork["state_hash"] == cp["state_hash"] and fork["spec"]["source_policies"]["background_enabled"] is False
        refused = new_plan(database, project, fork["id"], [step("stimulus.send", text="After cancellation")])
        started = start(database, project, fork["id"], refused)
        with pytest.raises(Conflict):
            database.command(project, fork["id"], "cancel", {})
        # Independently cancelling a controlled subject is forbidden. Inject a
        # host-side terminal boundary to test the admitted job's refusal path.
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='cancelled' WHERE id=%s", (fork["id"],))
        assert worker.once()
        with database.tx(project) as db:
            failed = research_plans.get(db, fork["id"], refused["id"])
            job = db.execute("SELECT status,attempts FROM jobs WHERE id=%s", (started["plan"]["job_id"],)).fetchone()
        assert failed["status"] == "failed" and "计划步骤被拒绝" in failed["error"]
        assert job["status"] == "failed" and job["attempts"] == 1


def test_plan_api_freezing_permissions_and_atomic_stimulus_receipt(database, monkeypatch):
    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        url = f"/api/v2/projects/{project}/runs/{run}/research"
        command_catalog = client.get(url + "/commands").json()
        assert len(command_catalog["commands"]) == 11
        assert any(c["id"] == "stimulus.frames" for c in command_catalog["commands"])
        assert (
            client.post(
                url + "/plans/validate", json={"steps": [step("observe.graph", url="unregistered")]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                url + "/plans",
                json={
                    "name": "automatic original",
                    "request_id": str(uuid4()),
                    "expected_revision": 1,
                    "protocol": {"mode": "automatic", "steps": [step("observe.summary")]},
                },
            ).status_code
            == 422
        )
        plan = new_plan(database, project, run, [step("stimulus.send", text="Cannot partially commit")])
        state = client.get(url + f"/plans/{plan['id']}/status").json()
        assert state["status"] == "ready" and "protocol" not in state
        start(database, project, run, plan)
        original = research_plans.save_receipt

        def fail(*args, **kwargs):
            raise RuntimeError("injected receipt rollback")

        monkeypatch.setattr(research_plans, "save_receipt", fail)
        assert Worker(database).once()
        monkeypatch.setattr(research_plans, "save_receipt", original)
        with database.tx(project) as db:
            failed = research_plans.get(db, run, plan["id"])
            assert db.execute("SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s", (run,)).fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM commands WHERE run_id=%s", (run,)).fetchone()["n"] == 0
        assert failed["status"] == "failed" and "receipt rollback" in failed["error"]
        other = client.post("/api/v2/projects", json={"name": "Other"}).json()["id"]
        assert client.get(url.replace(project, other) + f"/plans/{plan['id']}").status_code == 404
        # Already admitted jobs recheck the actor at execution time.
        plan2 = new_plan(database, project, run, [step("experiment.note", text="Denied after demotion")])
        start(database, project, run, plan2)
        with database.tx(project) as db:
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
            # Project membership cannot demote the platform superadministrator.
            # Revoke that platform role too, so this is genuinely a normal user.
            db.execute("DELETE FROM platform_user_roles WHERE user_id=%s", (LOCAL_USER,))
            db.execute(
                "INSERT INTO platform_user_roles(user_id,role_id) SELECT %s,id FROM platform_roles WHERE key='user'",
                (LOCAL_USER,),
            )
        assert Worker(database).once()
        with database.tx(project) as db:
            assert research_plans.get(db, run, plan2["id"])["status"] == "failed"
        assert client.get(url + "/plans").status_code == 200
        assert (
            client.post(
                url + "/plans",
                json={
                    "name": "denied",
                    "request_id": str(uuid4()),
                    "expected_revision": 1,
                    "protocol": {"steps": [step("observe.summary")]},
                },
            ).status_code
            == 403
        )
