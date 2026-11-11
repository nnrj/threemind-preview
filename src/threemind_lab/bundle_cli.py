import argparse
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from .bundle_transfer import download_file, upload_file
from .config import ROOT
from .operations_client import OperationsClient


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verified experiment file, peer and optional OCI transfer; never auto-resumes"
    )
    parser.add_argument("action", choices=("upload", "download", "copy", "push-oci", "pull-oci"))
    parser.add_argument("--url", default=os.getenv("THREEMIND_API_URL", "http://127.0.0.1:8877"))
    parser.add_argument("--username", default=os.getenv("THREEMIND_API_USERNAME"))
    parser.add_argument("--project", type=UUID)
    parser.add_argument("--bundle", type=UUID)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--request-id", type=UUID)
    parser.add_argument("--target-url")
    parser.add_argument("--target-project", type=UUID)
    parser.add_argument("--target-username", default=os.getenv("THREEMIND_TARGET_USERNAME"))
    parser.add_argument("--reference", help="OCI registry/repository:tag or @sha256:digest")
    args = parser.parse_args(argv)
    try:
        if args.action in ("push-oci", "pull-oci"):
            from .bundle_oci import pull, push

            if not args.file or not args.reference:
                raise ValueError("OCI transfer requires --file and --reference; credentials use oras login")
            result = (push if args.action == "push-oci" else pull)(args.reference, args.file)
        else:
            if not args.project:
                raise ValueError("--project is required")
            password = os.getenv("THREEMIND_API_PASSWORD")
            if args.username and not password:
                password = getpass.getpass("Source password: ")
            with OperationsClient(args.url, username=args.username, password=password) as client:
                if args.action == "upload":
                    if not args.file:
                        raise ValueError("--file is required")
                    rid = args.request_id or uuid4()
                    print(f"request_id={rid}", file=sys.stderr, flush=True)
                    result = upload_file(client, args.project, args.file, rid)
                elif args.action == "download":
                    if not args.bundle or not args.file:
                        raise ValueError("--bundle and --file are required")
                    result = download_file(client, args.project, args.bundle, args.file)
                else:
                    if not args.bundle or not args.target_url or not args.target_project:
                        raise ValueError("peer copy requires --bundle, --target-url and --target-project")
                    target_password = os.getenv("THREEMIND_TARGET_PASSWORD")
                    if args.target_username and not target_password:
                        target_password = getpass.getpass("Destination password: ")
                    directory = Path(os.getenv("THREEMIND_SCRATCH_DIR", ROOT / ".work" / "bundle-temp"))
                    directory.mkdir(parents=True, exist_ok=True)
                    with (
                        tempfile.TemporaryDirectory(dir=directory) as temporary,
                        OperationsClient(
                            args.target_url, username=args.target_username, password=target_password
                        ) as target,
                    ):
                        path = Path(temporary) / f"{args.bundle}.tmexperiment"
                        source = download_file(client, args.project, args.bundle, path)
                        rid = args.request_id or uuid4()
                        print(f"request_id={rid}", file=sys.stderr, flush=True)
                        result = upload_file(target, args.target_project, path, rid) | {"source": source}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
