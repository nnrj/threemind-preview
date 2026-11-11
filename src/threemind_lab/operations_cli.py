"""Schema-discoverable command line over the same authenticated API as the browser."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from .client_auth import client_from_arguments, connection_arguments


def main(argv=None):
    parser = argparse.ArgumentParser(description="ThreeMind shared operations (API / UI / CLI / MCP)")
    parser.add_argument("action", choices=("list", "show", "preflight", "call", "receipt"))
    parser.add_argument("operation", nargs="?")
    connection_arguments(parser)
    parser.add_argument(
        "--arguments", type=Path, help="UTF-8 JSON with path/query/body; keeps shell quoting out of protocols"
    )
    parser.add_argument("--request-id", type=UUID)
    parser.add_argument("--project", type=UUID)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args(argv)
    try:
        with client_from_arguments(args) as client:
            if args.action == "list":
                result = {
                    "schema": client.catalog()["schema"],
                    "operations": [
                        {k: r[k] for k in ("id", "title", "effect", "request_receipt", "human_confirmation")}
                        for r in client.catalog()["operations"]
                    ],
                }
            elif args.action == "show":
                result = {"operation": client.describe(args.operation), "components": client.catalog()["components"]}
            elif args.action == "receipt":
                if args.request_id is None or args.project is None:
                    raise ValueError("receipt requires --project and --request-id")
                result = client.request("GET", f"/api/v2/projects/{args.project}/operation-receipts/{args.request_id}")
            else:
                from threemind_transformer.cli import read

                arguments = json.loads(read(args.arguments, 4 * 1024 * 1024)) if args.arguments else {}
                row = client.describe(args.operation)
                identity = args.request_id or (uuid4() if row["request_receipt"] else None)
                if identity:
                    print(f"request_id={identity}", file=sys.stderr, flush=True)
                if args.action == "preflight":
                    result = client.preflight(args.operation, arguments, request_id=identity)
                else:
                    result = client.call(
                        args.operation, arguments, request_id=identity, output=args.output, maximum=args.max_bytes
                    )
            print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    except (ValueError, TypeError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
