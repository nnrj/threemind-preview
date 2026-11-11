"""Compare the frozen pre-2d447e3 emitter with the installed population emitter.

Small paired measurements, including complete-state and observation equality.
This does not measure database persistence, mature brains or GUI performance.
"""

import argparse
import copy
import hashlib
import inspect
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

from threemind_runtime.ecology import EcologyCoordinator, EcologySettings
from threemind_runtime.population_participant import CoreParticipant
from threemind_runtime.world_schema import default_world


def previous(self, event):
    """Exact emitter from commit 62a0b6b, before subscription-aware copying."""
    event = copy.deepcopy(event)
    event.setdefault("key", f"participant:{self.record_sequence}")
    self.record_sequence += 1
    self.output.publish(event, owned=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=32, choices=range(1, 257), metavar="1..256")
    parser.add_argument("--trials", type=int, default=4, choices=range(1, 101), metavar="1..100")
    parser.add_argument("--until-us", type=int, default=100000)
    parser.add_argument("--background-load", default="not reported")
    args = parser.parse_args()
    if args.output.exists() or args.until_us <= 0:
        parser.error("output must not exist and until-us must be positive")
    settings = EcologySettings(founder_count=args.count)
    settings.rules.reproduction.enabled = False
    settings.rules.reproduction.population_limit = args.count
    current = CoreParticipant.emit
    rows = []
    try:
        for subscribed in (False, True):
            for trial in range(args.trials):
                pair = []
                modes = ("before", "after") if trial % 2 == 0 else ("after", "before")
                for mode in modes:
                    CoreParticipant.emit = previous if mode == "before" else current
                    evidence = []
                    subscriber = (
                        (lambda identity, event, target=evidence: target.append((identity, event)))
                        if subscribed
                        else None
                    )
                    with EcologyCoordinator(default_world(), settings, participant_record=subscriber) as population:
                        started = time.perf_counter()
                        population.advance_to(args.until_us)
                        elapsed = time.perf_counter() - started
                        metadata, images = population.checkpoint()
                        pair.append(
                            {
                                "mode": mode,
                                "advance_s": elapsed,
                                "checkpoint_hash": metadata["checkpoint_hash"],
                                "brain_hashes": {key: image.digest for key, image in images.items()},
                                "evidence_rows": len(evidence),
                                "evidence_sha256": hashlib.sha256(
                                    json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
                                ).hexdigest(),
                            }
                        )
                for key in ("checkpoint_hash", "brain_hashes", "evidence_rows", "evidence_sha256"):
                    if pair[0][key] != pair[1][key]:
                        raise RuntimeError(f"paired equivalence failed for {key}; no successful result published")
                rows.append({"subscribed": subscribed, "trial": trial, "pair": pair})
                print(
                    json.dumps(
                        {
                            "subscribed": subscribed,
                            "trial": trial,
                            "timings": {value["mode"]: value["advance_s"] for value in pair},
                        }
                    ),
                    flush=True,
                )
    finally:
        CoreParticipant.emit = current
    summary = []
    for subscribed in (False, True):
        medians = {
            mode: statistics.median(
                value["advance_s"]
                for row in rows
                if row["subscribed"] == subscribed
                for value in row["pair"]
                if value["mode"] == mode
            )
            for mode in ("before", "after")
        }
        summary.append(
            {
                "subscribed": subscribed,
                "medians_s": medians,
                "median_elapsed_reduction": 1 - medians["after"] / medians["before"],
            }
        )
    result = {
        "schema": "threemind.performance-probe/1",
        "comparison_base_commit": "62a0b6b",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "current_emitter_source": inspect.getsource(current),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "count": args.count,
        "duration_us": args.until_us,
        "background_load": args.background_load,
        "settings": settings.model_dump(mode="json"),
        "full_metadata_brain_and_observation_hashes_equal_in_every_pair": True,
        "summary": summary,
        "trials": rows,
        "limits": [
            "Fresh small brains, not mature-model throughput",
            "No Lab, database or GUI",
            "Complete subscriber retains evidence in memory",
            "Local paired observations, not universal speedups",
        ],
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
