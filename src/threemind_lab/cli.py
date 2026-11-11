from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from .config import ROOT, Settings, load_env


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        from .auth_cli import main as auth_main

        auth_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "records":
        from .records_cli import main as records_main

        records_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] in ("data", "storage", "report-revisions"):
        if sys.argv[1] == "report-revisions":
            from .report_revision_cli import main as delegated_main
        elif sys.argv[1] == "storage":
            from .data_cli import storage_main as delegated_main
        else:
            from .data_cli import main as delegated_main

        delegated_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "language":
        from threemind_transformer.language_cli import main as language_main

        language_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "robot":
        from threemind_runtime.robot_cli import main as robot_main

        robot_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "bundle":
        from .bundle_cli import main as bundle_main

        bundle_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] in ("ops", "experiment"):
        from .operations_cli import main as operations_main

        operations_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="ThreeMind Lab 2")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "workstation"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--host", default="127.0.0.1")
        cmd.add_argument("--port", type=int, default=8877)
    worker_parser = sub.add_parser("worker")
    worker_parser.add_argument("--name")
    worker_parser.add_argument("--queue", choices=("runtime", "ai", "notification"), default="runtime")
    worker_parser.add_argument("--task-family", choices=("all", "playground", "kernel-reference"), default="all")
    worker_parser.add_argument("--backend", choices=("native", "reference"), help="Host execution backend; does not change scientific kernel identity")
    worker_parser.add_argument("--parent-watch", action="store_true", help=argparse.SUPPRESS)
    sub.add_parser("setup-local")
    sub.add_parser("migrate")
    user = sub.add_parser("create-admin")
    user.add_argument("username")
    sub.add_parser("doctor")
    sub.add_parser("auth", help="Protected API login, status, logout and scoped delegation")
    sub.add_parser("compute", help="Probe the configured optional Transformer compute process")
    sub.add_parser("robot", help="Independent robot task, asset and recovery commands")
    sub.add_parser("language", help="Independent language adapters, training and recovery")
    sub.add_parser("ops", help="Shared operation catalog, preflight, calls and durable receipts")
    sub.add_parser("experiment", help="Research operation commands (same contract as ops)")
    sub.add_parser("bundle", help="Verified file, peer and OCI experiment transfer")
    sub.add_parser("data", help="Data inventory, bundles, restoration and integrity")
    sub.add_parser("storage", help="Administrator storage targets, policies and explicit migration")
    sub.add_parser("report-revisions", help="Immutable report editions and revision registration")
    text_input = sub.add_parser("input-text", help="Submit a UTF-8 text carrier through the Lab API")
    from .client_auth import connection_arguments

    connection_arguments(text_input)
    text_input.add_argument("--project", type=UUID, required=True)
    text_input.add_argument("--run", type=UUID, required=True)
    text_input.add_argument("--file", type=Path, required=True)
    text_input.add_argument("--request-id", type=UUID, default=None, help="Reuse this ID after an uncertain response")
    text_input.add_argument("--delay-us", type=int, default=0)
    text_input.add_argument(
        "--preset", choices=("normal", "strong"), help="Text intensity preset; explicit --intensity wins"
    )
    text_input.add_argument(
        "--intensity", type=float, help="Optional text stimulus intensity (0–100); omission preserves the API default"
    )
    args = parser.parse_args()
    load_env()
    if args.command == "compute":
        from .compute_tools import probe_tool

        print(json.dumps(probe_tool(), ensure_ascii=False, indent=2))
        return
    if args.command == "input-text":
        from .input_client import submit_text

        request_id = args.request_id or uuid4()
        print(f"request_id={request_id}", file=sys.stderr, flush=True)
        try:
            result = submit_text(args, request_id)
        except (OSError, ValueError) as error:
            parser.exit(1, f"{error}\n")
        print(json.dumps(result, ensure_ascii=False, default=str))
        return
    if args.command == "setup-local":
        from .bootstrap import setup_existing

        print(json.dumps(setup_existing(), ensure_ascii=False))
        return
    if args.command == "migrate":
        from .database import migrate

        url = os.getenv("THREEMIND_MIGRATION_DATABASE_URL")
        if not url:
            parser.error("THREEMIND_MIGRATION_DATABASE_URL is required")
        migrate(url)
        print("Schema is up to date.")
        return
    if args.command == "workstation" and os.getenv("THREEMIND_MODE", "workstation") == "workstation":
        from .ai_secrets import ensure_local_key

        ensure_local_key()
    settings = Settings.from_env()
    if args.command == "doctor":
        from threemind_runtime import create_engine

        from .database import Database

        db = Database(settings.database_url)
        try:
            db.require_current_schema()
            engine = create_engine(backend=settings.backend)
            print(
                json.dumps(
                    {
                        "database": "connected",
                        "mode": settings.mode,
                        "backend": settings.backend,
                        "engine": engine.metrics(),
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            db.close()
        return
    if args.command in ("worker", "create-admin"):
        from .database import Database

        db = Database(settings.database_url)
        try:
            db.require_current_schema()
            if args.command == "worker":
                from .execution_limits import initialize

                initialize(db, settings)
                if args.queue == "ai":
                    from .ai_worker import AIWorker

                    worker = AIWorker(db, settings, name=args.name)
                elif args.queue == "notification":
                    from .notification_worker import NotificationWorker

                    worker = NotificationWorker(db, settings, name=args.name)
                else:
                    from .worker import Worker

                    worker = Worker(
                        db,
                        backend=args.backend or settings.backend,
                        max_active=settings.max_active_jobs,
                        name=args.name,
                        task_family=args.task_family,
                    )
                import signal

                def stop(signum, frame):
                    worker.stopping = True

                signal.signal(signal.SIGTERM, stop)
                signal.signal(signal.SIGINT, stop)
                if args.parent_watch:
                    # A private pipe survives Windows venv launcher indirection.
                    # EOF also arrives when the parent is killed without finally.
                    import threading

                    def parent_closed():
                        try:
                            while sys.stdin.buffer.read(1):
                                pass
                        finally:
                            worker.stopping = True

                    threading.Thread(target=parent_closed, name="workstation-parent", daemon=True).start()
                try:
                    worker.serve()
                except KeyboardInterrupt:
                    worker.stopping = True
            else:
                from .auth import create_user

                password = getpass.getpass("New administrator password (12+ characters): ")
                if password != getpass.getpass("Repeat password: "):
                    parser.error("passwords differ")
                user = create_user(db, args.username, password, admin=True)
                print("Created administrator:", user["username"])
        finally:
            db.close()
        return
    if settings.mode == "workstation" and args.host not in ("127.0.0.1", "::1", "localhost"):
        parser.error("network access requires THREEMIND_MODE=server and authenticated accounts")
    children = []
    try:
        if args.command == "workstation":
            from .database import Database

            preflight = Database(settings.database_url)
            try:
                preflight.require_current_schema()
            finally:
                preflight.close()
            queues = (
                ["runtime"] * settings.max_active_jobs
                + ["ai"] * settings.max_ai_jobs
                + ["notification"] * settings.max_notification_jobs
            )
            for queue in queues:
                children.append(
                    subprocess.Popen(
                        [sys.executable, "-m", "threemind_lab.cli", "worker", "--queue", queue, "--parent-watch"],
                        cwd=ROOT,
                        stdin=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                )
            if settings.backend == "native" and settings.max_active_jobs > 0:
                # A separate Python worker accepts only explicitly routed
                # reference jobs. It cannot steal historical host-default jobs;
                # database execution limits still bound total active tasks.
                children.append(subprocess.Popen(
                    [sys.executable, "-m", "threemind_lab.cli", "worker", "--queue", "runtime",
                     "--backend", "reference", "--task-family", "kernel-reference", "--parent-watch"],
                    cwd=ROOT, stdin=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                ))
        import uvicorn

        from .api import create_app

        uvicorn.run(
            create_app(settings),
            host=args.host,
            port=args.port,
            proxy_headers=settings.mode == "server",
            ws_max_size=131072,
            ws_max_queue=4,
        )
    finally:
        for child in children:
            # Request a checkpoint and orderly exit, including launcher children.
            if child.stdin:
                child.stdin.close()
        for child in children:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
