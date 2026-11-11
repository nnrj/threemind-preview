"""Explicit Docker Desktop worker launch for the existing local Lab database."""

import argparse
import os
import subprocess
from urllib.parse import urlsplit, urlunsplit

from threemind_lab.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="threemind-playground:local")
    parser.add_argument("--name", default="threemind-playground-worker")
    parser.add_argument(
        "--database-host", help="Container-reachable PostgreSQL host; localhost becomes host.docker.internal"
    )
    parser.add_argument("--memory", default="6g")
    parser.add_argument("--cpus", type=float, default=2)
    parser.add_argument(
        "--check", action="store_true", help="Only verify sources, device and database schema; claim no work"
    )
    args = parser.parse_args()
    settings = Settings.from_env()
    url = urlsplit(settings.database_url)
    host = args.database_host or (
        "host.docker.internal" if url.hostname in ("localhost", "127.0.0.1", "::1") else url.hostname
    )
    if not host or any(c in host for c in "/@?#") or not 0 < args.cpus <= 1024:
        parser.error("valid database host and positive CPU budget required")
    authority = url.netloc.rsplit("@", 1)[0] + "@" if "@" in url.netloc else ""
    authority += f"[{host}]" if ":" in host else host
    authority += f":{url.port or 5432}"
    container_url = urlunsplit(url._replace(netloc=authority))
    # Pass only the application connection. No admin key, Docker socket, home
    # directory or source checkout is mounted into this runtime worker.
    environment = os.environ | {"THREEMIND_DATABASE_URL": container_url}
    command = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--name",
        args.name,
        "--memory",
        args.memory,
        "--cpus",
        str(args.cpus),
        "--pids-limit",
        "256",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=536870912,mode=1777",
        "--stop-timeout",
        "60",
        "--env",
        "THREEMIND_DATABASE_URL",
        "--env",
        "THREEMIND_MAX_ACTIVE_JOBS=1",
        args.image,
    ]
    if args.check:
        command += [
            "python",
            "-c",
            "from threemind_runtime.playground_assets import probe; from threemind_lab.config import Settings; from threemind_lab.database import Database; print(probe('jax','cpu')); d=Database(Settings.from_env().database_url); d.require_current_schema(); d.close(); print('Database and CPU task worker ready; no jobs claimed')",
        ]
    else:
        command += ["python", "-m", "threemind_lab.cli", "worker", "--name", args.name, "--task-family", "playground"]
    raise SystemExit(subprocess.run(command, env=environment, check=False).returncode)


if __name__ == "__main__":
    main()
