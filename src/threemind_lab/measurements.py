"""Scientific endpoints derived from recorded Core ledgers, without mutation."""

import math

ENERGY_METRICS = ("energy_reserve", "energy_consumed", "energy_supplied", "energy_unserved")


def energy_endpoints(metric):
    ledger = metric.get("energy")
    empty = dict.fromkeys(ENERGY_METRICS)
    if not ledger or ledger.get("counter_overflowed") or not ledger.get("parameters", {}).get("energy_simulation_enabled"):
        return empty
    try:
        values = (
            ledger["reserve"],
            math.fsum(ledger[f"consumed_{kind}"] for kind in ("direct", "associative", "inhibition", "maintenance")),
            ledger["supplied_total"],
            ledger["unserved_total"],
        )
    except OverflowError:
        return empty
    if not all(math.isfinite(value) for value in values):
        return empty
    return dict(zip(ENERGY_METRICS, values, strict=True))
