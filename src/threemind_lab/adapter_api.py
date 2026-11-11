"""Capability scopes and per-run bindings, backed by the canonical configuration."""

import threading
import time
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from pydantic import Field

from threemind_runtime.adapter_contracts import Negotiation, manifest, negotiate, read_manifest
from threemind_runtime.capabilities import probe_api
from threemind_runtime.registry import default_adapter_registry

from . import auth
from .configuration import catalogue, default_spec
from .database import NotFound
from .protocols import RunSpec, StrictModel


class ContractValidation(StrictModel):
    manifest_json: str = Field(max_length=131072, strict=True)
    negotiation: Negotiation | None = None


def binding_state(row, spec, *, network_count=0):
    enabled = row["configured_enabled"]
    if row["id"] == "remote-anonymous":
        enabled = network_count > 0
    reasons = []
    for dependency in row["dependencies"]:
        if dependency == "device.binding":
            if network_count == 0:
                reasons.append("尚无有效的设备绑定，请在网络设备页配置。")
        elif ":" in dependency:
            path, options = dependency.split(":", 1)
            if spec.get(path) not in options.split("|"):
                reasons.append(
                    "仅适用于模拟物理／合成环境。" if path == "environment" else "真实遥测或连续采集需要实时时间模式。"
                )
        else:
            value = spec
            for key in dependency.split("."):
                value = value.get(key, {}) if isinstance(value, dict) else None
            if value is not True:
                reasons.append(f"需要先启用 {dependency}。")
    return row | {
        "configured_enabled": enabled,
        "enabled": enabled,
        "binding_status": "disabled" if not enabled else "inactive" if reasons else "configured",
        "binding_reasons": reasons,
    }


def describe(spec, *, network_count=0):
    fields = catalogue()["fields"]
    rows = []
    for row in default_adapter_registry().list(spec):
        root = row["configuration_root"]
        row["parameters"] = [f for f in fields if root and f["path"].startswith(root + ".")]
        rows.append(binding_state(row, spec, network_count=network_count))
    return rows


def network_bindings(db, run_id):
    return db.execute(
        """SELECT d.id,d.name,d.enabled AND d.expires_at>now() AND u.enabled
           AND COALESCE(m.role IN ('owner','researcher'),false) AS enabled
           FROM device_bindings d JOIN users u ON u.id=d.issuer_id
           LEFT JOIN members m ON m.project_id=d.project_id AND m.user_id=d.issuer_id
           WHERE d.run_id=%s ORDER BY d.created_at,d.id""",
        (run_id,),
    ).fetchall()


def worker_public(row):
    age = (datetime.now(UTC) - row["heartbeat"]).total_seconds() if row["heartbeat"] else None
    return row | {"online": age is not None and age < 90, "heartbeat_age_s": round(age, 1) if age is not None else None}


def register_adapter_routes(app, access):
    lock, stored = threading.Lock(), {}

    @app.get("/api/v2/adapters/{adapter_id}/manifest")
    def contract_manifest(adapter_id: str, request: Request):
        auth.identity(request)
        return manifest(default_adapter_registry().describe(adapter_id)["contract"])

    @app.post("/api/v2/adapters/validate")
    def validate_contract(request: Request, body: ContractValidation):
        auth.identity(request)
        value = read_manifest(body.manifest_json)
        contract = value["contract"]
        registry = default_adapter_registry()
        installed = contract["adapter_id"] in registry.descriptors
        exact = installed and value == manifest(registry.describe(contract["adapter_id"])["contract"])
        return {
            "manifest": value,
            "structurally_valid": True,
            "matches_installed_declaration": exact,
            "installed_id": installed,
            "execution_authorized": False,
            "negotiation": negotiate(contract, body.negotiation) if body.negotiation else None,
            "scope": "Structure and declared compatibility only. No uploaded code is installed or executed; no device binding or model is created.",
        }

    def api_report():
        with lock:
            if not stored or time.monotonic() - stored["at"] >= 30:
                stored.update(at=time.monotonic(), report=probe_api())
            return deepcopy(stored["report"])

    @app.get("/api/v2/capabilities")
    def capabilities(request: Request):
        user = auth.identity(request)
        from .permissions import has_action

        can_read_host = has_action(user, "system.read")
        workers = []
        if can_read_host:
            with app.state.db.tx() as db:
                workers = [
                    worker_public(r)
                    for r in db.execute(
                        "SELECT id,name,enabled,heartbeat,capabilities FROM workers ORDER BY name"
                    ).fetchall()
                ]
        return {
            "api": api_report(),
            "workers": workers,
            "all_workers_visible": can_read_host,
            "mode": app.state.settings.mode,
            "notice": "接口服务与工作进程分别检测；报告不证明设备正在采集。工作进程报告在启动时生成，依赖改变后请重启相应进程。",
        }

    @app.get("/api/v2/adapters")
    def adapters(request: Request):
        auth.identity(request)
        return {
            "schema": "threemind.adapter-registry/1",
            "adapters": describe(default_spec()),
            "scope": "installed runtime contracts with default configuration; not active bindings",
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/adapters")
    def bindings(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            run = db.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()
            if run is None:
                raise NotFound("run")
            devices = network_bindings(db, run_id)
            worker = db.execute(
                """SELECT w.id,w.name,w.enabled,w.heartbeat,w.capabilities FROM jobs j JOIN workers w ON w.id=j.worker_id
                   WHERE j.run_id=%s AND j.kind='run' ORDER BY j.created_at DESC,j.id DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            state = db.execute(
                "SELECT context->'source_enabled' AS source_enabled FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        spec = RunSpec(**run["spec"]).model_dump()
        return {
            "schema": "threemind.adapter-bindings/1",
            "run_id": str(run_id),
            "revision": str(run["revision"]),
            "status": run["status"],
            "source_enabled": state["source_enabled"] if state else None,
            "adapters": describe(spec, network_count=sum(d["enabled"] for d in devices)),
            "network_devices": devices,
            "api": api_report(),
            "worker": worker_public(worker) if worker else None,
            "configuration_store": "runs.spec; remote credentials and limits in device_bindings",
            "scientific_policy": "Use the shared paused configuration editor; this catalogue never executes an adapter or rewrites Core.",
        }
