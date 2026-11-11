import json
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from threemind_runtime.ecology_observer import VERSION, ObserverConfig, catalogue

from . import ecology_observers as store
from .database import NotFound
from .protocols import StrictModel


class Configuration(StrictModel):
    configuration: ObserverConfig
    expected_revision: int = Field(ge=0, strict=True)


class Retry(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)


def revision(db, identity, selected):
    if selected is None:
        current = db.execute("SELECT revision FROM ecology_observers WHERE campaign_id=%s", (identity,)).fetchone()
        if not current:
            return None
        selected = current["revision"]
    row = db.execute(
        "SELECT * FROM ecology_observer_revisions WHERE campaign_id=%s AND revision=%s", (identity, selected)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def ceiling(db, identity, checkpoint_id):
    campaign = store.subject(db, identity)
    if checkpoint_id is None:
        return campaign["checkpoint_revision"]
    cp = db.execute(
        "SELECT revision FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s", (checkpoint_id, identity)
    ).fetchone()
    if cp is None:
        raise NotFound()
    return cp["revision"]


def register_observer_routes(app, access):
    root = "/api/v2/projects/{project}/ecologies/{identity}/observer"

    @app.get(root)
    def detail(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            return store.detail(db, identity) | {"catalogue": catalogue()}

    @app.get(root + "/revisions")
    def revisions(project: UUID, identity: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.subject(db, identity)
            rows = db.execute(
                "SELECT revision,configuration,configuration_hash,first_checkpoint_revision,created_at FROM ecology_observer_revisions WHERE campaign_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 31",
                (identity, before, before),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.post(root + "/validate")
    def validate(project: UUID, identity: UUID, request: Request, body: ObserverConfig):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.subject(db, identity)
        return {"valid": True, "configuration": body.model_dump(mode="json")}

    @app.post(root + "/configuration")
    def configure(project: UUID, identity: UUID, request: Request, body: Configuration):
        actor = access(request, project, write=True)
        return store.configure(app.state.db, project, identity, actor["id"], body.configuration, body.expected_revision)

    @app.post(root + "/retry")
    def retry(project: UUID, identity: UUID, request: Request, body: Retry):
        access(request, project, write=True)
        return store.retry(app.state.db, project, identity, body.expected_revision)

    @app.get(root + "/entries")
    def entries(
        project: UUID,
        identity: UUID,
        request: Request,
        configuration_revision: int | None = Query(None, ge=1),
        checkpoint_id: UUID | None = None,
        before: int | None = Query(None, ge=1, le=2**63 - 1),
        kind: str | None = Query(None, pattern=r"^(event|summary|warning)$"),
    ):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            bound = ceiling(db, identity, checkpoint_id)
            config = revision(db, identity, configuration_revision)
            if config is None:
                return {"rows": [], "more": False, "configuration": None, "checkpoint_revision": bound}
            rows = db.execute(
                "SELECT e.id::text,e.checkpoint_id,e.kind,e.body,e.created_at FROM ecology_observer_entries e "
                "JOIN ecology_checkpoints c ON c.id=e.checkpoint_id WHERE e.campaign_id=%s AND e.configuration_revision=%s "
                "AND c.revision<=%s AND (%s::bigint IS NULL OR e.id<%s) AND (%s::text IS NULL OR e.kind=%s) ORDER BY e.id DESC LIMIT 31",
                (identity, config["revision"], bound, before, before, kind, kind),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30, "configuration": config, "checkpoint_revision": bound}

    @app.get(root + "/export")
    def export(
        project: UUID,
        identity: UUID,
        request: Request,
        configuration_revision: int = Query(ge=1),
        checkpoint_id: UUID | None = None,
    ):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            bound = ceiling(db, identity, checkpoint_id)
            config = revision(db, identity, configuration_revision)
            high = db.execute(
                "SELECT coalesce(max(e.id),0) AS id,count(*) AS count FROM ecology_observer_entries e JOIN ecology_checkpoints c ON c.id=e.checkpoint_id WHERE e.campaign_id=%s AND e.configuration_revision=%s AND c.revision<=%s",
                (identity, config["revision"], bound),
            ).fetchone()

        def stream():
            header = {
                "type": "manifest",
                "version": VERSION,
                "campaign_id": str(identity),
                "configuration_revision": config["revision"],
                "configuration": config["configuration"],
                "configuration_hash": config["configuration_hash"],
                "first_checkpoint_revision": config["first_checkpoint_revision"],
                "maximum_checkpoint_revision": bound,
                "maximum_entry_id": str(high["id"]),
                "entry_count": high["count"],
                "scope": "materialized-observer-entries-with-source-references",
            }
            yield (json.dumps(header, ensure_ascii=False) + "\n").encode()
            cursor = 0
            while cursor < high["id"]:
                with app.state.db.tx(project) as db:
                    rows = db.execute(
                        "SELECT e.id,e.body FROM ecology_observer_entries e JOIN ecology_checkpoints c ON c.id=e.checkpoint_id WHERE e.campaign_id=%s AND e.configuration_revision=%s AND c.revision<=%s AND e.id>%s AND e.id<=%s ORDER BY e.id LIMIT 100",
                        (identity, config["revision"], bound, cursor, high["id"]),
                    ).fetchall()
                if not rows:
                    break
                for row in rows:
                    yield (
                        json.dumps({"type": "entry", "id": str(row["id"]), **row["body"]}, ensure_ascii=False) + "\n"
                    ).encode()
                cursor = rows[-1]["id"]

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="ecology-observer-r{config["revision"]}.jsonl"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.get(root + "/live")
    def live(
        project: UUID,
        identity: UUID,
        request: Request,
        configuration_revision: int = Query(ge=1),
        after: int | None = Query(None, ge=0, le=2**63 - 1),
    ):
        """Optional live presentation, distinct from the complete evidence feed.

        A first request establishes a baseline. Later requests return at most
        three newest summaries/warnings and an exact count of skipped entries.
        This cursor has no effect on durable observer processing or retention.
        """
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            store.subject(db, identity)
            revision(db, identity, configuration_revision)
            if after is None:
                row = db.execute(
                    "SELECT id FROM ecology_observer_entries WHERE campaign_id=%s AND configuration_revision=%s AND kind IN ('summary','warning') ORDER BY id DESC LIMIT 1",
                    (identity, configuration_revision),
                ).fetchone()
                return {"cursor": str(row["id"] if row else 0), "rows": [], "omitted": 0, "baseline": True}
            count = db.execute(
                "SELECT count(*) AS n,max(id) AS latest FROM ecology_observer_entries WHERE campaign_id=%s AND configuration_revision=%s AND kind IN ('summary','warning') AND id>%s",
                (identity, configuration_revision, after),
            ).fetchone()
            rows = db.execute(
                "SELECT e.id::text,e.kind,e.body FROM ecology_observer_entries e WHERE e.campaign_id=%s AND e.configuration_revision=%s AND e.kind IN ('summary','warning') AND e.id>%s ORDER BY e.id DESC LIMIT 3",
                (identity, configuration_revision, after),
            ).fetchall()
            return {
                "cursor": str(count["latest"] or after),
                "rows": list(reversed(rows)),
                "omitted": count["n"] - len(rows),
                "baseline": False,
            }
