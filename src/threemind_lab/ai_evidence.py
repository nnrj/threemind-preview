"""Bounded, revision-correct evidence for external observers. No Core mutation."""

import json

from .database import NotFound
from .inputs import digest


def wire(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False, allow_nan=False))


def checkpoint(db, run_id, checkpoint_id=None):
    row = db.execute(
        "SELECT id,run_id,revision,time_us,state_hash,sequence,context->'recording' AS recording,"
        "context->>'end_us' AS end_us FROM checkpoints WHERE run_id=%s "
        + ("AND id=%s " if checkpoint_id else "")
        + "ORDER BY revision DESC LIMIT 1",
        (run_id, checkpoint_id) if checkpoint_id else (run_id,),
    ).fetchone()
    if row is None:
        raise NotFound("没有可引用的已提交恢复点")
    return wire(row)


def snapshot(db, run_id, checkpoint_id=None, *, config=None, trigger="manual", event_id=None, plan_id=None):
    cp = checkpoint(db, run_id, checkpoint_id)
    result = {
        "schema": "threemind.external-evidence/2",
        "checkpoint": cp,
        "trigger": trigger,
        "source_refs": [f"checkpoint:{cp['id']}"],
        "scope": "committed records at or before BOTH selected simulation time and checkpoint revision",
        "causal_attribution": "not-established; input envelopes anchor observation windows, not causal ownership",
    }
    observations = db.execute(
        "SELECT time_us,sequence,metrics,quality,commit_revision FROM observations WHERE run_id=%s "
        "AND time_us<=%s AND commit_revision<=%s ORDER BY time_us DESC LIMIT 32",
        (run_id, cp["time_us"], cp["revision"]),
    ).fetchall()
    result["metric_samples"] = []
    for observation in reversed(observations):
        ref = f"observation:{run_id}:{observation['time_us']}:{observation['commit_revision']}"
        result["metric_samples"].append(wire(observation) | {"source_ref": ref})
        result["source_refs"].append(ref)
    result["metric_coverage"] = {
        "selection": "latest at most 32 committed samples, chronological; not a complete trajectory",
        "empty_means": "no eligible recorded samples, never zero activation",
        "legacy_commit_unknown_omitted": bool(
            db.execute(
                "SELECT 1 FROM observations WHERE run_id=%s AND time_us<=%s AND commit_revision IS NULL LIMIT 1",
                (run_id, cp["time_us"]),
            ).fetchone()
        ),
    }
    include_active = config is not None and (
        trigger in ("manual", "manual_stimulus", "background_active_nodes")
        or trigger == "repeatable_structure"
        and config.active_nodes_enabled
    )
    events = []
    for kind in ("structural_readout", "temporal_readout"):
        event = db.execute(
            "SELECT id::text AS id,kind,time_us,commit_revision,"
            "jsonb_build_object('source',payload->'source','coverage',payload->'coverage',"
            "'start_us',payload->'start_us','end_us',payload->'end_us','classification',payload->'classification',"
            "'reason',payload->'reason','censored',payload->'censored','candidate_count',payload->'candidate_count',"
            "'state_signature',payload->'structure'->'state_signature',"
            "'recurrence_notice',payload->'structure'->'recurrence_notice',"
            "'occurrences',payload->'structure'->'occurrences',"
            "'source_node_count',payload->'source_node_count','threshold_node_count',payload->'threshold_node_count',"
            "'raw_observation',payload->'raw_observation',"
            "'recorded_active_nodes',jsonb_array_length(payload->'activity_nodes'),"
            "'recorded_temporal_nodes',jsonb_array_length(payload->'nodes'),"
            "'recorded_structure_edges',jsonb_array_length(payload->'structure'->'edges')) AS summary "
            "FROM events WHERE run_id=%s AND kind=%s AND time_us<=%s AND commit_revision<=%s "
            + ("AND id<=%s " if event_id is not None else "")
            + "ORDER BY time_us DESC,id DESC LIMIT 1",
            (run_id, kind, cp["time_us"], cp["revision"]) + ((event_id,) if event_id is not None else ()),
        ).fetchone()
        if event is None:
            continue
        event = wire(event)
        event["source_ref"] = "readout:" + event["id"]
        if kind == "structural_readout" and include_active:
            complete_raw = bool((event["summary"].get("raw_observation") or {}).get("complete"))
            node_array = "raw_nodes" if complete_raw else "activity_nodes"
            nodes = db.execute(
                "SELECT n.value AS node FROM events e CROSS JOIN LATERAL "
                f"jsonb_array_elements(e.payload->'{node_array}') n WHERE e.id=%s AND "
                "(n.value->>'activation')::double precision BETWEEN %s AND %s "
                "ORDER BY (n.value->>'activation')::double precision DESC,(n.value->>'id')::bigint LIMIT %s",
                (event["id"], config.activation_min, config.activation_max, config.max_active_nodes + 1),
            ).fetchall()
            event["active_nodes"] = [row["node"] for row in nodes[: config.max_active_nodes]]
            ids = [str(row["id"]) for row in event["active_nodes"]]
            edges = db.execute(
                "SELECT n.value AS edge FROM events e CROSS JOIN LATERAL "
                "jsonb_array_elements(e.payload->'structure'->'edges') n WHERE e.id=%s "
                "AND n.value->>'source'=ANY(%s) AND n.value->>'target'=ANY(%s) "
                "ORDER BY (n.value->>'weight')::double precision DESC,(n.value->>'source')::bigint,"
                "(n.value->>'target')::bigint LIMIT %s",
                (event["id"], ids, ids, config.max_edges + 1),
            ).fetchall()
            event["edges"] = [row["edge"] for row in edges[: config.max_edges]]
            event["selection"] = {
                "node_source": node_array,
                "scope": "explicitly selected analysis subset; not the full observed state",
                "unfiltered_source_available": complete_raw,
                "exclusion_does_not_mean": "absence of activity, irrelevance, hallucination or lack of internal association",
                "activation_min": config.activation_min,
                "activation_max": config.activation_max,
                "max_active_nodes": config.max_active_nodes,
                "nodes_limited": len(nodes) > config.max_active_nodes,
                "max_edges": config.max_edges,
                "edges_limited": len(edges) > config.max_edges,
                "edge_scope": "only recorded structural-reader edges between selected activity nodes; not full Core graph",
            }
        events.append(event)
        result["source_refs"].append(event["source_ref"])
    result["readouts"] = events
    result["active_detail_requested"] = include_active
    if plan_id is not None:
        plan = db.execute(
            "SELECT id,name,status,protocol_hash,origin,next_step,checkpoint_id,"
            "protocol->'limits' AS limits,protocol->>'mode' AS mode,jsonb_array_length(protocol->'steps') AS step_count "
            "FROM research_plans WHERE id=%s AND run_id=%s",
            (plan_id, run_id),
        ).fetchone()
        if plan is None:
            raise NotFound("受控计划不存在")
        # Each receipt must itself point at a result not newer than the selected boundary.
        operations = db.execute(
            "SELECT o.id,o.ordinal,o.kind,o.status,o.checkpoint_id,o.result_checkpoint_id,"
            "jsonb_build_object('duration_us',o.parameters->'duration_us','intensity',o.parameters->'intensity',"
            "'text_excerpt',left(o.parameters->>'text',800),'text_chars',length(o.parameters->>'text')) AS parameters,"
            "o.result->'metrics' AS metrics,o.result->'target_us' AS target_us,o.result->'envelope_id' AS envelope_id "
            "FROM research_operations o JOIN checkpoints c ON c.id=coalesce(o.result_checkpoint_id,o.checkpoint_id) "
            "WHERE o.plan_id=%s AND o.status='completed' AND c.revision<=%s AND c.time_us<=%s "
            "ORDER BY o.ordinal DESC LIMIT 50",
            (plan_id, cp["revision"], cp["time_us"]),
        ).fetchall()
        result["plan"] = wire(plan) | {
            "source_ref": f"plan:{plan_id}",
            "status_scope": "current at request, not historical replay",
        }
        result["source_refs"].append(f"plan:{plan_id}")
        result["operations"] = [wire(row) | {"source_ref": f"operation:{row['id']}"} for row in reversed(operations)]
        result["source_refs"] += [row["source_ref"] for row in result["operations"]]
        result["operations_scope"] = (
            "latest at most 50 completed receipts, with result time and revision bounded by selection"
        )
    # Dedup is about the supplied observations, excluding identity/time metadata.
    result["readout_signature"] = digest(
        {
            "metrics": [row["metrics"] for row in observations],
            "readouts": [
                {
                    "kind": event["kind"],
                    "summary": {
                        key: value for key, value in event["summary"].items() if key not in ("start_us", "end_us")
                    },
                    "active_nodes": event.get("active_nodes"),
                    "edges": event.get("edges"),
                    "selection": event.get("selection"),
                }
                for event in events
            ],
        }
    )
    return result
