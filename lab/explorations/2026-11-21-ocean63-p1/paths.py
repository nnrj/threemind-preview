"""Locations, identities and storage admission for the independent P1 experiment."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / "2026-11-21-ocean63"
sys.path[:0] = [str(OLD), str(ROOT / "src"), str(ROOT)]

from apparatus import GIB, KERNEL as KERNEL, read as read, sha as sha
from registration import (
    NS as NS,
    PROJECT as PROJECT,
    api as api,
    directory as directory,
    exclusive_json as exclusive_json,
    pool,
)

NAME = "ocean63-p1-20261121"
DESTINATION = "portable-i"
EXPECTED = Path("I:/ThreeMindData/experiments") / NAME
CONTROL = ROOT / ".work" / NAME
PARTS = [{"name": "worlds", "bytes": 22 * GIB}]
SEEDS = (471101, 471102)
SUPPLIES = {"reference": 1, "sparse": 8}
HORIZON = 2400
SECOND = 1_000_000


def admit():
    store = pool()
    placed = store.reserve(NAME, PARTS, directory_id=DESTINATION)
    if placed["parts"][0]["directory"] != DESTINATION:
        raise RuntimeError("P1 is restricted to the operator's I drive")
    root = store.guard(NAME, "worlds", check_directory=False)
    if root.resolve() != EXPECTED.resolve():
        raise RuntimeError(f"Unexpected P1 evidence location {root}")
    root.mkdir(parents=True, exist_ok=True)
    return root
