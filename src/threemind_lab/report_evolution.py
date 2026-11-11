"""Fixed generation/stage evidence for the existing record/report authoring tools."""

from .database import Conflict, NotFound
from .database_stream import stream_rows
from .evolution_protocol import SELECTION_METRICS

UNITS = {
    "observed_lifetime_s": "simulated seconds",
    "not_dead_at_end": "0 / 1",
    "nodes": "nodes",
    "edges": "connections",
    "activation": "activation units",
    "mean_activation": "activation units / node",
    "active_fraction": "fraction",
    "edge_density": "fraction",
    "mean_weight": "weight units",
    **{key: "model energy units" for key in SELECTION_METRICS if key.startswith("energy_")},
}


def used_by_document(db, spec, *, kinds=("evolution",)):
    from .research_documents import document

    sources = set(spec["sources"])
    for block in spec["blocks"]:
        if block["type"] == "record_block":
            record = document(db, block["record_id"], block["revision"])
            selected = next(b for b in record["spec"]["blocks"] if b["id"] == block["block_id"])
            if selected.get("source"):
                sources.add(selected["source"])
    return bool(
        db.execute(
            "SELECT 1 FROM report_source_requests WHERE id=ANY(%s::uuid[]) AND kind=ANY(%s::text[]) LIMIT 1",
            (list(sources), list(kinds)),
        ).fetchone()
    )


def freeze(db, body):
    campaign = db.execute(
        "SELECT id,name,protocol,protocol_hash,revision FROM evolution_campaigns WHERE id=%s FOR SHARE",
        (body.evolution_id,),
    ).fetchone()
    if not campaign:
        raise NotFound("多代实验不可用。")
    protocol = campaign["protocol"]
    generation, stage = body.evolution_generation, body.evolution_stage
    if generation >= protocol["generations"]:
        raise ValueError("所选代次超出冻结协议。")
    if stage == "selection":
        count = db.execute(
            "SELECT count(*) AS n FROM evolution_selections WHERE campaign_id=%s AND generation=%s",
            (body.evolution_id, generation),
        ).fetchone()["n"]
        expected = protocol["population_size"]
    else:
        if stage == "verification" and generation != protocol["generations"] - 1:
            raise ValueError("独立验证只发生在最终一代。")
        expected = protocol["population_size"] * len(protocol[stage + "_seeds"])
        count = db.execute(
            "SELECT count(*) AS n FROM evolution_members WHERE campaign_id=%s AND generation=%s AND stage=%s AND checkpoint_id IS NOT NULL",
            (body.evolution_id, generation, stage),
        ).fetchone()["n"]
    if count != expected:
        raise Conflict("所选代次和阶段尚未完整固定；等待全部候选完成，不能只采集成功者。")
    metrics = body.metrics or [criterion["metric"] for criterion in protocol["criteria"]]
    if not set(metrics) <= {criterion["metric"] for criterion in protocol["criteria"]}:
        raise ValueError("多代来源只能选择冻结协议已评估的指标。其他原始观测可从对应个体采集。")
    provenance = {
        "campaign_id": str(campaign["id"]),
        "run_name": campaign["name"],
        "campaign_revision": campaign["revision"],
        "protocol": protocol,
        "protocol_hash": campaign["protocol_hash"],
        "generation": generation,
        "stage": stage,
        "expected_rows": expected,
        "criteria": protocol["criteria"],
        "row_unit": "candidate aggregate across selection environments"
        if stage == "selection"
        else "independently born candidate/environment copy",
        "selection_boundary": "complete immutable generation and stage; all candidates, including unselected candidates",
        "inference_boundary": "descriptive evidence; shared ancestry and repeated environment blocks are not independent evolutionary replicates; verification never selects parents",
    }
    return provenance, metrics


def evidence_rows(db, request, coverage):
    selection, provenance = request["selection"], request["provenance"]
    identity = selection["evolution_id"]
    generation, stage = selection["evolution_generation"], selection["evolution_stage"]
    coverage.update(
        complete_generation_stage=True,
        row_unit=provenance["row_unit"],
        inference_boundary=provenance["inference_boundary"],
        unselected_candidates_included=True,
        verification_used_for_selection=False,
    )
    if stage == "selection":
        rows = stream_rows(
            db,
            "SELECT * FROM evolution_selections WHERE campaign_id=%s AND generation=%s ORDER BY slot",
            (identity, generation),
        )
    else:
        rows = stream_rows(
            db,
            "SELECT * FROM evolution_members WHERE campaign_id=%s AND generation=%s AND stage=%s ORDER BY slot,block_index",
            (identity, generation, stage),
        )
    count = 0
    censored = 0
    try:
        for item in rows:
            if stage == "selection":
                raw = item["scores"]
                trace = {key: item[key] for key in ("candidate_version_id", "rank", "selected", "evidence")}
                censored += sum(bool(block.get("lifetime_right_censored")) for block in item["evidence"]["blocks"])
                # The pinned block evidence contains the censoring status for each evaluation.
                label = f"g{generation + 1}/i{item['slot'] + 1}"
            else:
                raw = item["outcome"]["values"]
                trace = {
                    key: item[key]
                    for key in (
                        "run_id",
                        "source_version_id",
                        "checkpoint_id",
                        "state_hash",
                        "environment_seed",
                        "outcome",
                    )
                }
                censored += int(item["outcome"].get("lifetime_right_censored", False))
                label = f"g{generation + 1}/i{item['slot'] + 1}/e{item['block_index'] + 1}"
            count += 1
            yield {
                "time_us": None,
                "label": label,
                "quality": f"complete frozen evolution {stage}",
                "values": raw,
                "provenance": {"generation": generation, "slot": item["slot"], "stage": stage, **trace},
            }
    finally:
        rows.close()
    if count != provenance["expected_rows"]:
        raise Conflict("已固定的多代来源不完整；未保存部分证据。")
    coverage["lifetime_right_censored_blocks"] = censored
