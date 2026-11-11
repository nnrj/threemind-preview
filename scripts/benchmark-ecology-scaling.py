"""Native headless population capacity probe, with explicit observation settings.

Creates only synthetic in-memory populations and one requested JSON result.
No Lab/database, previous data, renderer or scientific conclusion is involved.
"""

import argparse
import gc
import json
import platform
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

import psutil

from threemind_runtime.ecology import EcologyCoordinator, EcologySettings
from threemind_runtime.population_participant import ParticipantConfig
from threemind_runtime.world_schema import default_world


def measure(count, duration, habitat):
    settings = EcologySettings(founder_count=count)
    settings.rules.habitat = habitat
    settings.rules.reproduction.population_limit = count
    settings.rules.reproduction.enabled = False
    options = ParticipantConfig()
    process = psutil.Process()
    gc.collect()
    rss_before = process.memory_info().rss
    start, cpu = time.perf_counter(), time.process_time()
    with EcologyCoordinator(default_world(), settings, participant_options=options) as runtime:
        initialized = time.perf_counter()
        rss_after_initialize = process.memory_info().rss
        runtime.advance_to(duration)
        advanced, cpu_after_advance = time.perf_counter(), time.process_time()
        rss_after_advance = process.memory_info().rss
        metadata, images = runtime.checkpoint()
        captured = time.perf_counter()
        rss_after_capture = process.memory_info().rss
        metadata_bytes = len(json.dumps(metadata, ensure_ascii=True, separators=(",", ":")).encode())
        model_bytes = sum(len(image.payload) for image in images.values())
        result = {
            "individuals": count,
            "living_bodies": len(runtime.world.members),
            "core_not_dead": sum(p.engine.life != "dead" for p in runtime.participants.values()),
            "duration_us": duration,
            "initialization_s": initialized - start,
            "advance_s": advanced - initialized,
            "initialization_and_advance_cpu_s": cpu_after_advance - cpu,
            "checkpoint_s": captured - advanced,
            "simulated_seconds_per_wall_second": duration / 1e6 / (advanced - initialized),
            "sampled_rss_bytes": {
                "before": rss_before,
                "initialized": rss_after_initialize,
                "advanced": rss_after_advance,
                "captured": rss_after_capture,
            },
            "metadata_json_bytes": metadata_bytes,
            "brain_payload_bytes": model_bytes,
            "total_nodes": sum(p.engine.metrics()["nodes"] for p in runtime.participants.values()),
            "total_edges": sum(p.engine.metrics()["edges"] for p in runtime.participants.values()),
            "checkpoint_hash": metadata["checkpoint_hash"],
            "brain_hashes": {key: image.digest for key, image in images.items()},
        }
    return result, settings.model_dump(mode="json"), options.model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=int, nargs="+", default=[8, 32, 128, 256])
    parser.add_argument("--duration-us", type=int, default=100000)
    parser.add_argument("--habitat", choices=("shared", "independent"), default="shared")
    parser.add_argument("--background-load", default="not recorded")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not 1 <= count <= 256 for count in args.counts) or not 1 <= args.duration_us <= 1000000:
        parser.error("counts must be 1..256; this short capacity probe supports at most 1000000 us")
    if args.output.exists():
        parser.error("output already exists; choose a new probe result path")
    source = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    rows = []
    for count in args.counts:
        row, settings, options = measure(count, args.duration_us, args.habitat)
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ("brain_hashes", "sampled_rss_bytes")}), flush=True)
    result = {
        "schema": "threemind.performance-probe/1",
        "source_commit": source,
        "backend": "native",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "mujoco": version("mujoco"),
        "numpy": version("numpy"),
        "logical_cpus": psutil.cpu_count(),
        "installed_memory_bytes": psutil.virtual_memory().total,
        "background_load": args.background_load,
        "habitat": args.habitat,
        "last_ecology_settings": settings,
        "participant_options": options,
        "world": default_world().model_dump(mode="json"),
        "evidence_subscriber": "none; readout calculations and clocks still execute according to participant options",
        "rows": rows,
        "limits": [
            "Small newly stimulated brains, one trial per size, not mature networks or a throughput guarantee",
            "RSS is sampled at named boundaries, not continuous peak tracking; allocator and caches persist between sizes",
            "No database, full evidence consumer, display, RGB, population turnover or distributed simulation",
            "No hardware sizing recommendation or consciousness claim follows from these measurements alone",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
