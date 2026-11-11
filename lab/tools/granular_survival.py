"""Reusable command interface for physical food, continuation and survivor birth.

python -m lab.tools.granular_survival --help
No database or running Lab service is required. Evidence folders are append-only.
"""

import argparse
import gzip
import json
import shutil
import signal
import threading
import time
from pathlib import Path

import psutil

from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth

from .granular_protocol import SurvivalProtocol
from .granular_session import SurvivalSession
from .service_study import encoded, new_json, read_json
from .survival import select_survivors


def load(folder):
    protocol = read_json(folder / "protocol.json")
    image = ArtifactCodec.decode((folder / "final.tmind").read_bytes())
    context = read_json(folder / "context.json")
    result = read_json(folder / "result.json")
    if result["final_hash"] != image.digest:
        raise ValueError("model and result receipt disagree")
    return protocol, image, context, result


def run(protocol, output, seconds, *, resume=None, born_from=None, wall_seconds=900, stop_file=None):
    if not 0 < seconds <= 3600 or not 0 < wall_seconds <= 14400:
        raise ValueError("duration exceeds one bounded tool operation")
    image = context = None
    origin = None
    if resume or born_from:
        old, image, context, result = load(resume or born_from)
        if old != protocol:
            raise ValueError("protocol differs from saved individual; edit explicitly in a separate study")
        if image.to_dict()["life"] == "dead":
            raise ValueError("a dead individual cannot continue or become a surviving parent")
        origin = {
            "folder": str(resume or born_from),
            "hash": image.digest,
            "mode": "birth" if born_from else "continuation",
        }
        if born_from:
            if image.to_dict()["life"] != "active" or result["status"] != "horizon":
                raise ValueError("birth requires an active, uncensored horizon survivor")
            image, context = birth(image), None
    SurvivalProtocol.model_validate(protocol)
    if round(seconds * 1e6) % protocol["world"]["period_us"]:
        raise ValueError("requested duration must contain whole control periods")
    output.mkdir(parents=True, exist_ok=False)
    stop = False

    def request_stop(*_):
        nonlocal stop
        stop = True

    previous = None
    start = time.monotonic()
    last_guard = 0.0
    status = "running"
    error = None
    with SurvivalSession(protocol, image=image, context=context) as s:
        if threading.current_thread() is threading.main_thread():
            previous = signal.signal(signal.SIGINT, request_stop)
        initial = s.engine.capture_state()
        (output / "initial.tmind").write_bytes(ArtifactCodec.encode(initial))
        new_json(output / "protocol.json", protocol)
        new_json(output / "origin.json", origin)
        target = s.engine.time_us + round(seconds * 1e6)
        try:
            with gzip.open(output / "events.jsonl.gz", "xb", compresslevel=3) as stream:

                def record(row):
                    stream.write(encoded(row) + b"\n")

                while s.engine.time_us < target and s.engine.life != "dead":
                    now = time.monotonic()
                    if stop or (stop_file and stop_file.exists()):
                        status = "paused-request"
                        break
                    if now - start >= wall_seconds:
                        status = "censored-wall"
                        break
                    if now - last_guard >= 1:
                        if (
                            psutil.Process().memory_info().rss > 4 * 2**30
                            or psutil.virtual_memory().available < 2 * 2**30
                        ):
                            status = "censored-memory"
                            break
                        if (
                            shutil.disk_usage(output).free < 15 * 2**30
                            or (output / "events.jsonl.gz").stat().st_size > 2 * 2**30
                        ):
                            status = "censored-storage"
                            break
                        last_guard = now
                    s.step(record)
                if status == "running":
                    status = "core-dead" if s.engine.life == "dead" else "horizon"
        except Exception as exc:  # noqa: BLE001 -- preserve failed trial evidence before returning failure
            status, error = "failed", type(exc).__name__ + ": " + str(exc)
        finally:
            if previous is not None:
                signal.signal(signal.SIGINT, previous)
        final = s.engine.capture_state()
        (output / "final.tmind").write_bytes(ArtifactCodec.encode(final))
        new_json(output / "context.json", s.context())
        result = {
            "schema": "threemind.granular-tool-result/1",
            "status": status,
            "error": error,
            "initial_hash": initial.digest,
            "final_hash": final.digest,
            "metrics": s.metrics(),
            "life": s.engine.life,
            "horizon_reached": s.engine.time_us >= target,
            "continuation_valid": s.engine.time_us == s.world.time_us and status != "failed",
            "wall_seconds": time.monotonic() - start,
            "origin": origin,
        }
        new_json(output / "result.json", result)
    return result


def select(folders, parents, offspring):
    rows = []
    for folder in folders:
        _, image, _, result = load(folder)
        state = image.to_dict()
        rows.append(
            {
                "id": str(folder.resolve()),
                "life": state["life"],
                "energy_reserve": state["energy"]["reserve"],
                "horizon_reached": result["horizon_reached"],
                "failed": result["status"] == "failed",
            }
        )
    return select_survivors(rows, parent_count=parents, offspring_count=offspring)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("template")
    a.add_argument("--output", type=Path, required=True)
    a = sub.add_parser("validate")
    a.add_argument("protocol", type=Path)
    sub.add_parser("schema")
    a = sub.add_parser("run")
    a.add_argument("--protocol", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    a.add_argument("--seconds", type=float, required=True)
    a.add_argument("--wall-seconds", type=int, default=900)
    a.add_argument("--stop-file", type=Path)
    b = a.add_mutually_exclusive_group()
    b.add_argument("--resume", type=Path)
    b.add_argument("--birth-from", type=Path)
    a = sub.add_parser("select")
    a.add_argument("folders", type=Path, nargs="+")
    a.add_argument("--parents", type=int, default=4)
    a.add_argument("--offspring", type=int, default=16)
    a.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.command == "template":
        new_json(a.output, SurvivalProtocol().model_dump(mode="json", by_alias=True))
        result = {"protocol": str(a.output)}
    elif a.command == "validate":
        result = {
            "valid": True,
            "protocol": SurvivalProtocol.model_validate_json(a.protocol.read_bytes()).model_dump(
                mode="json", by_alias=True
            ),
        }
    elif a.command == "schema":
        result = SurvivalProtocol.model_json_schema()
    elif a.command == "select":
        result = select(a.folders, a.parents, a.offspring)
        new_json(a.output, result)
    else:
        result = run(
            read_json(a.protocol),
            a.output,
            a.seconds,
            resume=a.resume,
            born_from=a.birth_from,
            wall_seconds=a.wall_seconds,
            stop_file=a.stop_file,
        )
    displayed = result
    if a.command == "run":
        displayed = {
            key: result[key]
            for key in ("status", "life", "horizon_reached", "continuation_valid", "wall_seconds", "error")
        }
        displayed.update(
            evidence=str(a.output),
            transferred=result["metrics"]["transferred"],
            energy=result["metrics"]["core"]["energy"]["reserve"],
        )
    print(json.dumps(displayed, ensure_ascii=False, allow_nan=False, default=str))
    if result.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
