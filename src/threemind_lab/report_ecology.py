"""Immutable whole-population evidence, with explicit model and physical times."""

from .database import Conflict, NotFound
from .database_stream import closing_iterator, stream_rows
from .measurements import ENERGY_METRICS, energy_endpoints

KINDS = ("ecology_trajectory", "ecology_members")
POPULATION_UNITS = {
    **dict.fromkeys(
        (
            "individuals",
            "living_bodies",
            "viable_cores",
            "births",
            "body_failures",
            "deferred_population",
            "deferred_budget",
        ),
        "count",
    ),
    "maximum_generation": "generation (founders = 0)",
    "physical_time_s": "physical simulated seconds",
    **dict.fromkeys(
        ("resource_initial_external", "resource_regenerated", "resource_remaining", "resource_spent"),
        "body resource units (not Core energy)",
    ),
}
MEMBER_UNITS = {
    "body_alive": "0 / 1 at physical boundary",
    "core_not_dead": "0 / 1 at model boundary (includes waiting)",
    "body_reserve": "body resource units (not Core energy)",
    "body_damage": "body damage units",
    "generation": "generation (founders = 0)",
    "offspring_count": "actual offspring born by this checkpoint",
    "observed_age_s": "global seconds since birth (not lifetime)",
    "core_observed_time_s": "Core simulated seconds (stops at observed death)",
    "nodes": "nodes",
    "edges": "connections",
    "activation": "activation units",
    "mean_weight": "weight units",
    "active_fraction": "fraction",
    **dict.fromkeys(ENERGY_METRICS, "model energy units"),
}
INFERENCE_BOUNDARY = (
    "Descriptive ecological evidence, including nonreproducing and dead individuals. "
    "Shared worlds, shared ancestry and repeated checkpoints are not independent experimental replicates. "
    "Body failure, Core death, job failure/cancellation and observation ending differ. "
    "Waiting is not Core death and not evidence of consciousness. Body states refer to the saved physical boundary, "
    "which can lead model time with inputs pending delivery. Observed age is not survival duration. "
    "Resource units are external body accounting, not Core energy, rewards or a consciousness quality score."
)


def freeze(db, body):
    campaign = db.execute(
        "SELECT id,name,protocol,protocol_hash,checkpoint_id FROM ecology_campaigns WHERE id=%s FOR SHARE",
        (body.ecology_id,),
    ).fetchone()
    if campaign is None:
        raise NotFound("生态训练不可用。")
    cp = db.execute(
        "SELECT id,revision,time_us,state_hash,status,observation->'population' AS population "
        "FROM ecology_checkpoints WHERE campaign_id=%s AND id=%s",
        (body.ecology_id, body.ecology_checkpoint_id or campaign["checkpoint_id"]),
    ).fetchone()
    if cp is None:
        raise Conflict("请选择该生态训练已完整提交的种群恢复点。")
    selection = {"ecology_checkpoint_id": str(cp["id"])}
    if body.kind == "ecology_trajectory":
        start, end = body.from_us or "0", body.through_us or cp["time_us"]
        if not 0 <= int(start) <= int(end) <= int(cp["time_us"]):
            raise ValueError("生态轨迹区间必须位于固定种群恢复点之内。")
        selection.update(from_us=start, through_us=end)
        expected = db.execute(
            "SELECT count(*) AS n FROM ecology_checkpoints WHERE campaign_id=%s AND revision<=%s AND time_us BETWEEN %s AND %s",
            (body.ecology_id, cp["revision"], start, end),
        ).fetchone()["n"]
        if not expected:
            raise Conflict("所选区间没有已提交的种群观测点。")
        row_unit = "one committed population checkpoint; not a physical microstep or independent replicate"
    else:
        expected = cp["population"]["individuals"]
        row_unit = "one individual in the complete fixed population; includes dead and nonreproducing individuals"
    provenance = {
        "campaign_id": str(campaign["id"]),
        "run_name": campaign["name"],
        "protocol": campaign["protocol"],
        "protocol_hash": campaign["protocol_hash"],
        "checkpoint": cp,
        "expected_rows": expected,
        "row_unit": row_unit,
        "selection_boundary": "one immutable population checkpoint and all referenced individuals; trajectory commit revision <= selected revision",
        "inference_boundary": INFERENCE_BOUNDARY,
    }
    return provenance, selection


def evidence_rows(db, request, coverage):
    selection, provenance = request["selection"], request["provenance"]
    cp, identity = provenance["checkpoint"], selection["ecology_id"]
    coverage.update(
        row_unit=provenance["row_unit"],
        inference_boundary=INFERENCE_BOUNDARY,
        unselected_and_dead_individuals_included=True,
        body_state_time="physical_time_us; may lead model time",
    )
    count = 0
    if request["kind"] == "ecology_trajectory":
        coverage.update(complete_commit_interval=True, repeated_time_commits_retained=True)
        with closing_iterator(
            stream_rows(
                db,
                "SELECT id,revision,time_us,state_hash,status,observation->'population' AS population "
                "FROM ecology_checkpoints WHERE campaign_id=%s AND revision<=%s AND time_us BETWEEN %s AND %s ORDER BY revision",
                (identity, cp["revision"], selection["from_us"], selection["through_us"]),
            )
        ) as rows:
            for row in rows:
                count += 1
                population = row.pop("population")
                values = population | {
                    "physical_time_s": int(population["physical_time_us"]) / 1e6,
                    **{f"resource_{key}": value for key, value in population["resource_balance"].items()},
                }
                yield {
                    "time_us": row["time_us"],
                    "label": f"r{row['revision']} / {row['time_us']} us",
                    "quality": "complete committed population observation",
                    "values": values,
                    "provenance": row
                    | {
                        "physical_time_us": population["physical_time_us"],
                        "pending_delivery_us": population["pending_delivery_us"],
                    },
                }
    else:
        coverage.update(complete_population=True)
        bodies_alive, cores_not_dead, waiting = 0, 0, 0
        with closing_iterator(
            stream_rows(
                db,
                "WITH offspring AS (SELECT m.parent,count(*) AS n FROM ecology_checkpoint_members c "
                "JOIN ecology_members m USING(campaign_id,individual) WHERE c.population_checkpoint_id=%s GROUP BY m.parent) "
                "SELECT m.*,c.checkpoint_id,c.state_hash,c.outcome,coalesce(o.n,0) AS offspring_count "
                "FROM ecology_checkpoint_members c JOIN ecology_members m USING(campaign_id,individual) "
                "LEFT JOIN offspring o ON o.parent=c.individual "
                "WHERE c.population_checkpoint_id=%s ORDER BY length(c.individual),c.individual",
                (cp["id"], cp["id"]),
            )
        ) as rows:
            for row in rows:
                count += 1
                outcome = row["outcome"]
                bodies_alive += int(outcome["alive"])
                cores_not_dead += int(outcome["core_life"] != "dead")
                waiting += int(outcome["core_life"] == "waiting")
                values = (
                    outcome["metrics"]
                    | energy_endpoints(outcome["metrics"])
                    | {
                        "body_alive": int(outcome["alive"]),
                        "core_not_dead": int(outcome["core_life"] != "dead"),
                        "body_reserve": outcome["reserve"],
                        "body_damage": outcome["damage"],
                        "generation": row["generation"],
                        "offspring_count": row["offspring_count"],
                        "observed_age_s": int(outcome["observed_age_us"]) / 1e6,
                        "core_observed_time_s": int(outcome["core_time_us"]) / 1e6,
                    }
                )
                yield {
                    "time_us": None,
                    "label": row["individual"],
                    "quality": "complete fixed population individual",
                    "values": values,
                    "provenance": row
                    | {
                        "population_checkpoint_id": cp["id"],
                        "population_time_us": cp["time_us"],
                        "physical_time_us": cp["population"]["physical_time_us"],
                        "body_survival_right_censored": outcome["alive"],
                        "core_death_not_observed_at_boundary": outcome["core_life"] != "dead",
                    },
                }
        coverage.update(
            bodies_alive_at_physical_boundary=bodies_alive,
            core_death_not_observed_count=cores_not_dead,
            cores_waiting_for_first_activation=waiting,
        )
    if count != provenance["expected_rows"]:
        raise Conflict("已固定的生态来源不完整；未保存部分证据。")
