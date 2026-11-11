"""Verify new cases, original inputs, source bundles and read-only observation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import time
from collections import Counter

from runner import ROOT, WORK, settings

from lab.tools.service_study import Study, digest, new_json, read_json
from lab.tools.study_input_audit import verify_input_bundle
from threemind_core import StateImage, Stimulus
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER
from threemind_runtime import create_engine

EXPECTED = {
    "parents": 16,
    "default": 1120,
    "ordinary2": 84,
    "stability2": 84,
    "interference": 288,
    "reversal": 544,
    "sequence": 672,
}


def observer_replays(study):
    records = []
    for i, tau, delay in ((0, 0, 1), (0, 1, 30), (1, 1, 1), (1, 3, 30)):
        key = f"default/100101/i{i}f{tau}/single4/wait{delay}/cue0.5"
        folder = WORK / "cases" / key
        if not (folder / "result.json").exists():
            continue
        result = read_json(folder / "result.json")
        image = StateImage(gzip.decompress((folder / "pre-probe.json.gz").read_bytes()))
        engine = create_engine(state=image, backend="native")
        start, wall = engine.time_us, time.monotonic()
        inputs = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
        for frame in inputs["frames"]:
            stimulus = Stimulus.from_dict(frame["stimulus"])
            if stimulus.time_us >= start:
                engine.inject(stimulus)
        while engine.time_us < int(result["time_us"]):
            study.guard()
            engine.advance_to(min(int(result["time_us"]), engine.time_us + 100000))
        assert engine.capture_state().digest == result["state_sha256"], key
        records.append(
            {
                "key": key,
                "state_sha256": result["state_sha256"],
                "observer_disabled_same_hash": True,
                "wall_seconds": time.monotonic() - wall,
            }
        )
    return records


def run(study, partial_reason):
    helper = ROOT / "lab/tools/study_input_audit.py"
    target = WORK / "audit-sources/study_input_audit.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == helper.read_bytes()
    else:
        shutil.copy2(helper, target)
    notes = []
    for prefix, filename in (
        ("design", "design"),
        ("reversal-design", "reversal-design"),
        ("sequence-design", "sequence-design"),
    ):
        for lang in ("zh", "en"):
            note = notebooks.note(study.db, study.project, LOCAL_USER, study.identity(f"{prefix}:{lang}"), revision=1)
            assert note["body"]["text"] == (study.here / f"{filename}.{lang}.md").read_text(encoding="utf-8")
            notes.append({"id": str(note["id"]), "content_hash": note["content_hash"]})
    totals, bundles, coverage, rows, normalized = Counter(), set(), Counter(), [], []
    for path in sorted((WORK / "cases").rglob("result.json")):
        study.guard()
        row = read_json(path)
        checkpoint, image = study.db.load_checkpoint(study.project, row["id"])
        local = StateImage(gzip.decompress((path.parent / "parent-state.json.gz").read_bytes()))
        assert local.digest == image.digest == row["state_sha256"]
        assert image.to_dict()["config"] == row["config"]
        context = checkpoint["context"]
        assert context["implementation"] == study.implementation
        signature = context["runner_manifest_sha256"]
        root = WORK / "runner-revisions" / signature
        manifest = read_json(root / "manifest.json")
        assert digest(manifest) == signature
        assert context["runner_sha256"] == manifest["lab/tools/service_study.py"]
        if signature not in bundles:
            for name, sha in manifest.items():
                assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
            bundles.add(signature)
        inputs = verify_input_bundle(study, path.parent, row, require_complete=not row["extra"].get("failure"))
        normalized.extend({"case": row["key"], **record} for record in inputs.pop("metadata_normalizations"))
        totals.update(inputs)
        coverage[row["key"].split("/")[0]] += 1
        rows.append(row)
        if len(rows) % 128 == 0:
            print(json.dumps({"verified_cases": len(rows), **totals}), flush=True)
    failures = [
        {"key": r["key"], "extra": r["extra"]}
        for r in rows
        if r["extra"].get("failure") or r["extra"].get("exact_replay") is False
    ]
    complete = dict(coverage) == EXPECTED and not failures
    if not complete and not partial_reason:
        raise RuntimeError("incomplete registered batches require an explicit partial-delivery reason")
    witnesses = observer_replays(study)
    calibration = read_json(WORK / "calibration.json")
    for path, sha in calibration["sources"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    historical = read_json(WORK / "reversal-registration.json")["historical_sources"]
    for path, sha in historical.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    with study.db.tx(study.project) as tx:
        runs = tx.execute("SELECT id FROM runs WHERE project_id=%s", (study.project,)).fetchall()
        jobs = tx.execute(
            "SELECT id FROM jobs WHERE project_id=%s AND status IN ('pending','leased')", (study.project,)
        ).fetchall()
        for table, key in (("input_envelopes", "envelopes"), ("input_frames", "frames")):
            n = tx.execute(f"SELECT count(*) AS n FROM {table} WHERE project_id=%s", (study.project,)).fetchone()["n"]
            assert n == totals[key]
    assert not jobs and {str(r["id"]) for r in runs} == {r["id"] for r in rows}
    study.guard(force=True)
    result = {
        "cases": len(rows),
        "registered_batches_complete": complete,
        "partial_reason": partial_reason,
        "coverage": dict(coverage),
        "expected_coverage": EXPECTED,
        "failures": failures,
        "inputs": dict(totals),
        "jsonb_metadata_normalizations": len(normalized),
        "verified_runner_bundles": len(bundles),
        "verified_design_notes": notes,
        "observer_replays": witnesses,
        "historical_sources_unchanged": True,
        "unchanged_core": True,
        "historical_exact_replays": sum(r["extra"].get("exact_replay") is True for r in rows),
        "simulation_wall_seconds": sum(r["wall_seconds"] for r in rows),
        "verification_simulation_seconds": sum(r["wall_seconds"] for r in witnesses),
        "storage_bytes_before_archive": study.storage_bytes,
        "usage_start": study.settings.usage_start,
        "usage_at_audit": read_json(WORK / "usage.json")["used_percent"],
        "audit_helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
    }
    assert result["simulation_wall_seconds"] + result["verification_simulation_seconds"] < study.settings.wall_seconds
    new_json(WORK / "input-metadata-normalizations.json", normalized)
    new_json(WORK / "audit.json", result)
    (WORK / "STOP").write_text("Registered simulations ended; preserve evidence and publish.\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partial-reason")
    args = parser.parse_args()
    study = Study(settings())
    try:
        run(study, args.partial_reason)
    finally:
        study.db.close()
