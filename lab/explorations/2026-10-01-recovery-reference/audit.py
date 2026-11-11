"""Read-back of registered evidence and exact observer-disabled replays."""

import argparse
import gzip
import hashlib
import json
import time
from collections import Counter

from common import HERE, ROOT, WORK, Study, ids, new_json, note_text, old_sensory, read_json, settings, sources
from run import schedule

from lab.tools.service_study import digest
from lab.tools.state_exchange_cut import exchange_cut
from lab.tools.study_input_audit import verify_input_bundle
from threemind_core import StateImage, Stimulus
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER
from threemind_runtime import create_engine

EXPECTED = {"cut": 512, "recovery": 240, "timing": 432, "jitter": 48, "reference": 288}


def check_course(folder, row):
    m = row["extra"]
    if m.get("stage") != "training":
        return False
    frames = [f["stimulus"] for f in json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))["frames"]]
    channels = ids(row["seed"])
    planned, end = schedule(
        m["family"],
        m["order"],
        m.get("phase_us", 0),
        m.get("variant", "fixed"),
        m.get("cadence", "dense"),
        m.get("layout", "shared"),
    )
    task = [f for f in frames if any(c in [channels[x] for x in "ABCD"] for c, _ in f["channels"])]
    assert len(task) == len(planned) and int(row["time_us"]) == end
    assert m["schedule"] == planned
    doses = Counter()
    for f, expected in zip(task, planned):
        assert int(f["time_us"]) == expected["at"] and f["intensity"] == 0.4
        assert sorted(f["channels"]) == sorted([[channels[x], 1.0] for x in expected["symbols"]])
        doses.update(expected["symbols"])
    if m["family"] == "reference":
        assert doses == Counter(A=12, B=12, C=12, D=12, X=24, Z=24)
    maintenance = [f for f in frames if f["channels"] == [[channels["K"], 1.0]]]
    times = [0] + list(range(500000 + m.get("maintenance_phase_us", 0), end, 500000))
    assert [int(f["time_us"]) for f in maintenance] == times
    assert all(f["intensity"] == 0.2 for f in maintenance)
    final = [f for f in frames if f["channels"] == [[channels["Y"], 1.0]]]
    assert len(final) == 1 and final[0]["intensity"] == 0.2 and int(final[0]["time_us"]) == end
    assert len(frames) == len(planned) + len(maintenance) + 1
    trace = json.loads(gzip.decompress((folder / "teaching-states.json.gz").read_bytes()))
    assert len(trace) == len(planned)
    assert all(
        t["frame"] == f and int(t["before"]["time_us"]) == f["at"] and int(t["after"]["time_us"]) == f["at"]
        for t, f in zip(trace, planned)
    )
    return True


def witnesses(study, rows):
    choices = {}
    for row in rows:
        meta = row["extra"]
        if meta.get("stage") != "probe" or not meta.get("cue"):
            continue
        group = meta["family"]
        if group == "cut":
            if meta["groups"] not in ("W", "none", "WSN"):
                continue
            group += "-" + meta["groups"]
        elif group == "timing":
            group += "-" + str(meta["maintenance_phase_us"])
        if group not in choices:
            choices[group] = row
    records = []
    for label, row in sorted(choices.items()):
        folder = WORK / "cases" / row["key"]
        image = StateImage(gzip.decompress((folder / "pre-probe.json.gz").read_bytes()))
        engine = create_engine(state=image, backend="native")
        inputs = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
        start, wall = engine.time_us, time.monotonic()
        for frame in inputs["frames"]:
            stimulus = Stimulus.from_dict(frame["stimulus"])
            if stimulus.time_us >= start:
                engine.inject(stimulus)
        while engine.time_us < int(row["time_us"]):
            study.guard()
            engine.advance_to(min(int(row["time_us"]), engine.time_us + 100000))
        assert engine.capture_state().digest == row["state_sha256"], row["key"]
        records.append({"key": row["key"], "label": label, "same_hash": True, "wall_seconds": time.monotonic() - wall})
    return records


def run(study, name, partial_reason):
    manifest = sources(study)
    notes = []
    for lang in ("zh", "en"):
        note = notebooks.note(study.db, study.project, LOCAL_USER, study.identity("design:" + lang), revision=1)
        assert note["body"]["text"] == note_text((HERE / f"design.{lang}.md").read_text(encoding="utf-8"))
        assert (WORK / f"design-frozen.{lang}.md").read_bytes() == (HERE / f"design.{lang}.md").read_bytes()
        notes.append({"id": str(note["id"]), "content_hash": note["content_hash"]})
    totals, coverage, bundles, rows = Counter(), Counter(), set(), []
    swap_checks = 0
    course_checks = 0
    originals = {}
    for path in sorted((WORK / "cases").rglob("result.json")):
        study.guard()
        row = read_json(path)
        checkpoint, image = study.db.load_checkpoint(study.project, row["id"])
        local = StateImage(gzip.decompress((path.parent / "parent-state.json.gz").read_bytes()))
        assert image.digest == local.digest == row["state_sha256"]
        assert image.to_dict()["config"] == row["config"]
        assert row["config"]["intensity_gain"] == 0.075
        context = checkpoint["context"]
        assert context["implementation"] == study.implementation
        signature = context["runner_manifest_sha256"]
        root = WORK / "runner-revisions" / signature
        bundle = read_json(root / "manifest.json")
        assert digest(bundle) == signature
        if signature not in bundles:
            for file, sha in bundle.items():
                assert hashlib.sha256((root / file).read_bytes()).hexdigest() == sha
            bundles.add(signature)
        input_result = verify_input_bundle(study, path.parent, row, require_complete=not row["extra"].get("failure"))
        normalizations = input_result.pop("metadata_normalizations")
        if normalizations:
            raise RuntimeError("unexpected representation difference; preserve and inspect before proceeding")
        totals.update(input_result)
        coverage[row["key"].split("/")[0]] += 1
        meta = row["extra"]
        course_checks += check_course(path.parent, row)
        if meta.get("family") == "cut":
            identity = (row["seed"], meta["mode"], meta["learn"])
            donor_identity = (row["seed"], meta["mode"], "11" if meta["learn"] == "01" else "01")
            for k in (identity, donor_identity):
                if k not in originals:
                    originals[k] = old_sensory(study, *k)
            groups = tuple(meta["groups"]) if meta["groups"] != "none" else ()
            reconstructed, receipt = exchange_cut(
                originals[identity]["image"], originals[donor_identity]["image"], groups
            )
            actual = json.loads(gzip.decompress((path.parent / "exchange.json.gz").read_bytes()))
            assert actual == receipt
            assert reconstructed.digest == meta["pre_probe_sha256"]
            swap_checks += 1
        if meta.get("stage") == "probe":
            pre = StateImage(gzip.decompress((path.parent / "pre-probe.json.gz").read_bytes()))
            assert pre.digest == meta["pre_probe_sha256"]
            assert int(row["time_us"]) - int(meta["probe_start_us"]) == (
                5600000 if meta["family"] in ("cut", "recovery") else 5000000
            )
        rows.append(row)
        if len(rows) % 128 == 0:
            print(json.dumps({"verified_cases": len(rows), "frames": totals["frames"]}), flush=True)
    failures = [r["key"] for r in rows if r["extra"].get("failure")]
    complete = dict(coverage) == EXPECTED and not failures
    if not complete and not partial_reason:
        raise RuntimeError("incomplete batch requires an explicit reason")
    replay = witnesses(study, rows)
    sensory_checks = timing_checks = 0
    for row in rows:
        m = row["extra"]
        old_key = None
        if m["family"] == "cut" and m["groups"] == "none":
            old_key = f"sensory/{row['seed']}/{m['mode']}/learn{m['learn']}/test11/sign{m['sign']}/physical{int(m['physical'])}"
            sensory_checks += 1
        elif m["family"] == "timing" and m["maintenance_phase_us"] == 0:
            suffix = "train" if m["stage"] == "training" else f"wait30/cue{m['cue_symbol']}"
            old_key = f"phase/{row['seed']}/f{m['tau']}/g50000/p{m['phase_us']}/{m['order']}/{suffix}"
            timing_checks += 1
        if old_key:
            old = read_json(ROOT / ".work/order-mechanisms-20261001/cases" / old_key / "result.json")
            assert row["state_sha256"] == old["state_sha256"]
    with study.db.tx(study.project) as tx:
        runs = tx.execute("SELECT id FROM runs WHERE project_id=%s", (study.project,)).fetchall()
        assert {str(r["id"]) for r in runs} == {r["id"] for r in rows}
        for table, key in (("input_envelopes", "envelopes"), ("input_frames", "frames")):
            n = tx.execute(f"SELECT count(*) AS n FROM {table} WHERE project_id=%s", (study.project,)).fetchone()["n"]
            assert n == totals[key]
    study.guard(force=True)
    result = {
        "cases": len(rows),
        "registered_complete": complete,
        "partial_reason": partial_reason,
        "coverage": dict(coverage),
        "failures": failures,
        "inputs": dict(totals),
        "swap_receipts_reconstructed": swap_checks,
        "matched_courses_verified": course_checks,
        "sensory_exact_replays": sensory_checks,
        "timing_exact_replays": timing_checks,
        "observer_disabled_replays": replay,
        "historical_sources_unchanged": True,
        "unchanged_core": True,
        "strong_input_default_unchanged": True,
        "source_files": len(manifest),
        "runner_bundles": len(bundles),
        "notes": notes,
        "simulation_wall_seconds": sum(r["wall_seconds"] for r in rows),
        "new_storage_bytes_before_archive": study.storage_bytes,
        "usage_start": study.settings.usage_start,
        "usage_at_audit": read_json(WORK / "usage.json")["used_percent"],
    }
    new_json(WORK / (name + ".json"), result)
    if complete or partial_reason:
        (WORK / "STOP").write_text("Simulations closed; preserve evidence and publish.\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", default="audit")
    p.add_argument("--partial-reason")
    args = p.parse_args()
    study = Study(settings())
    try:
        run(study, args.name, args.partial_reason)
    finally:
        study.db.close()
