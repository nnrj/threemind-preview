"""Independent whole-system evidence audit; no Core or scoring-module imports."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes())


def digest(x):
    return hashlib.sha256(
        json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(work):
    cases = load(work / "cases.json")
    analysis = load(work / "analysis-v1.json")
    assert load(work / "status.json") == dict(state="awaiting-analysis", sequences_completed=32)
    assert not (work / "STOP").exists() and not (work / "in-flight.json").exists()
    states = 0
    adapter_files = {}
    question_count = 0
    fit_updates = 0
    source_seeds = set()
    scores = {}
    for case in cases:
        source_seeds.add(case["seed"])
        root = work / "subjects" / case["key"]
        previous = load(root / "birth.json.gz")
        receipts = sorted((load(p) for p in root.rglob("complete.json")), key=lambda r: r["ordinal"])
        assert [r["ordinal"] for r in receipts] == list(range(1, len(receipts) + 1))
        for receipt in receipts:
            assert sha(work / receipt["state_file"]) == receipt["sha256"]
            assert sha(work / receipt["result_file"]) == receipt["result_sha256"]
            current = load(work / receipt["state_file"])
            result = load(work / receipt["result_file"])
            assert digest(previous) == receipt["before_sha256"] and digest(current) == receipt["after_sha256"]
            assert int(current["core"]["time_us"]) >= int(previous["core"]["time_us"])
            assert current["events"][: len(previous["events"])] == previous["events"]
            assert current["samples"][: len(previous["samples"])] == previous["samples"]
            assert current["core"]["dynamics"] == "threemind.continuous-memory/5.3"
            assert current["mapping"] == previous["mapping"] and current["identity"] == case["identity"]
            for name, expected in current["adapter_ref"]["files"].items():
                path = work / current["adapter_ref"]["path"] / name
                if path not in adapter_files:
                    adapter_files[path] = sha(path)
                assert adapter_files[path] == expected
            if "updates" in result:
                assert result["updates"] == 1200 and int(current["core"]["time_us"]) == int(previous["core"]["time_us"])
                assert current["core"] == previous["core"]
                assert result["committed_updates"] == result["computed_updates"]
                fit_updates += result["updates"]
            if "rows" in result:
                for row in result["rows"]:
                    question_count += 1
                    assert len(row["frames"]) == 20 and len(row["reader_frames"]) == 8
                    assert all(len(f) == 8 for f in row["reader_frames"])
                    assert row["choice"] == max(range(2), key=lambda k: row["logits"][k])
                    assert row["body"]["position"] == row["choice"]
                    assert row["end_us"] - row["start_us"] == 1_000_000
                    assert row["events"][-1]["role"] == "body-feedback"
                    assert row["events"][-1]["channels"] == [[current["mapping"]["body" + str(row["choice"])], 0.2]]
                if "correct" in result:
                    assert result["correct"] == sum(r["choice"] == r["target"] for r in result["rows"])
                    assert previous["reader_digest"] == current["reader_digest"]
            states += 1
            previous = current
        individual = next(s for s in analysis["subjects"] if s["key"] == case["key"])
        goals = {}
        for stage in ("initial", "new", "reversal", "return"):
            targets = (
                {"P0", "P1", "A0", "A1"} if stage == "initial" else {"B0", "B1"} if stage == "new" else {"A0", "A1"}
            )
            protected = {"P0", "P1", "A0", "A1"} if stage in ("initial", "new") else {"P0", "P1", "B0", "B1"}
            passes = []
            for phase in ("immediate", "delayed"):
                rows = load(root / stage / phase / "result.json.gz")["rows"]
                for group, cues in (("target", targets), ("protected", protected), ("total", {r["cue"] for r in rows})):
                    selected = [r for r in rows if r["cue"] in cues]
                    correct = sum(r["choice"] == r["target"] for r in selected)
                    declared = individual["stages"][stage]["scores"][phase][group]
                    assert declared["correct"] == correct and declared["n"] == len(selected)
                    if group != "total":
                        passes.append(correct >= 0.75 * len(selected))
            goals[stage] = all(passes)
            scores.setdefault(case["curve"], {}).setdefault(stage, 0)
            scores[case["curve"]][stage] += int(goals[stage])
        assert goals == individual["goals"]
    for row in analysis["summary"]:
        assert scores[row["curve"]] == {k: v["passed"] for k, v in row["scores"].items()}
    return dict(
        passed=True,
        independent_origins=len(source_seeds),
        complete_individuals=len(cases),
        complete_boundaries=states,
        adapter_files_checked=len(adapter_files),
        questions=question_count,
        optimizer_updates=fit_updates,
        scores=scores,
        method="Independent JSON, hashes and arithmetic; no Core or primary analyzer",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    a = p.parse_args()
    r = audit(a.work)
    with (a.work / "independent-audit-v1.json").open("x", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(json.dumps(r))
