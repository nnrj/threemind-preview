"""Read-only, checkpoint-pinned geometry and complete coordinate/distance export."""

import csv
import io
import json
from collections import OrderedDict
from threading import Lock
from typing import Literal
from uuid import UUID

from fastapi import Query, Request, Response
from fastapi.responses import StreamingResponse

from threemind_core.spatial import Spatial
from threemind_kernels.registry import kernel_catalog, state_kernel

from .database import NotFound
from .resource_evidence import selection


def snapshot(database, project, run_id, checkpoint_id):
    cp, image = database.load_checkpoint(project, run_id, checkpoint_id)
    state = image.to_dict()
    metadata = {
        "checkpoint_id": str(cp["id"]),
        "revision": cp["revision"],
        "time_us": state["time_us"],
        "state_time_us": state.get("state_time_us", state["time_us"]),
        "state_hash": image.digest,
        "dynamics": state["dynamics"],
        "total_nodes": len(state["nodes"]),
        "total_edges": len(state["edges"]),
    }
    if state["dynamics"] not in {k["kernel_id"] for k in kernel_catalog() if "causal_space" in k["capabilities"]}:
        return metadata | {"supported": False, "nodes": [], "edges": [], "summary": None}, state
    spatial = Spatial()
    nodes = {n["id"]: n for n in state["nodes"]}
    edges = {(e["source"], e["target"]): e for e in state["edges"]}
    geometry = spatial.geometry(state_kernel(image).configuration(state["config"]), nodes, edges)
    return metadata | {
        "supported": True,
        "summary": {k: v for k, v in geometry.items() if k not in ("nodes", "edges")},
        "nodes": [nodes[n["id"]] | n for n in geometry["nodes"]],
        "edges": [edges[e["source"], e["target"]] | e for e in geometry["edges"]],
    }, state


def axes_for(raw, dimensions):
    if not raw:
        return [i if i < dimensions else None for i in range(3)]
    items = raw.split(",")
    if len(items) != 3:
        raise ValueError("投影必须包含三个坐标轴，隐藏轴用 -1 表示。")
    if any(not item.isascii() or not (item == "-1" or item.isdecimal()) for item in items):
        raise ValueError("坐标轴必须为整数。")
    values = [None if item == "-1" else int(item) for item in items]
    selected = [v for v in values if v is not None]
    if not selected or any(v >= dimensions for v in selected) or len(set(selected)) != len(selected):
        raise ValueError("请选择当前维数内不重复的坐标轴，至少显示一个轴。")
    return values


def export_records(result, records, format):
    metadata = {k: v for k, v in result.items() if k not in ("nodes", "edges")}
    if format == "jsonl":
        yield (json.dumps({"selection": metadata}, ensure_ascii=False, allow_nan=False) + "\n").encode()
        for kind in ("nodes", "edges"):
            if records in (kind, "all"):
                for row in result[kind]:
                    yield (
                        json.dumps({"record": kind[:-1], **row}, ensure_ascii=False, allow_nan=False) + "\n"
                    ).encode()
        return
    keys = [
        "checkpoint_id",
        "revision",
        "time_us",
        "state_time_us",
        "state_hash",
        "coordinate_rule",
        "seed",
        "parameters",
    ]
    columns = (
        [
            "id",
            "channel",
            "activation",
            "inhibition",
            "trace",
            "support",
            "stability",
            "direct",
            "associative",
            "touches",
            "last_touch_us",
            "position",
            "cluster",
        ]
        if records == "nodes"
        else [
            "source",
            "target",
            "weight",
            "stability",
            "eligibility",
            "touches",
            "birth_us",
            "last_touch_us",
            "distance",
            "within_radius",
        ]
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(keys + columns)
    yield ("\ufeff" + output.getvalue()).encode()
    for value in result[records]:
        row = metadata | (metadata["summary"] or {}) | value
        output.seek(0)
        output.truncate(0)
        writer.writerow(
            [
                json.dumps(row[k], ensure_ascii=False, allow_nan=False)
                if isinstance(row.get(k), (list, dict))
                else row.get(k)
                for k in keys + columns
            ]
        )
        yield output.getvalue().encode()


def register_spatial_routes(app, access):
    # Cache only the validated, tiny projection header, never a model or graph.
    # A cold server decodes once; later unchanged requests still recheck RLS
    # and checkpoint identity in PostgreSQL before using this metadata.
    headers = OrderedDict()
    headers_lock = Lock()

    @app.get("/api/v2/projects/{project}/runs/{run_id}/checkpoint-history")
    def checkpoints(
        project: UUID,
        run_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        after_us: str = "0",
        until_us: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ):
        access(request, project)
        start, end = selection(after_us, until_us)
        with app.state.db.tx(project, repeatable=True) as db:
            if db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone() is None:
                raise NotFound("run")
            rows = db.execute(
                """SELECT id,revision,time_us,state_hash,created_at FROM checkpoints WHERE run_id=%s
                               AND (%s::bigint IS NULL OR revision<%s) AND time_us>=%s AND (%s::numeric IS NULL OR time_us<=%s)
                               ORDER BY revision DESC LIMIT %s""",
                (run_id, before, before, start, end, end, limit + 1),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[limit - 1]["revision"] if len(rows) >= limit else before,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/spatial")
    def evidence(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        node_after: int = Query(-1, ge=-1),
        edge_after: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=500),
    ):
        access(request, project)
        result, _ = snapshot(app.state.db, project, run_id, checkpoint_id)
        nodes = [n for n in result["nodes"] if n["id"] > node_after]
        edges = result["edges"]
        return result | {
            "nodes": nodes[:limit],
            "edges": edges[edge_after : edge_after + limit],
            "nodes_more": len(nodes) > limit,
            "edges_more": len(edges) > edge_after + limit,
            "nodes_next": nodes[limit - 1]["id"] if len(nodes) >= limit else node_after,
            "edges_next": edge_after + limit,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/spatial/graph")
    def graph(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        axes: str | None = None,
        limit: int = Query(10000, ge=1, le=100000),
        edge_limit: int = Query(1000000, ge=0, le=1000000),
        label_limit: int = Query(0, ge=0, le=500),
        since: int = -1,
    ):
        access(request, project)
        if since >= 0:
            identity = app.state.db.checkpoint_identity(project, run_id, checkpoint_id)
            key = (str(project), str(run_id), str(identity["id"]), identity["state_hash"])
            with headers_lock:
                header = headers.get(key)
                if header is not None:
                    headers.move_to_end(key)
            if header is not None:
                enabled, dimensions = header
                if not enabled:
                    raise ValueError("此检查点没有启用因果空间；普通三维观察投影仍可使用。")
                axes_for(axes, dimensions)
                if identity["revision"] == since:
                    return Response(status_code=304)
            checkpoint_id = identity["id"]
        result, state = snapshot(app.state.db, project, run_id, checkpoint_id)
        enabled = result["supported"] and result["summary"]["parameters"]["spatial_embedding"]
        dimensions = result["summary"]["parameters"]["spatial_dimensions"] if result["supported"] else None
        key = (str(project), str(run_id), result["checkpoint_id"], result["state_hash"])
        with headers_lock:
            headers[key] = (enabled, dimensions)
            headers.move_to_end(key)
            while len(headers) > 256:
                headers.popitem(last=False)
        if not enabled:
            raise ValueError("此检查点没有启用因果空间；普通三维观察投影仍可使用。")
        selected = axes_for(axes, dimensions)
        if result["revision"] == since:
            return Response(status_code=304)
        geometry = {n["id"]: n for n in result["nodes"][:limit]}
        nodes = [
            n
            | {
                "position": [geometry[n["id"]]["position"][axis] if axis is not None else 0.0 for axis in selected],
                "cluster": geometry[n["id"]]["cluster"],
            }
            for n in state["nodes"]
            if n["id"] in geometry
        ]
        from itertools import islice

        from .graph_annotations import annotations

        edges = list(
            islice((e for e in state["edges"] if e["source"] in geometry and e["target"] in geometry), edge_limit)
        )
        labels = {}
        if label_limit:
            with app.state.db.tx(project, repeatable=True) as db:
                labels = annotations(db, run_id, result["revision"], result["time_us"], nodes, label_limit)
        identity = json.dumps(
            [
                result["summary"]["coordinate_rule"],
                result["summary"]["seed"],
                result["summary"]["parameters"]["spatial_dimensions"],
                selected,
            ]
        )
        return {
            **{k: v for k, v in result.items() if k not in ("nodes", "edges")},
            "nodes": nodes,
            "edges": edges,
            "coordinates": "causal",
            "coordinate_identity": identity,
            "axes": selected,
            "complete": len(nodes) == len(state["nodes"]) and len(edges) == len(state["edges"]),
            **labels,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/spatial/export")
    def export(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        records: Literal["nodes", "edges", "all"] = "all",
        format: Literal["csv", "jsonl"] = "jsonl",
    ):
        access(request, project)
        if records == "all" and format == "csv":
            raise ValueError("CSV 请分别选择节点坐标或连接距离；完整混合记录可导出为 JSONL。")
        result, _ = snapshot(app.state.db, project, run_id, checkpoint_id)
        return StreamingResponse(
            export_records(result, records, format),
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="spatial-{run_id}-r{result["revision"]}-{records}.{format}"'
            },
        )
