from common import WORK, Case, Study, load_case, new_json
from experiment import KERNEL, SEEDS, finish, snapshots


def main():
    study = Study()
    try:
        for seed in SEEDS:
            for preset in ("ordinary", "facilitation"):
                study.guard(force=True)
                parent = load_case(study, f"background/{seed}/{preset}/fresh-group")
                key = f"retention/{seed}/{preset}"
                case = Case(study, key, KERNEL, seed, parent=parent)
                at = case.engine.time_us
                assert 999991 not in {n["channel"] for n in parent["image"].to_dict()["nodes"]}
                for delta in range(0, 120000000, 500000):
                    case.send([999991], 0.2, at=at + delta, source="registered-external-life-support")
                points, spans = snapshots(case, at + 120000000)
                state = case.engine.capture_state().to_dict()
                support_ids = {n["id"] for n in state["nodes"] if n["channel"] == 999991}
                cross = sum((e["source"] in support_ids) != (e["target"] in support_ids) for e in state["edges"])
                finish(
                    case,
                    {
                        "family": "retention",
                        "stage": "retention",
                        "condition": "external-single-channel",
                        "preset": preset,
                        "parent": parent["id"],
                        "cross_original_edges": cross,
                        "initial_edges": len(parent["image"].to_dict()["edges"]),
                    },
                    points,
                    spans,
                )
        new_json(WORK / "retention-complete.json", {"cases": 4})
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "failure": str(exc)})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
