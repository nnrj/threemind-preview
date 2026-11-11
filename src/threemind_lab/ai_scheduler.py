"""Durable, coalesced external schedules; the model's simulation clock is untouched."""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from . import ai_providers, ai_tools, permissions
from .ai_tool_schema import LabAITools, ToolRequest
from .database import Conflict, Forbidden, NotFound


def due(state, config, sim_us, now):
    if config.cadence_clock == "simulation":
        return sim_us >= int(state["next_sim_us"])
    return now >= datetime.fromisoformat(state["next_host_at"])


def next_trigger(db, run_id, after, config):
    # Read a bounded page. Non-trigger rows advance the cursor too. A selected
    # trigger waits behind the single in-flight request instead of disappearing.
    rows = db.execute(
        "SELECT c.id,c.kind,c.source_class,c.event_id,e.commit_revision,e.time_us,"
        "coalesce((e.payload->'structure'->>'recurrence_notice')::boolean,false) AS recurrent,"
        "coalesce(jsonb_array_length(e.payload->'activity_nodes'),0) AS active_count "
        "FROM conversation_entries c LEFT JOIN events e ON e.id=c.event_id WHERE c.run_id=%s AND c.id>%s "
        "AND (e.id IS NULL OR coalesce(e.payload->>'chat_primary','true')<>'false') ORDER BY c.id LIMIT 100",
        (run_id, after),
    ).fetchall()
    cursor = after
    for row in rows:
        trigger = None
        if row["kind"] == "temporal_readout" and row["source_class"] == "manual" and config.on_manual_stimulus:
            trigger = "manual_stimulus"
        elif row["kind"] == "structural_readout":
            if row["recurrent"] and config.on_repeatable_structure:
                trigger = "repeatable_structure"
            elif row["active_count"] > 0 and config.listen_background_active_nodes:
                trigger = "background_active_nodes"
        if trigger:
            cp = db.execute(
                "SELECT id FROM checkpoints WHERE run_id=%s AND revision=%s", (run_id, row["commit_revision"])
            ).fetchone()
            if cp:
                return {
                    "trigger": trigger,
                    "cursor": row["id"],
                    "event_id": row["event_id"],
                    "checkpoint_id": cp["id"],
                }, cursor
        cursor = row["id"]
    return None, cursor


def process(store, settings, project, run_id, *, now=None):
    token = permissions.actor_context.set(None)
    try:
        return _process(store, settings, project, run_id, now=now)
    finally:
        permissions.actor_context.reset(token)


def _process(store, settings, project, run_id, *, now=None):
    now = now or datetime.now(UTC)
    with store.tx(project) as db:
        run = ai_tools.get_run(db, run_id, lock=True)
        schedule = db.execute("SELECT * FROM ai_tool_schedules WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
        if schedule is None or not schedule["enabled"]:
            return
        saved = ai_tools.get(db, run_id)
        config = LabAITools.model_validate(saved["config"])
        state = schedule["state"]
        terminal = run["status"] in ("completed", "cancelled", "dead", "failed")
        for name, tool in (("environment", config.environment), ("interpreter", config.interpreter)):
            item = state.setdefault(name, {})
            if (not tool.enabled or name == "environment" and not tool.automatic
                    or name == "interpreter" and not any((tool.periodic_enabled, tool.on_manual_stimulus,
                                                          tool.on_repeatable_structure, tool.listen_background_active_nodes))):
                continue
            try:
                ai_providers.restore_scheduled_actor(db, project, item.get("actor_id", saved["actor_id"]),
                    item.get("execution_actor"), purpose="environment" if name == "environment" else "interpretation",
                    provider_id=tool.provider_id, run_id=run_id)
            except (Forbidden, NotFound, ValueError) as error:
                item["last_error"] = str(error)[:1000]
                continue
            pending = item.get("pending")
            if pending:
                call = db.execute(
                    "SELECT c.status,c.result,c.evidence,j.status AS job_status FROM ai_calls c JOIN jobs j ON j.id=c.job_id WHERE c.id=%s",
                    (pending,),
                ).fetchone()
                if call and (
                    call["status"] in ("queued", "sending")
                    or call["status"] == "completed"
                    and not call["result"]
                    and call["job_status"] in ("pending", "leased")
                ):
                    continue
                item["pending"] = None
                if (
                    call
                    and call["status"] == "completed"
                    and call["result"].get("application_status") in ("applied", "recorded")
                ):
                    item["generated"] = item.get("generated", 0) + 1
                    item["last_signature"] = call["evidence"]["snapshot"].get("readout_signature")
                elif call:
                    item["last_error"] = "上次请求未完成工具应用，请查看原始请求记录"
            if terminal:
                continue
            trigger, event_id, checkpoint_id = "periodic", None, None
            selected = None
            if name == "interpreter":
                selected, skipped = next_trigger(db, run_id, item.get("last_trigger_id", 0), tool)
                item["last_trigger_id"] = skipped
                if selected:
                    trigger, event_id, checkpoint_id = (
                        selected["trigger"],
                        selected["event_id"],
                        selected["checkpoint_id"],
                    )
            periodic = (
                (name == "environment" or tool.periodic_enabled)
                and run["status"] in ("running", "queued")
                and due(item, tool, int(run["time_us"]), now)
            )
            if not selected and not periodic:
                continue
            # One periodic request represents the latest observed point. We do
            # not backdate generated stimuli to missed simulated deadlines.
            request_id = uuid5(
                UUID(str(run_id)), f"ai:{saved['revision']}:{name}:{item.get('queued', 0)}:{trigger}:{event_id}"
            )
            try:
                with db.transaction():
                    if name == "interpreter" and tool.deduplicate_readouts:
                        snapshot = ai_tools.ai_evidence.snapshot(
                            db, run_id, checkpoint_id, config=tool, trigger=trigger, event_id=event_id
                        )
                        if snapshot["readout_signature"] == item.get("last_signature"):
                            item["deduplicated"] = item.get("deduplicated", 0) + 1
                            if selected:
                                item["last_trigger_id"] = selected["cursor"]
                            if periodic:
                                ai_tools.set_deadline(item, tool, run_id, int(run["time_us"]), now)
                            continue
                    call = ai_tools.request_in_transaction(
                        store,
                        settings,
                        db,
                        project,
                        run_id,
                        item.get("actor_id", saved["actor_id"]),
                        ToolRequest(
                            request_id=request_id,
                            purpose="environment" if name == "environment" else "interpretation",
                            checkpoint_id=checkpoint_id,
                        ),
                        trigger=trigger,
                        event_id=event_id,
                    )
                item.update(
                    pending=str(call["id"]),
                    last_call_id=str(call["id"]),
                    queued=item.get("queued", 0) + 1,
                    last_error=None,
                )
                if selected:
                    item["last_trigger_id"] = selected["cursor"]
                if periodic:
                    if tool.cadence_clock == "simulation":
                        late = max(0, int(run["time_us"]) - int(item["next_sim_us"]))
                        item["coalesced_intervals"] = item.get("coalesced_intervals", 0) + int(
                            late / max(1, round(item["interval_s"] * 1e6))
                        )
                    ai_tools.set_deadline(item, tool, run_id, int(run["time_us"]), now)
            except (Conflict, NotFound, Forbidden, ValueError) as error:
                item["last_error"] = str(error)[:1000]
                # The eligible trigger is kept for the next poll, with a visible
                # error; permission/configuration changes do not silently eat it.
        db.execute("UPDATE ai_tool_schedules SET state=%s WHERE run_id=%s", (Jsonb(state), run_id))
        if terminal and not any(state.get(name, {}).get("pending") for name in ("environment", "interpreter")):
            db.execute("UPDATE ai_tool_schedules SET enabled=false WHERE run_id=%s", (run_id,))


def tick(store, settings):
    with store.tx() as db:
        selected = db.execute(
            "WITH due AS (SELECT run_id FROM ai_tool_schedules WHERE enabled AND next_poll_at<=now() "
            "ORDER BY next_poll_at FOR UPDATE SKIP LOCKED LIMIT 10) UPDATE ai_tool_schedules s "
            "SET next_poll_at=now()+interval '1 second' FROM due WHERE s.run_id=due.run_id RETURNING s.project_id,s.run_id"
        ).fetchall()
    for row in selected:
        try:
            process(store, settings, row["project_id"], row["run_id"])
        except NotFound:
            pass  # Whole-run cleanup may win after the scheduling-index claim.
