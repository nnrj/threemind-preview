"""Python/CLI access to the same ocean apparatus, with atomic population images."""

import argparse
import gzip
import hashlib
import json
import shutil
import time
from pathlib import Path

import psutil

from lab.tools.ocean import Ocean, OceanProtocol
from threemind_runtime.codec import ArtifactCodec


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)


def read_json(path):
    return json.loads(path.read_bytes())


def save_population(ocean, path):
    """New immutable directory; manifest is the commit marker, written last."""
    path.mkdir(parents=True, exist_ok=False)
    context = ocean.capture()
    for i, e in ocean.engines.items():
        (path / f"{i}.tmind").write_bytes(ArtifactCodec.encode(e.capture_state()))
    source = Path(__file__).with_name("ocean.py")
    write_json(
        path / "manifest.json",
        {"context": context, "apparatus_sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
    )


def load_population(path, backend="native"):
    value = read_json(path / "manifest.json")
    if hashlib.sha256(Path(__file__).with_name("ocean.py").read_bytes()).hexdigest() != value["apparatus_sha256"]:
        raise ValueError("ocean implementation changed; exact continuation refused")
    context = value["context"]
    images = {int(i): ArtifactCodec.decode((path / f"{i}.tmind").read_bytes()) for i in context["core_hashes"]}
    return Ocean(context["protocol"], state=context, images=images, backend=backend)


def run(ocean, output, duration_us, *, wall_seconds=900, guard=None, checkpoint_us=120000000):
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "protocol.json", ocean.p.model_dump(by_alias=True))
    save_population(ocean, output / "initial")
    started = time.monotonic()
    start_us = ocean.time_us
    error = None
    status = "observing"
    events = []
    next_checkpoint = ocean.time_us + checkpoint_us
    try:
        with (
            gzip.open(output / "inputs.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as evidence,
            gzip.open(output / "trajectory.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as trajectory,
        ):

            def record(row):
                evidence.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
                events.extend(row["events"])

            while ocean.time_us < start_us + duration_us:
                if (ocean.time_us - start_us) % 1000000 == 0:
                    if guard:
                        guard()
                    if time.monotonic() - started > wall_seconds or (output / "STOP").exists():
                        status = "paused_resource_limit"
                        break
                    if psutil.Process().memory_info().rss > 4 * 2**30 or psutil.virtual_memory().available < 2 * 2**30:
                        status = "paused_resource_limit"
                        break
                    if shutil.disk_usage(output).free < 15 * 2**30:
                        status = "paused_resource_limit"
                        break
                    metrics = ocean.metrics()
                    if abs(metrics["energy_balance_error"]) > max(1e-5, ocean.totals["environment_food"] * 1e-9):
                        raise RuntimeError("population energy conservation failed")
                    trajectory.write(json.dumps(metrics, ensure_ascii=False, separators=(",", ":")) + "\n")
                ocean.step(record)
                if ocean.time_us >= next_checkpoint:
                    save_population(ocean, output / "checkpoints" / str(ocean.time_us))
                    write_json(
                        output / f"progress-{ocean.time_us}.json",
                        {
                            "time_us": ocean.time_us,
                            "wall_seconds": time.monotonic() - started,
                            "physical": sum(b.physical for b in ocean.bodies.values()),
                            "births": ocean.totals["births"],
                        },
                    )
                    next_checkpoint += checkpoint_us
                if all(e.life == "dead" for e in ocean.engines.values()):
                    status = "extinct"
                    break
            else:
                status = "horizon_paused"
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 -- checkpoint failed experiments without hiding status
        error = f"{type(exc).__name__}: {exc}"
        status = "paused_error"
    save_population(ocean, output / "final")
    write_json(output / "events.json", events)
    result = ocean.metrics() | {
        "status": status,
        "error": error,
        "wall_seconds": time.monotonic() - started,
        "observed_us": ocean.time_us - start_us,
        "horizon_reached": ocean.time_us == start_us + duration_us,
    }
    write_json(output / "result.json", result)
    return result


def verify(path, steps=None):
    ocean = load_population(path / "initial")
    count = 0
    with gzip.open(path / "inputs.jsonl.gz", "rt", encoding="utf-8") as rows:
        for line in rows:
            if steps is not None and count >= steps:
                return {"complete": False, "steps": count, "matched": True}
            expected = json.loads(line)
            observed = []
            ocean.step(observed.append)
            if observed != [expected]:
                raise ValueError(f"recorded input/action/event mismatch at step {count}")
            count += 1
    final = load_population(path / "final")
    if json.dumps(ocean.capture(), sort_keys=True) != json.dumps(final.capture(), sort_keys=True):
        raise ValueError("final population differs")
    return {"complete": True, "steps": count, "matched": True, "population": len(ocean.bodies)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("template")
    commands.add_parser("schema")
    validate = commands.add_parser("validate")
    validate.add_argument("protocol", type=Path)
    execute = commands.add_parser("run")
    execute.add_argument("protocol", type=Path)
    execute.add_argument("output", type=Path)
    execute.add_argument("--seconds", type=float, required=True)
    execute.add_argument("--wall-seconds", type=float, default=900)
    execute.add_argument("--resume", type=Path)
    replay = commands.add_parser("verify")
    replay.add_argument("folder", type=Path)
    replay.add_argument("--steps", type=int)
    args = parser.parse_args()
    if args.command == "template":
        result = OceanProtocol().model_dump(by_alias=True)
    elif args.command == "schema":
        result = OceanProtocol.model_json_schema()
    elif args.command == "validate":
        result = OceanProtocol.model_validate(read_json(args.protocol)).model_dump(by_alias=True)
    elif args.command == "verify":
        result = verify(args.folder, args.steps)
    else:
        protocol = OceanProtocol.model_validate(read_json(args.protocol)).model_dump(by_alias=True)
        ocean = load_population(args.resume) if args.resume else Ocean(protocol)
        if ocean.p.model_dump(by_alias=True) != protocol:
            parser.error("resume cannot replace the saved protocol")
        duration = round(args.seconds * 1e6)
        if duration <= 0 or duration % ocean.p.period_us or args.wall_seconds <= 0:
            parser.error("positive wall budget and whole positive sampling duration required")
        result = run(ocean, args.output, duration, wall_seconds=args.wall_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
