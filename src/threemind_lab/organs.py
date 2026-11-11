"""Passive runtime consumers and export of committed organ observations."""

import json

from threemind_runtime.output_organs import OutputOrgans

from .inputs import digest


def latest(database, project, run_id, after=0):
    """Bound the viewing stream to the newest committed sample per organ."""
    run = database.get_run(project, run_id)
    with database.tx(project, repeatable=True) as db:
        rows = {}
        for key in ("voices", "image"):
            row = db.execute(
                "SELECT id AS sample_id,time_us,payload,commit_revision FROM events "
                "WHERE run_id=%s AND kind='organ_output' AND id>%s AND payload ? %s ORDER BY id DESC LIMIT 1",
                (run_id, after, key),
            ).fetchone()
            if row:
                rows[row["sample_id"]] = row
        advanced = (
            db.execute(
                "SELECT count(*) AS n FROM events WHERE run_id=%s AND kind='organ_output' AND id>%s",
                (run_id, after),
            ).fetchone()["n"]
            if after
            else None
        )
    frames = sorted(rows.values(), key=lambda r: r["sample_id"])
    return {
        "frames": frames,
        "cursor": max(rows, default=after),
        "status": run["status"],
        "enabled": {
            "audio": bool(run["spec"].get("acoustic_output", {}).get("enabled")),
            "image": bool(run["spec"].get("activation_projector", {}).get("enabled")),
        },
        "initial": not after,
        "skipped_samples": max(0, advanced - len(frames)) if advanced is not None else None,
        "scope": "latest-committed-organ-samples; complete evidence remains in the database",
    }


class OrganHost:
    def __init__(self, spec, time_us, record, *, state=None):
        self.timeline = OutputOrgans(spec.acoustic_output, spec.activation_projector, time_us, state=state)
        self.bytes, self.record = 0, record
        self.timeline.output.subscribe("evidence", self.record_payload)

    def observe(self, engine, *, final=False):
        self.timeline.observe(engine, final=final)

    def record_payload(self, payload):
        self.bytes += 2048 + len(payload.get("image", {}).get("gray8_hex", "")) + 160 * len(payload.get("voices", ()))
        self.record(
            {
                "key": f"organs:{payload['time_us']}:{digest(payload)}",
                "kind": "organ_output",
                "time_us": payload["time_us"],
                "payload": payload,
            }
        )


def export_stream(database, project, run_id):
    with database.tx(project) as db, db.cursor(name="organ_export") as cursor:
        cursor.itersize = 20
        cursor.execute(
            "SELECT id AS sample_id,time_us,payload,commit_revision FROM events WHERE run_id=%s AND kind='organ_output' ORDER BY time_us,id",
            (run_id,),
        )
        for row in cursor:
            yield json.dumps(row, default=str, separators=(",", ":"), ensure_ascii=False) + "\n"
