"""Record real host/process telemetry for equal-input, accelerated replay."""

import argparse
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from threemind_runtime.telemetry import HostTelemetryConfig, ProcessTelemetryConfig, TelemetryEncoder
from threemind_runtime.telemetry_probe import SystemTelemetryProbe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=840)
    parser.add_argument("--interval-ms", type=int, default=1000)
    parser.add_argument("--intensity", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20261004)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600 or not 100 <= args.interval_ms <= 60000:
        raise ValueError("recording must be 1..3600s at 100..60000ms intervals")
    configs = {
        "host": HostTelemetryConfig(enabled=True, intensity=args.intensity, sample_interval_ms=args.interval_ms),
        "process": ProcessTelemetryConfig(enabled=True, intensity=args.intensity, sample_interval_ms=args.interval_ms),
    }
    encoders = {k: TelemetryEncoder(args.seed, v) for k, v in configs.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = args.output.with_suffix(".metadata.json")
    if args.output.exists() or metadata.exists():
        raise FileExistsError("recording exists; do not overwrite or join unrelated clock intervals")
    probe = SystemTelemetryProbe()
    start = time.monotonic()
    with metadata.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "schema": "threemind.telemetry-recording/1",
                "requested_seconds": args.seconds,
                "configs": {k: asdict(v) for k, v in configs.items()},
                "seed": args.seed,
                "epoch_started": time.time(),
                "probe_backend": probe.backend,
                "process_scope": "recorder process, not a consciousness worker",
                "runtime_scope": "not measured; no fabricated per-instance readings",
                "time_rule": "actual monotonic elapsed microseconds; replay retains them",
            },
            stream,
        )
    count = 0
    with args.output.open("x", encoding="utf-8") as stream:
        while True:
            deadline = start + count * args.interval_ms / 1000
            while time.monotonic() < deadline:
                time.sleep(min(0.25, deadline - time.monotonic()))
            now = time.monotonic()
            if (args.output.parent / "STOP").exists():
                raise RuntimeError("recording STOP file")
            if count % 30 == 0:
                if shutil.disk_usage("C:/").free < 5 * 2**30 or shutil.disk_usage("E:/").free < 15 * 2**30:
                    raise RuntimeError("disk reserve")
                if args.output.stat().st_size > 128 * 2**20:
                    raise RuntimeError("recording exceeds 128MiB")
            measurements = dict(zip(("host", "process"), probe.collect(now)))
            elapsed = round((now - start) * 1e6)
            for scope, source in measurements.items():
                raw = {k: v.to_dict() for k, v in source.items()}
                stimulus, audit = encoders[scope].encode(raw, monotonic_s=now, delivery_us=elapsed)
                stream.write(
                    json.dumps(
                        {
                            "sample": count,
                            "time_us": str(elapsed),
                            "scope": scope,
                            "raw": raw,
                            "audit": audit,
                            "stimulus": stimulus.to_dict() if stimulus else None,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            stream.flush()
            if count % 60 == 0:
                print(json.dumps({"recorded_seconds": round(now - start, 2), "samples": count + 1}), flush=True)
            count += 1
            if now - start >= args.seconds:
                break
    with args.output.with_suffix(".complete.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "samples": count,
                "elapsed_seconds": now - start,
                "encoder_states": {k: v.capture() for k, v in encoders.items()},
            },
            stream,
        )


if __name__ == "__main__":
    main()
