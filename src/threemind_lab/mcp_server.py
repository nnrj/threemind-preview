"""Thin optional stdio MCP transport over the same operation catalog as CLI/UI.

No LLM invocation, direct database access, autonomous scheduler or embedded shell.
Service URL and credentials come from the host environment, never tool arguments.
"""

import argparse
import json
import os
from uuid import UUID

from .operations_client import OperationsClient


def build_server(client_factory=None):
    from mcp.server import MCPServer
    from mcp.types import ToolAnnotations

    server = MCPServer(
        "ThreeMind research tools",
        instructions=(
            "Discover and inspect operation schemas before execution. These are the same authenticated services as the UI. "
            "Preserve request IDs on retry. Unknown results require receipt inspection, never a fresh-ID retry. "
            "Raw activations and original evidence must not be rewritten. Cleanup and credential administration remain human-controlled."
        ),
    )
    factory = client_factory or (
        lambda: OperationsClient.from_environment(source="ai", interactive=False)
    )
    read = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    write = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)

    @server.tool(annotations=read)
    def operations_list(search: str = "", offset: int = 0, limit: int = 40) -> dict:
        """Search the installed operation catalog. Does not operate on a consciousness."""
        if offset < 0 or not 1 <= limit <= 100 or len(search) > 200:
            raise ValueError("invalid catalog paging limits")
        with factory() as client:
            rows = [
                r
                for r in client.catalog()["operations"]
                if not r["human_confirmation"]
                and search.lower() in (r["id"] + " " + r["title"] + " " + r["path"]).lower()
            ]
            return {
                "total": len(rows),
                "offset": offset,
                "items": [
                    {k: r[k] for k in ("id", "title", "method", "path", "effect", "request_receipt")}
                    for r in rows[offset : offset + limit]
                ],
            }

    @server.tool(annotations=read)
    def operation_describe(operation: str) -> dict:
        """Get the real request schema and prerequisites for an operation."""
        with factory() as client:
            row = client.describe(operation)
            # Include only transitively referenced components, not every server schema.
            components, found = client.catalog()["components"].get("schemas", {}), {}
            pending = [row]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    ref = item.get("$ref", "")
                    if ref.startswith("#/components/schemas/"):
                        key = ref.rsplit("/", 1)[-1]
                        if key not in found:
                            found[key] = components[key]
                            pending.append(components[key])
                    pending.extend(item.values())
                elif isinstance(item, list):
                    pending.extend(item)
            return {"operation": row, "components": {"schemas": found}}

    @server.tool(annotations=read)
    def operation_preflight(operation: str, arguments: dict, request_id: str | None = None) -> dict:
        """Validate syntax without mutation; reports all runtime conditions still unchecked."""
        with factory() as client:
            return client.preflight(operation, arguments, request_id=request_id)

    @server.tool(annotations=write)
    def operation_call(operation: str, arguments: dict, request_id: str | None = None) -> dict:
        """Execute one canonical operation. Preserve the returned/requested ID when reconciling."""
        with factory() as client:
            row = client.describe(operation)
            if row["human_confirmation"]:
                raise ValueError("This sensitive operation requires its explicit human confirmation workflow; "
                                 "ordinary experiment operations remain available through the same API")
            # No automatic upload/download paths from model-generated tool arguments.
            result = client.call(operation, arguments, request_id=request_id, maximum=2 * 1024 * 1024)
            return {"request_id": request_id, "result": result}

    @server.tool(annotations=read)
    def operation_receipt(project: str, request_id: str) -> dict:
        """Inspect a durable outcome after a timeout/disconnection, without reissuing its mutation."""
        with factory() as client:
            return client.request("GET", f"/api/v2/projects/{UUID(project)}/operation-receipts/{UUID(request_id)}")

    @server.tool(annotations=write)
    def bundle_file_transfer(
        action: str, project: str, relative_path: str, bundle_id: str | None = None, request_id: str | None = None
    ) -> dict:
        """Upload/download a verified experiment archive inside the host-approved transfer directory. Never resumes it."""
        from pathlib import Path

        from .bundle_transfer import download_file, upload_file

        root = os.getenv("THREEMIND_MCP_TRANSFER_DIR")
        if not root:
            raise ValueError("The host must first set THREEMIND_MCP_TRANSFER_DIR; arbitrary host files are not exposed")
        root_path = Path(root).resolve(strict=True)
        relative = Path(relative_path)
        path = (root_path / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(root_path) or path == root_path:
            raise ValueError("transfer path must stay inside the host-approved directory")
        with factory() as client:
            if action == "upload" and request_id:
                return upload_file(client, UUID(project), path, UUID(request_id))
            if action == "download" and bundle_id:
                return download_file(client, UUID(project), UUID(bundle_id), path)
        raise ValueError("upload needs a stable request_id; download needs a bundle_id")

    return server


def main():
    parser = argparse.ArgumentParser(description="ThreeMind MCP stdio server; optional official MCP SDK")
    parser.add_argument("--describe", action="store_true", help="Print transport metadata without contacting a service")
    args = parser.parse_args()
    if args.describe:
        print(
            json.dumps(
                {
                    "name": "ThreeMind research tools",
                    "transport": "stdio",
                    "schema": "threemind.operations/1",
                    "endpoint_environment": "THREEMIND_API_URL",
                    "llm_calls": False,
                    "direct_database_access": False,
                }
            )
        )
        return
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
