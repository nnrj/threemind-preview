"""New whole-system origins, disjoint from R47a/R47b and apparatus checks."""

CURVES = ("exponential", "power-law", "inverse-logarithmic", "power-exponential")


def cases():
    return [
        dict(origin=o, seed=261111700 + o, curve=c, key=f"o{o}/{c}", identity=f"r47c-o{o}-{c}")
        for o in range(8)
        for c in CURVES
    ]
