"""Independent original-file arithmetic; imports neither Core nor main analysis."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(work):
    cases = read(work / "cases.json")
    analysis = read(work / "analysis-v1.json")
    assert read(work / "status.json") == dict(state="awaiting-analysis", sequences_completed=len(cases))
    assert not (work / "in-flight.json").exists()
    assert not (work / "STOP").exists()
    cache = {}
    total_seconds = 0
    files = 0
    for case in cases:
        folder = work / "subjects" / case["key"]
        previous = read(folder / "birth.json.gz")
        assert previous["case"] == case
        results = []
        for phase in ("teaching", "probe"):
            receipt = read(folder / phase / "complete.json")
            for field, sha_field in (("state_file", "sha256"), ("result_file", "result_sha256")):
                path = work / receipt[field]
                assert path.resolve().is_relative_to(work.resolve())
                assert file_hash(path) == receipt[sha_field], str(path)
                files += 1
            state = read(work / receipt["state_file"])
            result = read(work / receipt["result_file"])
            assert receipt["before_sha256"] == digest(previous)
            assert receipt["after_sha256"] == digest(state)
            assert int(receipt["start_us"]) == int(previous["core"]["time_us"])
            assert int(receipt["end_us"]) == int(state["core"]["time_us"])
            assert int(receipt["end_us"]) >= int(receipt["start_us"])
            assert state["core"]["dynamics"] == "threemind.experimental-weight-decay/1"
            assert state["case"] == case and state["mapping"] == previous["mapping"]
            assert len(state["events"]) >= len(previous["events"])
            assert state["events"][: len(previous["events"])] == previous["events"]
            total_seconds += (int(receipt["end_us"]) - int(receipt["start_us"])) / 1e6
            previous = state
            results.append(result)
        probe = results[1]
        end = results[0]["teaching_end_us"]
        assert probe["response"]["start_us"] == end + case["delay"] * 1_000_000
        assert probe["response"]["end_us"] == probe["response"]["start_us"] + 1_000_000
        assert len(probe["response"]["frames"]) == len(probe["baseline"]["frames"]) == 20
        cache[case["origin"], case["curve"], case["course"], case["delay"], case["history"], case["cue"]] = results
    counts = {}
    origins = sorted({c["origin"] for c in cases})
    curves = sorted({c["curve"] for c in cases})

    def edges(g, h):
        pair = {"cue", "out" + str(h)}
        return [e for e in g["edges"] if {e["source_symbol"], e["target_symbol"]} == pair]

    def series(o, c, course, d):
        vector = []
        for frame in range(20):
            for port in ("out0", "out1"):
                for f in ("activation", "inhibition", "direct", "associative"):
                    value = 0.0
                    for h, history_sign in ((0, -1), (1, 1)):
                        for q, cue_sign in ((False, -1), (True, 1)):
                            p = cache[o, c, course, d, h, q][1]
                            value += (
                                history_sign
                                * cue_sign
                                * (p["response"]["frames"][frame][port][f] - p["baseline"]["frames"][frame][port][f])
                            )
                    vector.append(value)
        return vector

    def tail(e, c):
        a = e["decay_age"]
        seconds = 2_592_000
        if c == "inverse-logarithmic":
            b = a + seconds / e["half_life"]
            return e["weight"] * (1 + math.log1p((math.e - 1) * a)) / (1 + math.log1p((math.e - 1) * b))
        k = math.log(2) / 86400
        h = 0.012 if c.endswith("slow") else 0.06
        w = e["weight"]
        if not w:
            return 0.0
        if c.startswith("matched"):
            return w * math.exp(-(k + h * (1 - 0.035)) * seconds)
        # Reciprocal solution; long horizon exceeds floating exponential range.
        x = (k + h) * seconds
        if x > 700:
            return 0.0
        return 1 / ((1 / w - h / (k + h)) * math.exp(x) + h / (k + h))

    for c in curves:
        counts[c] = {}
        for o in origins:
            goals = {}
            for course in ("spaced", "strong", "novelty"):
                surviving = [edges(cache[o, c, course, 300, h, False][1]["before"], h) for h in (0, 1)]
                goals["S:" + course] = all(len(e) == 2 for e in surviving)
                goals["F:" + course] = all(tail(e, c) < 0.008 for es in surviving for e in es)
                a = series(o, c, course, 1)
                b = series(o, c, course, 300)
                aa = sum(x * x for x in a)
                bb = sum(x * x for x in b)
                cos = sum(x * y for x, y in zip(a, b)) / math.sqrt(aa * bb) if aa * bb else 0.0
                goals["E:" + course] = (
                    math.sqrt(aa / 160) > 1e-4 and math.sqrt(bb / 160) > 1e-4 and bb >= 0.01 * aa and cos >= 0.8
                )
            goals["W"] = all(not edges(cache[o, c, "weak", 30, h, False][1]["before"], h) for h in (0, 1))
            formed = all(len(edges(cache[o, c, "weak", 1, h, True][0]["samples"][-1], h)) == 2 for h in (0, 1))
            goals["W"] = formed and goals["W"]
            declared = next(d for d in analysis["details"] if d["origin"] == o and d["curve"] == c)
            assert goals == declared["goals"], (o, c, goals, declared["goals"])
            for k, v in goals.items():
                counts[c][k] = counts[c].get(k, 0) + int(v)
        declared = next(r for r in analysis["summary"] if r["curve"] == c)
        assert counts[c] == {k: v["passed"] for k, v in declared["scores"].items()}
    return dict(
        passed=True,
        sequences=len(cases),
        complete_boundaries=2 * len(cases),
        checked_files=files,
        internal_seconds=total_seconds,
        independent_origins=len(origins),
        scores=counts,
        method="Separate file hashes, continuity chain and arithmetic; no Core or primary analysis imports.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    work = p.parse_args().work
    result = audit(work)
    with (work / "independent-audit-v1.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))
