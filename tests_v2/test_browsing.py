from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_api import client_for

from threemind_lab import auth, browsing, notebooks
from threemind_lab.database import LOCAL_USER


def actor():
    return {"id": LOCAL_USER}


def save_note(database, project, owner, title):
    return notebooks.save_note(
        database,
        project,
        owner,
        uuid4(),
        {
            "operation_id": str(uuid4()),
            "expected_revision": 0,
            "kind": "draft",
            "title": title,
            "body": {"format": "markdown", "text": title + " preserved original"},
        },
    )


def test_global_lists_filter_and_paginate_across_projects(database):
    first = database.create_project(actor(), "Project A")
    second = database.create_project(actor(), "Project B")
    runs = [
        database.create_run(p["id"], name, {})
        for p, name in [(first, "one"), (second, "two"), (first, "literal 100%_ name")]
    ]
    with client_for(database) as client:
        path = "/api/v2/browse/resources?kinds=run&limit=1"
        pages = [client.get(path + f"&offset={i}").json() for i in range(3)]
        assert all(p["total"] == 3 and len(p["rows"]) == 1 for p in pages)
        assert len({p["rows"][0]["id"] for p in pages}) == 3
        assert pages[0]["more"] and not pages[2]["more"]
        assert {p["rows"][0]["project_name"] for p in pages} == {"Project A", "Project B"}
        filtered = client.get(path + f"&project={second['id']}").json()
        assert filtered["total"] == 1 and filtered["rows"][0]["id"] == str(runs[1]["id"])
        assert client.get(path + "&q=100%25_").json()["total"] == 1
        summary = client.get("/api/v2/browse/overview?limit=1").json()
        assert summary["total"] == 2 and summary["totals"]["run"] == 3 and summary["more"]
        assert client.get("/api/v2/browse/resources?kinds=unknown").status_code == 422
        assert client.get(path + "&project=not-a-uuid").status_code == 422
        assert client.get("/api/v2/browse/resources?kinds=run&limit=101").status_code == 422


def test_browsing_preserves_membership_personal_notes_and_private_carriers(database):
    author = auth.create_user(database, "browse-author", "author test password long")
    peer = auth.create_user(database, "browse-peer", "peer test password long", admin=True)
    shared = database.create_project(author, "Shared")
    hidden = database.create_project(author, "Hidden")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (shared["id"], peer["id"]))
    mine = save_note(database, shared["id"], author["id"], "Author secret")
    visible_run = database.create_run(shared["id"], "Shared run", {})
    private_run = database.create_run(hidden["id"], "Hidden run", {})
    # Viewer notes are historical records; seed them while membership permits
    # writing, then restore viewer access before the observation checks.
    with database.tx() as db:
        db.execute(
            "UPDATE members SET role='researcher' WHERE project_id=%s AND user_id=%s", (shared["id"], peer["id"])
        )
    own = save_note(database, shared["id"], peer["id"], "Peer note")
    with database.tx() as db:
        db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (shared["id"], peer["id"]))
    job = database.enqueue(shared["id"], "analysis")
    private_artifact, public_artifact = uuid4(), uuid4()
    with database.tx(shared["id"]) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(author["id"]),))
        for identity, title in ((private_artifact, "private package carrier"), (public_artifact, "public artifact")):
            db.execute(
                "INSERT INTO artifacts(id,project_id,job_id,name,media_type,bytes,sha256,metadata) VALUES(%s,%s,%s,%s,'application/octet-stream',1,%s,%s)",
                (identity, shared["id"], job["id"], title, "a" * 64, Jsonb({})),
            )
        db.execute(
            "INSERT INTO data_private_carriers VALUES(%s,'artifact',%s,%s)",
            (shared["id"], private_artifact, author["id"]),
        )
        for name, private in (("private note package", True), ("public package", False)):
            db.execute(
                "INSERT INTO data_bundles(id,project_id,actor_id,name,private,manifest,bytes) VALUES(%s,%s,%s,%s,%s,%s,1)",
                (uuid4(), shared["id"], author["id"], name, private, Jsonb({})),
            )
    with client_for(database, "server") as client:
        assert client.get("/api/v2/browse/overview").status_code == 401
        login = client.post("/api/v2/login", json={"username": "browse-peer", "password": "peer test password long"})
        assert login.status_code == 200
        notes = client.get("/api/v2/browse/resources?kinds=note").json()
        assert [n["id"] for n in notes["rows"]] == [str(own["id"])]
        assert str(mine["id"]) not in str(notes)
        resources = client.get("/api/v2/browse/resources?kinds=run,artifact").json()
        ids = {r["id"] for r in resources["rows"]}
        assert ids == {str(visible_run["id"]), str(public_artifact)}
        assert client.get(f"/api/v2/browse/location/run/{private_run['id']}").status_code == 404
        assert client.get(f"/api/v2/browse/location/note/{mine['id']}").status_code == 404
        assert client.get(f"/api/v2/browse/resources?kinds=run&project={hidden['id']}").status_code == 403
        summary = client.get("/api/v2/browse/overview").json()
        assert summary["total"] == 1 and summary["totals"]["note"] == 1
        assert summary["totals"]["artifact"] == 1
        packages = client.get("/api/v2/browse/resources?kinds=data_bundle").json()
        assert [p["title"] for p in packages["rows"]] == ["public package"]
        located = client.get(f"/api/v2/browse/location/run/{visible_run['id']}").json()
        assert located["project_id"] == str(shared["id"]) and located["project_role"] == "viewer"
        assert (
            client.post(
                f"/api/v2/projects/{shared['id']}/runs",
                json={"name": "denied"},
                headers={"X-CSRF-Token": login.json()["csrf"]},
            ).status_code
            == 403
        )


def test_metadata_read_context_does_not_grant_writes_or_raw_state_access(database):
    project = database.create_project(actor(), "Read only")
    run = database.create_run(project["id"], "Preserved run", {})
    with database.tx(project["id"]) as db:
        db.execute(
            "INSERT INTO observations(project_id,run_id,time_us,sequence,metrics) VALUES(%s,%s,0,0,%s)",
            (project["id"], run["id"], Jsonb({"sentinel": 42})),
        )
    with browsing.read_scope(database, actor()) as db:
        assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM checkpoints").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM observations").fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            db.execute("UPDATE runs SET name='mutated'")
    with database.tx() as db:
        assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 0
        db.execute("SELECT set_config('tm.browse_user_id',%s,true)", (str(LOCAL_USER),))
        assert db.execute("UPDATE runs SET name='mutated' RETURNING id").fetchall() == []
    before = database.get_run(project["id"], run["id"])
    for _ in range(2):
        result = browsing.overview(database, actor())
        assert result["totals"]["run"] == 1
        browsing.listing(database, actor(), kinds=tuple(browsing.RESOURCES))
    assert database.get_run(project["id"], run["id"]) == before
    with database.tx(project["id"]) as db:
        assert db.execute("SELECT count(*) AS n FROM note_collections").fetchone()["n"] == 0


def test_archived_results_and_location_use_saved_identity(database):
    project = database.create_project(actor(), "Archived project")
    run = database.create_run(project["id"], "Older run", {})
    with database.tx(project["id"]) as db:
        db.execute("UPDATE runs SET archived_at=now() WHERE id=%s", (run["id"],))
    assert browsing.listing(database, actor(), kinds=("run",))["total"] == 0
    assert browsing.listing(database, actor(), kinds=("run",), archived="archived")["total"] == 1
    assert str(browsing.location(database, actor(), "run", run["id"])["project_id"]) == str(project["id"])
    assert browsing.overview(database, actor())["totals"]["run"] == 0
