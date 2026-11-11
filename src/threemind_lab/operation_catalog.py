"""Discoverable contract over the existing REST services, shared by UI, CLI and MCP.

No second implementation of run controls or experimental commands lives here.
Schemas are generated from the actual registered FastAPI routes.
"""

import hashlib
import re

from . import auth

VERSION = "threemind.operations/1"
PRIVATE = (
    "/admin/",
    "/auth/",
    "/account/",
    "/accounts/",
    "/login",
    "/logout",
    "/me",
    "/public",
    "/shared-documents/",
)
HUMAN_ONLY = ("cleanup", "secrets", "credentials", "providers", "members", "devices", "shares", "publication")
ALIASES = {
    ("GET", "/api/v2/research-experiments"): "records.list",
    ("POST", "/api/v2/projects/{project}/records"): "records.register",
    ("GET", "/api/v2/projects/{project}/records/{experiment}"): "records.detail",
    ("GET", "/api/v2/projects/{project}/records/{experiment}/entries"): "records.entries",
    ("POST", "/api/v2/projects/{project}/records/{experiment}/entries"): "records.append",
    ("GET", "/api/v2/projects/{project}/records/{experiment}/evidence"): "records.evidence",
    ("POST", "/api/v2/projects/{project}/records/{experiment}/evidence"): "records.attach",
    ("POST", "/api/v2/projects/{project}/records/{experiment}/texts"): "records.text",
    ("POST", "/api/v2/projects/{project}/records/{experiment}/finalize"): "records.finalize",
    ("GET", "/api/v2/projects/{project}/records/{experiment}/verify"): "records.verify",
    ("POST", "/api/v2/projects/{project}/records/backfill-plans"): "records.backfill_plan",
    ("POST", "/api/v2/projects/{project}/records/backfill-plans/{batch}/apply"): "records.backfill_apply",
    ("GET", "/api/v2/projects/{project}/records/receipts/{request_id}"): "records.receipt",
    ("GET", "/api/v2/projects/{project}/record-evidence/{evidence}/preview"): "records.preview",
    ("GET", "/api/v2/projects/{project}/record-evidence/{evidence}/content"): "records.download",
    ("GET", "/api/v2/projects/{project}/language"): "language.catalogue",
    ("GET", "/api/v2/projects/{project}/language/sessions/{run_id}/bundle"): "language.export",
    ("POST", "/api/v2/projects/{project}/language/imports"): "language.import",
    ("POST", "/api/v2/projects/{project}/language/sessions"): "language.create",
    ("GET", "/api/v2/projects/{project}/language/sessions/{run_id}/turns"): "language.turns",
    ("POST", "/api/v2/projects/{project}/language/sessions/{run_id}/turns"): "language.send",
    ("POST", "/api/v2/projects/{project}/language/sessions/{run_id}/observations"): "language.observe",
    ("POST", "/api/v2/projects/{project}/language/head-training"): "language.train_head",
    ("POST", "/api/v2/projects/{project}/language/scratch-training"): "language.train_scratch",
    ("GET", "/api/v2/projects/{project}/robots/catalogue"): "robot.catalogue",
    ("POST", "/api/v2/projects/{project}/robots/validate"): "robot.validate",
    ("GET", "/api/v2/projects/{project}/robots/assets/{identity}/template"): "robot.asset_template",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/world/observation"): "world.observe",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/world/protocol"): "world.protocol",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/bundles"): "bundle.export",
    ("GET", "/api/v2/projects/{project}/bundles"): "bundle.list",
    ("GET", "/api/v2/projects/{project}/bundles/{bundle_id}"): "bundle.inspect",
    ("GET", "/api/v2/projects/{project}/bundles/{bundle_id}/entry"): "bundle.entry",
    ("GET", "/api/v2/projects/{project}/bundles/{bundle_id}/download"): "bundle.download",
    ("POST", "/api/v2/projects/{project}/bundles/{bundle_id}/resumes"): "bundle.resume",
    ("POST", "/api/v2/projects/{project}/bundle-jobs/{job_id}/cancel"): "bundle.cancel",
    ("GET", "/api/v2/projects"): "projects.list",
    ("GET", "/api/v2/capabilities"): "capabilities.inspect",
    ("GET", "/api/v2/configuration"): "configuration.catalog",
    ("POST", "/api/v2/configuration/validate"): "configuration.validate",
    ("GET", "/api/v2/configuration/defaults"): "configuration.defaults",
    ("PUT", "/api/v2/configuration/defaults"): "configuration.save_defaults",
    ("GET", "/api/v2/configuration/templates"): "configuration.templates",
    ("POST", "/api/v2/configuration/templates"): "configuration.create_template",
    ("GET", "/api/v2/configuration/templates/{identity}"): "configuration.template",
    ("PUT", "/api/v2/configuration/templates/{identity}"): "configuration.edit_template",
    ("GET", "/api/v2/configuration/templates/{identity}/versions"): "configuration.template_versions",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/configuration-template"): "configuration.template_from_run",
    ("POST", "/api/v2/studies/validate"): "comparison.validate",
    ("POST", "/api/v2/projects/{project}/runs"): "consciousness.create",
    ("GET", "/api/v2/projects/{project}/runs"): "consciousness.list",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}"): "consciousness.inspect",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/readouts/{record_id}/process"): "observation.process",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/readouts/{record_id}/target"): "observation.target",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/readouts/{record_id}/response"): "observation.response",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/readouts/compare"): "observation.compare",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/inputs"): "stimulus.submit",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/commands"): "consciousness.command",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/forks"): "consciousness.fork",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/checkpoints"): "checkpoint.list",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/research/actions"): "research.action",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/research/plans"): "experiment.create",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/research/plans/validate"): "experiment.validate",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/research/plans"): "experiment.list",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/research/plans/{plan_id}"): "experiment.inspect",
    ("GET", "/api/v2/projects/{project}/runs/{run_id}/research/plans/{plan_id}/status"): "experiment.status",
    ("POST", "/api/v2/projects/{project}/runs/{run_id}/research/plans/{plan_id}/control"): "experiment.control",
    ("POST", "/api/v2/projects/{project}/studies"): "comparison.create",
    ("POST", "/api/v2/projects/{project}/transformer/training"): "transformer.train",
    ("POST", "/api/v2/projects/{project}/transformer/models/{model}/predictions"): "transformer.predict",
}


def receiptable(method, path):
    return (
        method in ("POST", "PUT", "PATCH", "DELETE")
        and bool(re.match(r"^/api/v2/(projects/[a-zA-Z0-9{}_-]+/|storage/)", path))
        and not any(part in path.split("/") for part in HUMAN_ONLY)
    )


def catalog(app):
    schema = app.openapi()
    rows = []
    for path, item in schema["paths"].items():
        if not path.startswith("/api/v2/") or any(part in path for part in PRIVATE):
            continue
        for method, value in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            method = method.upper()
            body = value.get("requestBody", {}).get("content", {})
            effect = "read" if method == "GET" else "write"
            human = effect != "read" and (
                any(part in path.split("/") for part in HUMAN_ONLY) or path == "/api/v2/storage/targets"
            )
            host = path.startswith("/api/v2/storage")
            identity = ALIASES.get((method, path)) or (
                value.get("operationId", "operation")[:100]
                + "_"
                + hashlib.sha256((method + path).encode()).hexdigest()[:8]
            )
            rows.append(
                {
                    "id": identity,
                    "title": value.get("summary", identity),
                    "method": method,
                    "path": path,
                    "parameters": value.get("parameters", []),
                    "request_body": body,
                    "responses": value.get("responses", {}),
                    "effect": effect,
                    "human_confirmation": human,
                    "request_receipt": receiptable(method, path) and "application/json" in body,
                    "scope": "host" if host else "project" if "/projects/{project}/" in path else "service",
                    "prerequisites": "Host administrator, CSRF and registered-resource checks"
                    if host
                    else "Platform system.write plus runs.read on the source; copies saved configuration without run control"
                    if identity == "configuration.template_from_run"
                    else "Same project role, model state, revision and resource checks as the UI",
                    "execution": "canonical_rest_service",
                    "undo": (
                        None
                        if effect == "read"
                        else "explicit_storage_rollback_before_new_writes"
                        if "/migrations/" in path
                        else "archive_metadata_can_be_restored"
                        if path.endswith("/archive")
                        else "irreversible"
                        if path.endswith("/cleanup")
                        else "none_declared; inspect_operation_specific_receipt"
                        if effect == "write"
                        else None
                    ),
                }
            )
    return {
        "schema": VERSION,
        "operations": rows,
        "components": schema.get("components", {}),
        "principles": {
            "core_unchanged": True,
            "no_llm_calls_by_transport": True,
            "unknown_result": "Inspect the original receipt and referenced resources. Never retry with a fresh ID.",
            "physical_devices": "Host/browser permissions are reported separately; remote agents cannot invent sensor access.",
        },
    }


def register(app):
    from fastapi import Request

    @app.get("/api/v2/operations/catalog")
    def operations_catalog(request: Request):
        auth.identity(request)
        return catalog(app)
