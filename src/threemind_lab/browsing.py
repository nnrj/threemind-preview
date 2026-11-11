"""Authorized metadata browsing; no engine, originals or write-side services."""

from contextlib import contextmanager
from uuid import UUID

from . import permissions
from .database import Forbidden, NotFound


def _row(
    kind,
    table,
    title,
    *,
    identity="id",
    status="''",
    updated="created_at",
    archived="false",
    details="'{}'::jsonb",
    joins="",
    owner="NULL::uuid",
):
    # All identifiers/expressions come from this private, fixed registry.
    return (
        f"SELECT r.project_id,r.{identity}::text AS id,'{kind}'::text AS kind,r.{title}::text AS title,"
        f"{status} AS status,r.created_at,r.{updated} AS updated_at,{archived} AS archived,"
        f"{details} AS details,{owner} AS owner_id FROM {table} r {joins}"
    )


RESOURCES = {
    "run": _row(
        "run",
        "runs",
        "name",
        status="r.status",
        updated="updated_at",
        archived="r.archived_at IS NOT NULL",
        details="jsonb_build_object('life',r.life,'kernel',r.spec->>'kernel_id','revision',r.revision,'time_us',r.time_us::text,'description',left(r.description,180))",
    ),
    "experiment": _row(
        "experiment",
        "research_experiments",
        "title",
        status="r.execution_status",
        updated="updated_at",
        details="jsonb_build_object('original_id',r.original_id,'coverage',r.coverage,'classification',r.classification)",
    ),
    "study": _row("study", "studies", "name", details="jsonb_build_object('protocol_hash',r.protocol_hash)"),
    "document": _row(
        "document",
        "research_documents",
        "title",
        updated="updated_at",
        archived="r.archived_at IS NOT NULL",
        details="jsonb_build_object('type',r.kind,'revision',r.revision)",
    ),
    "note": _row(
        "note",
        "notes",
        "title",
        owner="r.owner_id",
        updated="updated_at",
        archived="r.archived_at IS NOT NULL",
        details="jsonb_build_object('type',r.kind,'revision',r.revision,'excerpt',left(r.search_text,180))",
    ),
    "world": _row(
        "world",
        "world_documents",
        "title",
        updated="updated_at",
        archived="r.archived",
        details="jsonb_build_object('revision',r.revision,'type',CASE WHEN v.protocol->>'schema_id' IN ('threemind.robot-task/1','threemind.robot-task/2') THEN 'robot' ELSE 'world' END)",
        joins="JOIN world_versions v ON v.document_id=r.id AND v.revision=r.revision",
    ),
    "evolution": _row("evolution", "evolution_campaigns", "name", status="r.status", updated="updated_at"),
    "ecology": _row("ecology", "ecology_campaigns", "name", status="r.status", updated="updated_at"),
    "assessment": _row("assessment", "assessment_batches", "name", status="r.control_state"),
    "development": _row("development", "development_sessions", "name", details="jsonb_build_object('run_id',r.run_id)"),
    "innate": _row(
        "innate", "innate_versions", "name", details="jsonb_build_object('run_id',r.run_id,'generation',r.generation)"
    ),
    "language": _row(
        "language",
        "language_sessions",
        "run_id",
        identity="run_id",
        status="v.status",
        details="jsonb_build_object('name',v.name,'kernel',v.spec->>'kernel_id')",
        joins="JOIN runs v ON v.id=r.run_id",
    ),
    "species": _row(
        "species",
        "species_assets",
        "name",
        details="jsonb_build_object('sha256',r.bundle_hash,'bytes',octet_length(r.bundle))",
    ),
    "artifact": _row(
        "artifact",
        "artifacts",
        "name",
        details="jsonb_build_object('type',r.metadata->>'kind','bytes',r.bytes,'sha256',r.sha256)",
    ),
    "experiment_bundle": _row(
        "experiment_bundle",
        "experiment_bundles",
        "name",
        details="jsonb_build_object('bytes',r.bytes,'sha256',r.sha256)",
    ),
    "data_bundle": _row(
        "data_bundle", "data_bundles", "name", details="jsonb_build_object('bytes',r.bytes,'private',r.private)"
    ),
    "media": _row(
        "media",
        "media_assets",
        "sha256",
        identity="sha256",
        details="jsonb_build_object('bytes',r.byte_length,'sha256',r.sha256)",
    ),
    "probe": _row("probe", "probe_calibrations", "id", details="jsonb_build_object('run_id',r.run_id)"),
    "source": _row(
        "source",
        "report_sources",
        "id",
        details="jsonb_build_object('type',v.kind,'sha256',r.content_hash,'rows',r.row_count)",
        joins="JOIN report_source_requests v ON v.id=r.id",
    ),
}


KIND_ACTION = {
    "run": "runs.read", "language": "runs.read", "development": "runs.read",
    "experiment": "experiments.read", "study": "experiments.read", "evolution": "experiments.read",
    "ecology": "experiments.read", "assessment": "experiments.read", "probe": "experiments.read",
    "document": "reports.read", "source": "reports.read", "note": "notes.read",
    "world": "worlds.read", "innate": "data.read", "species": "data.read",
    "artifact": "data.read", "experiment_bundle": "data.read", "data_bundle": "data.read", "media": "data.read",
}
KIND_TABLES = {
    "run": ("runs",), "experiment": ("research_experiments",), "study": ("studies",),
    "document": ("research_documents",), "source": ("report_sources", "report_source_requests"),
    "note": ("notes", "note_collections"), "world": ("world_documents", "world_versions"),
    "evolution": ("evolution_campaigns",), "ecology": ("ecology_campaigns",),
    "assessment": ("assessment_batches",), "development": ("development_sessions",),
    "innate": ("innate_versions",), "language": ("language_sessions", "runs"),
    "species": ("species_assets",), "artifact": ("artifacts", "data_private_carriers"),
    "experiment_bundle": ("experiment_bundles",), "data_bundle": ("data_bundles",),
    "media": ("media_assets",), "probe": ("probe_calibrations",),
}


def _visible(actor, kind):
    action = KIND_ACTION[kind]
    if actor["superadmin"]:
        return "true"
    scopes = {g["scope"] for g in actor["permissions"] if g["action"] == action}
    choices = []
    if "all_projects" in scopes:
        choices.append("true")
    if "member_projects" in scopes:
        choices.append("m.user_id IS NOT NULL")
    if "own" in scopes and kind == "note":
        choices.append("b.owner_id='" + str(actor["id"]) + "'::uuid")
    return "(" + " OR ".join(choices) + ")" if choices else "false"


def _visibility(actor, kinds):
    return "(" + " OR ".join("(b.kind='" + kind + "' AND " + _visible(actor, kind) + ")" for kind in kinds) + ")"


@contextmanager
def read_scope(database, actor, project=None):
    actor = permissions.enrich(database, actor)
    if actor.get("delegation_id"):
        resources = [{"kind": "project", "id": str(project)}] if project else []
        if not permissions._resource_allowed(actor, resources):
            raise Forbidden("窄范围委托不能浏览整个项目或全库")
    with database.tx(read_only=True, repeatable=True) as db:
        if project and not actor["superadmin"]:
            member = db.execute("SELECT 1 FROM members WHERE project_id=%s AND user_id=%s", (project, actor["id"])).fetchone()
            if not any(permissions._scope_allowed(actor, action, project=project, owner_id=actor["id"], member=bool(member))
                       for action in (*set(KIND_ACTION.values()), "projects.read")):
                raise Forbidden("project access denied")
        permissions.set_context(db, actor, project)
        # Exact per-kind SQL predicates below enforce grants. This flag allows
        # their all-project branches to reach rows without membership joins.
        all_scope = actor["superadmin"] or any(g["scope"] == "all_projects" for g in actor["permissions"])
        db.execute("SELECT set_config('tm.platform_superadmin','false',true)")
        db.execute("SELECT set_config('tm.permission_metadata_only','true',true)")
        tables = {table for kind, action in KIND_ACTION.items() if permissions.has_action(actor, action)
                  for table in KIND_TABLES[kind]}
        db.execute("SELECT set_config('tm.permission_metadata_tables',%s,true)", (",".join(sorted(tables)),))
        db.execute("SELECT set_config('tm.permission_all_projects',%s,true)", ("true" if all_scope else "false",))
        db.execute("SELECT set_config('tm.permission_domain','data',true)")
        db.execute("SELECT set_config('tm.browse_user_id',%s,true)", (str(actor["id"]),))
        db.execute("SELECT set_config('tm.record_user_id',%s,true)", (str(actor["id"]),))
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
        yield db


def _query(kinds):
    kinds = tuple(dict.fromkeys(kinds))
    if not kinds or any(kind not in RESOURCES for kind in kinds):
        raise ValueError("unknown resource kind")
    return " UNION ALL ".join(RESOURCES[kind] for kind in kinds)


def listing(database, actor, *, kinds, project=None, q="", subtype="", archived="active", offset=0, limit=50):
    if archived not in ("active", "archived", "all") or not 0 <= offset <= 100000 or not 1 <= limit <= 100:
        raise ValueError("invalid browsing pagination or archive filter")
    actor = permissions.enrich(database, actor)
    kinds = tuple(dict.fromkeys(kinds))
    resource_query = _query(kinds)
    filters, arguments = [_visibility(actor, kinds)], [actor["id"]]
    if project:
        filters.append("b.project_id=%s")
        arguments.append(project)
    if q:
        filters.append(
            "(strpos(lower(b.title::text),lower(%s))>0 OR strpos(lower(p.name),lower(%s))>0 OR strpos(lower(coalesce(b.details->>'original_id','')),lower(%s))>0)"
        )
        arguments.extend((q, q, q))
    if subtype:
        filters.append("b.details->>'type'=%s")
        arguments.append(subtype)
    if archived != "all":
        filters.append("b.archived=%s")
        arguments.append(archived == "archived")
    source = (
        "WITH resources AS ("
        + resource_query
        + ") SELECT b.*,p.name AS project_name,m.role AS project_role FROM resources b "
        "JOIN projects p ON p.id=b.project_id LEFT JOIN members m ON m.project_id=p.id AND m.user_id=%s WHERE "
        + " AND ".join(filters)
    )
    with read_scope(database, actor, project) as db:
        total = db.execute("SELECT count(*) AS n FROM (" + source + ") visible", arguments).fetchone()["n"]
        rows = db.execute(
            source + " ORDER BY b.updated_at DESC,b.kind,b.id LIMIT %s OFFSET %s", (*arguments, limit + 1, offset)
        ).fetchall()
    return {"rows": rows[:limit], "more": len(rows) > limit, "total": total, "offset": offset, "limit": limit}


def location(database, actor, kind, identity):
    actor = permissions.enrich(database, actor)
    resource_query = _query((kind,))
    with read_scope(database, actor) as db:
        row = db.execute(
            "WITH resources AS (" + resource_query + ") SELECT b.project_id,p.name AS project_name,m.role AS project_role "
            "FROM resources b JOIN projects p ON p.id=b.project_id LEFT JOIN members m ON m.project_id=p.id "
            "AND m.user_id=%s WHERE b.id=%s AND " + _visibility(actor, (kind,)),
            (actor["id"], str(identity)),
        ).fetchone()
    if not row:
        raise NotFound("resource is unavailable or not authorized")
    return row


def overview(database, actor, *, project=None, q="", offset=0, limit=12):
    if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
        raise ValueError("invalid project pagination")
    actor = permissions.enrich(database, actor)
    kinds = tuple(kind for kind in RESOURCES if permissions.has_action(actor, KIND_ACTION[kind]))
    # Counts are filtered by the same per-kind grants as listings. Hidden
    # resource kinds do not leak through aggregate totals.
    resource_query = _query(kinds) if kinds else "SELECT NULL::uuid AS project_id,NULL::text AS kind,false AS archived WHERE false"
    visible = _visibility(actor, kinds) if kinds else "false"
    project_global = actor["superadmin"] or any(g == {"action": "projects.read", "scope": "all_projects"} for g in actor["permissions"])
    project_read = permissions.has_action(actor, "projects.read")
    with read_scope(database, actor, project) as db:
        rows = db.execute(
            "WITH resources AS (" + resource_query + "), counts AS ("
            "SELECT b.project_id,b.kind,count(*) AS n FROM resources b LEFT JOIN members m ON m.project_id=b.project_id "
            "AND m.user_id=%s WHERE " + visible + " AND NOT b.archived GROUP BY b.project_id,b.kind), "
            "summary AS (SELECT project_id,jsonb_object_agg(kind,n) AS counts FROM counts GROUP BY project_id) "
            "SELECT p.id,p.name,p.created_at,m.role,coalesce(s.counts,'{}'::jsonb) AS counts "
            "FROM projects p LEFT JOIN members m ON m.project_id=p.id AND m.user_id=%s "
            "LEFT JOIN summary s ON s.project_id=p.id WHERE (%s OR (%s AND m.user_id IS NOT NULL) OR s.project_id IS NOT NULL) "
            "AND (%s::uuid IS NULL OR p.id=%s) AND (%s='' OR strpos(lower(p.name),lower(%s))>0) ORDER BY p.created_at DESC,p.id",
            (actor["id"], actor["id"], project_global, project_read, project, project, q, q),
        ).fetchall()
    totals = {kind: sum(int(row["counts"].get(kind, 0)) for row in rows) for kind in kinds}
    return {"rows": rows[offset:offset + limit], "total": len(rows), "more": len(rows) > offset + limit,
            "totals": totals, "offset": offset, "limit": limit}


def register(app):
    from fastapi import Query, Request

    from .auth import identity

    @app.get("/api/v2/browse/resources")
    def resources(
        request: Request,
        kinds: str = "run",
        project: UUID | None = None,
        q: str = Query("", max_length=160),
        subtype: str = Query("", max_length=40),
        archived: str = "active",
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(50, ge=1, le=100),
    ):
        return listing(
            app.state.db,
            identity(request),
            kinds=kinds.split(","),
            project=project,
            q=q,
            subtype=subtype,
            archived=archived,
            offset=offset,
            limit=limit,
        )

    @app.get("/api/v2/browse/location/{kind}/{resource}")
    def resource_location(kind: str, resource: str, request: Request):
        return location(app.state.db, identity(request), kind, resource)

    @app.get("/api/v2/browse/overview")
    def project_overview(
        request: Request,
        project: UUID | None = None,
        q: str = Query("", max_length=160),
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(12, ge=1, le=100),
    ):
        return overview(app.state.db, identity(request), project=project, q=q, offset=offset, limit=limit)
