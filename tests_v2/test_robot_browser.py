"""Opt-in browser acceptance against a disposable DB, worker and local server."""

import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime.robot_templates import robot_templates


@pytest.mark.skipif(os.getenv("THREEMIND_VALIDATE_ROBOT_UI") != "1", reason="opt-in isolated browser")
def test_robot_desktop_mobile(database):
    root = Path(__file__).resolve().parents[1]
    project = database.create_project({"id": LOCAL_USER}, "机器人操作验收")["id"]
    spec = RunSpec(environment="robot", robot_protocol=robot_templates()["custom-arm-reach"], clock="realtime")
    run = database.create_run(project, "暂停的机械臂", spec.model_dump())
    database.enqueue(project, "run", run_id=run["id"])
    database.command(project, run["id"], "pause", {})
    worker = Worker(database, name="isolated-robot-ui")
    worker.once()
    errors = []

    def work():
        try:
            worker.serve()
        except Exception as error:  # noqa: BLE001 -- report worker failures to the owning test
            errors.append(error)

    worker_thread = threading.Thread(target=work, daemon=True)
    worker_thread.start()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        app = create_app(Settings(database_url=database.test_url, origins=(url,)), database)
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 25
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started
            subprocess.run(
                [shutil.which("node"), "node_modules/@playwright/test/cli.js", "test", "e2e/robot.spec.ts"],
                cwd=root / "threemind-ui",
                env=os.environ
                | {
                    "THREEMIND_E2E_URL": url,
                    "THREEMIND_ROBOT_PROJECT": str(project),
                    "THREEMIND_ROBOT_RUN": str(run["id"]),
                },
                check=True,
                timeout=240,
            )
        finally:
            worker.stopping = True
            with database.tx(project) as db:
                active = db.execute(
                    "SELECT id FROM runs WHERE status NOT IN ('completed','cancelled','failed')"
                ).fetchall()
            for row in active:
                database.command(project, row["id"], "cancel", {})
            worker_thread.join(timeout=30)
            server.should_exit = True
            thread.join(timeout=15)
            assert not thread.is_alive() and not worker_thread.is_alive()
            assert not errors, errors
