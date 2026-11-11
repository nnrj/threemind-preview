"""Bounded representative replay plus read-only segment/checkpoint integrity."""

import hashlib
import json
import time

from cases import segments
from experiment import ROOT, WORK, study

from lab.tools.ocean_cli import load_population, read_json, verify, write_json


def main():
    started = time.monotonic()
    s = study()
    try:
        s.guard(True)
        if s.completed_wall + 900 > s.settings.wall_seconds:
            raise RuntimeError("reserve 900 seconds within the existing budget for replay verification")
        apparatus = read_json(WORK / "apparatus-sources/manifest.json")
        for name, expected in apparatus.items():
            assert hashlib.sha256((ROOT / "lab/tools" / name).read_bytes()).hexdigest() == expected
        worlds = []
        for path in sorted((WORK / "cases").glob("*/result.json")):
            parts = segments(path.parent)
            prior = None
            for part in parts:
                initial = load_population(part / "initial")
                if prior is not None:
                    assert initial.capture() == prior.capture(), "continuation changed a saved world"
                prior = load_population(part / "final")
                result = read_json(part / "result.json")
                assert prior.time_us == result["time_us"]
                assert abs(prior.metrics()["energy_balance_error"]) < 1e-4
            worlds.append({"case": path.parent.name, "segments": len(parts), "restorable": True})
        # A full 900-second replay may consume the remaining simulation budget.
        # Replay the first 120 seconds including actual births, then complete
        # every continuation segment. These are verification, not new samples.
        scopes = [(WORK / "cases/phase1-0-core", 6000)]
        for path in sorted((WORK / "cases").glob("*/result.json")):
            scopes.extend((part, None) for part in segments(path.parent)[1:])
        results = []
        for path, steps in scopes:
            s.guard(True)
            tick = time.monotonic()
            answer = verify(path, steps)
            results.append({"case": str(path.relative_to(WORK)), **answer, "wall_seconds": time.monotonic() - tick})
        write_json(
            WORK / "formal-verification.json",
            {
                "apparatus_unchanged": True,
                "worlds": worlds,
                "replays": results,
                "wall_seconds": time.monotonic() - started,
                "scope": "all initial/final states and continuation boundaries; partial first world and full continuation replays; not every complete formal world",
            },
        )
        print(json.dumps(results, indent=2), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
