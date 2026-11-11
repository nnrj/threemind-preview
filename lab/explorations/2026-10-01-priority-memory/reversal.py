"""Exact old sensory replay and a preregistered four-factor expression experiment."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import shutil
import sys

from runner import HERE, ROOT, WORK, fresh, progress, saved, settings

from lab.tools.service_study import Study, new_json, read_json, write_gzip
from threemind_core import StateImage

OLD_HERE = ROOT / "lab/explorations/2026-09-30-memory-transfer"
OLD_WORK = ROOT / ".work/memory-transfer-20260930"
_original_path = list(sys.path)
sys.path.insert(0, str(OLD_HERE))
try:
    import experiment as legacy
finally:
    sys.path[:] = _original_path

SEEDS = (930101, 930102, 930103, 930104)
FIELDS = ("depletion_enabled", "fast_enabled", "context_enabled", "inhibition_response_gain")
VARIANTS = {"1111": {}}
VARIANTS.update(
    {
        "".join(map(str, bits)): {
            field: (False if field.endswith("enabled") else 0.0) for field, on in zip(FIELDS, bits) if not on
        }
        for bits in itertools.product((0, 1), repeat=4)
        if bits != (1, 1, 1, 1)
    }
)
VARIANTS["silence"] = {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(study):
    path = WORK / "reversal-registration.json"
    if path.exists():
        meta = read_json(path)
        for relative, expected in meta["historical_sources"].items():
            if sha(ROOT / relative) != expected:
                raise RuntimeError("historical replay source changed: " + relative)
        return
    sources = list(OLD_HERE.glob("*.py"))
    sources += [OLD_WORK / "calibration.json"]
    for seed, mode in itertools.product(SEEDS, ("full", "no_imu")):
        p = OLD_WORK / "cases" / f"memory/{seed}/ordinary/{mode}/wait-1"
        sources += [p / "result.json", p / "parent-state.json.gz"]
        for sign in (1, -1):
            original = OLD_WORK / "cases" / f"transfer/{seed}/ordinary/{mode}/original/{sign}"
            sources += [original / "result.json", original / "inputs-frames.jsonl.gz"]
            sources += [OLD_WORK / "materials" / f"pendulum-{seed}-{sign}-original.json"]
    manifest = {}
    for source in sorted(set(sources)):
        name = source.relative_to(ROOT).as_posix()
        manifest[name] = sha(source)
        destination = WORK / "reversal-sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for language in ("zh", "en"):
        source = HERE / f"reversal-design.{language}.md"
        study.note(
            f"reversal-design:{language}", f"本体反向响应：事前登记 {language}", source.read_text(encoding="utf-8")
        )
        shutil.copy2(source, WORK / source.name)
    new_json(
        path,
        {"historical_sources": manifest, "design_sha256": sha(HERE / "reversal-design.zh.md"), "variants": VARIANTS},
    )


def old_parent(study, seed, mode):
    folder = OLD_WORK / "cases" / f"memory/{seed}/ordinary/{mode}/wait-1"
    value = read_json(folder / "result.json")
    raw = gzip.decompress((folder / "parent-state.json.gz").read_bytes())
    image = StateImage(raw)
    assert image.digest == value["state_sha256"]
    old_project = read_json(OLD_WORK / "platform.json")["project_id"]
    _, stored = study.db.load_checkpoint(old_project, value["id"])
    assert image.digest == stored.digest
    return value | {"image": image, "external_project": True}


def run_case(study, parent, mode, sign, variant, physical):
    key = f"reversal/{parent['seed']}/{mode}/{sign}/{variant}/physical{int(physical)}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, parent["seed"], parent=parent, config=VARIANTS[variant], observe=True)
    before = c.engine.capture_state()
    if variant == "silence":
        edges = [(e["source"], e["target"]) for e in before.to_dict()["edges"]]
        c.engine.intervene(edges=edges, action="silence")
        c.events.append(
            {
                "key": "reversal:silence",
                "kind": "research_intervention",
                "time_us": str(c.engine.time_us),
                "payload": {
                    "action": "silence",
                    "edges": edges,
                    "before": before.digest,
                    "after": c.engine.capture_state().digest,
                },
            }
        )
    start, points, original_observer = c.engine.time_us, [], c.session.host.observe

    def passive(engine, *args, **kwargs):
        result = original_observer(engine, *args, **kwargs)
        state = engine.capture_state().to_dict()
        points.append(
            {
                "time_us": engine.time_us,
                "nodes": state["nodes"],
                "edges": state["edges"],
                "operator_state": state["operator_state"],
                "transport": state["transport"],
            }
        )
        return result

    c.session.host.observe = passive
    c.session.begin_observation("reversal-physical-course")
    if physical:
        legacy.clip(c, sign, mode, legacy.dose(), domain="original", observed=True)
    else:
        legacy.wait(c, start + legacy.EPISODE)
    c.session.begin_observation("reversal-after-input")
    legacy.trajectory(c, c.engine.time_us + legacy.PROBE_US)
    write_gzip(c.folder / "trajectory.json.gz", points)
    old = read_json(OLD_WORK / "cases" / f"transfer/{c.seed}/ordinary/{mode}/original/{sign}/result.json")
    match = c.engine.capture_state().digest == old["state_sha256"] if variant == "1111" and physical else None
    ids = legacy.identities(c.seed)
    state = c.engine.capture_state().to_dict()
    result = c.finish(
        {
            "stage": "reversal",
            "mode": mode,
            "sign": sign,
            "variant": variant,
            "physical": physical,
            "parent": parent["id"],
            "start_us": start,
            "targets": [ids["A"], ids["B"]],
            "expected": int(sign < 0),
            "source_case": old["id"],
            "source_sha256": old["state_sha256"],
            "exact_replay": match,
            "unsilenced_edges": len(state["edges"]) - len(state["silenced_edges"]),
        }
    )
    if match is False:
        new_json(
            WORK / f"reversal-replay-failed-{c.seed}-{mode}-{sign}.json",
            {"key": key, "expected": old["state_sha256"], "actual": result["state_sha256"]},
        )
        raise RuntimeError("untreated replay does not match old final Core state; batch stopped")
    return result


def run(study, seeds, sham_only):
    register(study)
    study.allow_extension()
    # Validate all unmodified historical replays before interpreting interventions.
    for seed, mode, sign in itertools.product(seeds, ("full", "no_imu"), (1, -1)):
        p = old_parent(study, seed, mode)
        run_case(study, p, mode, sign, "1111", True)
    if sham_only:
        return
    for seed, mode, sign in itertools.product(seeds, ("full", "no_imu"), (1, -1)):
        p = old_parent(study, seed, mode)
        for variant, physical in itertools.product(VARIANTS, (False, True)):
            run_case(study, p, mode, sign, variant, physical)
        progress(study, f"reversal/{seed}/{mode}/{sign}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-only", action="store_true")
    parser.add_argument("--sham-only", action="store_true")
    parser.add_argument("--block", type=int, choices=SEEDS, action="append")
    args = parser.parse_args()
    study = Study(settings())
    try:
        if args.register_only:
            register(study)
        else:
            run(study, args.block or SEEDS, args.sham_only)
    except Exception as exc:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(exc), "budget_stop": True})
        raise
    finally:
        study.db.close()
