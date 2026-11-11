"""Prespecified secondary cue-dose follow-up; original test results stay intact."""

import argparse
import json

from experiment import CONDITIONS, HERE, WORK, guard, probe, protocol, read_json, study

from lab.tools.recorded_background import RecordedBackground
from lab.tools.service_study import new_json
from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run"))
    args = parser.parse_args()
    s = study()
    try:
        if args.action == "register":
            for language in ("zh", "en"):
                s.note(
                    "cue-dose-design:" + language,
                    "E43 提示强度诊断 / Cue-dose diagnosis " + language,
                    (HERE / f"probe-dose.{language}.md").read_text(encoding="utf-8"),
                )
            new_json(
                WORK / "cue-dose-registered.json",
                {"extra_cases": 40, "cue_intensity": 1.0, "primary_criterion_unchanged": True},
            )
            return
        if not (WORK / "cue-dose-registered.json").exists():
            raise RuntimeError("register the secondary comparison first")
        tape, assets = RecordedBackground(WORK / "physical-telemetry.jsonl"), read_json(WORK / "assets.json")
        for seed in (17, 29):
            for condition in CONDITIONS:
                for cue in (1, 3, 5, 7):
                    probe(s, tape, assets, seed, condition, 830, cue, intensity=1, prefix="d1-", kind="probe-dose")
            cases = [read_json(p) for p in sorted((WORK / "cases").glob(f"d1-s{seed}-*/result.json"))]
            rows = [
                {
                    "key": c["key"],
                    "condition": c["condition"],
                    "probe": c["probe"],
                    "label": c["label"],
                    "features": c["windows"][1]["features"],
                }
                for c in cases
                if len(c["windows"]) >= 2
            ]
            path = WORK / "computations" / f"dose1-s{seed}"
            if (path / "result.json").exists():
                continue
            if path.exists():
                raise RuntimeError("partial decode retained")
            guard(s, True)
            policy = LanguageCompute(
                compute_device="cuda",
                memory_mib=6144,
                wall_seconds=min(1800, max(1, int(7200 - s.completed_wall - s.compute_wall))),
                threads=2,
            )
            payload = {"protocol": protocol(seed).model_dump(), "windows": [r["features"] for r in rows]}
            new_json(path / "index.json", [r | {"window": 1} for r in rows])
            new_json(
                path / "request.json", {"policy": policy.model_dump(), "operation": "decode_many", "payload": payload}
            )
            try:
                result, _ = compute(
                    "decode_many", payload, policy, head=(WORK / f"head-{seed}.safetensors").read_bytes()
                )
            except Exception as error:
                new_json(path / "failure.json", {"error": str(error), "evidence": getattr(error, "report", None)})
                raise
            new_json(path / "result.json", result)
            print(
                json.dumps(
                    {"diagnostic_seed": seed, "cases": len(cases), "decoded_seconds": result.get("elapsed_seconds")}
                ),
                flush=True,
            )
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
