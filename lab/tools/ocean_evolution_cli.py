"""Ocean /2 CLI with exact Arrow records, bounded execution and saved continuation."""

import argparse
import gzip
import hashlib
import json
import shutil
import time
from pathlib import Path

import psutil
import pyarrow as pa
from pyarrow import ipc

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_evolution import EvolutionOcean, EvolutionProtocol
from threemind_runtime.codec import ArtifactCodec

INPUT = pa.struct(
    [
        ("individual", pa.uint32()),
        ("time_us", pa.int64()),
        ("channels", pa.list_(pa.uint32())),
        ("values", pa.list_(pa.float64())),
        ("intensity", pa.float64()),
        ("food", pa.float64()),
        ("raw", pa.list_(pa.float64())),
        ("action", pa.list_(pa.float64())),
    ]
)
SCHEMA = pa.schema(
    [("time_us", pa.int64()), ("inputs", pa.list_(INPUT)), ("events", pa.string())],
    metadata={b"schema": b"threemind.ocean-inputs/2", b"floats": b"lossless IEEE754 float64"},
)


def apparatus():
    here = Path(__file__).parent
    return {
        n: hashlib.sha256((here / n).read_bytes()).hexdigest()
        for n in ("ocean.py", "ocean_evolution.py", "ocean_evolution_cli.py")
    }


def save_population(ocean, path):
    path.mkdir(parents=True, exist_ok=False)
    state = ocean.capture()
    for i, e in ocean.engines.items():
        (path / f"{i}.tmind").write_bytes(ArtifactCodec.encode(e.capture_state()))
    write_json(path / "manifest.json", {"context": state, "apparatus": apparatus()})


def load_population(path, backend="native"):
    value = read_json(path / "manifest.json")
    if value["apparatus"] != apparatus():
        raise ValueError("ocean /2 source changed; exact continuation refused")
    state = value["context"]
    images = {int(i): ArtifactCodec.decode((path / f"{i}.tmind").read_bytes()) for i in state["core_hashes"]}
    return EvolutionOcean(state["protocol"], state=state, images=images, backend=backend)


class RecordWriter:
    def __init__(self, folder, chunk_steps=1000):
        self.folder, self.chunk_steps = folder, chunk_steps
        folder.mkdir()
        self.rows, self.ordinal = [], 0

    def record(self, row):
        inputs = []
        for item in row["inputs"]:
            s = item["stimulus"]
            inputs.append(
                {
                    "individual": item["individual"],
                    "time_us": int(s["time_us"]),
                    "channels": [x[0] for x in s["channels"]],
                    "values": [x[1] for x in s["channels"]],
                    "intensity": s["intensity"],
                    "food": item["food"],
                    "raw": item["raw"],
                    "action": item["action"],
                }
            )
        self.rows.append(
            {
                "time_us": row["time_us"],
                "inputs": inputs,
                "events": json.dumps(row["events"], ensure_ascii=False, separators=(",", ":"), allow_nan=False),
            }
        )
        if len(self.rows) >= self.chunk_steps:
            self.flush()

    def flush(self):
        if not self.rows:
            return
        target = self.folder / f"{self.ordinal:06d}.arrow"
        temp = target.with_suffix(".partial")
        with (
            pa.OSFile(str(temp), "wb") as stream,
            ipc.new_file(stream, SCHEMA, options=ipc.IpcWriteOptions(compression="zstd")) as writer,
        ):
            writer.write_batch(pa.RecordBatch.from_pylist(self.rows, schema=SCHEMA))
        temp.rename(target)
        self.rows = []
        self.ordinal += 1


def iter_records(folder):
    for path in sorted(folder.glob("*.arrow")):
        with pa.memory_map(str(path), "r") as source:
            reader = ipc.open_file(source)
            if reader.schema != SCHEMA:
                raise ValueError("unknown ocean record schema")
            for b in range(reader.num_record_batches):
                for row in reader.get_batch(b).to_pylist():
                    inputs = []
                    for i in row["inputs"]:
                        inputs.append(
                            {
                                "individual": i["individual"],
                                "stimulus": {
                                    "time_us": str(i["time_us"]),
                                    "channels": [list(x) for x in zip(i["channels"], i["values"], strict=True)],
                                    "intensity": i["intensity"],
                                },
                                "food": i["food"],
                                "raw": i["raw"],
                                "action": i["action"],
                            }
                        )
                    yield {"time_us": row["time_us"], "inputs": inputs, "events": json.loads(row["events"])}


def run(ocean, output, duration_us, *, wall_seconds=7200, guard=None, checkpoint_us=120000000):
    if duration_us <= 0 or duration_us % ocean.p.period_us or wall_seconds <= 0:
        raise ValueError("positive duration in complete sampling periods required")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "protocol.json", ocean.p.model_dump(by_alias=True))
    save_population(ocean, output / "initial")
    records = RecordWriter(output / "inputs")
    start_us, started = ocean.time_us, time.monotonic()
    next_checkpoint = ocean.time_us + checkpoint_us
    status, error = "observing", None
    events = []
    try:
        with gzip.open(output / "trajectory.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as trajectory:

            def record(row):
                records.record(row)
                events.extend(row["events"])

            while ocean.time_us < start_us + duration_us:
                if (ocean.time_us - start_us) % 1000000 == 0:
                    if guard:
                        guard()
                    if time.monotonic() - started > wall_seconds or (output / "STOP").exists():
                        status = "paused_resource_limit"
                        break
                    if (
                        psutil.Process().memory_info().rss > 4 * 2**30
                        or psutil.virtual_memory().available < 2 * 2**30
                        or shutil.disk_usage(output).free < 15 * 2**30
                    ):
                        status = "paused_resource_limit"
                        break
                    metrics = ocean.metrics()
                    if abs(metrics["energy_balance_error"]) > max(1e-4, ocean.totals["environment_food"] * 1e-9):
                        raise RuntimeError("population energy conservation failed")
                    # Include actual food coordinates; the viewer never invents them.
                    metrics["food_positions"] = ocean.food.tolist()
                    trajectory.write(
                        json.dumps(metrics, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
                    )
                ocean.step(record)
                if ocean.time_us >= next_checkpoint:
                    records.flush()
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
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 -- preserve failed runs with explicit status
        error = f"{type(exc).__name__}: {exc}"
        status = "paused_error"
    records.flush()
    save_population(ocean, output / "final")
    write_json(output / "events.json", events)
    result = ocean.metrics() | {
        "status": status,
        "error": error,
        "wall_seconds": time.monotonic() - started,
        "observed_us": ocean.time_us - start_us,
        "horizon_reached": ocean.time_us == start_us + duration_us,
        "food_positions": ocean.food.tolist(),
    }
    write_json(output / "result.json", result)
    return result


def verify(path, steps=None):
    world = load_population(path / "initial")
    count = 0
    for expected in iter_records(path / "inputs"):
        if steps is not None and count >= steps:
            return {"complete": False, "steps": count, "matched": True}
        observed = []
        world.step(observed.append)
        if observed != [expected]:
            raise ValueError(f"input/action/event mismatch at step {count}")
        count += 1
    final = load_population(path / "final")
    if world.capture() != final.capture():
        raise ValueError("final population differs")
    return {"complete": True, "steps": count, "matched": True, "population": len(world.bodies)}


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
    execute.add_argument("--wall-seconds", type=float, default=7200)
    execute.add_argument("--resume", type=Path)
    replay = commands.add_parser("verify")
    replay.add_argument("folder", type=Path)
    replay.add_argument("--steps", type=int)
    args = parser.parse_args()
    if args.command == "template":
        answer = EvolutionProtocol().model_dump(by_alias=True)
    elif args.command == "schema":
        answer = EvolutionProtocol.model_json_schema()
    elif args.command == "validate":
        answer = EvolutionProtocol.model_validate(read_json(args.protocol)).model_dump(by_alias=True)
    elif args.command == "verify":
        answer = verify(args.folder, args.steps)
    else:
        protocol = EvolutionProtocol.model_validate(read_json(args.protocol)).model_dump(by_alias=True)
        world = load_population(args.resume) if args.resume else EvolutionOcean(protocol)
        if world.p.model_dump(by_alias=True) != protocol:
            parser.error("resume cannot change saved protocol")
        answer = run(world, args.output, round(args.seconds * 1e6), wall_seconds=args.wall_seconds)
        answer = {
            k: answer[k] for k in ("status", "error", "time_us", "wall_seconds", "totals", "energy_balance_error")
        }
    print(json.dumps(answer, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
