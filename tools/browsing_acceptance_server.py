"""Synthetic browsing acceptance server on a dedicated test PostgreSQL cluster.

Requires the trust-authenticated loopback test cluster on port 55439, role
threemind_test. Never reads .env or starts a simulation worker. All synthetic
data lives in a new temporary database, removed on exit. See the browsing guide.
"""

import json
import threading
from pathlib import Path
from uuid import uuid4

import psycopg
import uvicorn
from psycopg import sql

from threemind_lab import worlds
from threemind_lab.api import create_app
from threemind_lab.bootstrap import provision
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.protocols import RunSpec
from threemind_lab.research_records import ResearchRecords
from threemind_lab.world_api import WorldEdit
from threemind_runtime.world_schema import default_world


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".work"
    output.mkdir(exist_ok=True)
    stop = output / "global-browse-ui.stop"
    stop.unlink(missing_ok=True)
    admin = {"host": "127.0.0.1", "port": 55439, "user": "threemind_test", "dbname": "postgres"}
    suffix = uuid4().hex[:10]
    names = {key: f"tm2_browse_ui_{key}_{suffix}" for key in ("db", "owner", "app")}
    _, url = provision(admin, database=names["db"], owner=names["owner"], app=names["app"])
    database = Database(url)
    try:
        actor = {"id": LOCAL_USER}
        projects = [database.create_project(actor, "Browse A"), database.create_project(actor, "Browse B")]
        viewer_project = database.create_project(actor, "Browse read-only")
        with database.tx() as connection:
            connection.execute(
                "UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s",
                (viewer_project["id"], LOCAL_USER),
            )
        records = ResearchRecords(database)
        fixture = {
            "projects": [str(p["id"]) for p in projects],
            "viewer_project": str(viewer_project["id"]),
            "runs": [],
            "notes": [],
            "documents": [],
            "experiments": [],
            "worlds": [],
        }
        spec = RunSpec(environment="manual", clock="unbounded", duration_s=1).model_dump(mode="json")
        for index in range(54):
            project = projects[index % 2]["id"]
            run = database.create_run(project, f"Browse instance {index:02d}", spec)
            fixture["runs"].append({"id": str(run["id"]), "project": str(project), "name": run["name"]})
        for index, project in enumerate(projects):
            identity = records.register(
                project["id"],
                actor,
                {
                    "request_id": str(uuid4()),
                    "spec": {
                        "source_key": f"development-ui-{index}",
                        "original_id": f"UI-{index}",
                        "title": f"Browse research {index}",
                        "classification": "development",
                        "execution_status": "planned",
                        "executor": "ai",
                    },
                },
            )["id"]
            fixture["experiments"].append({"id": identity, "project": str(project["id"])})
            for kind in ("note", "report"):
                title = f"Browse {kind} {index}"
                text = records.save_text(
                    project["id"],
                    actor,
                    identity,
                    {
                        "request_id": str(uuid4()),
                        "identity": str(uuid4()),
                        "kind": kind,
                        "title": title,
                        "markdown": f"UI fixture {kind} content {index}; no experiment was executed.",
                    },
                )
                fixture["notes" if kind == "note" else "documents"].append(
                    {
                        "id": str(text["text"]["id"]),
                        "project": str(project["id"]),
                        "name": title,
                    }
                )
            document = worlds.save(
                database,
                project["id"],
                LOCAL_USER,
                WorldEdit.model_validate(
                    {
                        "operation_id": str(uuid4()),
                        "protocol": default_world().model_dump(mode="json") | {"label": f"Browse world {index}"},
                    }
                ),
            )
            fixture["worlds"].append({"id": str(document["document_id"]), "project": str(project["id"])})
        (output / "global-browse-ui-fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
        app = create_app(Settings(database_url=url, backend="reference", origins=("http://127.0.0.1:8898",)), database)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8898, access_log=False))
        finished = threading.Event()

        def check_stop():
            while not finished.wait(0.2):
                if stop.exists():
                    server.should_exit = True
                    return

        thread = threading.Thread(target=check_stop, daemon=True)
        thread.start()
        try:
            server.run()
        finally:
            finished.set()
            thread.join(timeout=1)
    finally:
        database.close()
        # Exact names generated by this invocation; no other database or role.
        with psycopg.connect(**admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(names["db"])))
            for key in ("owner", "app"):
                connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(names[key])))


if __name__ == "__main__":
    main()
