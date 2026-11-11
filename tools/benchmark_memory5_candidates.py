"""Compare preserved isolated executables; never build, install or restore a subject."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    for path in (work, output):
        if not path.is_relative_to((ROOT / ".work").resolve()):
            raise ValueError("Use ignored repository .work paths")
    binaries = ["baseline", "cache", "weight-view"]
    config = work / "configs.json"
    sources = json.loads((work / "source-hashes.json").read_text(encoding="utf-8"))
    for relative, expected in sources.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Production source changed: {relative}")
    evidence = [config, work / "source-hashes.json", Path(__file__).resolve()]
    evidence += [work / f"{name}.exe" for name in binaries]
    for phase in ("cache", "weight-view"):
        manifest = work / f"memory5-perf-{phase}.json"
        if json.loads(manifest.read_text(encoding="utf-8"))["status"] != "applied":
            raise ValueError("Candidate preparation incomplete")
        evidence.append(manifest)
    provenance = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence
    }
    output.mkdir(parents=True, exist_ok=False)
    cases = [("5-h", 64, 2, "dense", 8), ("5-h", 1024, 100, "pairs", 8)]
    cases += [(arm, 16, 2, "dense", 1) for arm in ("2", "3.1", "4-h", "4-s", "5-s", "5-no-h")]
    results = []
    for arm, channels, seconds, pattern, rounds in cases:
        rows = []
        for repetition in range(rounds):
            order = binaries if repetition % 2 == 0 else list(reversed(binaries))
            for name in order:
                raw = subprocess.check_output(
                    [str(work / f"{name}.exe"), str(config), arm, str(channels), str(seconds), pattern],
                    text=True, encoding="utf-8", timeout=300,
                )
                row = json.loads(raw)
                row.update(binary=name, repetition=repetition, warmup=rounds > 1 and repetition == 0)
                path = output / f"{arm}-{channels}-{seconds}-{pattern}-{repetition}-{name}.json"
                with path.open("x", encoding="utf-8") as stream:
                    json.dump(row, stream, indent=2)
                rows.append(row)
        hashes = {row["state_hash"] for row in rows}
        if len(hashes) != 1:
            raise ValueError(f"Full final state mismatch: {arm}/{channels}/{pattern}; raw evidence retained")
        samples = {
            name: [row["advance_s"] for row in rows if row["binary"] == name and not row["warmup"]]
            for name in binaries
        }
        medians = {name: statistics.median(values) for name, values in samples.items()}
        result = {
            "arm": arm, "channels": channels, "simulation_s": seconds, "pattern": pattern,
            "purpose": "repeated timing" if rounds > 1 else "single state control, not a timing conclusion",
            "measured_rounds": rounds - 1 if rounds > 1 else 1,
            "state_hash": hashes.pop(), "samples_s": samples, "medians_s": medians,
            "reduction_percent": {name: 100 * (1 - medians[name] / medians["baseline"]) for name in binaries[1:]},
        }
        results.append(result)
        print(json.dumps(result), flush=True)
    summary = {
        "schema": "threemind.memory5-candidate-benchmark/1",
        "created_utc": datetime.now(UTC).isoformat(), "provenance": provenance,
        "scope": "Fresh synthetic engineering objects, alternating order, no instrumentation, no installation",
        "limits": ["Final-state witnesses only, not all intermediate trajectories or restore proof.",
                   "Shared workstation; no confidence interval or formal training speed claim."],
        "results": results,
    }
    with (output / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)


if __name__ == "__main__":
    main()
