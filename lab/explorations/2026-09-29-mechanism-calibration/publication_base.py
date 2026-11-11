"""Reused versioned-publication helpers; new study and 4 GiB budget.

Adapted from ../2026-09-29-input-rate-and-autonomy/publish.py.
"""

import hashlib
import io
import json
import threading
import time
import zipfile
from contextlib import contextmanager

from common import GIB, HERE, WORK, Study, encoded, read_json

from threemind_lab import notebooks, research_documents
from threemind_lab.database import LOCAL_USER


class Publisher(Study):
    def __init__(self):
        super().__init__()
        self.path = WORK / "publication.json"
        self.state = read_json(self.path) if self.path.exists() else {}
        self.worker = "mechanism-calibration-publication-20260929"

    def remember(self, key, value):
        self.state[key] = json.loads(encoded(value))
        staging = self.path.with_suffix(".tmp")
        staging.write_bytes(encoded(self.state))
        staging.replace(self.path)
        return value

    def guard(self, force=False):
        if not force and time.time() - self.last_check < 15:
            return
        with self.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        if local + max(0, size - self.meta["database_bytes_before"]) > 4 * GIB:
            raise RuntimeError("4 GiB publication budget")
        self.last_check = time.time()

    def note(self, key, title, body):
        if key not in self.state:
            value = notebooks.save_note(
                self.db,
                self.project,
                LOCAL_USER,
                self.identity(key),
                {
                    "operation_id": self.identity(key + ":write"),
                    "expected_revision": 0,
                    "kind": "note",
                    "collection_id": self.meta["notebook_id"],
                    "title": title,
                    "body": {"format": "markdown", "text": body},
                },
            )
            self.remember(key, value)

    @contextmanager
    def owned(self, job_id):
        # Check before admission. This publisher must never execute another project.
        with self.db.tx() as db:
            pending = db.execute("SELECT id FROM jobs WHERE status IN ('pending','leased')").fetchall()
        if any(str(r["id"]) != str(job_id) for r in pending):
            raise RuntimeError("another task is pending; publish later without taking its work")
        with self.db.tx(self.project) as db:
            task = db.execute("SELECT required_features FROM jobs WHERE id=%s", (job_id,)).fetchone()
        cap = {
            "schema": "threemind.worker-capabilities/1",
            "queue": "runtime",
            "scope": "bounded study publication",
            "features": {f: {"state": "available"} for f in task["required_features"]},
        }
        job = self.db.claim(self.worker, capabilities=cap, max_active=1)
        if not job or str(job["id"]) != str(job_id):
            raise RuntimeError("publication lease unavailable; no job executed")
        stop = threading.Event()

        def renew():
            while not stop.wait(15):
                self.db.renew(job)

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield job
        finally:
            stop.set()
            thread.join(timeout=2)

    def archive(self):
        key = "archive"
        if key in self.state and self.state[key].get("artifact_id"):
            return self.state[key]
        path = WORK / "evidence.zip"
        buffer = io.BytesIO()
        entries = [
            p
            for p in WORK.rglob("*")
            if p.is_file()
            and p not in (path, self.path)
            and p.suffix not in (".tmp", ".pyc")
            and "__pycache__" not in p.parts
        ]
        manifest = []
        with zipfile.ZipFile(buffer, "w", allowZip64=True) as z:
            for p in sorted(entries):
                self.guard()
                name = p.relative_to(WORK).as_posix()
                with p.open("rb") as f:
                    sha = hashlib.file_digest(f, "sha256").hexdigest()
                manifest.append({"path": name, "bytes": p.stat().st_size, "sha256": sha})
                z.write(
                    p,
                    name,
                    compress_type=zipfile.ZIP_STORED if p.suffix in (".gz", ".tmt", ".png") else zipfile.ZIP_DEFLATED,
                )
            for p in sorted(HERE.iterdir()):
                if p.is_file() and p.suffix in (".py", ".md"):
                    raw = p.read_bytes()
                    name = "publication-sources/" + p.name
                    manifest.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                    z.writestr(name, raw, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr(
                "archive-manifest.json",
                encoded(
                    {
                        "files": manifest,
                        "model_state_location": "Parent states in parent-state.json.gz; probe snapshots and diagnostic states included. Final checkpoints also reside in the study database, identified by result.json hashes.",
                        "old_data_included": False,
                    }
                ),
                compress_type=zipfile.ZIP_DEFLATED,
            )
        # Verify every member before uploading the in-memory archive.
        with zipfile.ZipFile(buffer) as z:
            manifest = json.loads(z.read("archive-manifest.json"))["files"]
            assert len(z.namelist()) == len(manifest) + 1
            assert set(z.namelist()) == {r["path"] for r in manifest} | {"archive-manifest.json"}
            for member in manifest:
                self.guard()
                assert z.getinfo(member["path"]).file_size == member["bytes"]
                with z.open(member["path"]) as f:
                    assert hashlib.file_digest(f, "sha256").hexdigest() == member["sha256"]
        buffer.seek(0)
        archive_hash = hashlib.sha256(buffer.getbuffer()).hexdigest()
        with self.db.tx() as tx:
            database_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local_bytes = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        if (
            local_bytes + max(0, database_bytes - self.meta["database_bytes_before"]) + buffer.getbuffer().nbytes * 1.1
            > 4 * GIB
        ):
            raise RuntimeError("archive upload would exceed the 4 GiB total with database overhead reserve")
        item = self.state.get(key)
        if not item:
            item = self.remember(
                key,
                {
                    "job_id": self.db.enqueue(
                        self.project,
                        "analysis",
                        {"purpose": "archive intensity novelty and retention evidence; no Core execution"},
                    )["id"]
                },
            )
        with self.owned(item["job_id"]) as job:
            buffer.seek(0)
            artifact = self.db.put_artifact_stream(
                job,
                "mechanism-calibration-evidence.zip",
                "application/zip",
                buffer,
                metadata={"schema": "mechanism-calibration-evidence/1", "study": self.meta["design_sha256"]},
            )
            assert artifact["sha256"] == archive_hash
            self.db.finish(job, result={"artifact_id": str(artifact["id"]), "evidence_archive": True})
        return self.remember(
            key,
            item
            | {
                "artifact_id": str(artifact["id"]),
                "sha256": artifact["sha256"],
                "bytes": artifact["bytes"],
                "verified_members": len(manifest),
                "local_archive_copy": False,
            },
        )

    def document(self, key, kind, title, body, sources=(), blocks=()):
        if key in self.state:
            return self.state[key]["id"]
        value = research_documents.save(
            self.db,
            self.project,
            LOCAL_USER,
            self.identity(key),
            {
                "operation_id": self.identity(key + ":write"),
                "expected_revision": 0,
                "spec": {
                    "kind": kind,
                    "title": title,
                    "sources": list(sources),
                    "blocks": [
                        {"id": "narrative", "type": "commentary", "markdown": body, "section": "results"},
                        *blocks,
                    ],
                },
            },
        )
        self.remember(key, value)
        return value["id"]
