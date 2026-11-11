from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_blob_store import claim_export, filesystem

from threemind_core import Engine, Stimulus
from threemind_lab.ai_secrets import SecretBox
from threemind_lab.blob_store import BlobStore, object_chunks
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.protocols import RunSpec
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_backup import create, inspect, restore


@pytest.fixture(params=["filesystem", "s3"])
def backup_blobs(request, tmp_path, monkeypatch):
    if request.param == "filesystem":
        yield filesystem(tmp_path)[0]
        return
    boto3 = pytest.importorskip("boto3")
    server_class = pytest.importorskip("moto.server").ThreadedMotoServer
    from cryptography.fernet import Fernet

    server = server_class(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    try:
        host, port = server.get_host_and_port()
        endpoint = f"http://{host}:{port}"
        client = boto3.client(
            "s3", endpoint_url=endpoint, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
        )
        client.create_bucket(Bucket="backup-isolated")
        client.put_bucket_versioning(Bucket="backup-isolated", VersioningConfiguration={"Status": "Enabled"})
        key = Fernet.generate_key().decode()
        box = SecretBox((key,))
        storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
        target = storage.register_target(
            kind="s3",
            name="local backup emulator",
            configuration={
                "endpoint": endpoint,
                "bucket": "backup-isolated",
                "encrypted_secret": box.seal({"access_key_id": "test", "secret_access_key": "test"}),
            },
        )
        blobs = BlobStore(storage, secret_box=box)
        blobs.set_policy("export", target["id"], expected_revision=0)
        monkeypatch.setenv("THREEMIND_STORAGE_CONTROL", str(storage.control_dir))
        monkeypatch.setenv("THREEMIND_SECRET_KEYS", key)
        yield blobs
    finally:
        server.stop()


@pytest.mark.parametrize("relation_routing", [False, True])
def test_snapshot_and_external_originals_restore_only_new_database(database, tmp_path, backup_blobs, relation_routing):
    pg_bin = Path("D:/Program Files/PostgreSQL/17/bin")
    if not (pg_bin / "pg_dump.exe").exists():
        pytest.skip("PostgreSQL backup utilities not installed")
    params = conninfo_to_dict(database.test_url)
    assert params["dbname"].startswith("tm2_test_db_")
    params.pop("password", None)
    params["user"] = "threemind_test"
    admin_url = make_conninfo(**params)
    database.blobs = backup_blobs
    project = database.create_project({"id": LOCAL_USER}, "isolated backup")["id"]
    run = database.create_run(project, "continuous subject", RunSpec().model_dump())
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.4))))
    engine.advance_to(50000)
    image = engine.capture_state()
    database.save_checkpoint(project, run["id"], image, expected_revision=0)
    job = claim_export(database, project)
    artifact = database.put_artifact(
        job, "backup-evidence.bin", "application/octet-stream", b"unchanged external evidence"
    )
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET status='done',lease_until=NULL WHERE id=%s", (job["id"],))
    backup_dir = tmp_path / "backup"
    explicit_blobs = None if next(iter(backup_blobs.storage.targets()))["kind"] == "s3" else backup_blobs
    receipt = create(
        admin_url,
        backup_dir,
        blobs=explicit_blobs,
        pg_bin=pg_bin,
        key_ids=["test-key-id-only"],
        compression="zstd:3" if relation_routing else None,
    )
    assert receipt["state"] == "complete"
    manifest = inspect(backup_dir)
    assert manifest["keys"] == {"identifiers": ["test-key-id-only"], "included": False}
    with pytest.raises(ValueError, match="not exist"):
        create(admin_url, backup_dir, blobs=database.blobs, pg_bin=pg_bin)
    name = "tm2_test_restore_" + uuid4().hex[:12]
    relation_root = tmp_path / "restore-relation"
    try:
        result = restore(
            admin_url,
            backup_dir,
            name,
            tmp_path / "restored-objects",
            pg_bin=pg_bin,
            relation_roots={"observations": relation_root} if relation_routing else None,
        )
        assert result["state"] == "restored_unactivated"
        if relation_routing:
            with psycopg.connect(make_conninfo(**(params | {"dbname": name}))) as admin:
                assert admin.execute(
                    "SELECT pg_tablespace_location(reltablespace) FROM pg_class WHERE oid='tm2.observations'::regclass"
                ).fetchone()[0] == str(relation_root)
        restored_url = make_conninfo(**(params | {"dbname": name}))
        recovered = Database(restored_url, allow_owner=True)
        try:
            recovered.blobs = BlobStore(restore_projection=tmp_path / "restored-objects/restore.json")
            assert recovered.load_checkpoint(project, run["id"])[1] == image
            assert (
                b"".join(object_chunks(recovered, project, "artifact", artifact["id"]))
                == b"unchanged external evidence"
            )
            with recovered.tx(project) as db:
                assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 1
        finally:
            recovered.close()
        with pytest.raises(ValueError, match="already exists"):
            restore(admin_url, backup_dir, name, tmp_path / "another-isolated-object-root", pg_bin=pg_bin)
    finally:
        assert name.startswith("tm2_test_restore_")
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
            for row in admin.execute(
                "SELECT spcname FROM pg_tablespace WHERE pg_tablespace_location(oid)=%s",
                (str(relation_root),),
            ).fetchall():
                admin.execute(sql.SQL("DROP TABLESPACE {}").format(sql.Identifier(row[0])))
    member = backup_dir / manifest["objects"][0]["path"]
    member.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="corrupt"):
        inspect(backup_dir)


def test_pg_utilities_preserve_explicit_libpq_security(monkeypatch):
    from threemind_lab import storage_backup

    calls = []
    monkeypatch.setattr(
        storage_backup.subprocess, "run", lambda args, **kw: calls.append((args, kw)) or SimpleNamespace(returncode=0)
    )
    storage_backup._pg(
        "host=127.0.0.1 dbname=isolated user=test password=private sslmode=verify-full sslrootcert=roots.pem sslcert=client.pem sslkey=private.pem channel_binding=require connect_timeout=7 options='-c statement_timeout=1000'",
        "pg_dump",
        ["--format=custom"],
    )
    args, kw = calls[0]
    assert "private" not in " ".join(args)
    assert kw["env"]["PGSSLMODE"] == "verify-full"
    assert kw["env"]["PGSSLROOTCERT"] == "roots.pem"
    assert kw["env"]["PGSSLKEY"] == "private.pem"
    assert kw["env"]["PGCHANNELBINDING"] == "require"
    assert kw["env"]["PGCONNECT_TIMEOUT"] == "7"
    assert kw["env"]["PGOPTIONS"] == "-c statement_timeout=1000"
