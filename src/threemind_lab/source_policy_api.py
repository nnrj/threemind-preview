"""Read-only source controls catalogue; mutations use the versioned configuration API."""

from dataclasses import asdict
from uuid import UUID

from fastapi import Request

from threemind_runtime.source_policies import CATEGORIES, POLICY_VERSION, SourcePolicies

from .inputs import digest


def register_source_policy_routes(app, access):
    @app.get("/api/v2/projects/{project}/runs/{run_id}/source-policies")
    def policies(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        run = app.state.db.get_run(project, run_id)
        config = SourcePolicies(**run["spec"].get("source_policies", {}))
        return {
            "schema": POLICY_VERSION,
            "configuration": asdict(config),
            "configuration_hash": digest(asdict(config)),
            "revision": run["revision"],
            "categories": [{"id": key, "label": label} for key, label in CATEGORIES],
            "rows": config.rows(),
            "scope": "new sensory admission and scheduling; committed Core queue retains its policy",
        }
