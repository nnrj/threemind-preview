"""Independent new whole-system sources, paired across the five declared arms."""

from candidate import RULES as CURVES


def cases():
    return [
        dict(origin=o, seed=261111900 + o, curve=c, key=f"o{o}/{c}", identity=f"r48b-o{o}-{c}")
        for o in range(8)
        for c in CURVES
    ]
