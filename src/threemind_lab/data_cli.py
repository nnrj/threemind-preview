"""Explicit REST data operations, with local bounded transfer and no auto-resume."""

import argparse
import getpass
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx

from .client_auth import client_from_arguments, connection_arguments
from .operation_receipts import HEADER


def connection(parser):
    connection_arguments(parser, request_id=True)


def connect(args):
    return client_from_arguments(args)


def read_object(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError("JSON input exceeds 4 MiB")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("JSON input must be an object")  # noqa: TRY004 - CLI input diagnostic
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Query, package and explicitly restore research data")
    parser.add_argument(
        "action",
        choices=(
            "list",
            "detail",
            "export-plan",
            "export",
            "bundles",
            "bundle",
            "preflight",
            "import",
            "download",
            "manifest",
            "restore-records",
            "resume-plan",
            "resume",
            "integrity",
            "cleanup-preview",
            "candidates",
            "cleanup",
            "job-status",
            "cancel",
            "object",
        ),
    )
    connection(parser)
    parser.add_argument("--project", type=UUID, required=True)
    parser.add_argument("--kind")
    parser.add_argument("--id")
    parser.add_argument("--bundle", type=UUID)
    parser.add_argument("--plan", type=UUID)
    parser.add_argument("--json", type=Path, help="Selection or filter JSON file")
    parser.add_argument("--file", type=Path, action="append", help="One volume, or repeat for each volume")
    parser.add_argument("--manifest-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--volume", type=int, default=0)
    parser.add_argument("--name", default="Imported data bundle")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--maximum-bytes", type=int, default=8 * 1024**3)
    parser.add_argument(
        "--backend", choices=("native", "reference"), help="Runtime backend; defaults to the deployment setting"
    )
    parser.add_argument("--acknowledge-external-changes", action="store_true")
    parser.add_argument("--token")
    parser.add_argument("--confirm-name")
    args = parser.parse_args(argv)
    try:
        base = f"/api/v2/projects/{args.project}/data"
        identity = args.request_id or uuid4()
        headers = {HEADER: str(identity)}
        if args.action in ("export-plan", "export", "import", "restore-records", "resume", "cleanup", "cancel"):
            print(f"request_id={identity}", file=sys.stderr, flush=True)
        with connect(args) as client:
            if args.action in ("preflight", "import"):
                if not args.file or len(args.file) > 128:
                    raise ValueError("provide one to 128 --file volumes")
                if args.maximum_bytes <= 0 or sum(path.stat().st_size for path in args.file) > args.maximum_bytes:
                    raise ValueError("upload exceeds --maximum-bytes; raise its explicit total budget if appropriate")
                if any(path.stat().st_size > 8 * 1024**3 for path in args.file):
                    raise ValueError("one volume cannot exceed 8 GiB")
                with ExitStack() as stack:
                    files = [
                        ("files", (path.name, stack.enter_context(path.open("rb")), "application/octet-stream"))
                        for path in args.file
                    ]
                    if args.manifest_file:
                        files.append(
                            (
                                "manifest",
                                (
                                    args.manifest_file.name,
                                    stack.enter_context(args.manifest_file.open("rb")),
                                    "application/json",
                                ),
                            )
                        )
                    data = {"operation_id": str(identity), "name": args.name} if args.action == "import" else {}
                    if args.action == "preflight" and args.backend:
                        data["backend"] = args.backend
                    client._prepare_authentication()
                    response = client.client.post(
                        base + "/imports" + ("/preflight" if args.action == "preflight" else ""),
                        files=files,
                        data=data,
                        timeout=3600,
                    )
                    if response.status_code >= 300:
                        raise ValueError(
                            f"HTTP {response.status_code}: {response.json().get('detail', 'upload rejected')}"
                        )
                    result = response.json()
            elif args.action == "list":
                params = read_object(args.json) if args.json else {}
                result = client.request("GET", base, params=params | {"offset": args.offset, "limit": args.limit})
            elif args.action == "detail":
                if not args.kind or not args.id:
                    raise ValueError("--kind and --id are required")
                result = client.request(
                    "GET", base + f"/resources/{quote(args.kind, safe='')}/{quote(args.id, safe='')}"
                )
            elif args.action == "export-plan":
                if not args.json:
                    raise ValueError("--json selection is required")
                result = client.request(
                    "POST",
                    base + "/export-plans",
                    body={"selection": read_object(args.json), "operation_id": str(identity)},
                    headers=headers,
                )
            elif args.action == "export":
                if not args.plan:
                    raise ValueError("--plan is required")
                result = client.request(
                    "POST",
                    base + "/exports",
                    body={"plan_id": str(args.plan), "operation_id": str(identity)},
                    headers=headers,
                )
            elif args.action == "bundles":
                result = client.request("GET", base + "/bundles", params={"offset": args.offset, "limit": args.limit})
            elif args.action == "integrity":
                result = client.request(
                    "GET", base + "/integrity", params={"verify": args.verify, "maximum_bytes": args.maximum_bytes}
                )
            elif args.action == "candidates":
                result = client.request("GET", base + "/blob-candidates", params={"maximum_records": args.limit})
            elif args.action in ("job-status", "cancel"):
                if not args.id:
                    raise ValueError("--id task UUID is required")
                path = base + f"/jobs/{UUID(args.id)}"
                result = (
                    client.request("GET", path)
                    if args.action == "job-status"
                    else client.request("POST", path + "/cancel", body={"operation_id": str(identity)}, headers=headers)
                )
            elif args.action in ("cleanup-preview", "cleanup"):
                if not args.id:
                    raise ValueError("--id upload candidate UUID is required")
                path = base + f"/blob-candidates/{UUID(args.id)}/" + args.action
                if args.action == "cleanup":
                    if not args.token or not args.confirm_name:
                        raise ValueError("human cleanup requires fresh preview --token and exact --confirm-name")
                    result = client.request("POST", path, body={"token": args.token, "confirm_name": args.confirm_name})
                else:
                    result = client.request("GET", path)
            else:
                if not args.bundle:
                    raise ValueError("--bundle is required")
                path = base + f"/bundles/{args.bundle}"
                if args.action == "bundle":
                    result = client.request("GET", path)
                elif args.action == "object":
                    if not args.id:
                        raise ValueError("--id source object is required")
                    result = client.request("GET", path + "/objects/" + quote(args.id, safe=""))
                elif args.action in ("download", "manifest"):
                    if not args.output:
                        raise ValueError("--output is required; existing files are never overwritten")
                    endpoint = path + (f"/volumes/{args.volume}" if args.action == "download" else "/manifest")
                    result = client.request("GET", endpoint, output=args.output, maximum=args.maximum_bytes)
                    if args.action == "download":
                        detail = client.request("GET", path)
                        volume = next((row for row in detail["volumes"] if row["ordinal"] == args.volume), None)
                        if not volume or result["bytes"] != volume["bytes"] or result["sha256"] != volume["sha256"]:
                            raise ValueError("download integrity mismatch; preserve the file for diagnosis")
                elif args.action == "restore-records":
                    result = client.request(
                        "POST", path + "/restore-records", body={"operation_id": str(identity)}, headers=headers
                    )
                elif args.action == "resume-plan":
                    if not args.id:
                        raise ValueError("--id origin object is required")
                    result = client.request(
                        "GET",
                        path + "/resume-plan",
                        params={"object_id": args.id} | ({"backend": args.backend} if args.backend else {}),
                    )
                else:
                    if not args.id:
                        raise ValueError("--id origin object is required")
                    result = client.request(
                        "POST",
                        path + "/resumes",
                        body={
                            "object_id": args.id,
                            "operation_id": str(identity),
                            "name": args.name,
                            "acknowledge_external_changes": args.acknowledge_external_changes,
                        }
                        | ({"backend": args.backend} if args.backend else {}),
                        headers=headers,
                    )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.exit(1, f"{error}\n")


def storage_main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "transfer":
        from .experiment_transfer_cli import main as transfer_main

        return transfer_main(argv[1:])
    if argv and argv[0] == "backup":
        from .storage_backup import main as backup_main

        return backup_main(argv[1:])
    if argv and argv[0] == "pool":
        from .experiment_pool_cli import main as pool_main

        return pool_main(argv[1:])
    parser = argparse.ArgumentParser(
        description="Host storage registration, migration, backups and experiment placement",
        epilog="Use 'storage pool' for placement, 'storage transfer' for experiment files, and 'storage backup' for host backups.",
    )
    parser.add_argument(
        "action",
        choices=(
            "inspect",
            "target",
            "policy",
            "resource-register",
            "resource",
            "plan",
            "status",
            "execute",
            "resume",
            "cancel",
            "verify",
            "activate",
            "rollback",
            "receipt",
            "artifact",
            "artifacts",
            "export",
            "export-status",
            "export-manifest",
            "export-download",
            "root-preview",
            "root-plan",
            "root-execute",
            "root-resume",
            "root-cancel",
            "root-verify",
            "root-rollback",
            "root-status",
            "checkpoint-backend",
            "payload-migrate",
            "seal",
        ),
    )
    connection(parser)
    parser.add_argument("--json", type=Path, help="Canonical request body JSON; credentials use interactive input")
    parser.add_argument("--id")
    parser.add_argument("--category", choices=("media-original", "note-image", "export", "checkpoint"))
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project", type=UUID)
    parser.add_argument("--kind", choices=("artifact", "media", "note-image", "checkpoint", "blob"))
    parser.add_argument("--target")
    parser.add_argument("--backend", choices=("database", "filesystem"))
    parser.add_argument(
        "--local", action="store_true", help="Explicit local administrative command; no HTTP server required"
    )
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--maximum-bytes", type=int, default=8 * 1024**3)
    parser.add_argument("--volume", type=int, default=0)
    parser.add_argument("--s3-credentials", action="store_true", help="Prompt for credentials; encrypt on the server")
    args = parser.parse_args(argv)
    try:
        identity = args.request_id or uuid4()
        body = read_object(args.json) if args.json else {}
        if args.local and not (
            args.action.startswith("root-") or args.action in ("checkpoint-backend", "payload-migrate", "seal")
        ):
            raise ValueError("--local is supported only for root changes, checkpoint-backend, payload-migrate and seal")
        if args.local:
            from .config import Settings
            from .database import LOCAL_USER, Database
            from .storage_root import RootChanges, summary

            settings = Settings.from_env()
            database = Database(settings.database_url, checkpoint_backend=settings.checkpoint_backend)
            try:
                service = RootChanges(database)
                actor = {"id": LOCAL_USER, "admin": True}
                if args.action == "checkpoint-backend":
                    result = service.storage.set_checkpoint_backend(
                        args.backend or body["backend"],
                        expected_revision=args.expected_revision
                        if args.expected_revision is not None
                        else body["expected_revision"],
                    )
                elif args.action in ("payload-migrate", "seal"):
                    from .data_catalog import authorized

                    if not args.project or not args.id:
                        raise ValueError("--project and --id are required")
                    with authorized(database, args.project, LOCAL_USER, write=True):
                        pass
                    if args.action == "seal":
                        result = database.payloads.seal(args.project, UUID(args.id))
                    else:
                        result = database.payloads.migrate(
                            args.project,
                            args.kind or body["kind"],
                            args.id,
                            args.target or body["target_id"],
                            operation_id=identity,
                            actor=LOCAL_USER,
                        )
                elif args.action == "root-preview":
                    result = service.preview(args.destination or body["destination"], actor)
                elif args.action == "root-plan":
                    result = service.plan(
                        args.destination or body["destination"],
                        actor,
                        operation_id=identity,
                        expected_revision=args.expected_revision
                        if args.expected_revision is not None
                        else body["expected_revision"],
                    )
                else:
                    action = args.action.removeprefix("root-")
                    if action in ("execute", "resume"):
                        result = service.execute(UUID(args.id), resume=action == "resume")
                    else:
                        result = getattr(service, action)(UUID(args.id))
                if args.output:
                    with args.output.open("x", encoding="utf-8") as out:
                        json.dump(result, out, ensure_ascii=False, default=str, indent=2)
                print(json.dumps(summary(result), ensure_ascii=False, default=str, indent=2))
                return
            finally:
                database.close()
        if "credentials" in body:
            raise ValueError("credential JSON files are not accepted; use --s3-credentials")
        if args.s3_credentials:
            if args.action != "target":
                raise ValueError("credentials are only accepted for target registration")
            if not args.interactive or not sys.stdin.isatty():
                raise ValueError("S3 credential entry requires explicit --interactive in a terminal")
            body["credentials"] = {
                "access_key_id": getpass.getpass("S3 access key: "),
                "secret_access_key": getpass.getpass("S3 secret key: "),
            }
        base = "/api/v2/storage"
        with connect(args) as client:
            if args.action == "checkpoint-backend":
                body.update(
                    backend=args.backend or body.get("backend"),
                    expected_revision=args.expected_revision
                    if args.expected_revision is not None
                    else body.get("expected_revision"),
                )
                result = client.request("PUT", base + "/checkpoint-backend", body=body, headers={HEADER: str(identity)})
            elif args.action in ("payload-migrate", "seal"):
                if not args.project or not args.id:
                    raise ValueError("--project and --id are required")
                path = f"/api/v2/projects/{args.project}/storage/"
                if args.action == "seal":
                    path += "seals/" + str(UUID(args.id))
                    body = {"operation_id": str(identity)}
                else:
                    path += "payload-migrations"
                    body.update(
                        kind=args.kind or body.get("kind"),
                        object_id=args.id,
                        target_id=args.target or body.get("target_id"),
                        operation_id=str(identity),
                    )
                result = client.request("POST", path, body=body, headers={HEADER: str(identity)})
            elif args.action.startswith("root-"):
                action = args.action.removeprefix("root-")
                if action in ("preview", "plan"):
                    body["destination"] = str(args.destination or body.get("destination", ""))
                    path = base + "/root-changes" + ("/preview" if action == "preview" else "")
                    if action == "plan":
                        body.update(
                            operation_id=str(identity),
                            expected_revision=args.expected_revision
                            if args.expected_revision is not None
                            else body.get("expected_revision", 0),
                        )
                    result = client.request("POST", path, body=body, headers={HEADER: str(identity)})
                else:
                    if not args.id:
                        raise ValueError("--id root-change UUID is required")
                    path = base + "/root-changes/" + str(UUID(args.id))
                    result = (
                        client.request("GET", path)
                        if action == "status"
                        else client.request(
                            "POST",
                            path + "/" + action,
                            body={"operation_id": str(identity)},
                            headers={HEADER: str(identity)},
                        )
                    )
            elif args.action == "inspect":
                result = client.request("GET", base)
            elif args.action == "artifacts":
                result = client.request("GET", base + "/research-artifacts", params=body)
            elif args.action in ("export-status", "export-manifest", "export-download"):
                if not args.id:
                    raise ValueError("--id export UUID is required")
                path = base + f"/data-exports/{UUID(args.id)}"
                if args.action == "export-status":
                    result = client.request("GET", path)
                else:
                    if not args.output:
                        raise ValueError("--output is required; existing evidence is never overwritten")
                    receipt = client.request("GET", path)
                    if args.action == "export-manifest":
                        row = {"bytes": receipt["manifest_bytes"], "sha256": receipt["manifest_sha256"]}
                        path += "/manifest"
                    else:
                        row = next((row for row in receipt["volumes"] if row["ordinal"] == args.volume), None)
                        if row is None:
                            raise ValueError("--volume is not registered in this export")
                        path += f"/volumes/{args.volume}"
                    result = client.request("GET", path, output=args.output, maximum=args.maximum_bytes)
                    if result["bytes"] != row["bytes"] or result["sha256"] != row["sha256"]:
                        raise ValueError(
                            "offline data export download differs from its receipt; preserve for diagnosis"
                        )
            elif args.action in ("resource", "status", "receipt", "artifact"):
                if not args.id:
                    raise ValueError("--id is required")
                endpoint = {
                    "resource": "/resources/",
                    "status": "/migrations/",
                    "receipt": "/operation-receipts/",
                    "artifact": "/research-artifacts/",
                }[args.action]
                path = base + endpoint + quote(args.id, safe="") + ("/content" if args.action == "artifact" else "")
                if args.action == "artifact" and not args.output:
                    raise ValueError("--output is required for artifact bytes")
                result = client.request(
                    "GET", path, output=args.output if args.action == "artifact" else None, maximum=args.maximum_bytes
                )
            else:
                if args.action == "target":
                    path, method = base + "/targets", "POST"
                elif args.action == "policy":
                    if not args.category:
                        raise ValueError("--category is required")
                    path, method = base + "/policies/" + args.category, "PUT"
                elif args.action == "resource-register":
                    path, method = base + "/resources", "POST"
                elif args.action == "plan":
                    path, method = base + "/migrations", "POST"
                    body.setdefault("request_id", str(identity))
                elif args.action == "export":
                    if not args.id:
                        raise ValueError("--id registered research resource is required")
                    path, method = base + "/data-exports", "POST"
                    body.update(resource_id=args.id, operation_id=str(identity))
                else:
                    if not args.id:
                        raise ValueError("--id migration plan is required")
                    path, method = base + f"/migrations/{quote(args.id, safe='')}/{args.action}", "POST"
                    if args.action in ("execute", "resume"):
                        body.setdefault("request_id", str(identity))
                if args.expected_revision is not None:
                    body["expected_revision"] = args.expected_revision
                print(f"request_id={identity}", file=sys.stderr, flush=True)
                result = client.request(method, path, body=body, headers={HEADER: str(identity)})
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.exit(1, f"{error}\n")
