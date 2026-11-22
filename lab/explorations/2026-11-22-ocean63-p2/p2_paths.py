import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1 = HERE.parent / "2026-11-21-ocean63-p1"
sys.path.insert(0, str(P1))

import paths as previous
from paths import GIB, HORIZON, KERNEL, NS, PROJECT, ROOT, SECOND, SEEDS, SUPPLIES, api, exclusive_json, pool, read, sha

__all__ = [
    "CONTROL",
    "EXPECTED",
    "GIB",
    "HERE",
    "HORIZON",
    "KERNEL",
    "NAME",
    "NS",
    "P1",
    "PROJECT",
    "ROOT",
    "RULES",
    "SECOND",
    "SEEDS",
    "SUPPLIES",
    "api",
    "exclusive_json",
    "pool",
    "previous",
    "read",
    "sha",
]

NAME = "ocean63-p2-20261122"
CONTROL = ROOT / ".work" / NAME
EXPECTED = previous.EXPECTED.parent / NAME
RULES = "threemind.ocean-juvenile-kin-care/1"
