"""Local and authenticated HTTP entry points for the same experiment placements."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx

from .data_cli import connect, connection, read_object
from .experiment_storage import ExperimentStorage, component
from .operation_receipts import HEADER


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plan, reserve and inspect experiment disk space")
    parser.add_argument(
        "action",
        choices=(
            "status",
            "configure",
            "preview",
            "reserve",
            "study",
            "path",
            "finish",
            "cancel",
            "archive",
            "verify",
            "extract",
            "download",
        ),
    )
    parser.add_argument("--local", action="store_true", help="Use the host control directory without a server")
    parser.add_argument("--json", type=Path, help="Directory configuration or experiment budget")
    parser.add_argument("--name", help="Reserved experiment name")
    parser.add_argument("--part", help="Named world, batch or volume")
    parser.add_argument("--member", help="Archive file to restore, including its data part prefix")
    parser.add_argument("--output", type=Path, help="New destination for a downloaded volume")
    connection(parser)
    args = parser.parse_args(argv)
    try:
        body = read_object(args.json) if args.json else {}
        action = args.action
        if action in ("configure", "preview", "reserve") and not body:
            raise ValueError("provide --json with the configuration or budget")
        if action not in ("status", "configure", "preview", "reserve"):
            component(args.name)
        if action == "extract" and (not args.member or bool(args.part) == bool(args.output)):
            raise ValueError("provide --member and either a readback --part or a new --output file")
        if args.local:
            from .config import load_env
            from .experiment_volumes import create_archive, export_member, extract_member, verify_archive
            from .research_storage import ResearchStorage

            load_env()
            pool = ExperimentStorage(ResearchStorage(os.getenv("THREEMIND_STORAGE_CONTROL") or None))
            if action == "status":
                result = pool.status()
            elif action in ("configure", "preview", "reserve"):
                result = getattr(pool, action)(**body)
            elif action == "path":
                result = {"path": str(pool.path(args.name, args.part))}
            elif action == "archive":
                result = create_archive(pool, args.name)
            elif action == "verify":
                result = verify_archive(pool, args.name)
            elif action == "extract":
                if args.output:
                    result = export_member(pool, args.name, args.member, args.output)
                else:
                    result = extract_member(pool, args.name, args.part, args.member)
            elif action == "download":
                raise ValueError("use the HTTP download command or open the local volume at its registered path")
            else:
                result = getattr(pool, action)(args.name)
        else:
            base = "/api/v2/storage/experiment-pool"
            study = base + "/studies/" + quote(args.name or "", safe="")
            headers = {HEADER: str(args.request_id or uuid4())}
            with connect(args) as client:
                if action in ("status", "study"):
                    result = client.request("GET", base if action == "status" else study)
                elif action == "configure":
                    result = client.request("PUT", base, body=body, headers=headers)
                elif action in ("preview", "reserve"):
                    result = client.request("POST", base + "/" + action, body=body, headers=headers)
                elif action == "path":
                    result = client.request("GET", study + "/path", params={"part": args.part} if args.part else {})
                elif action == "extract" and args.output:
                    result = client.request(
                        "GET", study + "/member", params={"member": args.member}, output=args.output, maximum=2**53 - 1
                    )
                elif action == "extract":
                    result = client.request(
                        "POST", study + "/extract", body={"part": args.part, "member": args.member}, headers=headers
                    )
                elif action == "download":
                    if not args.output or not args.part:
                        raise ValueError("provide --part and a new --output path")
                    manifest = client.request("GET", study + "/manifest")
                    row = next((v for v in manifest["volumes"] if v["part"] == args.part), None)
                    if row is None:
                        raise ValueError("unknown published volume")
                    result = client.request(
                        "GET",
                        study + "/volumes/" + quote(args.part, safe=""),
                        output=args.output,
                        maximum=row["bytes"],
                        expected_sha256=row["sha256"],
                    )
                else:
                    result = client.request("POST", study + "/" + action, body={}, headers=headers)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, httpx.HTTPError) as error:
        parser.exit(1, f"{error}\n")
