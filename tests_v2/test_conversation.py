import csv
import io
import json
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from test_api import client_for

from threemind_lab import auth
from threemind_lab.worker import Worker


def fixture(client, name="conversation"):
    project = client.post("/api/v2/projects", json={"name": name}).json()["id"]
    run = client.post(
        f"/api/v2/projects/{project}/runs",
        json={"name": name, "spec": {"environment": "manual", "clock": "unbounded", "duration_s": 0.2}},
    ).json()["id"]
    return project, run, f"/api/v2/projects/{project}/runs/{run}"


def stimulus(db, project, run, source, text="carrier", id=None):
    id = id or uuid4()
    db.execute(
        "INSERT INTO input_envelopes(id,project_id,run_id,adapter_id,adapter_version,source,request_hash,"
        "payload,payload_hash,configuration,configuration_hash,frame_count,channel_count) "
        "VALUES(%s,%s,%s,'text-sensor','1',%s,'fixture',%s,'original-hash','{}','config-hash',1,1)",
        (id, project, run, source, Jsonb({"text": text})),
    )
    return str(id)


def readout(db, project, run, source="", envelope=None, kind="temporal_readout", key=None):
    payload = {
        "kind": kind,
        "envelope_id": str(envelope) if envelope else None,
        "source": source,
        "classification": "unresolved",
        "reason": "maximum_window",
        "nodes": [{"node_id": 1}] * 1200,
        "activity_nodes": [{"node_id": 2}],
        "series": [{"time_us": "0"}] * 1200,
        "structure": None,
        "configuration": {},
        "start_us": "0",
        "end_us": "1000",
        "candidate_ids": [1],
        "candidate_count": 1,
        "annotations": {},
        "overlapping_envelopes": [],
    }
    return db.execute(
        "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) VALUES(%s,%s,%s,1000,%s,%s,0) "
        "ON CONFLICT(run_id,event_key) DO NOTHING RETURNING id",
        (project, run, key or str(uuid4()), kind, Jsonb(payload)),
    ).fetchone()


def test_exact_links_visibility_deferred_order_and_bounded_summaries(database):
    with client_for(database) as client:
        p, r, base = fixture(client)
        env = uuid4()
        with database.tx(p) as db:
            event = readout(db, p, r, "ambient-disturbance", env, key="same-event")
            assert readout(db, p, r, "ambient-disturbance", env, key="same-event") is None
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM conversation_entries WHERE event_id=%s", (event["id"],)
                ).fetchone()["n"]
                == 0
            )
            linked = stimulus(db, p, r, "ambient-disturbance", id=env)
            unrelated = stimulus(db, p, r, "ambient-disturbance", "Same simulation instant, no recorded association")
            manual = stimulus(db, p, r, "manual-text", "<script>unsafe()</script>意识😀" * 180)
            ai = stimulus(db, p, r, "ai-environment", "External AI carrier")
            readout(db, p, r, "ai-environment", ai)
            passive = readout(db, p, r, kind="structural_readout")
        ordinary = client.get(base + "/conversation").json()
        assert {row["input_id"] for row in ordinary["rows"] if row["input_id"]} == {manual, ai}
        default_ids = {row["id"] for row in ordinary["rows"]}
        assert all(row["event_id"] != str(passive["id"]) for row in ordinary["rows"])
        reply = next(row for row in ordinary["rows"] if row["event_id"])
        assert reply["linked_input_id"] == ai and reply["readout"]["node_count"] == 1200
        assert "nodes" not in reply["readout"] and "series" not in reply["readout"]
        text = next(row["stimulus"] for row in ordinary["rows"] if row["input_id"] == manual)
        assert len(text["text"]) == 2000 and text["text_length"] > 2000 and "<script>" in text["text"]
        expanded = client.get(base + "/conversation", params={"background": True}).json()["rows"]
        assert linked in {row["input_id"] for row in expanded}
        assert unrelated not in {row["input_id"] for row in expanded}
        association = next(row for row in expanded if row["event_id"] == str(event["id"]))
        receipt = next(row for row in expanded if row["input_id"] == linked)
        assert int(receipt["id"]) < int(association["id"]) and association["linked_input_id"] == linked
        hidden = client.get(base + "/conversation", params={"background": True, "triggering": False}).json()["rows"]
        assert not any(row["input_id"] in (linked, unrelated, ai) for row in hidden)
        all_rows = client.get(base + "/conversation", params={"background": True, "environment": True}).json()["rows"]
        assert len(all_rows) == 7 and all(not row["reconstructed"] for row in all_rows)
        assert {row["id"] for row in client.get(base + "/conversation").json()["rows"]} == default_ids
        with pytest.raises(RuntimeError), database.tx(p) as db:
            stimulus(db, p, r, "manual-text", "must roll back")
            readout(db, p, r)
            raise RuntimeError("rollback")
        assert (
            len(client.get(base + "/conversation", params={"background": True, "environment": True}).json()["rows"])
            == 7
        )


def test_pagination_ceiling_exports_and_rls_do_not_modify_model(database):
    with client_for(database) as client:
        p, r, base = fixture(client)
        with database.tx(p) as db:
            for n in range(125):
                stimulus(db, p, r, "manual-text", f"=carrier {n}")
        before_run = client.get(base).json()
        first = client.get(base + "/conversation", params={"limit": 7}).json()
        with database.tx(p) as db:
            new_id = stimulus(db, p, r, "manual-text", "later")
        all_rows = first["rows"][:]
        result = first
        while result["more"]:
            result = client.get(
                base + "/conversation", params={"limit": 7, "ceiling": first["ceiling"], "before": result["next"]}
            ).json()
            all_rows += result["rows"]
        assert len(all_rows) == len({row["id"] for row in all_rows}) == 125
        assert new_id not in {row["input_id"] for row in all_rows}
        params = {"ceiling": first["ceiling"]}
        export = client.get(base + "/conversation/export", params=params)
        lines = [json.loads(line) for line in export.text.splitlines()]
        assert lines[0]["metadata"]["schema"] == "threemind-conversation-index/1" and len(lines) == 126
        assert [row["id"] for row in lines[1:]] == [row["id"] for row in all_rows]
        csv_export = client.get(base + "/conversation/export", params=params | {"format": "csv"})
        assert len(list(csv.DictReader(io.StringIO(csv_export.text.lstrip("\ufeff"))))) == 125
        assert client.get(base + "/conversation", params={"kind": "made-up"}).status_code == 422
        assert client.get(base + "/conversation", params={"limit": 101}).status_code == 422
        after_run = client.get(base).json()
        for key in ("spec", "state_hash", "revision", "time_us", "sequence"):
            assert after_run[key] == before_run[key]
        p2, _r2, base2 = fixture(client, "Other project")
        assert client.get(base2 + "/conversation").json()["rows"] == []
        assert client.get(f"/api/v2/projects/{p2}/runs/{r}/conversation").status_code == 404
        with database.tx(p2) as db:
            assert db.execute("SELECT count(*) AS n FROM conversation_entries").fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.ForeignKeyViolation), database.tx(p) as db:
            db.execute(
                "INSERT INTO conversation_entries(project_id,run_id,kind,input_id,source) VALUES(%s,%s,'input',%s,'')",
                (p, r, uuid4()),
            )
        viewer = auth.create_user(database, "feed-viewer", "test conversation password")
        with database.tx() as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (p, viewer["id"]))
    with client_for(database, "server") as client:
        assert client.get(base + "/conversation").status_code == 401
        assert (
            client.post(
                "/api/v2/login", json={"username": "feed-viewer", "password": "test conversation password"}
            ).status_code
            == 200
        )
        assert client.get(base + "/conversation").status_code == 200
        assert client.get(base + "/conversation/export").status_code == 200
        assert client.get(base2 + "/conversation").status_code == 403


def test_worker_receipts_readouts_are_real_and_observer_is_passive(database):
    with client_for(database) as client:
        _p, _r, base = fixture(client)
        response = client.post(
            base + "/inputs",
            json={"adapter_id": "text-sensor", "payload": {"text": "意识网络\n研究输入"}, "request_id": str(uuid4())},
        )
        assert response.status_code == 202, response.text
        assert Worker(database).once()
        state = client.get(base).json()
        assert state["status"] == "completed", state.get("error")
        result = client.get(base + "/conversation", params={"background": True, "environment": True}).json()
        stimulus_row = next(row for row in result["rows"] if row["input_id"] == response.json()["id"])
        assert stimulus_row["stimulus"]["delivered_count"] > 0
        temporal = next(row for row in result["rows"] if row["kind"] == "temporal_readout")
        assert temporal["linked_input_id"] == response.json()["id"]
        assert client.get(base + f"/readouts/{temporal['event_id']}").status_code == 200
        for environment in (True, False):
            for background in (True, False):
                assert (
                    client.get(
                        base + "/conversation", params={"environment": environment, "background": background}
                    ).status_code
                    == 200
                )
        assert client.get(base).json()["state_hash"] == state["state_hash"]
        assert (
            client.get(base + f"/inputs/{response.json()['id']}").json()["envelope"]["payload"]["text"]
            == "意识网络\n研究输入"
        )


def test_existing_database_index_backfill_is_marked_and_scoped(database):
    with client_for(database) as client:
        fixtures = [fixture(client, f"Historical {i}") for i in range(2)]
        for p, r, _ in fixtures:
            with database.tx(p) as db:
                id = stimulus(db, p, r, "manual-text")
                readout(db, p, r, "manual-text", id)
        name = conninfo_to_dict(database.test_url)["dbname"]
        assert name.startswith("tm2_test_db_")
        with psycopg.connect(
            host="127.0.0.1", port=conninfo_to_dict(database.test_url)["port"], user="threemind_test", dbname=name
        ) as db:
            owner = db.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()"
            ).fetchone()[0]
            db.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(owner)))
            db.execute("SET search_path=tm2,pg_catalog")
            db.execute("DROP TRIGGER conversation_input ON input_envelopes")
            db.execute("DROP TRIGGER conversation_readout ON events")
            db.execute("DROP TABLE conversation_entries")
            db.execute("DROP FUNCTION index_conversation_input(), index_conversation_readout()")
            db.execute("ALTER TABLE input_envelopes DROP CONSTRAINT input_envelopes_scope")
            db.execute("ALTER TABLE events DROP CONSTRAINT events_scope")
            db.execute("DELETE FROM schema_version WHERE version=13")
            db.execute(
                (Path(__file__).resolve().parents[1] / "migrations/013_conversation.sql").read_text(encoding="utf-8")
            )
        for p, r, base in fixtures:
            result = client.get(base + "/conversation").json()["rows"]
            assert len(result) == 2 and all(row["reconstructed"] for row in result)
            with database.tx(p) as db:
                stimulus(db, p, r, "manual-text", "new")
            rows = client.get(base + "/conversation").json()["rows"]
            assert len(rows) == 3 and not rows[0]["reconstructed"]
