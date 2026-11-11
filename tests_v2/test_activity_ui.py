"""Explicit opt-in browser validation against a disposable database and server."""

import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from test_readouts import delivery

from threemind_core import Config, Engine, Stimulus
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import RunSpec
from threemind_runtime.readout_host import ReadoutHost


@pytest.mark.skipif(
    os.getenv("THREEMIND_VALIDATE_ACTIVITY_UI") != "1", reason="explicit isolated browser acceptance only"
)
def test_activity_reader_desktop_mobile(database):
    root = Path(__file__).resolve().parents[1]
    project = database.create_project({"id": LOCAL_USER}, "时序活动读出验收")["id"]
    engine = Engine(Config(propagation_rate=0, activation_decay_enabled=False, inhibition_gain=0))
    spec = RunSpec(
        environment="manual",
        clock="unbounded",
        config=engine.config.to_dict(),
        activity_readout={"enabled": True, "analysis_version": 2, "max_response_us": 2000000},
    )
    run = database.create_run(project, "独立活动过程", spec.model_dump())
    records = []
    host = ReadoutHost(spec, run["id"], 0, record=records.append)
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.4))))
    host.delivered(delivery(id=str(uuid4()), labels={"1": ["甲"], "2": ["松子"]}))
    for at in range(0, 2100000, 100000):
        engine.advance_to(at)
        host.observe(engine)
    host.close(engine.time_us, "run_ended")
    database.save_checkpoint(
        project,
        run["id"],
        engine.capture_state(),
        expected_revision=0,
        status="completed",
        context={"protocol": spec.model_dump(), "readouts": host.capture()},
        events=records,
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        app = create_app(Settings(database_url=database.test_url, origins=(url,)), database)
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 25
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started, "isolated acceptance server failed to start"
            env = os.environ | {
                "THREEMIND_E2E_URL": url,
                "THREEMIND_ACTIVITY_PROJECT": str(project),
                "THREEMIND_ACTIVITY_RUN": str(run["id"]),
            }
            subprocess.run(
                [shutil.which("node"), "node_modules/@playwright/test/cli.js", "test", "e2e/activity-reader.spec.ts"],
                cwd=root / "threemind-ui",
                env=env,
                check=True,
                timeout=180,
            )
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            assert not thread.is_alive(), "isolated acceptance server did not stop"
