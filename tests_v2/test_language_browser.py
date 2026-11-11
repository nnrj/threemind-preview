"""Opt-in real browser/worker/database acceptance for the external language instrument."""

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
from threemind_lab.worker import Worker


@pytest.mark.skipif(os.getenv("THREEMIND_VALIDATE_LANGUAGE_UI") != "1", reason="opt-in isolated browser")
def test_dialogue_desktop_mobile(database):
    root = Path(__file__).resolve().parents[1]
    project = database.create_project({"id": LOCAL_USER}, "语言感官验收")["id"]
    worker = Worker(database, name="isolated-language-ui", max_active=1)
    thread = threading.Thread(target=worker.serve, daemon=True)
    thread.start()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(Settings(database_url=database.test_url, origins=(url,)), database), log_level="warning"
            )
        )
        serve = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        serve.start()
        try:
            deadline = time.monotonic() + 25
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started
            subprocess.run(
                [
                    shutil.which("node"),
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "e2e/dialogue.spec.ts",
                    "--output=../.work/browser-results/language",
                ],
                cwd=root / "threemind-ui",
                env=os.environ | {"THREEMIND_E2E_URL": url, "THREEMIND_LANGUAGE_PROJECT": str(project)},
                check=True,
                timeout=240,
            )
        finally:
            worker.stopping = True
            thread.join(timeout=30)
            server.should_exit = True
            serve.join(timeout=15)
            assert not thread.is_alive() and not serve.is_alive()
