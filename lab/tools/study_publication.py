"""Publish a bounded Study with public Lab services and a streamed evidence archive."""

import hashlib
import json
import shutil
import threading
import time
import zipfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import psutil

from lab.tools.service_study import GIB, encoded, read_json
from threemind_lab import notebooks, research_documents
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.report_revisions import SHA, revision_notice


class ArchivedStudy:
    """Publication-only access to a frozen study; cannot create/advance cases.

    UI/library changes may occur during a long experiment. Publishing its recorded
    evidence must not replace the recorded implementation or require rerunning it.
    """
    def __init__(self, work):
        from types import SimpleNamespace

        from threemind_lab.config import Settings
        from threemind_lab.database import Database
        self.work = Path(work).resolve()
        self.meta = read_json(self.work / 'platform.json')
        self.project = self.meta['project_id']
        self.settings = SimpleNamespace(**self.meta['settings'])
        self.here = Path(self.settings.sources)
        self.db = Database(Settings.from_env().database_url)
        if (self.work / '.research-records/identity.json').exists():
            from threemind_lab.research_recorder import ResearchRecorder
            from threemind_lab.research_records import ResearchRecords
            self.recorder = ResearchRecorder(self.work, self.project,
                service=ResearchRecords(self.db), actor={'id': LOCAL_USER})
            self.recorder.resume_recording()

    def identity(self, name):
        from uuid import UUID, uuid5
        return str(uuid5(UUID(self.project), name))

    def note(self, key, title, text):
        return notebooks.save_note(self.db, self.project, LOCAL_USER, self.identity(key), {
            'operation_id': self.identity(key + ':write'), 'expected_revision': 0, 'kind':'note',
            'collection_id': self.meta['notebook_id'], 'title':title,
            'body':{'format':'markdown','text':text}})


class Publication:
    def __init__(self, study):
        self.study = study
        self.db, self.project, self.work = study.db, study.project, study.work
        self.path = self.work / "publication.json"
        self.state = read_json(self.path) if self.path.exists() else {}
        self.worker = "study-publication-" + self.project
        self.last_guard = 0
        from threemind_lab.experiment_storage import ExperimentStorage

        self.pool = ExperimentStorage(self.db.blobs.storage)
        self.placement = self.pool.binding(self.work)

    def remember(self, key, value):
        self.state[key] = json.loads(encoded(value))
        staging = self.path.with_suffix(".tmp")
        staging.write_bytes(encoded(self.state))
        staging.replace(self.path)
        return self.state[key]

    def guard(self, *, reserve=0, workspace_write=False):
        if not reserve and time.monotonic() - self.last_guard < 15:
            return
        if psutil.Process().memory_info().rss > 4 * GIB or psutil.virtual_memory().available < 2 * GIB:
            raise RuntimeError("publication memory reserve")
        database_reserve = reserve
        if self.placement:
            if self.pool.guard(*self.placement, reserve if workspace_write else 0) != self.work:
                raise RuntimeError("workspace drive letter changed; reopen the study before publishing")
            if workspace_write:
                database_reserve = 0
        if shutil.disk_usage("C:/").free < 5 * GIB or shutil.disk_usage("E:/").free < 15 * GIB + database_reserve:
            raise RuntimeError("publication disk reserve")
        with self.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(p.stat().st_size for p in self.work.rglob("*") if p.is_file())
        if local + max(0, size - self.study.meta["database_bytes_before"]) + reserve > self.study.settings.storage_hard:
            raise RuntimeError("publication total storage budget")
        self.last_guard = time.monotonic()

    def queue_clear(self, allowed=None):
        with self.db.tx() as tx:
            rows = tx.execute("SELECT id FROM jobs WHERE status IN ('pending','leased')").fetchall()
        if any(str(r["id"]) != str(allowed) for r in rows):
            raise RuntimeError("another job is pending; publication must wait without executing it")

    @contextmanager
    def owned(self, job_id):
        self.queue_clear(job_id)
        with self.db.tx(self.project) as tx:
            row = tx.execute(
                "SELECT required_features FROM jobs WHERE id=%s AND project_id=%s", (job_id, self.project)
            ).fetchone()
        if not row:
            raise RuntimeError("publication job does not belong to this study")
        cap = {
            "schema": "threemind.worker-capabilities/1",
            "queue": "runtime",
            "scope": "bounded study publication",
            "features": {f: {"state": "available"} for f in row["required_features"]},
        }
        job = self.db.claim(self.worker, capabilities=cap, max_active=1)
        if not job or str(job["id"]) != str(job_id):
            raise RuntimeError("publication lease unavailable; no job executed")
        stop, errors = threading.Event(), []

        def renew():
            while not stop.wait(15):
                try:
                    self.db.renew(job)
                except Exception as error:  # noqa: BLE001 -- transfer thread failure to the publishing caller
                    errors.append(error)
                    break

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield job
            if errors:
                raise RuntimeError("publication lease renewal failed") from errors[0]
        finally:
            stop.set()
            thread.join(timeout=2)

    def document(self, key, kind, title, body, *, sources=(), blocks=()):
        if key in self.state:
            return self.state[key]
        value = research_documents.save(
            self.db,
            self.project,
            LOCAL_USER,
            self.study.identity(key),
            {
                "operation_id": self.study.identity(key + ":write"),
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
        result = self.remember(key, value)
        recorder = getattr(self.study, 'recorder', None)
        if recorder:
            recorder.attach({'logical_id': f'document:{result["id"]}:r{result["revision"]}',
                'role': 'report' if kind == 'report' else 'protocol', 'label': title, 'format': 'text/markdown',
                'locator': {'kind': 'document', 'id': str(result['id']), 'revision': result['revision']}})
            recorder.synchronize()
        return result

    def revise_document(
        self, key, body=None, *, reason, date, operation_id, expected_revision,
        expected_parent_hash, language="zh", title=None,
    ):
        """Append to the same published document, preserving every prior revision.

        Fetch the *fixed* parent on retry: the database might have committed even
        if updating publication.json failed. The canonical save operation then
        replays the original result instead of creating another document/version.
        """
        if key not in self.state:
            raise ValueError("publish the original document before requesting a revision")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("a fixed parent revision is required")
        if not isinstance(expected_parent_hash, str) or not SHA.fullmatch(expected_parent_hash):
            raise ValueError("an exact parent content hash is required")
        operation_id = str(UUID(str(operation_id)))
        document_id = self.state[key]["id"]
        parent = research_documents.get(self.db, self.project, document_id, revision=expected_revision)
        if parent["content_hash"] != expected_parent_hash:
            raise Conflict("published parent hash changed; preserve the correction and reload")
        spec = deepcopy(parent["spec"])
        notice = revision_notice(
            edition=expected_revision + 1, parent=expected_revision, date=date,
            reason=reason, language=language, original=f"`{document_id}` r1",
        )
        previous_notice = next((b for b in spec["blocks"] if b["id"] == "revision_notice"), None)
        if previous_notice is not None:
            if previous_notice["type"] != "commentary":
                raise Conflict("the reserved revision notice identifier belongs to a data block")
            spec["blocks"].remove(previous_notice)
        spec["blocks"].insert(0, {
            "id": "revision_notice", "type": "commentary", "section": "other", "markdown": notice,
        })
        if body is not None:
            narrative = next((b for b in spec["blocks"] if b["id"] == "narrative"), None)
            if narrative is None or narrative["type"] != "commentary":
                raise Conflict("this document has no publication narrative block; use the document editor")
            narrative["markdown"] = body
        if title is not None:
            spec["title"] = title
        result = research_documents.save(self.db, self.project, LOCAL_USER, document_id, {
            "operation_id": operation_id, "expected_revision": expected_revision,
            "spec": spec, "review": "draft", "ai_call_id": parent.get("ai_call_id"),
        })
        head = research_documents.get(self.db, self.project, document_id)
        current = {"id": document_id, "revision": head["content_revision"], "content_hash": head["content_hash"]}
        self.state.setdefault("_document_revision_requests", {})[operation_id] = {
            "key": key, "parent": expected_revision, "parent_hash": expected_parent_hash,
            "date": date, "reason": reason, "result": json.loads(encoded(result)),
        }
        self.remember(key, current)
        recorder = getattr(self.study, 'recorder', None)
        if recorder:
            recorder.attach({'logical_id': f'document:{document_id}:r{result["revision"]}',
                'role': 'report' if spec['kind'] == 'report' else 'protocol', 'label': spec['title'],
                'format': 'text/markdown', 'locator': {'kind': 'document', 'id': str(document_id),
                                                     'revision': result['revision']}})
            recorder.synchronize()
        return result

    def note(self, key, title, body):
        if key not in self.state:
            self.remember(key, self.study.note(key, title, body))
        return self.state[key]

    def image(self, name, path):
        self.guard()
        asset_id = self.study.identity(name + ":image")
        notebooks.save_asset(self.db, self.project, LOCAL_USER, asset_id, name + ".png", path.read_bytes())
        return f"![{name}](/api/v2/projects/{self.project}/note-assets/{asset_id})"

    def archive(self, name, *, historical_data_included=False):
        if self.state.get("archive", {}).get("artifact_id"):
            return self.state["archive"]
        path = self.work / "evidence.zip"
        if not path.exists():
            entries = [
                p
                for p in self.work.rglob("*")
                if p.is_file()
                and p not in (path, self.path)
                and p.suffix not in (".tmp", ".pyc")
                and ".partial" not in p.name
                and "__pycache__" not in p.parts
            ]
            self.guard(reserve=sum(p.stat().st_size for p in entries), workspace_write=True)
            manifest = []
            staging = path.with_suffix(f".zip.partial-{time.time_ns()}")
            with zipfile.ZipFile(staging, "x", allowZip64=True) as archive:
                for p in sorted(entries):
                    self.guard()
                    member = p.relative_to(self.work).as_posix()
                    with p.open("rb") as stream:
                        sha = hashlib.file_digest(stream, "sha256").hexdigest()
                    manifest.append({"path": member, "bytes": p.stat().st_size, "sha256": sha})
                    archive.write(
                        p,
                        member,
                        compress_type=zipfile.ZIP_STORED if p.suffix in (".gz", ".png") else zipfile.ZIP_DEFLATED,
                    )
                sources = list(self.study.here.glob("*.py")) + list(self.study.here.glob("*.md"))
                sources.append(Path(__file__))
                for p in sorted(sources):
                    raw = p.read_bytes()
                    member = "publication-sources/" + p.name
                    manifest.append({"path": member, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                    archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED)
                archive.writestr(
                    "archive-manifest.json",
                    encoded({"files": manifest, "historical_data_included": historical_data_included}),
                )
            staging.rename(path)
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("archive-manifest.json"))["files"]
            assert len(archive.namelist()) == len(manifest) + 1
            assert set(archive.namelist()) == {m["path"] for m in manifest} | {"archive-manifest.json"}
            for member in manifest:
                self.guard()
                assert archive.getinfo(member["path"]).file_size == member["bytes"]
                with archive.open(member["path"]) as stream:
                    assert hashlib.file_digest(stream, "sha256").hexdigest() == member["sha256"]
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        self.guard(reserve=int(path.stat().st_size * 1.1))
        item = self.state.get("archive")
        if item is None:
            self.queue_clear()
            item = self.remember(
                "archive",
                {
                    "job_id": self.db.enqueue(
                        self.project, "analysis", {"purpose": "archive registered study evidence; no Core execution"}
                    )["id"]
                },
            )
        with self.owned(item["job_id"]) as job, path.open("rb") as stream:
            artifact = self.db.put_artifact_stream(
                job, name, "application/zip", stream, metadata={"schema": "study-evidence/1", "study": self.study.name}
            )
            assert artifact["sha256"] == sha
            self.db.finish(job, result={"artifact_id": str(artifact["id"]), "evidence_archive": True})
        return self.remember(
            "archive",
            item
            | {
                "artifact_id": str(artifact["id"]),
                "sha256": sha,
                "bytes": artifact["bytes"],
                "verified_members": len(manifest),
            },
        )

    def verify(self):
        for key, item in self.state.items():
            if key.startswith(("report:", "record:")):
                got = research_documents.get(self.db, self.project, item["id"], revision=item["revision"])
                assert got["content_hash"] == item["content_hash"]
        archive = self.state["archive"]
        sha, size = hashlib.sha256(), 0
        with self.db.tx(self.project) as tx, tx.cursor(name="study_archive_verify") as cursor:
            cursor.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (archive["artifact_id"],)
            )
            for row in cursor:
                sha.update(row["body"])
                size += len(row["body"])
        assert sha.hexdigest() == archive["sha256"] and size == archive["bytes"]
        self.guard(reserve=1)
        recorder = getattr(self.study, 'recorder', None)
        if recorder:
            recorder.attach({'logical_id': 'archive:' + archive['artifact_id'], 'role': 'original-archive',
                'label': 'Complete scientific originals', 'format': 'application/zip',
                'sha256': archive['sha256'], 'byte_count': archive['bytes'],
                'locator': {'kind': 'artifact', 'id': archive['artifact_id']}})
            recorder.finalize('completed')
            recorder.synchronize(strict=True)
