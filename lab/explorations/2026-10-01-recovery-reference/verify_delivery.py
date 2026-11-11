"""Read back E22 after hibernation without running Core or modifying old evidence."""

import gzip
import hashlib
import json
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from common import ROOT, WORK, new_json, read_json, settings

from lab.tools.study_publication import Publication
from threemind_core import StateImage
from threemind_lab import notebooks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify():
    started = time.monotonic()
    output = WORK / "resume-audit.json"
    if output.exists():
        raise RuntimeError("preserve the existing recovery audit; use a new, dated receipt for a later check")
    meta = read_json(WORK / "platform.json")
    receipt = read_json(WORK / "delivery.json")
    events = read_json(WORK / "power-events-after-study.json")
    resumed = next(e for e in events if e["id"] == 1)
    asleep_at = datetime.fromisoformat(resumed["values"]["SleepTime"]).timestamp()
    assert not any(e["id"] in (41, 6008) for e in events)
    assert sha(WORK / "evidence.zip") == receipt["archive"]["sha256"]

    db = Database(Settings.from_env().database_url)
    try:
        db.require_current_schema()
        # Avoid Study initialization: verification must not create runner revisions or instances.
        publication = Publication(
            SimpleNamespace(db=db, project=meta["project_id"], work=WORK, meta=meta, settings=settings())
        )

        def guard():
            if time.monotonic() - started > 900:
                raise RuntimeError("read-back wall budget exceeded")
            publication.guard()

        with zipfile.ZipFile(WORK / "evidence.zip") as archive:
            manifest = json.loads(archive.read("archive-manifest.json"))["files"]
            names = [m["path"] for m in manifest]
            assert len(names) == len(set(names)) == receipt["archive"]["verified_members"]
            assert set(archive.namelist()) == set(names) | {"archive-manifest.json"}
            local_checked = 0
            for member in manifest:
                guard()
                with archive.open(member["path"]) as stream:
                    assert hashlib.file_digest(stream, "sha256").hexdigest() == member["sha256"]
                assert archive.getinfo(member["path"]).file_size == member["bytes"]
                # The usage monitor is intentionally refreshed after wake. Publication sources
                # are immutable copies inside the archive, not paths beneath WORK.
                if member["path"] != "usage.json" and not member["path"].startswith("publication-sources/"):
                    assert sha(WORK / member["path"]) == member["sha256"], member["path"]
                    local_checked += 1
        print(
            json.dumps({"archive_members_verified": len(manifest), "local_files_verified": local_checked}), flush=True
        )

        cases = sorted((WORK / "cases").rglob("result.json"))
        assert len(cases) == receipt["cases"]
        ids, status = set(), Counter()
        for index, path in enumerate(cases, 1):
            guard()
            row = read_json(path)
            assert not row["extra"].get("failure")
            assert path.stat().st_mtime < asleep_at
            checkpoint, image = db.load_checkpoint(meta["project_id"], row["id"])
            local = StateImage(gzip.decompress((path.parent / "parent-state.json.gz").read_bytes()))
            assert image.digest == local.digest == row["state_sha256"]
            assert checkpoint["context"]["implementation"] == meta["implementation"]
            ids.add(row["id"])
            if index % 256 == 0:
                print(json.dumps({"database_checkpoints_verified": index}), flush=True)
        with db.tx(meta["project_id"]) as tx:
            runs = tx.execute("SELECT id,status FROM runs WHERE project_id=%s", (meta["project_id"],)).fetchall()
            assert {str(r["id"]) for r in runs} == ids
            status.update(r["status"] for r in runs)
            assert not set(status) & {"queued", "running", "blocked", "failed"}
            jobs = tx.execute(
                "SELECT status,count(*) AS n FROM jobs WHERE project_id=%s GROUP BY status", (meta["project_id"],)
            ).fetchall()
            jobs = {r["status"]: r["n"] for r in jobs}
            assert not set(jobs) & {"pending", "leased", "failed"}
            inputs = tx.execute(
                "SELECT status,count(*) AS n FROM input_frames WHERE project_id=%s GROUP BY status",
                (meta["project_id"],),
            ).fetchall()
            inputs = {r["status"]: r["n"] for r in inputs}
            assert inputs == {"delivered": receipt["inputs"]["frames"]}
        assert all((p.parent / "result.json").exists() for p in (WORK / "cases").rglob("parent-state.json.gz"))
        partials = [
            p.relative_to(WORK).as_posix()
            for p in WORK.rglob("*")
            if p.is_file() and (".partial" in p.name or p.suffix == ".tmp")
        ]
        assert not partials
        for name, digest in read_json(WORK / "sources.json").items():
            assert sha(ROOT / name) == digest
        for name, digest in meta["implementation"]["source_files"].items():
            assert sha(ROOT / name) == digest
        publication.verify()
        notes = 0
        for item in publication.state.values():
            if isinstance(item, dict) and item.get("collection_id"):
                got = notebooks.note(db, meta["project_id"], LOCAL_USER, item["id"], revision=item["revision"])
                assert got["content_hash"] == item["content_hash"]
                notes += 1
        stamps = {
            name: datetime.fromtimestamp((WORK / name).stat().st_mtime, UTC).isoformat()
            for name in ("audit.json", "STOP", "delivery.json")
        }
        assert all(datetime.fromisoformat(stamp).timestamp() < asleep_at for stamp in stamps.values())
        result = {
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "power_events": events,
            "completed_before_hibernation": True,
            "artifact_timestamps_utc": stamps,
            "cases": len(cases),
            "run_statuses": dict(status),
            "job_statuses": jobs,
            "input_frame_statuses": inputs,
            "archive_members_verified": len(manifest),
            "local_files_verified": local_checked,
            "archive_sha256": receipt["archive"]["sha256"],
            "database_archive_reports_records_verified": True,
            "published_notes_verified": notes,
            "historical_sources_and_implementation_unchanged": True,
            "partial_files": partials,
            "new_simulations": 0,
            "wall_seconds": time.monotonic() - started,
            "verifier_sha256": sha(__file__),
        }
        new_json(output, result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    verify()
