"""Replay eight existing trials with denser passive inspection, requiring identical Core hashes."""

import argparse
import gzip
import time

from common import HERE, WORK, Study, encoded, load_case, new_json
from experiment import clip, dose, fresh, observe, saved
from materials import identities

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def register(study):
    path = WORK / "transfer-trace-note.json"
    if path.exists():
        return
    value = notebooks.save_note(
        study.db,
        study.project,
        LOCAL_USER,
        study.identity("transfer-trace-design"),
        {
            "operation_id": study.identity("transfer-trace-design:write"),
            "expected_revision": 0,
            "kind": "note",
            "collection_id": study.meta["notebook_id"],
            "title": "迁移的反向响应：输入期间的只读补录",
            "body": {
                "format": "markdown",
                "text": (HERE / "transfer-trace-registration.md").read_text(encoding="utf-8"),
            },
        },
    )
    new_json(path, value)


def run(study):
    for seed in (930101, 930102):
        for mode in ("full", "no_imu"):
            parent = load_case(study, f"memory/{seed}/ordinary/{mode}/wait-1")
            for sign in (1, -1):
                original = load_case(study, f"transfer/{seed}/ordinary/{mode}/original/{sign}")
                key = f"transfer-trace/{seed}/ordinary/{mode}/{sign}"
                if saved(study, key):
                    continue
                c = fresh(study, key, seed, "ordinary", parent=parent, observe=True)
                begin = c.engine.time_us
                timeline = [{"relative_us": 0, "time_us": str(begin), "nodes": c.engine.observation_nodes()}]
                previous = c.session.host.observe

                def capture(engine, previous=previous, timeline=timeline, begin=begin):
                    previous(engine)
                    timeline.append(
                        {
                            "relative_us": engine.time_us - begin,
                            "time_us": str(engine.time_us),
                            "nodes": engine.observation_nodes(),
                        }
                    )

                c.session.host.observe = capture
                clip(c, sign, mode, dose(), domain="original", observed=True)
                result = observe(
                    c,
                    {
                        "family": "transfer-trace",
                        "preset": "ordinary",
                        "mode": mode,
                        "parent": parent["id"],
                        "domain": "original",
                        "sign": sign,
                        "targets": [identities(seed)["A"], identities(seed)["B"]],
                        "expected": int(sign < 0),
                        "original_case": original["id"],
                        "original_state_sha256": original["state_sha256"],
                        "physical_begin_us": begin,
                    },
                    None,
                )
                with gzip.open(c.folder / "input-trajectory.json.gz", "xb") as f:
                    f.write(encoded(timeline))
                assert result["state_sha256"] == original["state_sha256"], "inspection changed Core dynamics"
    new_json(WORK / "completed-transfer-trace.json", {"finished_at": time.time()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()
    study = Study()
    try:
        register(study)
        if not args.register_only:
            run(study)
    except Exception as exc:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"budget_stop": True, "stage": "interrupted", "error": str(exc)})
        new_json(WORK / f"failure-transfer-trace-{time.time_ns()}.json", {"error": str(exc)})
        raise
    finally:
        study.db.close()
