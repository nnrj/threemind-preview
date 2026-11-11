"""Manual consistent PostgreSQL + referenced external-object backup.

The caller supplies a full-reading backup connection, never an application RLS
view. Restore creates a new database and a new external-object tree, and exports
a host-registry projection for explicit installation; it does not switch the
current host or start any consciousness. Encryption keys are deliberately absent.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from .blob_store import BlobStore
from .config import ROOT
from .storage_files import atomic_json, checked_path, file_lock, under_root

SCHEMA = "threemind.storage-backup/1"
COMPRESSED_SCHEMA = "threemind.storage-backup/2"


def _hash(path):
    digest, size = hashlib.sha256(), 0
    with checked_path(path).open("rb") as stream:
        while block := stream.read(1024**2):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


@contextmanager
def _member(destination, row):
    path = under_root(destination, row["path"])
    encoding = row.get("encoding")
    if encoding not in (None, "gzip"):
        raise ValueError("unsupported backup member encoding")
    with gzip.open(path, "rb") if encoding else path.open("rb") as stream:
        yield stream


def _verify_member(destination, row):
    if not row.get("encoding"):
        return _hash(under_root(destination, row["path"]))
    if _hash(under_root(destination, row["path"])) != {
        "sha256": row["stored_sha256"],
        "bytes": row["stored_bytes"],
    }:
        raise ValueError("compressed backup member is missing or corrupt")
    digest, size = hashlib.sha256(), 0
    with _member(destination, row) as stream:
        while block := stream.read(1024**2):
            size += len(block)
            if size > row["bytes"]:
                raise ValueError("decoded backup member exceeds its original size")
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def compact_research(destination):
    """Losslessly encode a complete backup's originals; source data is untouched.

    Publish the new manifest only after decoded hashes pass. Interrupted output
    is disposable, while the old manifest and originals remain readable until
    publication. Cleanup affects redundant members inside this backup only.
    """
    destination = checked_path(destination)
    with file_lock(destination / "research-compaction.lock"):
        manifest = inspect(destination)
        before = json.loads(json.dumps(manifest))
        encoded = {}
        cleanup = manifest.get("research_compaction", {})
        obsolete = {r["path"]: r for r in cleanup.get("pending_cleanup", [])}
        saved = cleanup.get("saved_bytes", 0)
        for row in manifest.get("research_files", []):
            # Keep representations that already have their own compression.
            already_encoded = (
                str(row.get("member", ""))
                .lower()
                .endswith((".gz", ".zip", ".tmind", ".mp4", ".png", ".jpg", ".jpeg", ".webp", ".npz", ".whl"))
            )
            if row.get("encoding") or row["bytes"] < 4096 or already_encoded:
                continue
            if row["path"] not in encoded:
                source = under_root(destination, row["path"])
                if not source.is_relative_to(destination / "research"):
                    raise ValueError("research compaction requires a backup research member")
                output = under_root(destination, row["path"] + ".gz")
                if not output.exists():
                    temporary = output.with_name(output.name + "." + uuid4().hex + ".tmp")
                    try:
                        with source.open("rb") as reader, temporary.open("xb") as sink:
                            with gzip.GzipFile(
                                filename="", fileobj=sink, mode="wb", compresslevel=1, mtime=0
                            ) as writer:
                                shutil.copyfileobj(reader, writer, 1024**2)
                            sink.flush()
                            os.fsync(sink.fileno())
                        temporary.replace(output)
                    finally:
                        temporary.unlink(missing_ok=True)
                stored = _hash(output)
                candidate = row | {
                    "path": output.relative_to(destination).as_posix(),
                    "encoding": "gzip",
                    "stored_sha256": stored["sha256"],
                    "stored_bytes": stored["bytes"],
                }
                if _verify_member(destination, candidate) != {k: row[k] for k in ("sha256", "bytes")}:
                    raise ValueError("compressed backup does not decode to its original bytes")
                if stored["bytes"] < row["bytes"]:
                    encoded[row["path"]] = {
                        key: candidate[key] for key in ("path", "encoding", "stored_sha256", "stored_bytes")
                    }
                    obsolete[row["path"]] = {key: row[key] for key in ("path", "sha256", "bytes")}
                    saved += row["bytes"] - stored["bytes"]
                else:
                    encoded[row["path"]] = {}
                    output.unlink()
            row.update(encoded[row["path"]])
        if obsolete:
            previous = destination / "manifest.before-research-compaction.json"
            if not previous.exists():
                atomic_json(previous, before)
            manifest["schema"] = COMPRESSED_SCHEMA
            manifest["research_compaction"] = {"pending_cleanup": list(obsolete.values()), "saved_bytes": saved}
            atomic_json(destination / "manifest.json", manifest)
            # The published manifest now resolves verified encoded bytes. Do
            # not delete source experiments, another backup or the DB dump.
            current_members = {r["path"] for r in manifest["research_files"]}
            for row in obsolete.values():
                path = under_root(destination, row["path"])
                if row["path"] in current_members or not path.is_relative_to(destination / "research"):
                    raise ValueError("backup compaction cleanup overlaps a current member")
                if path.exists():
                    if _hash(path) != {k: row[k] for k in ("sha256", "bytes")}:
                        raise ValueError("obsolete backup member changed before cleanup")
                    path.unlink()
            manifest["research_compaction"]["pending_cleanup"] = []
            atomic_json(destination / "manifest.json", manifest)
        return {
            "state": "complete",
            "encoded_files": len({r["path"] for r in manifest.get("research_files", []) if r.get("encoding")}),
            "saved_bytes": saved,
            "path": str(destination),
        }


def _pg(url, binary, args, *, pg_bin=None, timeout=None):
    params = conninfo_to_dict(url)
    environment = os.environ.copy()
    for key, var in (
        ("password", "PGPASSWORD"),
        ("host", "PGHOST"),
        ("port", "PGPORT"),
        ("user", "PGUSER"),
        ("dbname", "PGDATABASE"),
        ("hostaddr", "PGHOSTADDR"),
        ("connect_timeout", "PGCONNECT_TIMEOUT"),
        ("options", "PGOPTIONS"),
        ("application_name", "PGAPPNAME"),
        ("sslmode", "PGSSLMODE"),
        ("sslrootcert", "PGSSLROOTCERT"),
        ("sslcert", "PGSSLCERT"),
        ("sslkey", "PGSSLKEY"),
        ("sslcrl", "PGSSLCRL"),
        ("sslcrldir", "PGSSLCRLDIR"),
        ("sslpassword", "PGSSLPASSWORD"),
        ("ssl_min_protocol_version", "PGSSLMINPROTOCOLVERSION"),
        ("ssl_max_protocol_version", "PGSSLMAXPROTOCOLVERSION"),
        ("channel_binding", "PGCHANNELBINDING"),
        ("gssencmode", "PGGSSENCMODE"),
        ("target_session_attrs", "PGTARGETSESSIONATTRS"),
        ("passfile", "PGPASSFILE"),
        ("service", "PGSERVICE"),
    ):
        if key in params:
            environment[var] = params[key]
    executable = str(Path(pg_bin) / (binary + (".exe" if os.name == "nt" else ""))) if pg_bin else binary
    result = subprocess.run(
        [executable, *map(str, args)], env=environment, capture_output=True, timeout=timeout, check=False
    )
    if result.returncode:
        # libpq error text may contain connection details. Keep secrets out of logs.
        raise ValueError(
            f"{binary} failed (exit {result.returncode}); inspect deployment permissions/connection locally"
        )


def create(url, destination, *, blobs=None, pg_bin=None, key_ids=(), compression=None):
    if compression is not None and compression not in ("gzip:1", "gzip:6", "zstd:1", "zstd:3"):
        raise ValueError("unsupported backup compression selection")
    destination = checked_path(destination)
    if destination.exists():
        raise ValueError("backup destination must not exist; originals are never replaced")
    if destination.is_relative_to(ROOT / ".git"):
        raise ValueError("backup cannot live in active Git metadata")
    if blobs is None:
        from .ai_secrets import SecretBox

        blobs = BlobStore(
            secret_box=SecretBox(tuple(k for k in os.getenv("THREEMIND_SECRET_KEYS", "").split(",") if k))
        )
    backup_id = uuid4()
    destination.mkdir(parents=True)
    manifest = {
        "schema": SCHEMA,
        "id": str(backup_id),
        "state": "incomplete",
        "objects": [],
        "keys": {"identifiers": list(key_ids), "included": False},
        "targets": {},
        "source_host": blobs.storage.host_info(),
        "role_restore": "separate administrator operation",
        "research_files": [],
        "control_files": [],
        "compression": compression or "postgresql-default",
    }
    atomic_json(destination / "manifest.json", manifest)
    with psycopg.connect(url, row_factory=dict_row) as connection:
        connection.execute("SET search_path TO tm2,pg_catalog")
        role = connection.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        if not (role["rolsuper"] or role["rolbypassrls"]):
            raise ValueError("full backup needs an explicit BYPASSRLS/full-reading backup account")
        size = connection.execute("SELECT pg_database_size(current_database()) bytes").fetchone()["bytes"]
        external_bytes = connection.execute("SELECT coalesce(sum(bytes),0)::bigint bytes FROM stored_blobs").fetchone()[
            "bytes"
        ]
        research_bytes = 0
        if connection.execute("SELECT to_regclass('tm2.research_record_evidence') present").fetchone()["present"]:
            research_bytes = connection.execute(
                "SELECT coalesce(sum(byte_count),0)::bigint bytes FROM "
                "(SELECT DISTINCT locator,byte_count FROM research_record_evidence WHERE locator->>'kind' IN ('file','package') "
                "AND locator ? 'resource_id') originals"
            ).fetchone()["bytes"]
        # Conservative: compression is not a promise of available disk space.
        manifest["database_physical_bytes"] = size
        if shutil.disk_usage(destination).free < size + external_bytes + research_bytes + 15 * 1024**3:
            raise OSError("backup destination lacks the conservative DB/originals estimate plus 15 GiB reserve")
        # A lease is a durable FK, not an expiring wall-clock assumption. A crashed
        # backup conservatively keeps it until explicit administrative release.
        connection.execute(
            "INSERT INTO blob_backup_leases(backup_id,blob_id,project_id) SELECT %s,id,project_id FROM stored_blobs",
            (backup_id,),
        )
        connection.commit()
        connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = connection.execute("SELECT pg_export_snapshot() AS snapshot").fetchone()["snapshot"]
        rows = connection.execute("SELECT * FROM stored_blobs ORDER BY project_id,id").fetchall()
        if connection.execute("SELECT to_regclass('tm2.blob_location_heads') present").fetchone()["present"]:
            locations = {
                r["blob_id"]: r
                for r in connection.execute(
                    "SELECT v.* FROM blob_location_heads h JOIN blob_location_versions v USING(project_id,blob_id,revision)"
                )
            }
            rows = [
                row
                | ({k: locations[row["id"]][k] for k in ("locator", "version_id")} if row["id"] in locations else {})
                for row in rows
            ]
        research = []
        if connection.execute("SELECT to_regclass('tm2.research_record_evidence') present").fetchone()["present"]:
            research = connection.execute(
                "SELECT DISTINCT locator,sha256,byte_count FROM research_record_evidence WHERE locator->>'kind' IN ('file','package') AND locator ? 'resource_id'"
            ).fetchall()
        registry_before = blobs.storage._load()
        control_before = {}
        for name in ("registry.json", "blob-policies.json", "checkpoint-settings.json"):
            source = blobs.storage.control_dir / name
            if source.exists():
                control_before[name] = source.read_bytes()
        for resource in registry_before["resources"].values():
            if resource.get("member_manifest"):
                name = resource["member_manifest"]["path"]
                control_before[name] = under_root(blobs.storage.control_dir, name).read_bytes()
        # Do not permit a newly published object to enter the snapshot without a
        # matching lease. This is checked before the dump starts.
        leased = connection.execute(
            "SELECT blob_id FROM blob_backup_leases WHERE backup_id=%s", (backup_id,)
        ).fetchall()
        if {r["id"] for r in rows} - {r["blob_id"] for r in leased}:
            raise ValueError("an object was published across the backup boundary; retry a new backup")
        manifest["database_snapshot"] = snapshot
        manifest["schema_versions"] = [
            r["version"] for r in connection.execute("SELECT version FROM schema_version ORDER BY version")
        ]
        _pg(
            url,
            "pg_dump",
            [
                "--format=custom",
                "--snapshot=" + snapshot,
                "--file=" + str(destination / "database.dump"),
                *(["--compress=" + compression] if compression else []),
            ],
            pg_bin=pg_bin,
        )
        connection.rollback()
    # The dump fixes the snapshot; committed leases retain objects during IO.
    for row in rows:
        path = under_root(destination, f"objects/{row['id']}.bin")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            for chunk in blobs.read(row, resolve=False):
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        target = blobs.storage.target(row["locator"]["target_id"], revision=row["locator"]["config_revision"])
        key = target["id"] + ":" + str(target["config_revision"])
        # Encrypted credentials are deployment-private, keys themselves absent.
        manifest["targets"][key] = target
        manifest["objects"].append(
            {
                "id": str(row["id"]),
                "project_id": str(row["project_id"]),
                "path": path.relative_to(destination).as_posix(),
                "locator": row["locator"],
                "version_id": row["version_id"],
                **_hash(path),
            }
        )
    # Exact historical originals, including mixed directories, are backed up by
    # their logical members. Unrelated caches and credentials are never swept in.
    from .data_api import registered_artifacts

    resource_roots = [
        (resource["id"], blobs.storage.resolve_locator(resource["locator"])) for resource in blobs.storage.resources()
    ]
    for entry in registered_artifacts(blobs.storage):
        archive = blobs.storage.repository_root / entry["archive_path"]
        for resource_id, root in resource_roots:
            if archive.is_relative_to(root) and archive != root:
                research.append(
                    {
                        "locator": {"resource_id": resource_id, "member": archive.relative_to(root).as_posix()},
                        "sha256": entry["sha256"],
                        "byte_count": entry["bytes"],
                    }
                )
                break
    seen = set()
    for row in research:
        locator = row["locator"]
        identity = (locator["resource_id"], locator.get("member"))
        if identity in seen:
            continue
        seen.add(identity)
        source = blobs.storage.resolve_member(*identity)
        if not source.is_file():
            raise ValueError("registered backup evidence does not identify an exact regular file")
        path = under_root(destination, "research/" + row["sha256"][:2] + "/" + row["sha256"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with source.open("rb") as reader, path.open("xb") as writer:
                before = os.fstat(reader.fileno())
                shutil.copyfileobj(reader, writer, 1024**2)
                writer.flush()
                os.fsync(writer.fileno())
                after = os.fstat(reader.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("research original changed across backup copy")
        expected = {"sha256": row["sha256"], "bytes": int(row["byte_count"])}
        if _hash(path) != expected or _hash(source) != expected:
            raise ValueError("research original disagrees with its immutable evidence reference")
        manifest["research_files"].append(
            {
                "resource_id": identity[0],
                "member": identity[1],
                "path": path.relative_to(destination).as_posix(),
                **expected,
            }
        )
    if blobs.storage._load() != registry_before:
        raise ValueError("host location registry changed during backup; retain incomplete backup and retry")
    for name, raw in control_before.items():
        if (blobs.storage.control_dir / name).read_bytes() != raw:
            raise ValueError("host control configuration changed during backup")
        path = under_root(destination, "control/" + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        manifest["control_files"].append(
            {"name": name, "path": path.relative_to(destination).as_posix(), **_hash(path)}
        )
    manifest["database"] = {"path": "database.dump", **_hash(destination / "database.dump")}
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    manifest["code_commit"] = result.stdout.strip() if result.returncode == 0 else None
    manifest["state"] = "complete"
    manifest["lease_id"] = str(backup_id)
    atomic_json(destination / "manifest.json", manifest)
    return {
        "id": str(backup_id),
        "path": str(destination),
        "objects": len(rows),
        "state": "complete",
        "leases_retained": True,
    }


def inspect(destination):
    from .storage_files import read_json

    destination = checked_path(destination)
    manifest = read_json(destination / "manifest.json")
    if manifest.get("schema") not in (SCHEMA, COMPRESSED_SCHEMA) or manifest.get("state") != "complete":
        raise ValueError("backup is unsupported or incomplete")
    for row in [
        manifest["database"],
        *manifest["objects"],
        *manifest.get("research_files", []),
        *manifest.get("control_files", []),
    ]:
        if row.get("encoding") and manifest["schema"] != COMPRESSED_SCHEMA:
            raise ValueError("encoded backup requires the explicit version 2 format")
        actual = _verify_member(destination, row)
        if actual != {key: row[key] for key in ("sha256", "bytes")}:
            raise ValueError("backup member is missing or corrupt")
    return manifest


def restore(url, destination, new_database, external_root, *, pg_bin=None, relation_roots=None):
    manifest = inspect(destination)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", new_database) or new_database in (
        "postgres",
        "template0",
        "template1",
        "threemind",
    ):
        raise ValueError("restore requires a new, explicitly named isolated database")
    external_root = checked_path(external_root)
    if external_root.exists():
        raise ValueError("restore external-object root must not exist")
    relation_roots = relation_roots or {}
    placements = {}
    for relation, root in relation_roots.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", relation):
            raise ValueError("restore relation name must be a plain tm2 table name")
        root = checked_path(root)
        if root.exists() or root.is_relative_to(external_root) or external_root.is_relative_to(root):
            raise ValueError("restore relation root must be new and separate from the external-object root")
        if any(root.is_relative_to(p["root"]) or p["root"].is_relative_to(root) for p in placements.values()):
            raise ValueError("restore relation roots must be disjoint")
        placements[relation] = {"name": "tm_restore_" + uuid4().hex[:20], "root": root}
    params = conninfo_to_dict(url)
    if params.get("dbname") == new_database:
        raise ValueError("source/administrative connection cannot be the restore target")
    with psycopg.connect(url, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (new_database,)).fetchone():
            raise ValueError("restore database already exists; no overwrite is supported")
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(new_database)))
    # Failure leaves a visibly incomplete new target; never silently drop it.
    restore_params = params | {"dbname": new_database}
    target_url = psycopg.conninfo.make_conninfo(**restore_params)
    restore_args = ["--dbname=" + new_database, "--exit-on-error", "--no-owner"]
    dump = Path(destination) / "database.dump"
    if placements:
        # Only the new isolated database is routed. The source database and
        # scientific contents are untouched; these are storage-only tablespaces.
        _pg(target_url, "pg_restore", [*restore_args, "--section=pre-data", dump], pg_bin=pg_bin)
        with psycopg.connect(target_url, autocommit=True) as target:
            for relation, placement in placements.items():
                if not target.execute(
                    "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='tm2' AND c.relname=%s AND c.relkind='r'",
                    (relation,),
                ).fetchone():
                    raise ValueError("restore relation was not found in the isolated database")
                placement["root"].mkdir(parents=True)
                target.execute(
                    sql.SQL("CREATE TABLESPACE {} LOCATION {}").format(
                        sql.Identifier(placement["name"]), sql.Literal(str(placement["root"]))
                    )
                )
                target.execute(
                    sql.SQL("ALTER TABLE tm2.{} SET TABLESPACE {}").format(
                        sql.Identifier(relation), sql.Identifier(placement["name"])
                    )
                )
        for section in ("data", "post-data"):
            _pg(target_url, "pg_restore", [*restore_args, "--section=" + section, dump], pg_bin=pg_bin)
    else:
        _pg(target_url, "pg_restore", [*restore_args, dump], pg_bin=pg_bin)
    return _restore_originals(
        destination, manifest, new_database, external_root,
        relation_roots={r: {"name": p["name"], "path": str(p["root"])} for r, p in placements.items()},
        database_restored=True,
    )


def _restore_target_root(external_root, target):
    # A scientific target ID is not a filesystem component. Historical IDs may
    # contain colons, including those created by the backfill adapter on Windows.
    identity = hashlib.sha256(target["id"].encode("utf-8")).hexdigest()
    return under_root(external_root, f"targets/{identity}/{target['config_revision']}")


def _restore_originals(destination, manifest, new_database, external_root, *, relation_roots, database_restored=False):
    external_root = checked_path(external_root)
    with file_lock(external_root.with_name(external_root.name + ".restore-files.lock")):
        return _restore_originals_locked(
            destination, manifest, new_database, external_root,
            relation_roots=relation_roots, database_restored=database_restored,
        )


def _restore_originals_locked(destination, manifest, new_database, external_root, *, relation_roots, database_restored):
    intent = {
        "schema": "threemind.storage-file-restore/1", "backup_id": manifest["id"],
        "database": new_database, "relation_roots": relation_roots,
    }
    intent_path = external_root / "restore.intent.json"
    if intent_path.exists():
        if json.loads(intent_path.read_text(encoding="utf-8")) != intent:
            raise ValueError("external restore directory belongs to a different backup or target")
    elif external_root.exists() and any(external_root.iterdir()):
        raise ValueError("external restore directory is nonempty and has no matching intent")
    external_root.mkdir(parents=True, exist_ok=True)
    atomic_json(intent_path, intent)

    def copy_member(row, output):
        expected = {key: row[key] for key in ("bytes", "sha256")}
        if output.exists():
            if _hash(output) != expected:
                raise ValueError("restored member conflicts with its original hash; no overwrite is supported")
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = under_root(external_root, ".restore-staging/" + hashlib.sha256(str(output).encode()).hexdigest())
        stage.parent.mkdir(parents=True, exist_ok=True)
        # Only this intent's unpublished staging representation is replaceable.
        with _member(Path(destination), row) as source, stage.open("wb") as sink:
            size = 0
            while block := source.read(1024**2):
                size += len(block)
                if size > expected["bytes"]:
                    raise ValueError("restored member exceeds its original size")
                sink.write(block)
            sink.flush()
            os.fsync(sink.fileno())
        if _hash(stage) != expected:
            raise ValueError("restored member failed read-back verification")
        os.link(stage, output)  # Exclusive publication; never replace an existing original.
        stage.unlink()

    targets = {}
    for key, target in manifest["targets"].items():
        projected = json.loads(json.dumps(target))
        directory = _restore_target_root(external_root, target)
        directory.mkdir(parents=True, exist_ok=True)
        projected["kind"] = "filesystem"
        projected["configuration"] = {"path": str(directory)}
        targets[key] = projected
    objects = []
    for row in manifest["objects"]:
        key = row["locator"]["target_id"] + ":" + str(row["locator"]["config_revision"])
        target = targets[key]
        output = under_root(Path(target["configuration"]["path"]), row["locator"]["key"])
        copy_member(row, output)
        objects.append(row | {"restored_path": str(output)})
    # Locations in the immutable restored DB are untouched. The generated host
    # registry rebinds the exact original target IDs/revisions to isolated roots.
    registry = {
        "schema": "threemind.research-storage/1",
        "host_id": manifest["source_host"]["host_id"],
        "resources": {},
        "targets": {},
    }
    controls = {r["name"]: r for r in manifest.get("control_files", [])}
    if "registry.json" in controls:
        registry = json.loads(under_root(Path(destination), controls["registry.json"]["path"]).read_bytes())
        # Rebind every filesystem configuration in the isolated restore only.
        # The original backup and scientific DB locators remain unchanged.
        for record in registry["targets"].values():
            for target in record["versions"].values():
                if target["kind"] == "filesystem":
                    target["configuration"] = {
                        "path": str(_restore_target_root(external_root, target))
                    }
    for key, projected in targets.items():
        target = json.loads(json.dumps(manifest["targets"][key]))
        if target["kind"] == "filesystem":
            target["configuration"] = projected["configuration"]
        record = registry["targets"].setdefault(
            target["id"], {"id": target["id"], "current_revision": 0, "versions": {}}
        )
        record["current_revision"] = max(record["current_revision"], target["config_revision"])
        # Preserve backend identity; S3 locators need an explicit local restore
        # projection reader, not an implicit rewrite of historical metadata.
        record["versions"][str(target["config_revision"])] = target
    from .research_storage import ResearchStorage

    registry_path = external_root / "registry.restore.json"
    if registry_path.exists() and json.loads(registry_path.read_text(encoding="utf-8")) != registry:
        raise ValueError("restored registry changed; no overwrite is supported")
    atomic_json(registry_path, registry)
    projected_storage = ResearchStorage(external_root / "control", repository_root=ROOT)
    # Use a distinct explicit registry file until the operator activates it.
    projected_storage.registry_path = external_root / "registry.restore.json"
    for name, row in controls.items():
        if name.startswith("resource-members/"):
            output = under_root(external_root / "control", name)
            output.parent.mkdir(parents=True, exist_ok=True)
            copy_member(row, output)
    for row in manifest.get("research_files", []):
        output = projected_storage.resolve_member(row["resource_id"], row.get("member"))
        if not output.is_relative_to(external_root):
            raise ValueError("restored research member leaves isolated restore root")
        copy_member(row, output)
    atomic_json(external_root / "registry.restore.json", registry)
    atomic_json(
        external_root / "restore.json",
        {
            "schema": "threemind.storage-restore/1",
            "database": new_database,
            "backup_id": manifest["id"],
            "objects": objects,
            "state": "restored_unactivated" if database_restored else "external_files_restored_unactivated",
            "original_targets": manifest["targets"],
            "relation_roots": relation_roots,
        },
    )
    return {
        "database": new_database,
        "external_root": str(external_root),
        "objects": len(objects),
        "state": "restored_unactivated" if database_restored else "external_files_restored_unactivated",
        "registry": str(external_root / "registry.restore.json"),
        "relation_roots": relation_roots,
    }


def restore_external(destination, new_database, external_root, *, relation_roots=None):
    """Resume only a claimed external-file tree; never create or restore a DB.

    The caller must separately verify the database phase. This receipt expressly
    does not claim database restoration, activation or whole-system recovery.
    """
    manifest = inspect(destination)
    external_root = checked_path(external_root)
    intent_path = external_root / "restore.intent.json"
    if relation_roots is None and intent_path.exists():
        relation_roots = json.loads(intent_path.read_text(encoding="utf-8"))["relation_roots"]
    return _restore_originals(
        destination, manifest, new_database, external_root, relation_roots=relation_roots or {},
    ) | {"database_checked": False}


def main(argv=None):
    from .config import load_env

    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("create")
    a.add_argument("destination", type=Path)
    a.add_argument("--key-id", action="append", default=[])
    a.add_argument("--compression", choices=("gzip:1", "gzip:6", "zstd:1", "zstd:3"))
    b = sub.add_parser("inspect")
    b.add_argument("destination", type=Path)
    b = sub.add_parser("compact-research")
    b.add_argument("destination", type=Path)
    c = sub.add_parser("restore")
    c.add_argument("destination", type=Path)
    c.add_argument("--new-database", required=True)
    c.add_argument("--external-root", required=True, type=Path)
    c.add_argument(
        "--relation-root",
        action="append",
        default=[],
        metavar="TABLE=PATH",
        help="Explicit storage-only tablespace for a tm2 table in the new isolated database",
    )
    d = sub.add_parser("restore-files")
    d.add_argument("destination", type=Path)
    d.add_argument("--new-database", required=True, help="Identity only; this command does not operate on the database")
    d.add_argument("--external-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "inspect":
        value = inspect(args.destination)
        result = {"state": value["state"], "objects": len(value["objects"]), "id": value["id"], "keys_included": False}
    elif args.command == "compact-research":
        result = compact_research(args.destination)
    elif args.command == "restore-files":
        result = restore_external(args.destination, args.new_database, args.external_root)
    else:
        url = os.getenv("THREEMIND_BACKUP_DATABASE_URL")
        if not url:
            parser.error("set THREEMIND_BACKUP_DATABASE_URL locally for the explicitly authorized backup administrator")
        if args.command == "create":
            result = create(
                url, args.destination, pg_bin=args.pg_bin, key_ids=args.key_id, compression=args.compression
            )
        else:
            roots = {}
            for value in args.relation_root:
                relation, separator, path = value.partition("=")
                if not separator or not path or relation in roots:
                    parser.error("--relation-root needs a unique TABLE=PATH")
                roots[relation] = path
            result = restore(
                url,
                args.destination,
                args.new_database,
                args.external_root,
                pg_bin=args.pg_bin,
                relation_roots=roots,
            )
    print(json.dumps(result, ensure_ascii=False))
