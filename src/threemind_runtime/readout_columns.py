"""Transient column storage for the passive temporal observer.

The public recovery/record schema remains readout/1. No object in this module
belongs to Core. Elementwise arithmetic preserves the scalar operation order;
aggregate sums and tie-breaking remain in the reader's numeric node-id order.
"""

import numpy as np

FLOATS = (
    "baseline_mean",
    "baseline_noise",
    "activation_integral",
    "excess_integral",
    "inhibition_integral",
    "direct_trace_integral",
    "associative_trace_integral",
    "peak_activation",
    "peak_inhibition",
    "last_activation",
    "last_excess",
    "last_inhibition",
    "last_direct",
    "last_associative",
    "stability",
)
INTS = ("active_us", "tail_active_us", "longest_run_us", "current_run_us", "entries")
BOOLS = ("has_direct_trace", "has_associative_trace", "last_active")
TIMES = ("first_active_us", "last_active_us")
CURRENT = ("activation", "inhibition", "direct", "associative", "stability")
INTEGRALS = (
    ("activation_integral", "last_activation"),
    ("excess_integral", "last_excess"),
    ("inhibition_integral", "last_inhibition"),
    ("direct_trace_integral", "last_direct"),
    ("associative_trace_integral", "last_associative"),
)


class WindowColumns:
    def __init__(self, rows):
        # A reference window can predate f64 observations (e.g. an embedding
        # passed integer scalars). Do not silently change its recovery types.
        for row in rows.values():
            if any(
                type(row[field]) is not float
                and not (field == "last_excess" and type(row[field]) is int and row[field] == 0)
                for field in FLOATS
            ):
                raise TypeError("window contains non-f64 observer values")
        self.keys = sorted(rows, key=int)
        self.index = {key: i for i, key in enumerate(self.keys)}
        self.excess_integer = np.fromiter((type(rows[key]["last_excess"]) is int for key in self.keys), dtype=np.bool_)
        self.values = {}
        for fields, dtype in ((FLOATS, np.float64), (INTS, np.int64), (BOOLS, np.bool_), (TIMES, object)):
            for field in fields:
                self.values[field] = np.array([rows[key][field] for key in self.keys], dtype=dtype)

    def rows(self):
        columns = {name: value.tolist() for name, value in self.values.items()}
        result = {}
        for i, key in enumerate(self.keys):
            row = {"node_id": int(key), **{field: values[i] for field, values in columns.items()}}
            # Scalar max(0, x) returns the integer 0 when x <= 0; retain that
            # distinction in serialized recovery state, including cold rows.
            if self.excess_integer[i]:
                row["last_excess"] = 0
            result[key] = row
        return result

    def integrate(self, dt_us, tail_us):
        values, dt = self.values, dt_us / 1e6
        for field, previous in INTEGRALS:
            values[field] += values[previous] * dt
        active = values["last_active"]
        for field, duration in (("active_us", dt_us), ("tail_active_us", tail_us), ("current_run_us", dt_us)):
            values[field][active] += duration
        np.maximum(values["longest_run_us"], values["current_run_us"], out=values["longest_run_us"])

    def observe(self, nodes, baseline, cfg, time_us):
        incoming = {str(n["id"]): n for n in nodes}
        added = sorted(incoming.keys() - self.index.keys(), key=int)
        if len(self.keys) + len(added) > cfg.max_node_entries:
            return None
        if added:
            keys = sorted(self.keys + added, key=int)
            index = {key: i for i, key in enumerate(keys)}
            old = np.fromiter((index[key] for key in self.keys), dtype=np.intp)
            integers = np.zeros(len(keys), dtype=np.bool_)
            integers[old] = self.excess_integer
            self.excess_integer = integers
            for field, values in self.values.items():
                expanded = (
                    np.full(len(keys), None, dtype=object)
                    if field in TIMES
                    else np.zeros(len(keys), dtype=values.dtype)
                )
                expanded[old] = values
                self.values[field] = expanded
            for key in added:
                mean, noise = baseline.get(key, (0.0, 0.0))
                self.values["baseline_mean"][index[key]] = mean
                self.values["baseline_noise"][index[key]] = noise
            self.keys, self.index = keys, index
        v = self.values
        indices = np.fromiter((self.index[key] for key in incoming), dtype=np.intp)
        current = np.zeros((len(self.keys), len(CURRENT)), dtype=np.float64)
        if incoming:
            current[indices] = np.array([[n[field] for field in CURRENT] for n in incoming.values()], dtype=np.float64)
        activation, inhibition, direct, associative, stability = current.T
        present = np.zeros(len(self.keys), dtype=np.bool_)
        present[indices] = True
        excess = activation - v["baseline_mean"] - cfg.baseline_noise_gain * v["baseline_noise"]
        excess = np.where(present & (excess > 0), excess, 0.0)
        self.excess_integer = present & (excess == 0)
        active = (
            (activation > 0)
            & (excess > 0)
            & (activation >= cfg.activation_threshold)
            & (excess >= cfg.excess_activation_min)
        )
        entered = active & ~v["last_active"]
        v["entries"][entered] += 1
        v["current_run_us"][~active | entered] = 0
        first = np.fromiter((value is None for value in v["first_active_us"]), dtype=np.bool_)
        v["first_active_us"][active & first] = time_us
        v["last_active_us"][active] = time_us
        v["last_active"] = active
        for field, values in (
            ("last_activation", activation),
            ("last_excess", excess),
            ("last_inhibition", inhibition),
            ("last_direct", direct),
            ("last_associative", associative),
            ("stability", stability),
        ):
            v[field] = values.copy()
        # Python max keeps the old value on ties, including signed zero.
        v["peak_activation"] = np.where(activation > v["peak_activation"], activation, v["peak_activation"])
        v["peak_inhibition"] = np.where(inhibition > v["peak_inhibition"], inhibition, v["peak_inhibition"])
        v["has_direct_trace"] |= (direct >= cfg.excess_activation_min) & (direct > 0)
        v["has_associative_trace"] |= (associative >= cfg.excess_activation_min) & (associative > 0)
        candidates = active.copy()
        if cfg.candidate_scope != "all-active":
            candidates &= v["has_associative_trace"] | (
                (v["tail_active_us"] > 0) if cfg.candidate_scope == "associative-or-persistent" else False
            )
        # Conversion only for ordered aggregate inputs, not every state field.
        active_excess = {self.keys[i]: float(excess[i]) for i in np.flatnonzero(active)}
        comparison = {key: value for key, value in active_excess.items() if candidates[self.index[key]]}
        return active_excess, comparison


def can_batch(window, time_us, nodes):
    # Core observations use f64 values. Preserve unusual caller-supplied scalar
    # types through the reference path, and never narrow an unbounded duration.
    span = time_us - window["start_us"]
    return 0 <= span < 2**62 and all(type(n[k]) is float for n in nodes for k in CURRENT)
