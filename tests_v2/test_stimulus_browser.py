"""Opt-in browser acceptance against an owned API and isolated PostgreSQL database."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


@pytest.mark.skipif(os.getenv("THREEMIND_STIMULUS_BROWSER") != "1", reason="explicit local browser acceptance")
def test_stimulus_browser(database, tmp_path):
    root = Path(__file__).parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    address = f"http://127.0.0.1:{port}"
    env = os.environ | {
        "THREEMIND_DATABASE_URL": database.test_url,
        "THREEMIND_ORIGINS": address,
        "THREEMIND_E2E_URL": address,
    }
    with (tmp_path / "api.log").open("w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "threemind_lab.cli", "serve", "--port", str(port)],
            cwd=root,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for _ in range(100):
                try:
                    with urlopen(address + "/api/v2/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if server.poll() is not None:
                        pytest.fail("isolated API exited; inspect test api.log")
                    time.sleep(0.2)
            else:
                pytest.fail("isolated API readiness timeout")
            result = subprocess.run(
                ["node", "node_modules/@playwright/test/cli.js", "test", "e2e/stimulus-spacetime.spec.ts"],
                cwd=root / "threemind-ui",
                env=env,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        finally:
            server.terminate()
            server.wait(timeout=20)
