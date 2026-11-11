"""Read-only evidence inventory; no deletion, model advance, or raw-body expansion."""

import hashlib
import json

from run import HERE, META, OLD, WORK, encoded, heads

from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.storage_audit import scan


def index():
    meta = json.loads(META.read_bytes())
    project = meta["project_id"]
    assert set(meta["completed_phases"]) == {"calibration", "memory", "relations"}
    db = Database(Settings.from_env().database_url)
    try:
        assert heads(db, OLD) == meta["old_heads_before"]
        with db.tx(project) as c:
            rows = c.execute(
                "SELECT c.id,c.run_id,c.checkpoint_id,c.source_hash,c.protocol,c.sensor_seed,j.status,j.result FROM probe_calibrations c JOIN jobs j ON j.id=c.job_id WHERE c.project_id=%s ORDER BY c.created_at,c.id",
                (project,),
            ).fetchall()
            artifacts = c.execute(
                "SELECT id,sha256,bytes,name FROM artifacts WHERE project_id=%s", (project,)
            ).fetchall()
            physical = c.execute("SELECT pg_database_size(current_database()) n").fetchone()["n"]
        by_id = {str(a["id"]): a for a in artifacts}
        for row in rows:
            assert row["status"] == "done"
            row["downloads"] = {}
            for key in ["artifact_id", "bundle_artifact_id"]:
                ident = row["result"][key]
                row["downloads"][key] = {**by_id[ident], "url": f"/api/v2/projects/{project}/artifacts/{ident}"}
        data = {
            "project_id": project,
            "old_heads_unchanged": True,
            "calibrations": rows,
            "analysis_phases": {
                name: {"file": file, "sha256": hashlib.sha256((WORK / file).read_bytes()).hexdigest()}
                for name, file in meta["completed_phases"].items()
            },
            "first_failed_attempt": "calibration-results.json; completed measurement retained but not in analysis",
            "archive_note": "each bundle includes all raw activities, actual inputs, source/final model files; URLs require project access",
        }
        (HERE / "evidence-index.json").write_bytes(encoded(data) + b"\n")
        audit = scan(db, project, LOCAL_USER, include_database=True)
        audit["database_growth_bytes"] = physical - meta["database_bytes_before"]
        audit["local_evidence_bytes"] = sum(p.stat().st_size for p in WORK.glob("*.json")) + sum(
            p.stat().st_size for p in HERE.iterdir() if p.is_file()
        )
        (HERE / "storage-audit.json").write_bytes(encoded(audit) + b"\n")
        print(
            encoded(
                {
                    "calibrations": len(rows),
                    "artifacts": len(artifacts),
                    "database_growth_bytes": audit["database_growth_bytes"],
                    "payload_bytes": audit["stored_payload_bytes"],
                    "projection_estimate": audit["network_projection_estimate_bytes"],
                    "local_evidence_bytes": audit["local_evidence_bytes"],
                }
            ).decode()
        )
    finally:
        db.close()


if __name__ == "__main__":
    index()
