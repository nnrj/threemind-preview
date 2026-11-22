"""Read a sealed P1 or P2 aquatic checkpoint and count recorded events up to it."""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def checked_bytes(archive, manifest, name):
    payload = archive.read(name)
    if hashlib.sha256(payload).hexdigest() != manifest[name]:
        raise ValueError(f"Member checksum mismatch: {archive.filename}/{name}")
    return payload


def summarize(case, last):
    segments = sorted(case.glob("seg-*.zip"))
    if last is not None:
        end = case / f"seg-{last:04d}.zip"
        if end not in segments:
            raise ValueError(f"Missing sealed boundary: {end}")
        segments = [path for path in segments if path.name <= end.name]
    if not segments:
        raise ValueError(f"No sealed segment in {case}")
    counts = Counter()
    time_us, state_hash = 0, None
    for path in segments:
        with ZipFile(path) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
            if len(names) != len(set(names)) or set(names) != set(manifest) | {"manifest.json"}:
                raise ValueError(f"Invalid member list: {path}")
            meta = json.loads(checked_bytes(archive, manifest, "segment.json"))
            if meta["start_us"] != time_us or (state_hash is not None and meta["start_hash"] != state_hash):
                raise ValueError(f"Discontinuous segment: {path}")
            time_us, state_hash = meta["end_us"], meta["end_hash"]
            events = checked_bytes(archive, manifest, "events.jsonl.gz")
            with gzip.GzipFile(fileobj=io.BytesIO(events)) as stream:
                counts.update(json.loads(line)["kind"] for line in stream)
            if path == segments[-1]:
                payload = checked_bytes(archive, manifest, "end.zip")
    with ZipFile(io.BytesIO(payload)) as checkpoint:
        world = json.loads(checkpoint.read("world.json"))
        core_count = sum(name.startswith("cores/") and name.endswith(".json") for name in checkpoint.namelist())
    if world["time_us"] != time_us:
        raise ValueError("The checkpoint and last sealed segment end at different times.")
    state = world["context"]
    while "bodies" not in state:
        key = next((k for k in ("carrion", "material", "enclosure", "group", "community", "world") if k in state), None)
        if key is None:
            raise ValueError("No body records in checkpoint")
        state = state[key]
    bodies = state["bodies"]
    return dict(last_segment=segments[-1].name, internal_seconds=time_us / 1_000_000,
                saved_cores=core_count, alive=sum(bool(b["physical"]) for b in bodies),
                highest_generation=max(b["generation"] for b in bodies), births=counts["birth"],
                live_predation=counts["body_engulfed"], scavenging=counts["carrion_meal"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="Directory containing the sealed seg-*.zip files")
    parser.add_argument("--last", type=int, help="Last segment number to include, inclusive")
    args = parser.parse_args()
    print(json.dumps(summarize(args.case, args.last), indent=2))
