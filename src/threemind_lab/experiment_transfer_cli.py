"""Experiment transfer CLI. Local and authenticated HTTP modes share the same service."""

import argparse
import json
import os
from urllib.parse import quote
from uuid import uuid4

import httpx

from .data_cli import connect, connection
from .experiment_transfers import OPERATIONS
from .operation_receipts import HEADER


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sync, back up, migrate, archive or restore experiment files")
    parser.add_argument(
        "action",
        choices=[
            "list",
            "discover",
            "adopt",
            "import-backup",
            "preview",
            "status",
            "resume",
            "cancel",
            "release",
            *sorted(OPERATIONS),
        ],
    )
    parser.add_argument("--local", action="store_true", help="Use this host without a running API server")
    parser.add_argument("--name", help="Experiment name")
    parser.add_argument("--to", dest="destination", help="Configured destination directory ID")
    parser.add_argument("--directory", help="Directory ID for discovery, adoption or backup import")
    parser.add_argument("--operation", choices=sorted(OPERATIONS), help="Operation to preview")
    parser.add_argument("--backup", help="Backup version ID to import or restore")
    parser.add_argument("--as", dest="restore_as", help="New experiment name for a restored backup")
    parser.add_argument("--job", help="Transfer ID for status, resume, cancel or release")
    connection(parser)
    args = parser.parse_args(argv)
    a = args.action
    try:
        if a in OPERATIONS or a == "preview":
            op = args.operation if a == "preview" else a
            if not op or not args.name or not args.destination:
                raise ValueError("provide the operation, --name and --to")
            body = {
                "operation": op,
                "name": args.name,
                "destination": args.destination,
                "backup": args.backup,
                "restore_as": args.restore_as,
            }
        elif a in ("discover", "adopt", "import-backup"):
            if not args.directory or a != "discover" and not args.name:
                raise ValueError("provide --directory and the selected experiment --name")
            body = {"directory": args.directory}
            if a != "discover":
                body["name"] = args.name
            if a == "import-backup":
                body["backup"] = args.backup
        elif a != "list" and not args.job:
            raise ValueError("provide --job with the transfer ID")
        if args.local:
            from .config import load_env
            from .experiment_storage import ExperimentStorage
            from .experiment_transfers import ExperimentTransfers
            from .research_storage import ResearchStorage

            load_env()
            svc = ExperimentTransfers(
                ExperimentStorage(ResearchStorage(os.getenv("THREEMIND_STORAGE_CONTROL") or None))
            )
            if a in OPERATIONS:
                job = svc.create(**body, job_id=str(args.request_id or uuid4()))
                result = svc.run(job["id"])
            elif a == "list":
                result = svc.catalog()
            elif a in ("preview", "adopt", "import-backup", "discover"):
                result = getattr(svc, a.replace("-", "_"))(**body)
            else:
                result = getattr(svc, {"status": "job", "resume": "run"}.get(a, a))(args.job)
        else:
            base = "/api/v2/storage/experiment-pool/transfers"
            job_path = base + "/jobs/" + quote(args.job or "", safe="")
            headers = {HEADER: str(args.request_id or uuid4())}
            with connect(args) as client:
                if a == "list":
                    result = client.request("GET", base)
                elif a == "discover":
                    result = client.request("GET", base + "/discover", params=body)
                elif a == "status":
                    result = client.request("GET", job_path)
                elif a in ("resume", "cancel", "release"):
                    result = client.request("POST", job_path + "/" + a, body={}, headers=headers)
                else:
                    result = client.request(
                        "POST", base + ("/jobs" if a in OPERATIONS else "/" + a), body=body, headers=headers
                    )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"{exc}\n")
