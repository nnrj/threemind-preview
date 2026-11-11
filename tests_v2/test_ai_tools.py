import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from lease_helpers import claim_as
from psycopg.types.json import Jsonb
from test_ai_providers import chat_response, create, get_call
from test_research_operations import advance, fixture

from threemind_lab import ai_evidence, ai_scheduler, ai_tools, research_plans
from threemind_lab.ai_tool_schema import LabAITools, ToolEdit, ToolRequest
from threemind_lab.ai_worker import AIWorker
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.worker import Worker


def client_for(database):
    return TestClient(
        create_app(Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),)), database)
    )


def configured(database, client):
    project, run, cp, image = fixture(database, client)
    settings = client.app.state.settings
    provider = create(database, settings, project)
    config = LabAITools.model_validate(
        {
            "environment": {"enabled": True, "automatic": False, "provider_id": str(provider["id"])},
            "interpreter": {"enabled": True, "periodic_enabled": False, "provider_id": str(provider["id"])},
            "assistant": {"enabled": True, "provider_id": str(provider["id"])},
        }
    )
    ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=config))
    return project, run, cp, image, config, provider


def ask(database, client, project, run, purpose, **options):
    body = ToolRequest(request_id=uuid4(), purpose=purpose, **options)
    call = ai_tools.request(database, client.app.state.settings, project, run, LOCAL_USER, body)
    return call, body


def worker_reply(database, client, text):
    return AIWorker(database, client.app.state.settings, transport=httpx.MockTransport(lambda _: chat_response(text)))


def test_environment_ordinary_bus_exactly_once_and_result_transaction_rollback(database, monkeypatch):
    with client_for(database) as client:
        project, run, _cp, image, _config, _provider = configured(database, client)
        call, request = ask(database, client, project, run, "environment")
        assert "snapshot" not in call["prompt"]["user"] and "nodes" not in call["prompt"]["user"]
        worker = worker_reply(database, client, "雨声")
        assert worker.once()
        done = get_call(database, project, call)
        assert done["result"]["application_status"] == "applied", done
        assert database.load_checkpoint(project, run)[1].digest == image.digest
        with database.tx(project) as db:
            envelope = db.execute(
                "SELECT * FROM input_envelopes WHERE run_id=%s AND source='ai-environment'", (run,)
            ).fetchone()
            assert envelope["source"] == "ai-environment" and envelope["payload"] == {"text": "雨声", "intensity": 0.7}
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (call["job_id"],))
        assert (
            ai_tools.request(database, client.app.state.settings, project, run, LOCAL_USER, request)["id"] == call["id"]
        )
        assert worker.once()
        with database.tx(project) as db:
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s AND source='ai-environment'", (run,)
                ).fetchone()["n"]
                == 1
            )
        advance(database, project, run, 1, 3700)
        assert Worker(database).once()
        with database.tx(project) as db:
            assert (
                db.execute("SELECT delivered_count FROM input_envelopes WHERE id=%s", (envelope["id"],)).fetchone()[
                    "delivered_count"
                ]
                > 0
            )
        assert database.load_checkpoint(project, run)[1].digest != image.digest
        second, _ = ask(database, client, project, run, "environment")
        original = ai_tools.submit

        def fail_after_input(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("injected after input write")

        monkeypatch.setattr(ai_tools, "submit", fail_after_input)
        assert worker.once()
        assert get_call(database, project, second)["result"]["application_status"] == "rejected"
        with database.tx(project) as db:
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s AND source='ai-environment'", (run,)
                ).fetchone()["n"]
                == 1
            )
        assert client.get(f"/api/v2/projects/{project}/runs/{run}/ai-tools/export").status_code == 200


def test_independent_tool_changes_cancel_only_affected_calls_and_check_again_before_application(database):
    with client_for(database) as client:
        project, run, _cp, image, config, _provider = configured(database, client)
        observation, _ = ask(database, client, project, run, "interpretation")
        environment, _ = ask(database, client, project, run, "environment")
        changed = config.model_copy(deep=True)
        changed.environment.intensity = 0.9
        ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=changed, expected_revision=1))
        assert not get_call(database, project, observation)["cancel_requested"]
        assert get_call(database, project, environment)["cancel_requested"]
        worker = worker_reply(database, client, "仅描述已记录状态，无法据此判定意识。")
        assert worker.once() and worker.once()
        assert get_call(database, project, observation)["result"]["application_status"] == "recorded"
        assert get_call(database, project, environment)["status"] == "cancelled"
        call, _ = ask(database, client, project, run, "environment")
        job = claim_as(database, "effect-race", queue="ai")
        assert job["params"]["call_id"] == str(call["id"])
        assert worker.run(job)["status"] == "completed"
        changed.environment.enabled = False
        ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=changed, expected_revision=2))
        result = ai_tools.apply_completed(database, job)
        assert result["application_status"] == "rejected"
        assert database.load_checkpoint(project, run)[1].digest == image.digest
        with database.tx(project) as db:
            assert not db.execute("SELECT * FROM input_envelopes WHERE run_id=%s", (run,)).fetchall()


@pytest.mark.parametrize("complete_raw", [False, True])
def test_snapshot_revision_boundary_active_selection_and_analysis_source_validation(database, complete_raw):
    with client_for(database) as client:
        project, run, first, image, config, _provider = configured(database, client)
        # Synthetic readout records test the observer boundary; no scientific
        # conclusions are drawn from these fixtures.
        payload = {
            "activity_nodes": [
                {"id": 1, "activation": 0.2},
                {"id": 2, "activation": 0.8},
                {"id": 3, "activation": 0.01},
            ],
            "source_node_count": 3,
            "structure": {
                "edges": [{"source": 1, "target": 2, "weight": 0.5}],
                "state_signature": "fixture",
                "recurrence_notice": True,
            },
        }
        if complete_raw:
            payload["raw_nodes"] = payload["activity_nodes"] + [{"id": 4, "activation": 0.4}]
            payload["raw_observation"] = {"complete": True, "node_count": 4, "scope": "all-source-nodes"}
            payload["source_node_count"] = 4
        second = database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=1,
            status="paused",
            context={"protocol": database.get_run(project, run)["spec"], "end_us": "100000"},
            observations=[{"time_us": "0", "sequence": 0, "activation": 1.0}],
            events=[{"key": "synthetic-structure", "time_us": "0", "kind": "structural_readout", "payload": payload}],
        )
        with database.tx(project) as db:
            old = ai_evidence.snapshot(db, run, first["id"], config=config.interpreter)
            current = ai_evidence.snapshot(db, run, second["id"], config=config.interpreter)
            periodic = ai_evidence.snapshot(db, run, second["id"], config=config.interpreter, trigger="periodic")
        assert old["readouts"] == [] and old["metric_samples"] == []
        assert len(current["metric_samples"]) == 1
        assert [row["id"] for row in current["readouts"][0]["active_nodes"]] == ([2, 4, 1] if complete_raw else [2, 1])
        selection = current["readouts"][0]["selection"]
        assert selection["unfiltered_source_available"] is complete_raw
        assert selection["node_source"] == ("raw_nodes" if complete_raw else "activity_nodes")
        assert current["causal_attribution"].startswith("not-established")
        assert len(current["readouts"][0]["edges"]) == 1
        assert "active_nodes" not in periodic["readouts"][0]
        call, _ = ask(database, client, project, run, "analysis", checkpoint_id=second["id"])
        wrong = {"summary": "Unsupported", "observations": [{"text": "invented", "source_refs": ["readout:99999999"]}]}
        assert worker_reply(database, client, json.dumps(wrong)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "rejected"
        valid, _ = ask(database, client, project, run, "analysis", checkpoint_id=second["id"])
        answer = {
            "summary": "Evidence provided",
            "observations": [{"text": "有一条采样记录。", "source_refs": [current["source_refs"][1]]}],
        }
        assert worker_reply(database, client, json.dumps(answer)).once()
        result = get_call(database, project, valid)["result"]
        assert result["application_status"] == "recorded" and result["review_status"] == "unreviewed"
        assert database.load_checkpoint(project, run)[1].digest == image.digest


def plan_reply(mode="confirm"):
    return json.dumps(
        {
            "name": "AI proposed sequence",
            "rationale": "Compare a brief input with the fixed initial state.",
            "protocol": {
                "mode": mode,
                "steps": [
                    {"command": "stimulus.send", "parameters": {"text": "甲"}},
                    {"command": "runtime.wait", "parameters": {"duration_us": 3700}},
                    {"command": "observe.summary"},
                ],
            },
        }
    )


def test_ai_plan_validated_frozen_and_only_executes_registered_steps_after_confirmation(database):
    with client_for(database) as client:
        project, run, _cp, image, _config, _provider = configured(database, client)
        wrong, _ = ask(database, client, project, run, "research_plan", objective="test")
        assert worker_reply(database, client, '{"name":"x","protocol":{"steps":[{"command":"shell"}]}}').once()
        assert get_call(database, project, wrong)["result"]["application_status"] == "rejected"
        call, _ = ask(database, client, project, run, "research_plan", objective="Compare sequence", mode="confirm")
        worker = worker_reply(database, client, plan_reply())
        assert worker.once()
        result = get_call(database, project, call)["result"]
        assert result["application_status"] == "applied", result
        assert database.load_checkpoint(project, run)[1].digest == image.digest
        with database.tx(project) as db:
            plan = research_plans.get(db, run, result["plan_id"])
            assert plan["status"] == "ready" and plan["origin"] == "ai" and plan["ai_call_id"] == call["id"]
            assert not db.execute("SELECT * FROM jobs WHERE kind='research_plan'").fetchall()
        research_plans.control(
            database,
            project,
            run,
            plan["id"],
            LOCAL_USER,
            action="start",
            request_id=uuid4(),
            expected_step=0,
            expected_revision=1,
        )
        assert Worker(database).once()
        with database.tx(project) as db:
            assert research_plans.get(db, run, plan["id"])["status"] == "completed"
            envelope = db.execute("SELECT * FROM input_envelopes WHERE source='ai-debug'").fetchone()
            assert envelope["delivered_count"] > 0
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (call["job_id"],))
        assert worker.once()
        assert database.get_run(project, run)["time_us"] == "3700"


def test_explicit_automatic_plan_only_on_fork_and_changed_command_boundary_rejected(database):
    with client_for(database) as client:
        project, run, _cp, _image, config, _provider = configured(database, client)
        with pytest.raises(Conflict, match="受限自动"):
            ask(database, client, project, run, "research_plan", objective="test", mode="automatic")
        call, _ = ask(database, client, project, run, "research_plan", objective="test")
        from threemind_lab.inputs import submit

        submit(
            database,
            project,
            run,
            {"id": LOCAL_USER},
            adapter_id="text-sensor",
            payload={"text": "outside"},
            request_id=uuid4(),
        )
        assert worker_reply(database, client, plan_reply()).once()
        assert get_call(database, project, call)["result"]["application_status"] == "rejected"
        fork = client.post(
            f"/api/v2/projects/{project}/runs/{run}/forks", json={"name": "AI sandbox", "paused": True}
        ).json()
        config.assistant.allow_automatic = True
        ai_tools.save(database, project, fork["id"], LOCAL_USER, ToolEdit(config=config))
        automatic, _ = ask(
            database, client, project, fork["id"], "research_plan", objective="bounded sequence", mode="automatic"
        )
        assert worker_reply(database, client, plan_reply("automatic")).once()
        result = get_call(database, project, automatic)["result"]
        assert result["application_status"] == "applied", result
        assert Worker(database).once()
        with database.tx(project) as db:
            assert research_plans.get(db, fork["id"], result["plan_id"])["status"] == "completed"


def test_durable_cadence_trigger_queue_dedup_and_no_model_time_mutation(database):
    with client_for(database) as client:
        project, run, _cp, image, config, _provider = configured(database, client)
        config.environment.automatic = True
        config.environment.random_frequency = False
        config.environment.frequency_s = 1.0
        config.interpreter.periodic_enabled = False
        config.interpreter.on_repeatable_structure = True
        config.interpreter.deduplicate_readouts = True
        ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=config, expected_revision=1))
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        now = datetime.now(UTC) + timedelta(seconds=2)
        ai_scheduler.process(database, client.app.state.settings, project, run, now=now)
        ai_scheduler.process(database, client.app.state.settings, project, run, now=now)
        with database.tx(project) as db:
            calls = db.execute("SELECT * FROM ai_calls WHERE run_id=%s AND purpose='environment'", (run,)).fetchall()
        assert len(calls) == 1 and database.load_checkpoint(project, run)[1].digest == image.digest
        assert worker_reply(database, client, "风声").once()
        # A pure trigger record is used to test queue selection and identity.
        for i in range(2):
            with database.tx(project) as db:
                db.execute(
                    "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) VALUES(%s,%s,%s,0,'structural_readout',%s,1)",
                    (
                        project,
                        run,
                        f"fixture-recurrence-{i}",
                        Jsonb(
                            {"activity_nodes": [], "structure": {"state_signature": "same", "recurrence_notice": True}}
                        ),
                    ),
                )
            ai_scheduler.process(database, client.app.state.settings, project, run)
            if i == 0:
                assert worker_reply(database, client, "重复结构仅表示记录中的状态复现。").once()
        with database.tx(project) as db:
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM ai_calls WHERE run_id=%s AND purpose='interpretation'", (run,)
                ).fetchone()["n"]
                == 1
            )
            state = db.execute("SELECT state FROM ai_tool_schedules WHERE run_id=%s", (run,)).fetchone()["state"]
            assert state["interpreter"]["deduplicated"] == 1
        assert database.load_checkpoint(project, run)[1].digest == image.digest
        simulated = config.environment.model_copy(update={"cadence_clock": "simulation"})
        state = {"next_sim_us": "5000000"}
        assert not ai_scheduler.due(state, simulated, 4999999, now)
        assert ai_scheduler.due(state, simulated, 5000000, now)


def test_completed_response_cancel_before_apply_and_human_revision_preserves_ai_source(database):
    with client_for(database) as client:
        project, run, _cp, _image, _config, _provider = configured(database, client)
        call, _ = ask(database, client, project, run, "environment")
        job = claim_as(database, "completed-cancellation", queue="ai")
        worker = worker_reply(database, client, "cancelled before admission")
        assert worker.run(job)["status"] == "completed"
        url = f"/api/v2/projects/{project}/ai/calls/{call['id']}"
        assert client.get(url + "/status").json()["job_status"] == "leased"
        assert client.post(url + "/cancel").json()["cancel_requested"]
        assert ai_tools.apply_completed(database, job)["application_status"] == "rejected"
        database.finish(job, result={})
        with database.tx(project) as db:
            assert not db.execute("SELECT id FROM input_envelopes WHERE run_id=%s", (run,)).fetchall()
        stale, _ = ask(database, client, project, run, "environment")
        job = claim_as(database, "off-then-on", queue="ai")
        assert worker.run(job)["status"] == "completed"
        disabled = _config.model_copy(deep=True)
        disabled.environment.enabled = False
        ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=disabled, expected_revision=1))
        ai_tools.save(database, project, run, LOCAL_USER, ToolEdit(config=_config, expected_revision=2))
        assert get_call(database, project, stale)["cancel_requested"]
        assert ai_tools.apply_completed(database, job)["application_status"] == "rejected"
        database.finish(job, result={})
        proposal, _ = ask(database, client, project, run, "research_plan", objective="test")
        assert worker_reply(database, client, plan_reply()).once()
        original = get_call(database, project, proposal)["result"]["plan_id"]
        body = {
            "name": "Human edited AI proposal",
            "derived_from": original,
            "expected_revision": 1,
            "request_id": str(uuid4()),
            "protocol": {"steps": [{"command": "observe.summary"}]},
        }
        endpoint = f"/api/v2/projects/{project}/runs/{run}/research/plans"
        saved = client.post(endpoint, json=body)
        assert saved.status_code == 201, saved.text
        assert saved.json()["ai_call_id"] == str(proposal["id"])
        assert saved.json()["derived_from"] == original and saved.json()["origin"] == "ai"
        assert client.post(endpoint, json=body).json()["id"] == saved.json()["id"]
        with database.tx(project) as db:
            assert research_plans.get(db, run, original)["protocol"]["steps"][0]["command"] == "stimulus.send"


def test_manual_trigger_background_filter_and_metrics_dedup_identity(database):
    with client_for(database) as client:
        project, run, _cp, image, config, _provider = configured(database, client)
        config.interpreter.on_manual_stimulus = True
        with database.tx(project) as db:
            for name, kind, payload in (
                ("automatic", "temporal_readout", {"source": "ai-environment"}),
                ("background", "structural_readout", {"activity_nodes": [{"id": 1, "activation": 0.3}]}),
                ("manual", "temporal_readout", {"source": "manual-text"}),
            ):
                db.execute(
                    "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) VALUES(%s,%s,%s,0,%s,%s,1)",
                    (project, run, name, kind, Jsonb(payload)),
                )
            db.execute("SET CONSTRAINTS conversation_readout IMMEDIATE")
            found, _ = ai_scheduler.next_trigger(db, run, 0, config.interpreter)
            assert found["trigger"] == "manual_stimulus"
            config.interpreter.listen_background_active_nodes = True
            background, _ = ai_scheduler.next_trigger(db, run, 0, config.interpreter)
            assert background["trigger"] == "background_active_nodes"
            first = ai_evidence.snapshot(db, run, config=config.interpreter)
            db.execute(
                "INSERT INTO observations(project_id,run_id,time_us,sequence,metrics,commit_revision) VALUES(%s,%s,0,0,%s,1)",
                (project, run, Jsonb({"activation": 0.3})),
            )
            second = ai_evidence.snapshot(db, run, config=config.interpreter)
            assert first["readout_signature"] != second["readout_signature"]
        assert database.load_checkpoint(project, run)[1].digest == image.digest


def test_tool_api_project_boundaries_and_actor_revocation_before_result(database):
    with client_for(database) as client:
        project, run, _cp, image, config, _provider = configured(database, client)
        other = database.create_project({"id": LOCAL_USER}, "Other project")["id"]
        endpoint = f"/api/v2/projects/{project}/runs/{run}/ai-tools"
        assert client.get(f"/api/v2/projects/{other}/runs/{run}/ai-tools").status_code == 404
        invalid = config.model_dump(mode="json")
        invalid["interpreter"]["activation_min"] = 2.0
        assert client.post(endpoint + "/validate", json=invalid).status_code == 422
        call, _ = ask(database, client, project, run, "interpretation")
        job = claim_as(database, "role-revoked", queue="ai")
        assert worker_reply(database, client, "returned").run(job)["status"] == "completed"
        with database.tx(project) as db:
            # The local identity is now a real superadministrator. Revoke its
            # platform role as well, rather than expecting membership to limit root.
            db.execute("UPDATE platform_user_roles SET role_id='00000000-0000-4000-8000-000000000103' WHERE user_id=%s", (LOCAL_USER,))
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
        assert client.get(endpoint).status_code == 200
        assert (
            client.put(endpoint, json={"config": config.model_dump(mode="json"), "expected_revision": 1}).status_code
            == 403
        )
        assert (
            client.post(
                endpoint + "/requests", json={"request_id": str(uuid4()), "purpose": "interpretation"}
            ).status_code
            == 403
        )
        assert ai_tools.apply_completed(database, job)["application_status"] == "rejected"
        assert database.load_checkpoint(project, run)[1].digest == image.digest
        assert get_call(database, project, call)["response_text"] == "returned"
