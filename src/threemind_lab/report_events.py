"""Fixed Lab event evidence. Admission, scheduling and delivery are different facts."""

from datetime import UTC
from uuid import uuid4

from .database import wire_rows
from .notebooks import digest

GROUPS = {
    "all": [],
    "inputs": [
        "sensory_input",
        "input_scheduled",
        "input_rejected",
        "input_delivered",
        "energy_supply",
        "energy_scheduled",
        "energy_delivered",
        "input_modulation",
        "input_modulation_scheduled",
        "input_modulation_delivered",
        "telemetry_session",
    ],
    "interventions": ["intervention", "configuration_changed"],
    "lifecycle": ["phase", "pause", "cancel", "close_inputs", "checkpoint", "research_advance"],
    "readouts": ["structural_readout", "temporal_readout", "organ_output"],
}

# Applied at SQL projection, before large payloads are decoded or sent to the UI.
PREVIEW_FIELDS = "ordinal,time_us::text,label,quality,values,(provenance-'payload'-'recorded_provenance') AS provenance"
FULL_FIELDS = "ordinal,time_us::text,label,quality,values,provenance"


def phase(kind, key, payload):
    if key.startswith("command:"):
        return "processed_command"
    if kind == "configuration_changed":
        return "configuration_commit"
    if kind.endswith("_scheduled") and isinstance(payload, dict) and payload.get("status") == "rejected":
        return "rejected_input"
    if kind.endswith("_scheduled"):
        return "scheduled_input"
    if kind.endswith("_delivered"):
        return "delivered_input"
    if kind == "input_rejected":
        return "rejected_input"
    return "recorded_event"


def evidence_rows(db, request, coverage):
    selection, cp = request["selection"], request["provenance"]["checkpoint"]
    where = "e.run_id=%s AND e.time_us BETWEEN %s AND %s"
    params = [request["run_id"], selection["from_us"], selection["through_us"]]
    for kinds in (GROUPS[selection["event_group"]], selection["event_kinds"]):
        if kinds:
            where += " AND e.kind=ANY(%s)"
            params.append(kinds)
    legacy = db.execute(
        f"SELECT count(*) AS n FROM events e WHERE {where} AND e.commit_revision IS NULL", params
    ).fetchone()["n"]
    coverage.update(
        legacy_commit_unknown_omitted=legacy,
        requested_from_us=selection["from_us"],
        requested_through_us=selection["through_us"],
        evidence_scope="committed Lab event log; not a complete Core propagation trace or pending command queue",
        order="simulation time, then original event ID; not a claim of within-timestamp causal ordering",
        raw_event_payload="preserved in each full source row; omitted from table previews and AI prompts",
        empty_result_means="no committed matching Lab events; not proof of no internal activity",
        command_clock="admitted_at is host UTC; row time_us is processing time in simulation microseconds; do not subtract them",
        event_count_unit="one log entry; scheduling, delivery and command entries can describe the same input",
    )
    with db.cursor(name="report_events_" + uuid4().hex, row_factory=wire_rows) as cursor:
        cursor.itersize = 16
        cursor.execute(
            "SELECT e.id::text,e.event_key,e.time_us::text,e.kind,e.payload,e.commit_revision,e.provenance,"
            "c.id::text AS command_id,c.created_at AS admitted_at "
            "FROM events e LEFT JOIN commands c ON c.run_id=e.run_id AND e.event_key='command:'||c.id::text "
            f"WHERE {where} AND e.commit_revision<=%s ORDER BY e.time_us,e.id",
            [*params, cp["revision"]],
        )
        for row in cursor:
            yield {
                "time_us": row["time_us"],
                "label": row["kind"],
                "quality": phase(row["kind"], row["event_key"], row["payload"]),
                "values": {"event_count": 1},
                "provenance": {
                    "event_id": row["id"],
                    "event_key": row["event_key"],
                    "commit_revision": row["commit_revision"],
                    "command_id": row["command_id"],
                    "admitted_at": row["admitted_at"].astimezone(UTC).isoformat() if row["admitted_at"] else None,
                    "payload": row["payload"],
                    "recorded_provenance": row["provenance"],
                    "payload_hash": digest({"payload": row["payload"], "provenance": row["provenance"]}),
                },
            }


def counts(db, source_id):
    return db.execute(
        "SELECT label,quality AS phase,count(*) AS count,min(time_us)::text AS first_time_us,"
        "max(time_us)::text AS last_time_us FROM report_source_rows WHERE source_id=%s "
        "GROUP BY label,quality ORDER BY label,quality",
        (source_id,),
    ).fetchall()
