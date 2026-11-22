"""Independent apparatus and prospective cost checks, not formal selection."""
import argparse
import json
from pathlib import Path
import time
import ring as r


def close(a, b, path=""):
    if isinstance(a, float) and isinstance(b, (int, float)):
        assert abs(a - b) <= 1e-12, (path, a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for key in a: close(a[key], b[key], path + "/" + str(key))
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)): close(x, y, path + "/" + str(i))
    else:
        assert a == b, (path, a, b)


def main(work):
    folder = work / "apparatus-v1"
    assert not folder.exists()
    folder.mkdir(parents=True)
    r.save(folder / "declared.json", {"formal": False, "seed": r.INSTRUMENT_SEED,
           "protocol_sha256": r.digest((r.HERE / "protocol.zh.md").read_text("utf8")),
           "declared_before_runs": True})
    results, endings = {}, {}
    for mode in ("normal", "frequent", "paused", "restored"):
        result, ending = r.execute(folder / mode, "apparatus-common", r.INSTRUMENT_SEED,
                                  position=.125, seconds=3, mode=mode)
        results[mode], endings[mode] = result, ending
        print(json.dumps({"check": mode, "wall": result["wall_seconds"]}), flush=True)
    assert len({r.digest(v) for v in endings.values()}) == 1
    ref_result, ref = r.execute(folder / "reference", "apparatus-common", r.INSTRUMENT_SEED,
                               position=.125, seconds=3, backend="reference")
    close(ref["core"], endings["normal"]["core"])
    close(ref["body"], endings["normal"]["body"])
    close(r.read(folder / "normal/trajectory.json.gz")["rows"],
          r.read(folder / "reference/trajectory.json.gz")["rows"])
    parent = endings["normal"]
    parent_hash = r.digest(parent)
    assessment = r.Ring("assessment", r.INSTRUMENT_SEED, whole=parent, position=.5625)
    assert assessment.engine.capture_state().digest == r.StateImage.from_dict(parent["core"]).digest
    assert assessment.ancestry["birth_called"] is False
    assert assessment.engine.time_us == 3000000
    expected = r.birth(r.StateImage.from_dict(parent["core"]), decay_age="preserve")
    child = r.Ring("child", r.INSTRUMENT_SEED, parent=parent, position=.125)
    assert child.engine.time_us == 0 and child.engine.capture_state().digest == expected.digest
    assert r.digest(parent) == parent_hash
    # Independent full-length pilot measures costs; it never chooses a scientific seed or rule.
    pilot, developed = r.execute(folder / "development-60s", "budget-development", r.INSTRUMENT_SEED,
                                position=.125, seconds=60)
    probe, probe_state = r.execute(folder / "assessment-60s", "budget-assessment", r.INSTRUMENT_SEED,
                                  whole=developed, position=.0625, seconds=60)
    child_result, child_state = r.execute(folder / "offspring-60s", "budget-offspring", r.INSTRUMENT_SEED,
                                         parent=developed, position=.375, seconds=60)
    for name in ("development-60s", "assessment-60s", "offspring-60s"):
        value = r.read(folder / name / "result.json")
        rows = r.read(folder / name / "trajectory.json.gz")["rows"]
        assert len(rows) == 600 and value["region1"] == sum(x["region"] for x in rows) / 600
        assert all(x["body"]["phase"] == 0 for x in rows)
        assert all(x["time_us"] == rows[0]["time_us"] + 100000 * i for i, x in enumerate(rows))
        assert value["life"] != "dead"
    samples = (pilot, probe, child_result)
    seconds = max(x["wall_seconds"] for x in samples)
    sizes = [sum(p.stat().st_size for p in (folder / name).glob("*")) for name in
             ("development-60s", "assessment-60s", "offspring-60s")]
    report = {"passed": True, "independent_calibration_seed": r.INSTRUMENT_SEED,
              "mode_hashes": {k: r.digest(v) for k, v in endings.items()},
              "reference_native_tolerance": 1e-12, "assessment_exact_core": True,
              "birth_only_for_offspring": True, "parent_unchanged": True,
              "full_length_pilots": samples, "largest_stage_bytes": max(sizes),
              "estimated_scientific_seconds": seconds * 5056,
              "estimated_raw_bytes": max(sizes) * 5056,
              "under_six_hours": seconds * 5056 < 6 * 3600,
              "under_three_gib": max(sizes) * 5056 < 3 * 2**30}
    r.save(folder / "checks.json", report)
    assert report["under_six_hours"] and report["under_three_gib"], "cost target not met; retain evidence"
    r.save(work / "apparatus.json", report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    main(parser.parse_args().work)
