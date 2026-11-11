"""Read/export committed scientific resource accounting from the single Lab DB."""

import csv
import io
import json

from threemind_core.attention import COUNTERS as ATTENTION_COUNTERS
from threemind_core.energy import Energy
from threemind_core.resources import COUNTERS
from threemind_core.spec import ATTENTION_DEFAULTS, BUDGET_DEFAULTS, ENERGY_DEFAULTS, timestamp

from .database import NotFound


def selection(after="0", until=None):
    start = timestamp(after)
    end = timestamp(until) if until is not None else None
    if end is not None and end < start:
        raise ValueError("结束时间不能小于起始时间。")
    return start, end


QUERY = """SELECT time_us,sequence,metrics->'resources' AS resources,quality
    FROM observations WHERE run_id=%s AND time_us>=%s AND (%s::numeric IS NULL OR time_us<=%s)
    AND jsonb_typeof(metrics->'resources')='object' ORDER BY time_us"""


def accounting_query(field):
    if field not in ("resources", "energy", "attention"):
        raise ValueError("unknown accounting field")
    return QUERY.replace("resources", field)


def evidence_schema(field):
    return f"threemind.{field if field != 'resources' else 'resource'}-evidence/1"


def rows(database, project, run_id, *, after="0", until=None, limit=50, field="resources"):
    start, end = selection(after, until)
    with database.tx(project, repeatable=True) as db:
        run = db.execute("SELECT metrics,time_us,revision FROM runs WHERE id=%s", (run_id,)).fetchone()
        if run is None:
            raise NotFound("run")
        values = db.execute(accounting_query(field) + " LIMIT %s", (run_id, start, end, end, limit + 1)).fetchall()
        provider = None
        if field == "energy":
            cp = db.execute(
                "SELECT context->'energy_supplier' AS provider FROM checkpoints WHERE run_id=%s AND revision=%s",
                (run_id, run["revision"]),
            ).fetchone()
            provider = cp["provider"] if cp else None
    for value in values:
        value["time_us"] = str(value["time_us"])
    return {
        "schema": evidence_schema(field),
        "latest": run["metrics"].get(field),
        "revision": run["revision"],
        "latest_time_us": str(run["time_us"]),
        **({"provider": provider} if field == "energy" else {}),
        "rows": values[:limit],
        "more": len(values) > limit,
        "next": str(int(values[limit - 1]["time_us"]) + 1) if len(values) >= limit else after,
        "selection": {"after_us": str(start), "until_us": str(end) if end is not None else None},
        "scope": "Committed ledger samples since the accounting epoch; values between observations are not a continuous trajectory.",
    }


def export_stream(database, project, run_id, *, after="0", until=None, format="jsonl", field="resources"):
    start, end = selection(after, until)
    with database.tx(project, repeatable=True) as db:
        run = db.execute("SELECT id,revision,state_hash FROM runs WHERE id=%s", (run_id,)).fetchone()
        if run is None:
            raise NotFound("run")
        metadata = {
            "schema": evidence_schema(field),
            "run_id": str(run_id),
            "revision": run["revision"],
            "state_hash": run["state_hash"],
            "after_us": str(start),
            "until_us": str(end) if end is not None else None,
            "scope": "Ledger values at committed observation times; zero is not assumed before accounting existed.",
        }
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        keys = [
            "time_us",
            "sequence",
            "since_us",
            "adaptation_period_us",
            "adaptations_used",
            *COUNTERS,
            "counter_overflowed",
            "step_us",
            *BUDGET_DEFAULTS,
            "quality",
            "revision",
            "state_hash",
            "after_us",
            "until_us",
        ]
        if field == "energy":
            keys = [
                "time_us",
                "sequence",
                *Energy.__dataclass_fields__,
                *ENERGY_DEFAULTS,
                # Historical observations retain the parameters actually used.
                # Current models leave these retired columns empty.
                "irreversible_energy_death_enabled",
                "energy_starvation_death_us",
                "settled_state_time_us",
                "quality",
                "revision",
                "state_hash",
                "after_us",
                "until_us",
            ]
        if field == "attention":
            keys = [
                "time_us",
                "sequence",
                "since_us",
                *ATTENTION_COUNTERS,
                "counter_overflowed",
                *ATTENTION_DEFAULTS,
                "effective",
                "modulators",
                "quality",
                "revision",
                "state_hash",
                "after_us",
                "until_us",
            ]
        if format == "jsonl":
            yield (json.dumps({"selection": metadata}, ensure_ascii=False) + "\n").encode()
        else:
            writer.writerow(keys)
            yield ("\ufeff" + buffer.getvalue()).encode()
        with db.cursor(name="resource_evidence") as cursor:
            cursor.execute(accounting_query(field), (run_id, start, end, end))
            cursor.itersize = 500
            for row in cursor:
                row["time_us"] = str(row["time_us"])
                if format == "jsonl":
                    yield (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode()
                else:
                    buffer.seek(0)
                    buffer.truncate(0)
                    record = {
                        **metadata,
                        **row,
                        **row[field],
                        **row[field]["limits" if field == "resources" else "parameters"],
                        "revision": metadata["revision"],
                        "state_hash": metadata["state_hash"],
                    }
                    writer.writerow(
                        [
                            json.dumps(record[k], ensure_ascii=False, allow_nan=False)
                            if isinstance(record.get(k), (dict, list))
                            else record.get(k)
                            for k in keys
                        ]
                    )
                    yield buffer.getvalue().encode()
