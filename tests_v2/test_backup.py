"""Real pg_dump/pg_restore on disposable databases, never the workstation."""

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from threemind_core import Engine, Stimulus
from threemind_lab.database import LOCAL_USER, Database


def test_full_database_backup_restores_model_and_projection(database, tmp_path):
    pg_bin = Path(os.getenv("THREEMIND_PG_BIN", r"D:\Program Files\PostgreSQL\17\bin"))
    dump = shutil.which("pg_dump") or str(pg_bin / "pg_dump.exe")
    restore = shutil.which("pg_restore") or str(pg_bin / "pg_restore.exe")
    if not Path(dump).is_file() or not Path(restore).is_file():
        pytest.skip("pg_dump and pg_restore are required for the real backup test")
    with database.tx() as conn:
        original = conn.execute("SELECT current_database() AS name").fetchone()["name"]
    assert original.startswith("tm2_test_")
    project = database.create_project({"id": LOCAL_USER}, "Backup acceptance")
    run = database.create_run(project["id"], "Pending causal events", {})
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.5), (2, 0.8))))
    engine.inject(Stimulus(73000, ((2, 0.3),)))
    engine.advance_to(12345)
    image = engine.capture_state()
    cp = database.save_checkpoint(project["id"], run["id"], image, expected_revision=0, status="paused")
    previous = image.to_dict()
    engine.advance_to(12346)
    image = engine.capture_state()
    cp = database.save_checkpoint(
        project["id"], run["id"], image, expected_revision=1, status="paused", previous=(cp, previous)
    )
    assert cp["storage_format"] == "row-delta/1"
    backup = tmp_path / "research.dump"
    port = conninfo_to_dict(database.test_url)["port"]
    connection = ["-h", "127.0.0.1", "-p", port, "-U", "threemind_test", "--no-password"]
    subprocess.run([dump, *connection, "-d", original, "-Fc", "-f", str(backup)], check=True, capture_output=True)
    target = "tm2_test_restore_" + uuid4().hex[:12]
    with psycopg.connect(
        host="127.0.0.1", port=port, dbname="postgres", user="threemind_test", autocommit=True
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
        try:
            subprocess.run(
                [restore, *connection, "-d", target, "--exit-on-error", str(backup)], check=True, capture_output=True
            )
            restored = Database(database.test_url.rsplit("/", 1)[0] + "/" + target)
            try:
                cp, loaded = restored.load_checkpoint(project["id"], run["id"])
                assert cp["revision"] == 2 and loaded.digest == image.digest
                rows = restored.query_graph(project["id"], run["id"], table="edges")
                assert len(rows["rows"]) == 2
                continued = Engine(state=loaded)
                continued.advance_to(100000)
                engine.advance_to(100000)
                assert continued.capture_state().digest == engine.capture_state().digest
            finally:
                restored.close()
        finally:
            assert target.startswith("tm2_test_restore_")
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target)))
