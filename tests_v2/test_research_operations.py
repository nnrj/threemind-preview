from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Stimulus
from threemind_lab import auth, research_operations
from threemind_lab.configuration import default_spec
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.worker import Worker
from threemind_runtime import create_engine


def fixture(database, client, *, kernel_id=None):
    project = client.post("/api/v2/projects", json={"name": "Manual time research"}).json()["id"]
    spec = default_spec(kernel_id) | {
        "environment": "manual",
        "clock": "unbounded",
        "duration_s": 0.1,
        "checkpoint_us": 10000,
        "sample_us": 10000,
    }
    run = database.create_run(project, "Exact paused subject", spec)
    engine = create_engine(kernel_id=kernel_id)
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.5))))
    engine.inject(Stimulus(3500, ((2, 0.8), (3, 0.4))))
    image = engine.capture_state()
    cp = database.save_checkpoint(
        project,
        run["id"],
        image,
        expected_revision=0,
        status="paused",
        context={
            "protocol": spec,
            "start_us": "0",
            "end_us": "100000",
            "replay_loaded": True,
        },
    )
    return project, run["id"], cp, image


def advance(database, project, run, revision, duration_us=3700, request_id=None):
    return research_operations.submit_advance(
        database,
        project,
        run,
        LOCAL_USER,
        request_id=request_id or uuid4(),
        expected_revision=revision,
        duration_us=duration_us,
    )


def test_manual_advance_absolute_stop_retry_and_continuation(database):
    with client_for(database) as client:
        project, run, _cp, image = fixture(database, client)
        request_id = uuid4()
        admitted = advance(database, project, run, 1, request_id=request_id)
        assert admitted["parameters"]["target_us"] == "3700"
        assert advance(database, project, run, 1, request_id=request_id)["id"] == admitted["id"]
        with pytest.raises(Conflict):
            advance(database, project, run, 1, duration_us=6000, request_id=request_id)
        worker = Worker(database)
        assert worker.once()
        row = database.get_run(project, run)
        assert row["status"] == "paused" and row["time_us"] == "3700"
        result = advance(database, project, run, 1, request_id=request_id)
        assert result["status"] == "completed" and result["result"]["target_reached"]
        first, _ = database.load_checkpoint(project, run)
        assert first["context"]["end_us"] == "100000"
        assert first["context"]["readouts"]  # Timed windows remain recoverable across the pause.
        with pytest.raises(Conflict):
            advance(database, project, run, 1)
        next_step = advance(database, project, run, row["revision"], duration_us=6300)
        assert next_step["parameters"]["target_us"] == "10000"
        assert worker.once()
        _, stepped = database.load_checkpoint(project, run)
        reference = create_engine(state=image)
        reference.advance_to(10000)
        assert stepped.digest == reference.capture_state().digest
        # Crash after final state commit but before job acknowledgement: retrying
        # the original job cannot advance another 3.7 ms or create a new checkpoint.
        original_revision = database.get_run(project, run)["revision"]
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET status='pending',attempts=0 WHERE id=%s", (admitted["job_id"],))
        assert worker.once()
        assert database.get_run(project, run)["revision"] == original_revision


def test_manual_advance_pending_recovery_and_atomic_completion(database, monkeypatch):
    with client_for(database) as client:
        project, run, _cp, _image = fixture(database, client)
        operation = advance(database, project, run, 1, duration_us=57000)
        original = research_operations.finish_at_checkpoint

        def fail(*args, **kwargs):
            raise RuntimeError("injected research receipt failure")

        monkeypatch.setattr(research_operations, "finish_at_checkpoint", fail)
        worker = Worker(database)
        assert worker.once()
        with database.tx(project) as db:
            failed = db.execute("SELECT * FROM research_operations WHERE id=%s", (operation["id"],)).fetchone()
            events = db.execute("SELECT id FROM events WHERE run_id=%s AND kind='research_advance'", (run,)).fetchall()
        assert failed["status"] == "failed" and failed["result_checkpoint_id"] is None and events == []
        latest, _latest_image = database.load_checkpoint(project, run)
        assert int(latest["time_us"]) < 57000
        # Simulate a worker lease retry from its last acknowledged intermediate
        # state, retaining the admitted absolute target and request identity.
        monkeypatch.setattr(research_operations, "finish_at_checkpoint", original)
        with database.tx(project) as db:
            db.execute("UPDATE research_operations SET status='pending',error=NULL WHERE id=%s", (operation["id"],))
            db.execute("UPDATE jobs SET status='pending',attempts=0 WHERE id=%s", (operation["job_id"],))
            db.execute("UPDATE runs SET status='queued',error=NULL WHERE id=%s", (run,))
        assert worker.once()
        assert database.get_run(project, run)["time_us"] == "57000"
        with pytest.raises(ValueError, match="终点"):
            advance(database, project, run, database.get_run(project, run)["revision"], duration_us=100000)


def test_research_api_checkpoint_evidence_notes_roles_and_validation(database, monkeypatch):
    from psycopg.types.json import Jsonb

    with client_for(database) as client:
        project, run, cp, image = fixture(database, client)
        url = f"/api/v2/projects/{project}/runs/{run}/research/actions"
        cp2 = database.save_checkpoint(project, run, image, expected_revision=1, status="paused", context=cp["context"])
        with database.tx(project) as db:
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) VALUES(%s,%s,'later-output',0,'organ_output',%s,2)",
                (project, run, Jsonb({"voices": [], "image": {}})),
            )
        original_load = database.load_checkpoint

        def no_state_expansion(*args, **kwargs):
            raise AssertionError("annotations and output references must not expand the model")

        monkeypatch.setattr(database, "load_checkpoint", no_state_expansion)
        note = {
            "kind": "experiment.note",
            "request_id": str(uuid4()),
            "checkpoint_id": str(cp["id"]),
            "text": "<script>observer text</script>",
        }
        saved = client.post(url, json=note)
        assert saved.status_code == 200, saved.text
        assert saved.json()["parameters"]["text"] == note["text"]
        assert client.post(url, json=note).json()["id"] == saved.json()["id"]
        assert client.post(url, json=note | {"text": "changed"}).status_code == 409
        historical = client.post(
            url, json={"kind": "observe.output", "request_id": str(uuid4()), "checkpoint_id": str(cp["id"])}
        )
        assert historical.json()["result"]["events"] == []
        current = client.post(
            url, json={"kind": "observe.output", "request_id": str(uuid4()), "checkpoint_id": str(cp2["id"])}
        )
        assert {r["channel"] for r in current.json()["result"]["events"]} == {"voices", "image"}
        monkeypatch.setattr(database, "load_checkpoint", original_load)
        summary = client.post(url, json={"kind": "observe.summary", "request_id": str(uuid4())})
        assert summary.status_code == 200 and summary.json()["result"]["state_hash"] == image.digest
        assert database.get_run(project, run)["revision"] == 2
        rows = client.get(url + "?limit=2").json()
        assert len(rows["rows"]) == 2 and rows["more"]
        newer = client.post(url, json=note | {"request_id": str(uuid4()), "text": "New note after first page"})
        page_two = client.get(url + f"?limit=2&before={rows['next']}&ceiling={rows['ceiling']}").json()
        assert not ({r["id"] for r in rows["rows"]} & {r["id"] for r in page_two["rows"]})
        assert newer.json()["id"] not in {r["id"] for r in page_two["rows"]}
        exported = client.get(url.removesuffix("actions") + "export")
        assert exported.status_code == 200 and len(exported.text.splitlines()) == 5
        graph = client.get(url.removesuffix("research/actions") + f"graph?checkpoint_id={cp['id']}")
        assert graph.json()["state_hash"] == image.digest and graph.json()["checkpoint_id"] == str(cp["id"])
        paused_fork = client.post(
            url.removesuffix("research/actions") + "forks",
            json={
                "name": "Stopped sandbox",
                "checkpoint_id": str(cp["id"]),
                "paused": True,
            },
        )
        assert paused_fork.status_code == 201 and paused_fork.json()["status"] == "paused"
        assert paused_fork.json()["revision"] == 1 and paused_fork.json()["origin_checkpoint_id"] == str(cp["id"])
        with database.tx(project) as db:
            assert not db.execute("SELECT 1 FROM jobs WHERE run_id=%s", (paused_fork.json()["id"],)).fetchone()
        assert (
            client.post(
                url.removesuffix("research/actions") + "commands",
                json={
                    "kind": "intervention",
                    "payload": {"lesion": "false"},
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                url,
                json={
                    "kind": "runtime.advance",
                    "request_id": str(uuid4()),
                    "expected_revision": 2,
                    "duration_us": "5000",
                },
            ).status_code
            == 422
        )
        assert client.post(url, json={"kind": "unregistered", "request_id": str(uuid4())}).status_code == 422
        other = client.post("/api/v2/projects", json={"name": "Other operation project"}).json()["id"]
        assert client.get(url.replace(project, other)).status_code == 404
    viewer = auth.create_user(database, "operation-viewer", "isolated operation viewer password")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "operation-viewer", "password": "isolated operation viewer password"}
        )
        assert client.get(url).status_code == 200
        assert (
            client.post(
                url, json=note | {"request_id": str(uuid4())}, headers={"X-CSRF-Token": login.json()["csrf"]}
            ).status_code
            == 403
        )


def test_incremental_research_migration_uses_its_own_schema_and_grants(database):
    import psycopg

    from threemind_lab.database import MIGRATIONS, migrate

    # This fixture is a newly generated, isolated test database, never the
    # configured workstation. Reconstruct the version-15 upgrade boundary.
    with psycopg.connect(database.test_migration_url) as db:
        assert db.info.dbname.startswith("tm2_test_db_")
        from migration_helpers import remove_observer_schema

        remove_observer_schema(db)
        db.execute("DROP TRIGGER device_wiring_immutable ON tm2.device_bindings")
        db.execute("DROP FUNCTION tm2.preserve_device_wiring()")
        db.execute("ALTER TABLE tm2.device_bindings DROP COLUMN wiring_id")
        db.execute("ALTER TABLE tm2.report_source_requests DROP COLUMN ecology_id, DROP COLUMN ecology_checkpoint_id")
        db.execute("DROP FUNCTION tm2.required_job_features_v39(text,uuid,jsonb)")
        db.execute(
            "DROP TABLE tm2.ecology_events,tm2.ecology_checkpoint_members,tm2.ecology_members,tm2.ecology_checkpoints,tm2.ecology_campaigns"
        )
        db.execute("DROP FUNCTION tm2.preserve_ecology_record(),tm2.required_job_features_v38(text,uuid,jsonb)")
        db.execute("DROP TABLE tm2.world_versions,tm2.world_documents")
        db.execute("DROP FUNCTION tm2.required_job_features_v37(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.preserve_world_version(),tm2.required_job_features_v36(text,uuid,jsonb)")
        db.execute("ALTER TABLE tm2.report_source_requests DROP COLUMN evolution_id")
        db.execute(
            "DROP TABLE tm2.evolution_events,tm2.evolution_selections,tm2.evolution_members,tm2.evolution_campaigns"
        )
        db.execute("DROP FUNCTION tm2.required_job_features_v34(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.required_job_features_v35(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.preserve_evolution_record(),tm2.required_job_features_v33(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.required_job_features_v32(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.required_job_features_v31(text,uuid,jsonb)")
        db.execute("DROP TABLE tm2.development_sessions,tm2.innate_versions")
        db.execute("DROP FUNCTION tm2.preserve_development_record(),tm2.required_job_features_v30(text,uuid,jsonb)")
        db.execute("DROP TRIGGER immutable_shared_artifact ON tm2.artifacts")
        db.execute("DROP TRIGGER immutable_shared_chunks ON tm2.artifact_chunks")
        db.execute("DROP TABLE tm2.research_document_shares")
        db.execute("DROP FUNCTION tm2.preserve_research_share(),tm2.preserve_shared_artifact()")
        db.execute(
            "DROP TABLE tm2.research_generation_records,tm2.research_generation_sources,tm2.research_generations"
        )
        db.execute("DROP TABLE tm2.research_document_exports")
        db.execute(
            "DROP TABLE tm2.research_document_refs,tm2.research_document_sources,tm2.research_document_versions,tm2.research_documents,tm2.report_source_rows,tm2.report_sources,tm2.report_source_requests"
        )
        db.execute(
            "DROP FUNCTION tm2.preserve_research_evidence(),tm2.reject_completed_source_insert(),tm2.reject_partial_source_delete(),tm2.required_job_features_v24(text,uuid,jsonb)"
        )
        db.execute("DROP TABLE tm2.note_asset_refs,tm2.note_versions,tm2.notes,tm2.note_collections,tm2.note_assets")
        db.execute("DROP FUNCTION tm2.preserve_note_revision()")
        db.execute("DROP TABLE tm2.job_assignments")
        db.execute("DROP TRIGGER job_features ON tm2.jobs")
        db.execute("DROP TRIGGER run_job_features ON tm2.runs")
        db.execute(
            "DROP FUNCTION tm2.set_job_features(),tm2.refresh_run_job_features(),tm2.required_job_features(text,uuid,jsonb)"
        )
        db.execute("ALTER TABLE tm2.jobs DROP COLUMN required_features")
        db.execute("DROP INDEX tm2.jobs_project_recent")
        db.execute("DROP TABLE tm2.execution_limit_history,tm2.project_execution_limits,tm2.execution_limits")
        db.execute("DROP INDEX tm2.jobs_project_queue_active")
        db.execute("DROP TABLE tm2.state_captures")
        db.execute(
            "DROP FUNCTION tm2.notify_run_transition(),tm2.notify_recurrence(),tm2.notify_job_finished() CASCADE"
        )
        db.execute("DROP FUNCTION tm2.emit_notification(uuid,uuid,text,text,jsonb,boolean)")
        db.execute(
            "DROP TABLE tm2.notification_reads,tm2.notifications,tm2.notification_versions,tm2.notification_settings"
        )
        db.execute("DROP INDEX tm2.jobs_queue_claim")
        db.execute(
            "DROP TABLE tm2.ai_run_tools,tm2.ai_tool_versions,tm2.ai_tool_schedules,tm2.ai_call_checkpoints,"
            "tm2.research_operations,tm2.research_plans,tm2.ai_reservations,tm2.ai_calls,tm2.ai_provider_grants,tm2.ai_providers"
        )
        db.execute("ALTER TABLE tm2.observations DROP COLUMN commit_revision")
        db.execute("DROP INDEX tm2.input_frames_observation_labels,tm2.input_frames_label_keys")
        db.execute("ALTER TABLE tm2.audit DROP COLUMN details")
        db.execute("DELETE FROM tm2.schema_version WHERE version>=16")
    migrate(database.test_migration_url)
    with database.tx() as db:
        assert db.execute("SELECT max(version) AS version FROM schema_version").fetchone()["version"] == len(MIGRATIONS)
        assert db.execute("SELECT to_regclass('public.research_operations') AS relation").fetchone()["relation"] is None
        assert db.execute("SELECT * FROM research_operations").fetchall() == []
        assert db.execute("SELECT * FROM notifications").fetchall() == []
        assert db.execute("SELECT * FROM state_captures").fetchall() == []
        assert db.execute("SELECT * FROM research_document_shares").fetchall() == []
        assert db.execute("SELECT * FROM development_sessions").fetchall() == []
        assert db.execute("SELECT * FROM innate_versions").fetchall() == []
        assert db.execute("SELECT ai_call_id,ai_protocol_hash FROM world_versions").fetchall() == []
        assert db.execute("SELECT * FROM ecology_campaigns").fetchall() == []
