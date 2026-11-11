"""Replay the latest old evidence, without creating Core or touching its sources."""

import gzip
import hashlib
import itertools
import json
import math
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / ".work/intensity-mechanisms-20260930"
DEST = ROOT / ".work/priority-memory-20261001"


def integral(points, channel):
    values = {
        int(p["time_us"]): next((n["activation"] for n in p["nodes"] if n["channel"] == channel), 0.0) for p in points
    }
    ordered = sorted(values.items())
    return math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(ordered))


def main():
    # Only the encoder is imported; no Engine, Study or database is created.
    from threemind_runtime.adapters import channel_id

    start, hashes, rows = time.monotonic(), {}, []

    def read(path, zipped=False):
        body = path.read_bytes()
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(body).hexdigest()
        return gzip.decompress(body) if zipped else body

    for path in sorted((SOURCE / "cases").rglob("result.json")):
        if time.monotonic() - start > 180:
            raise RuntimeError("read-only calibration exceeded three minutes")
        result = json.loads(read(path))
        meta = result["extra"]
        if meta.get("stage") != "probe" or meta.get("failure"):
            continue
        trajectory = json.loads(read(path.parent / "trajectory.json.gz", True))
        channel = channel_id(result["seed"], "intensity-mechanisms/1", 1)
        events = [json.loads(line) for line in read(path.parent / "events.jsonl.gz", True).splitlines()]
        window = next(
            (e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")),
            {},
        )
        node_id = next((n["id"] for p in trajectory for n in p["nodes"] if n["channel"] == channel), None)
        ranking = window.get("analyses", {}).get("pattern", {}).get("nodes", [])
        times = sorted({p["time_us"] for p in trajectory})
        assert times[0] == meta["probe_start_us"] and times[-1] - times[0] == 5_000_000
        rows.append(
            {
                "key": result["key"],
                "parent": meta["parent"],
                "cue": meta["cue"],
                "history": meta["history"],
                "start": times[0],
                "end": times[-1],
                "max_gap_us": max(b - a for a, b in itertools.pairwise(times)),
                "integral": integral(trajectory, channel),
                "final_activation": next((n["activation"] for n in ranking if n["node_id"] == node_id), 0.0),
            }
        )
    index = {r["key"]: r for r in rows}
    groups = Counter()
    for row in rows:
        if not row["cue"]:
            continue
        key = row["key"].replace(f"/cue{row['cue']}", "/cue0.0", 1)
        base = index.get(key)
        if base is None:
            row["paired"] = False
            continue
        assert (base["parent"], base["start"], base["end"]) == (row["parent"], row["start"], row["end"])
        row.update(paired=True, net=row["integral"] - base["integral"])
        groups["paired_cued"] += 1
        groups["positive_1e9"] += row["net"] > 1e-9
        groups["positive_1e6"] += row["net"] > 1e-6
        groups["final_positive"] += row["final_activation"] > 1e-9
        if row["history"] == "none":
            groups["untrained"] += 1
            groups["untrained_positive"] += row["net"] > 1e-9
        if "-connection-silence" in row["key"]:
            groups["silenced"] += 1
            groups["silenced_positive"] += row["net"] > 1e-9
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == h for path, h in hashes.items())
    output = {
        "schema": "threemind.priority-calibration/1",
        "new_simulations": 0,
        "counts": dict(groups),
        "windows": len(rows),
        "max_gap_us": max(r["max_gap_us"] for r in rows),
        "rows": rows,
        "sources": hashes,
        "source_hashes_unchanged": True,
        "wall_seconds": time.monotonic() - start,
    }
    body = json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2).encode()
    if len(body) > 256 * 1024**2:
        raise RuntimeError("calibration evidence size limit")
    DEST.mkdir(parents=True, exist_ok=True)
    with (DEST / "calibration.json").open("xb") as out:
        out.write(body)
    print(json.dumps({k: v for k, v in output.items() if k not in ("rows", "sources")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
