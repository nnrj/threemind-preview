from .database import Conflict, NotFound
from .measurements import ENERGY_METRICS


def study_trajectories(database, project, study_id, metric, buckets):
    allowed = {
        "activation",
        "edges",
        "inhibition",
        "mean_weight",
        "mean_activation",
        "active_fraction",
        "saturated_fraction",
        "edge_density",
        *ENERGY_METRICS,
    }
    if metric not in allowed:
        raise ValueError("unsupported trajectory metric")
    with database.tx(project, repeatable=True) as db:
        study = db.execute("SELECT protocol FROM studies WHERE id=%s", (study_id,)).fetchone()
        if study is None:
            raise NotFound()
        protocol = study["protocol"]
        origin = round(protocol["warmup_s"] * 1e6)
        duration = round(protocol["base"]["duration_s"] * 1e6)
        buckets = min(buckets, max(2, duration // protocol["base"].get("sample_us", 100000) + 1))
        rows = db.execute(
            """
            WITH run_bins AS (
                SELECT r.spec->>'condition' AS condition, r.id,
                    least(%s-1, floor((o.time_us-%s)/%s*%s)::integer) AS bin,
                    avg((o.metrics->>%s)::double precision) AS value
                FROM observations o JOIN runs r ON r.id=o.run_id
                WHERE r.spec->>'study_id'=%s AND o.time_us BETWEEN %s AND %s
                  AND jsonb_typeof(o.metrics->%s)='number'
                GROUP BY condition,r.id,bin
            )
            SELECT condition,bin,avg(value) AS mean,min(value) AS minimum,max(value) AS maximum,count(*) AS n
            FROM run_bins GROUP BY condition,bin ORDER BY condition,bin
        """,
            (buckets, origin, duration, buckets, metric, str(study_id), origin, origin + duration, metric),
        ).fetchall()
    conditions = []
    for arm in protocol["arms"]:
        by_bin = {r["bin"]: r for r in rows if r["condition"] == arm["name"]}
        conditions.append(
            {
                "name": arm["name"],
                "rows": [
                    {
                        "time_us": str(round((i + 0.5) / buckets * duration)),
                        metric: by_bin[i]["mean"] if i in by_bin else None,
                        "n": by_bin[i]["n"] if i in by_bin else 0,
                    }
                    for i in range(buckets)
                ],
            }
        )
    return {
        "metric": metric,
        "buckets": buckets,
        "series": conditions,
        "phases": protocol["base"].get("phases", []),
        "expected_n": len(protocol["seeds"]),
        "method": "Within each time bin average samples per run, then give each independent run equal weight. Empty bins are gaps. These display means are not confidence intervals or raw evidence.",
    }


def checkpoint_rows(database, project, run_id, table, checkpoint_id=None, *, minimum=0.0, source=None, revision=None):
    if table not in ("nodes", "edges", "changes"):
        raise ValueError("unknown graph table")
    cp, image = database.load_checkpoint(project, run_id, checkpoint_id)
    if revision is not None and revision != cp["revision"]:
        raise Conflict("state changed; restart pagination")
    state = image.to_dict()
    legacy = state["dynamics"] == "unified-associative"
    if source is not None:
        source = str(source) if legacy else int(source)
    if table in ("nodes", "edges"):
        rows = [
            r
            for r in state[table]
            if r["activation" if table == "nodes" else "weight"] >= minimum
            and (table == "nodes" or source is None or (str(r["source"]) if legacy else r["source"]) == source)
        ]
    else:
        with database.tx(project) as db:
            previous = db.execute(
                "SELECT id,time_us FROM checkpoints WHERE run_id=%s AND revision<%s ORDER BY revision DESC LIMIT 1",
                (run_id, cp["revision"]),
            ).fetchone()
        old = database.load_checkpoint(project, run_id, previous["id"])[1].to_dict()["edges"] if previous else []
        a = {(e["source"], e["target"]): e for e in old}
        b = {(e["source"], e["target"]): e for e in state["edges"]}
        rows = []
        for key in sorted(a.keys() | b.keys(), key=(lambda pair: tuple(map(str, pair))) if legacy else None):
            if source is not None and (str(key[0]) if legacy else key[0]) != source:
                continue
            before, after = a.get(key), b.get(key)
            if before == after:
                continue
            weight_before = before["weight"] if before else None
            weight_after = after["weight"] if after else None
            delta = (weight_after or 0) - (weight_before or 0)
            if abs(delta) < minimum:
                continue
            rows.append(
                {
                    "source": key[0],
                    "target": key[1],
                    "change": "created" if before is None else "removed" if after is None else "changed",
                    "weight_before": weight_before,
                    "weight_after": weight_after,
                    "weight_delta": delta,
                    "stability_before": before["stability"] if before else None,
                    "stability_after": after["stability"] if after else None,
                    "from_time_us": str(previous["time_us"]) if previous else "0",
                    "to_time_us": state["time_us"],
                    "quality": "checkpoint interval",
                }
            )
    return cp, image, rows
