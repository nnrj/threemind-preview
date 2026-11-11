"""Registered 300-second edge intervention; public research interface only."""

import json
import time

from common import HERE, WORK, Study, load_case, new_json
from experiment import PRESETS, fresh, observe, saved
from materials import SEEDS, identities

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def register(study):
    path = WORK / "memory-intervention-note.json"
    if path.exists():
        return
    row = notebooks.save_note(
        study.db,
        study.project,
        LOCAL_USER,
        study.identity("memory-intervention-design"),
        {
            "operation_id": study.identity("memory-intervention-design:write"),
            "expected_revision": 0,
            "kind": "note",
            "collection_id": study.meta["notebook_id"],
            "title": "300 秒后记忆：屏蔽与恢复连接的追加验证",
            "body": {
                "format": "markdown",
                "text": (HERE / "memory-intervention-registration.md").read_text(encoding="utf-8"),
            },
        },
    )
    new_json(path, row)


def select(image, channel, targets):
    ids = {n["channel"]: n["id"] for n in image["nodes"]}
    source = ids[channel]
    edges = {(e["source"], e["target"]): e for e in image["edges"]}
    chosen = sorted(k for k in edges if k[0] == source)
    assert chosen, "no retained outgoing cue edge"
    excluded = {source, *(ids[t] for t in targets)}
    pool = {k for k in edges if not set(k) & excluded}
    matched, errors = [], []
    for edge in chosen:
        assert pool, "insufficient independently matched edges"

        def distance(k, edge=edge):
            return abs(edges[k]["weight"] - edges[edge]["weight"]) + abs(
                edges[k]["stability"] - edges[edge]["stability"]
            )

        best = min(pool, key=lambda k: (distance(k), k))
        matched.append(best)
        errors.append(distance(best))
        pool.remove(best)
    return chosen, matched, errors


def run(study):
    for seed in SEEDS:
        for preset in PRESETS:
            for mode in ("full", "no_imu"):
                parent = load_case(study, f"memory/{seed}/{preset}/{mode}/wait-300")
                ids = identities(seed)
                targets = [ids["position_positive"], ids["position_negative"]]
                for cue in ("A", "B"):
                    for condition in ("silence", "restore", "matched"):
                        key = f"memory-intervention/{seed}/{preset}/{mode}/{cue}/{condition}"
                        if saved(study, key):
                            continue
                        c = fresh(study, key, seed, preset, parent=parent, observe=True)
                        before = c.engine.capture_state()
                        chosen, matched, errors = select(before.to_dict(), ids[cue], targets)
                        applied = matched if condition == "matched" else chosen
                        c.engine.intervene(edges=applied, action="silence")
                        silenced = c.engine.capture_state().digest
                        if condition == "restore":
                            c.engine.intervene(edges=applied, action="unsilence")
                            restored = c.engine.capture_state().to_dict()
                            original = before.to_dict()
                            # The audit sequence records two interventions, not a dynamics change.
                            original.pop("sequence", None)
                            restored.pop("sequence", None)
                            assert original == restored
                        intervention = {
                            "condition": condition,
                            "targets": chosen,
                            "applied": applied,
                            "matching_errors": errors if condition == "matched" else [],
                            "before": before.digest,
                            "silenced": silenced,
                            "after": c.engine.capture_state().digest,
                        }
                        c.events.append(
                            {
                                "key": f"research:{condition}",
                                "kind": "research_intervention",
                                "time_us": str(c.engine.time_us),
                                "payload": intervention,
                            }
                        )
                        observe(
                            c,
                            {
                                "family": "memory-intervention",
                                "preset": preset,
                                "mode": mode,
                                "delay_s": 300,
                                "cue": cue,
                                "expected": int(cue == "B"),
                                "parent": parent["id"],
                                "targets": targets,
                                "intervention": intervention,
                            },
                            ids[cue],
                        )
            print(json.dumps({"stage": "memory-intervention", "seed": seed, "preset": preset}), flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()
    study = Study()
    try:
        register(study)
        if not args.register_only:
            run(study)
            new_json(WORK / "completed-memory-intervention.json", {"finished_at": time.time()})
    except Exception as exc:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"budget_stop": True, "stage": "interrupted", "error": str(exc)})
        new_json(WORK / f"failure-intervention-{time.time_ns()}.json", {"error": str(exc)})
        raise
    finally:
        study.db.close()
