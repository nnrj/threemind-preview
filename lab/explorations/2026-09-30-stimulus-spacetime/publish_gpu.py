"""Archive the separate device acceptance; never rerun or replace the frozen Core study."""

import hashlib
import io
import json
import zipfile
from uuid import UUID, uuid5

from common import ROOT, WORK, encoded, new_json, read_json

from threemind_lab import notebooks, research_documents
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database


def note_body(lang):
    text = (ROOT / f"docs/{lang}/plans/transformer-gpu-acceptance.md").read_text(encoding="utf-8")
    other = "en" if lang == "zh" else "zh"
    return text.replace(
        f"(../../{other}/plans/transformer-gpu-acceptance.md)",
        f"(/docs?doc=docs/{other}/plans/transformer-gpu-acceptance.md)",
    ).replace(
        "(stimulus-intensity-and-spacetime.md)", f"(/docs?doc=docs/{lang}/plans/stimulus-intensity-and-spacetime.md)"
    )


def main():
    result_path = WORK / "gpu-publication.json"
    if result_path.exists():
        raise ValueError("GPU publication is already saved; do not overwrite it")
    meta = read_json(WORK / "platform.json")
    project = meta["project_id"]
    entries = {}
    for name in (
        "transformer-device-20260930",
        "transformer-device-fallback-20260930",
        "transformer-portability-20260930",
    ):
        for path in (ROOT / ".work" / name).iterdir():
            if path.is_file() and path.suffix in (".json", ".tmt"):
                entries[f"{name}/{path.name}"] = path.read_bytes()
    for name in ("scripts/validate-transformer-device.py", "src/threemind_transformer/supervisor.py"):
        entries[name] = (ROOT / name).read_bytes()
    for lang in ("zh", "en"):
        name = f"docs/{lang}/plans/transformer-gpu-acceptance.md"
        entries[name] = (ROOT / name).read_bytes()
    assert sum(map(len, entries.values())) < 2 * 1024**2, "bounded engineering evidence only"
    manifest = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in entries.items()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(entries.items()):
            archive.writestr(name, raw)
        archive.writestr("manifest.json", encoded(manifest))
    raw = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name, item in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == item["sha256"]
    db = Database(Settings.from_env().database_url)
    try:
        # Resume an interrupted publication without duplicating its successful archive.
        with db.tx(project) as tx:
            existing = tx.execute("SELECT * FROM artifacts WHERE name='transformer-device-acceptance.zip'").fetchall()
        assert len(existing) <= 1
        artifact = existing[0] if existing else None
        if artifact is None:
            with db.tx() as tx:
                if tx.execute("SELECT 1 FROM jobs WHERE status IN ('pending','leased') LIMIT 1").fetchone():
                    raise RuntimeError("another job is active; stop without taking its work")
            queued = db.enqueue(project, "analysis", {"purpose": "archive GPU engineering acceptance; no simulation"})
            capabilities = {
                "schema": "threemind.worker-capabilities/1",
                "features": {f: {"state": "available"} for f in queued["required_features"]},
            }
            job = db.claim("stimulus-gpu-publication-20260930", capabilities=capabilities, max_active=1)
            if not job or job["id"] != queued["id"]:
                raise RuntimeError("own publication lease unavailable; no job executed")
            try:
                artifact = db.put_artifact(
                    job,
                    "transformer-device-acceptance.zip",
                    "application/zip",
                    raw,
                    metadata={"engineering_only": True},
                )
                assert artifact["sha256"] == hashlib.sha256(raw).hexdigest()
                db.finish(job, result={"artifact_id": str(artifact["id"]), "no_core_execution": True})
            except Exception as exc:
                db.finish(job, error=str(exc))
                raise
        with db.tx(project) as tx:
            chunks = tx.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (artifact["id"],)
            ).fetchall()
        stored = b"".join(bytes(c["body"]) for c in chunks)
        assert hashlib.sha256(stored).hexdigest() == artifact["sha256"]
        with zipfile.ZipFile(io.BytesIO(stored)) as archive:
            assert json.loads(archive.read("manifest.json")) == manifest
        appendix = f"\n\n[完整设备证据 / Device evidence](/api/v2/projects/{project}/artifacts/{artifact['id']})\n"
        identity = lambda key: uuid5(UUID(project), "gpu-acceptance:" + key)
        notes = {}
        for lang in ("zh", "en"):
            body = note_body(lang) + appendix
            title = "本机 GPU 与 CPU 回退验收" if lang == "zh" else "Local GPU and CPU fallback acceptance"
            value = notebooks.save_note(
                db,
                project,
                LOCAL_USER,
                identity(lang),
                {
                    "operation_id": identity(lang + ":write"),
                    "expected_revision": 0,
                    "kind": "note",
                    "collection_id": meta["notebook_id"],
                    "title": title,
                    "body": {"format": "markdown", "text": body},
                },
            )
            restored = notebooks.note(db, project, LOCAL_USER, identity(lang))
            assert restored["body"]["text"] == body
            notes[lang] = str(value["id"])
        record = research_documents.save(
            db,
            project,
            LOCAL_USER,
            identity("record"),
            {
                "operation_id": identity("record-write"),
                "expected_revision": 0,
                "spec": {
                    "kind": "record",
                    "title": "工程验收：真实 GPU 与 CPU 回退 / Real-device acceptance",
                    "sources": [],
                    "blocks": [
                        {
                            "id": "verification",
                            "type": "commentary",
                            "section": "results",
                            "markdown": note_body("zh") + appendix,
                        }
                    ],
                },
            },
        )
        restored = research_documents.get(db, project, record["id"])
        assert restored["content_hash"] == record["content_hash"]
        result = {
            "project_id": project,
            "artifact_id": str(artifact["id"]),
            "sha256": artifact["sha256"],
            "bytes": artifact["bytes"],
            "readback_verified": True,
            "notes": notes,
            "record_id": str(record["id"]),
            "account_used_percent": 66,
        }
        new_json(result_path, result)
        print(json.dumps(result))
    finally:
        db.close()


if __name__ == "__main__":
    main()
