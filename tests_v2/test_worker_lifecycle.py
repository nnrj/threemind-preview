import os
import subprocess
import sys
import time

from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import RunSpec


def test_workstation_pipe_shutdown_checkpoints_even_during_very_slow_clock(database):
    project = database.create_project({"id": LOCAL_USER}, "Parent lifetime")
    run = database.create_run(
        project["id"],
        "Slow clock",
        RunSpec(
            environment="manual",
            clock="scaled",
            speed=0.000001,
            duration_s=60,
        ).model_dump(),
    )
    database.command(project["id"], run["id"], "checkpoint", {})
    database.enqueue(project["id"], "run", run_id=run["id"])
    process = subprocess.Popen(
        [sys.executable, "-m", "threemind_lab.cli", "worker", "--parent-watch", "--name", "pipe-exit-test"],
        env=os.environ | {"THREEMIND_DATABASE_URL": database.test_url, "THREEMIND_BACKEND": "native"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        # The optional isolated RGB capability probe has a 20-second timeout;
        # slow cold starts must still leave time to test the actual pipe lifecycle.
        deadline = time.monotonic() + 40
        while database.get_run(project["id"], run["id"])["status"] != "running":
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
        # Closing the sole parent write end is the same EOF produced by parent death.
        process.stdin.close()
        process.stdin = None
        _, error = process.communicate(timeout=15)
        assert process.returncode == 0, error.decode(errors="replace")
        row = database.get_run(project["id"], run["id"])
        assert row["status"] == "paused" and row["revision"] >= 1
        assert int(row["time_us"]) == 0  # shutdown did not jump over an unfinished physical wait
    finally:
        if process.stdin:
            process.stdin.close()
            process.stdin = None
        if process.poll() is None:
            process.communicate(timeout=15)
