"""Withdraw actual inputs without clearing internal events or reviving a model."""

import argparse
import gzip
import hashlib
import json

from calibrate import KERNELS, Trial, done, tokens, train
from common import HERE, WORK, Study, encoded, new_json

SEEDS = (9293101, 9293102)


def observe(study, parent, branch):
    key = parent["key"].rsplit("/", 1)[0] + "/observe-" + branch
    if saved := done(study, key):
        return saved
    c = Trial(study, key, parent["kernel"], parent["seed"], parent=parent, bg=branch == "background")
    start = c.engine.time_us
    task_channels = set(tokens(c.seed).values())
    rows, cue = [], None

    def record():
        nodes = c.engine.observation_nodes()
        rows.append(
            {
                "relative_us": c.engine.time_us - start,
                "life": c.engine.life,
                "nodes": nodes,
                "transport": c.engine.metrics()["transport"],
            }
        )

    record()
    while c.engine.time_us < start + 60_000_000 and c.engine.life != "dead":
        if branch in "ADN" and c.engine.time_us == start + 30_000_000:
            cue = c.send([tokens(c.seed)[branch]], 0.5, source="manual-probe")
            c.step(c.engine.time_us)
            record()
        c.advance(min(start + 60_000_000, c.engine.time_us + 100000))
        record()
    with gzip.open(c.folder / "activity.jsonl.gz", "xb") as f:
        for row in rows:
            f.write(encoded(row) + b"\n")
    active = [r["relative_us"] for r in rows if any(n["activation"] > 0 for n in r["nodes"])]
    task = [
        r["relative_us"] for r in rows if any(n["activation"] > 0 and n["channel"] in task_channels for n in r["nodes"])
    ]
    return c.finish(
        {
            "kind": "input_withdrawal",
            "branch": branch,
            "start_us": str(start),
            "parent": parent["id"],
            "cue_envelope": cue,
            "cue_not_administered": branch in "ADN" and cue is None,
            "last_sample_with_any_activation_us": max(active, default=None),
            "last_sample_with_task_activation_us": max(task, default=None),
            "end_relative_us": c.engine.time_us - start,
        }
    )


def run(study):
    if not (WORK / "activity-registration.json").exists():
        new_json(
            WORK / "activity-registration.json",
            {
                "seeds": SEEDS,
                "interval_us": 1000000,
                "max_instances": 32,
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("activity.*")},
            },
        )
    results = []
    for seed in SEEDS:
        for balanced in (False, True):
            prefix = "activity-balanced" if balanced else "activity-paired"
            parent = train(study, "continuous", seed, 1000000, prefix=prefix, balanced=balanced)
            results.append(observe(study, parent, "early-withdrawal"))
            key = parent["key"].rsplit("/", 1)[0] + "/aged"
            aged = done(study, key)
            if not aged:
                c = Trial(study, key, KERNELS["continuous"], seed, parent=parent)
                c.advance(c.engine.time_us + 299_000_000)
                aged = c.finish({"kind": "activity_aged", "balanced": balanced, "parent": parent["id"]})
            for branch in ("background", "withdrawal", "A", "D", "N"):
                results.append(observe(study, aged, branch))
            study.guard(force=True)
            print(json.dumps({"seed": seed, "balanced": balanced, "observations_complete": True}), flush=True)
    new_json(WORK / "activity-analysis.json", [{k: r[k] for k in ("id", "key", "life", "extra")} for r in results])


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    study = Study()
    try:
        run(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
