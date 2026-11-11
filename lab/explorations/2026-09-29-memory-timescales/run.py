"""Bounded D/F/L study through public Kernel, Runtime and Lab services."""

import argparse
import bisect
import gzip
import hashlib
import itertools
import json
import random
from dataclasses import replace
from uuid import UUID, uuid5

from common import ROOT, WORK, Case, Study, encoded, load_case, new_json, prepare

from threemind_core import StateImage, Stimulus
from threemind_kernels.mechanisms import FastTrace, ShortTermState
from threemind_lab.inputs import envelope_record
from threemind_runtime.telemetry import HostTelemetryConfig, TelemetryEncoder

KERNEL = "threemind.continuous-memory/1"
SEED = 9291000
TOKENS = dict(zip("ABCDE", random.Random(SEED).sample(range(1000, 9000), 16)[8:13]))
BITS = ["".join(map(str, b)) for b in itertools.product((0, 1), repeat=3)]
GAPS = (0.1, 1, 3)
DELAYS = (1, 30, 300)
BACKGROUND = None


def flags(bits):
    return {
        "depletion_enabled": bits[0] == "1",
        "stp_facilitation_tau_s": float(bits[1]),
        "edge_consolidation_enabled": bits[2] == "1",
    }


def done(study, key):
    value = load_case(study, key) if (WORK / "cases" / key / "result.json").exists() else None
    if value and value["extra"].get("budget_stop"):
        raise RuntimeError(f"{key} was interrupted; register a separate retry, never overwrite it")
    return value


def background():
    global BACKGROUND
    if BACKGROUND is not None:
        return BACKGROUND
    path = ROOT / ".work/candidates-20260929/host-0.jsonl"
    assert path.with_suffix(".complete.json").exists()
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    encoder = TelemetryEncoder(SEED, HostTelemetryConfig(enabled=True))
    frames = []
    for line in raw.splitlines():
        row = json.loads(line)
        stim, _audit = encoder.encode(
            row["measurements"], monotonic_s=row["monotonic_s"], delivery_us=row["elapsed_us"] + 1_000_000
        )
        if stim:
            frames.append((replace(stim, intensity=0.2), row["index"]))
    metadata = json.loads(path.with_suffix(".complete.json").read_bytes())
    period_us = round(metadata["duration_s"] * 1e6)
    assert frames and frames[-1][0].time_us - 1_000_000 <= period_us
    # Repeat the actual clip using its recorded duration, retaining sampling jitter.
    repeated = [
        (replace(s, time_us=s.time_us + cycle * period_us), index, cycle) for cycle in range(3) for s, index in frames
    ]
    assert all(a[0].time_us < b[0].time_us for a, b in itertools.pairwise(repeated))
    BACKGROUND = (repeated, [s.time_us for s, _, _ in repeated], sha)
    return BACKGROUND


class Trial(Case):
    def __init__(self, study, key, *, config=None, parent=None, bg=True, kernel=KERNEL):
        super().__init__(study, key, kernel, SEED, config=config, parent=parent)
        self.bg = bg
        self.bg_cursor = bisect.bisect_right(background()[1], self.engine.time_us) if bg else 0

    def step(self, target):
        if self.bg:
            frames, times, sha = background()
            stop = bisect.bisect_right(times, target)
            for stim, index, cycle in frames[self.bg_cursor : stop]:
                self.send_stimulus(
                    stim,
                    source="host-telemetry",
                    adapter="host-telemetry",
                    payload={"recording_sha256": sha, "sample": index, "cycle": cycle, "frames": [stim.to_dict()]},
                )
            self.bg_cursor = stop
        self.session.advance_to(target, guard=self.guard)

    def advance(self, target, *, fast_sample=False):
        quantum = 10_000 if fast_sample else 1_000_000
        while self.engine.time_us < target and self.engine.life != "dead":
            self.guard()
            self.step(min(target, self.engine.time_us + quantum))
            self.sample()
        return self.engine.life != "dead"


def sequence_train(study, key, *, swap=False, bg=True, kernel=KERNEL, reverse=False):
    if saved := done(study, key):
        return saved
    c = Trial(study, key, bg=bg, kernel=kernel)
    c.advance(2_200_000)
    seqs = [("A", "B", "E" if swap else "C"), ("D", "B", "C" if swap else "E")]
    if reverse:
        seqs.reverse()
    for count in (20, 10, 5):
        for seq in seqs:
            for _ in range(count):
                for i, symbol in enumerate(seq):
                    frame = [symbol] if i == 0 else [seq[i - 1], symbol]
                    assert c.pulse([TOKENS[x] for x in frame], 1.0, 1_000_000)
    return c.finish(
        {
            "kind": "sequence_training",
            "swap": swap,
            "reverse": reverse,
            "background": bg,
            "frames": 210,
            "tokens": TOKENS,
        }
    )


def pair_train(study, key, bits, swap, balanced):
    if saved := done(study, key):
        return saved
    c = Trial(study, key, config=flags(bits))
    c.advance(2_200_000)
    sequences = [("A", "C"), ("D", "E")] if not balanced else [("A", "C"), ("A", "E"), ("D", "C"), ("D", "E")]
    frames = [
        pair for count in ((20, 10, 10) if not balanced else (10, 5, 5)) for pair in sequences for _ in range(count)
    ]
    for i, pair in enumerate(frames):
        symbols = [({"C": "E", "E": "C"}.get(s, s) if swap else s) for s in pair]
        assert c.pulse([TOKENS[s] for s in symbols], 1.0, 0 if i == len(frames) - 1 else 1_000_000)
    return c.finish(
        {
            "kind": "pair_training",
            "bits": bits,
            "swap": swap,
            "balanced": balanced,
            "frames": len(frames),
            "tokens": TOKENS,
            "last_training_frame_us": str(c.engine.time_us),
        }
    )


def settled(c):
    value = c.engine.capture_state().to_dict()
    ids = {n["id"] for n in value["nodes"] if n["channel"] in TOKENS.values()}
    expected_u = 0 if c.engine.config.stp_facilitation_tau_s else c.engine.config.stp_utilization
    states = []
    for row in value["operator_state"]["short_term"]:
        if row["source"] in ids and row["target"] in ids:
            s = ShortTermState(**(row["state"] | {"time_us": int(row["state"]["time_us"])}))
            now = s.recovered(c.engine.time_us, c.engine.config.short_term())
            states.append(max(abs(1 - now.available), now.active, abs(now.utilization - expected_u)))
    fast = [
        FastTrace(**(r["state"] | {"time_us": int(r["state"]["time_us"])})).projected(
            c.engine.time_us, c.engine.config.fast_trace()
        )
        for r in value["operator_state"]["fast"]
        if r["source"] in ids and r["target"] in ids
    ]
    return {
        "short_max_residual": max(states, default=0),
        "fast_max_residual": max(fast, default=0),
        "within_tolerance": max(states + fast, default=0) <= 1e-6,
    }


def warm(study, parent, key, bits):
    if saved := done(study, key):
        return saved
    c = Trial(study, key, parent=parent, config=flags(bits))
    assert c.advance(c.engine.time_us + 20_000_000)
    return c.finish({"kind": "warm", "bits": bits, "swap": parent["extra"]["swap"], "settled": settled(c)})


def sample(c, start, scope="all"):
    return {
        "relative_us": c.engine.time_us - start,
        "life": c.engine.life,
        "nodes": [n for n in c.engine.observation_nodes() if scope == "all" or n["channel"] in TOKENS.values()],
        "transport": c.engine.metrics()["transport"],
    }


def phase(trace, begin):
    rows = [r for r in trace if r["relative_us"] >= begin]
    out = {}
    for symbol in "CE":
        pairs = [
            (r["relative_us"], next((n["activation"] for n in r["nodes"] if n["channel"] == TOKENS[symbol]), 0))
            for r in rows
        ]
        t, peak = max(pairs, key=lambda x: x[1], default=(None, 0))
        area = sum((b[0] - a[0]) / 1e6 * (a[1] + b[1]) / 2 for a, b in itertools.pairwise(pairs))
        out[symbol] = {
            "peak": peak,
            "peak_us": t,
            "area": area,
            "last_positive_us": max((t for t, a in pairs if a > 0), default=None),
        }
    return out


def probe(
    study,
    parent,
    key,
    name,
    *,
    gap=1.0,
    delay=0.0,
    bg=True,
    seconds=15,
    detailed=False,
    config=None,
    scope="all",
    transmission_log=False,
):
    if saved := done(study, key):
        return saved
    c = Trial(study, key, parent=parent, bg=bg, kernel=parent["kernel"], config=config)
    observer_events = []
    if transmission_log:
        delegate = c.engine

        class Observer:
            def __getattr__(self, name):
                return getattr(delegate, name)

            def advance_to(self, target, observer=None, *, inputs_only=False):
                def observed(event):
                    observer_events.append(event)
                    if len(observer_events) > 100_000:
                        raise RuntimeError("diagnostic observer event budget")
                    if observer:
                        observer(event)

                return delegate.advance_to(target, observed, inputs_only=inputs_only)

        c.session.engine = Observer()
    before_wait = c.engine.capture_state().digest
    c.advance(c.engine.time_us + round(delay * 1e6))
    start = c.engine.time_us
    schedule = {
        "AB": [(0, "A"), (gap, "B")],
        "DB": [(0, "D"), (gap, "B")],
        "B": [(gap, "B")],
        "A": [(0, "A")],
        "D": [(0, "D")],
        "none": [],
    }[name]
    carrier = None
    if schedule and c.engine.life != "dead":
        frames = [{"stimulus": Stimulus(start + round(t * 1e6), ((TOKENS[s], 1.0),), 0.5)} for t, s in schedule]
        carrier = str(uuid5(UUID(c.id), "probe"))
        item = envelope_record(
            carrier,
            "anonymous-frames",
            "manual-probe",
            {"frames": [f["stimulus"].to_dict() for f in frames]},
            {"dose": 0.5},
            len(frames),
            len(frames),
        )
        c.inputs.changes["envelopes"].append(item)
        c.inputs.schedule(item, frames)
    states = {"before_probe": c.engine.capture_state().to_dict()}
    trace = [sample(c, start, scope)]
    c.step(start)
    trace.append(sample(c, start, scope))
    milestones = {
        100_000,
        500_000,
        round(gap * 1e6),
        round(gap * 1e6) + 100_000,
        round(gap * 1e6) + 300_000,
        round(gap * 1e6) + 1_000_000,
        round(gap * 1e6) + 3_000_000,
    }
    while c.engine.time_us < start + round(seconds * 1e6) and c.engine.life != "dead":
        c.step(min(start + round(seconds * 1e6), c.engine.time_us + 10_000))
        trace.append(sample(c, start, scope))
        if c.engine.time_us % 100_000 == start % 100_000:
            c.sample()
        t = c.engine.time_us - start
        if scope == "all" and (t in milestones or detailed and t % 100_000 == 0):
            states[str(t)] = c.engine.capture_state().to_dict()
    c.session.host.close(c.engine.time_us, "run_ended")
    windows = (
        [e["payload"] for e in c.events if e["kind"] == "temporal_readout" and e["payload"]["envelope_id"] == carrier]
        if carrier
        else []
    )
    window = windows[-1] if windows else None
    ids = {n["id"]: s for n in c.engine.observation_nodes() for s, ch in TOKENS.items() if n["channel"] == ch}
    final = {"C": 0.0, "E": 0.0}
    if window:
        for n in window["nodes"]:
            if ids.get(n["node_id"]) in final:
                final[ids[n["node_id"]]] = n["last_activation"]
    valid = bool(window and window["classification"] == "converged")
    states["end"] = c.engine.capture_state().to_dict()
    with gzip.open(c.folder / "trajectory.jsonl.gz", "xb") as f:
        for row in trace:
            f.write(encoded(row) + b"\n")
    with gzip.open(c.folder / "snapshots.json.gz", "xb") as f:
        f.write(encoded(states))
    if transmission_log:
        with gzip.open(c.folder / "transmissions.jsonl.gz", "xb") as f:
            for row in observer_events:
                f.write(encoded(row) + b"\n")
    extra = {
        "kind": "probe",
        "parent_id": parent["id"],
        "training": parent["extra"],
        "probe": name,
        "gap_s": gap,
        "delay_s": delay,
        "start_us": str(start),
        "before_wait_hash": before_wait,
        "background": bg,
        "cue_scheduled": carrier is not None,
        "cue_delivery": [r for r in c.inputs.changes["delivered"] if r.get("envelope_id") == carrier],
        "classification": window["classification"] if window else "no_window",
        "reason": window["reason"] if window else "no_window",
        "primary_available": valid,
        "primary_end_activation": final if valid else None,
        "raw_end_activation": final,
        "post_cue": phase(trace, round(gap * 1e6) if name in ("AB", "DB", "B") else 0),
        "samples": len(trace),
        "trajectory_scope": scope,
        "transmission_events": len(observer_events),
        "window": window,
        "pre_probe_settled": settled_from_state(states["before_probe"]),
    }
    return c.finish(extra)


def settled_from_state(value):
    # Raw state is retained; no normalization or hidden resetting.
    return {
        "task_activation": {
            s: next((n["activation"] for n in value["nodes"] if n["channel"] == ch), 0) for s, ch in TOKENS.items()
        }
    }


def validation(study):
    from common import TEMPORAL

    TEMPORAL["max_response_us"] = 12_000_000
    old = sequence_train(study, "validation/original", bg=False, kernel="threemind.continuous/1")
    frozen = ROOT / ".work/continuous-mechanisms-20260929/cases/validation/train/parent-state.json.gz"
    with gzip.open(frozen, "rb") as source:
        image = StateImage(source.read())
    assert old["image"].digest == image.digest, "previous training no longer reproduces"
    candidate = sequence_train(study, "validation/candidate", bg=False)
    value = candidate["image"].to_dict()
    for k in ("schema", "dynamics", "definition", "definition_hash"):
        value[k] = image.to_dict()[k]
    value["config"] = image.to_dict()["config"]
    assert value == image.to_dict(), "new identity has unintended baseline behavior"
    comparisons = []
    for name in ("AB", "DB"):
        a = probe(study, old, f"validation/old-{name}", name, bg=False, delay=1, seconds=12)
        b = probe(study, candidate, f"validation/new-{name}", name, bg=False, delay=1, seconds=12)
        assert a["extra"]["post_cue"] == b["extra"]["post_cue"]
        comparisons.append({"name": name, "post_cue": a["extra"]["post_cue"], "equal": True})
    new_json(WORK / "validation.json", comparisons)


def short(study):
    for swap in (False, True):
        parent = sequence_train(study, f"short/train-{int(swap)}", swap=swap)
        bits_order = BITS.copy()
        random.Random(SEED + int(swap)).shuffle(bits_order)
        for bits in bits_order:
            p = warm(study, parent, f"short/s{int(swap)}/{bits}/warm", bits)
            for gap in GAPS:
                for name in ("AB", "DB", "B"):
                    probe(
                        study,
                        p,
                        f"short/s{int(swap)}/{bits}/g{gap}/{name}",
                        name,
                        gap=gap,
                        detailed=not swap and gap == 1 and bits in ("101", "111") and name != "B",
                    )
            for name in ("A", "D", "none"):
                probe(study, p, f"short/s{int(swap)}/{bits}/{name}", name)
            study.guard(force=True)
            print(f"short swap={swap} DFL={bits} complete", flush=True)


def retention(study):
    for swap in (False, True):
        order = BITS.copy()
        random.Random(SEED + 100 + int(swap)).shuffle(order)
        for bits in order:
            for balanced in (False, True):
                root = f"retention/s{int(swap)}/{bits}/{'balanced' if balanced else 'paired'}"
                parent = pair_train(study, root + "/train", bits, swap, balanced)
                for delay in DELAYS:
                    for name in ("A", "D"):
                        probe(study, parent, f"{root}/d{delay}/{name}", name, delay=delay, scope="task")
            study.guard(force=True)
            print(f"retention swap={swap} DFL={bits} complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "validate", "short", "retention"))
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
        from threemind_kernels.memory import MemoryConfig

        frames, _, sha = background()
        new_json(
            WORK / "execution-manifest.json",
            {
                "configs": {b: MemoryConfig(**flags(b)).to_dict() for b in BITS},
                "varied_fields": list(flags("111")),
                "background_sha256": sha,
                "background_period_us": frames[300][0].time_us - frames[0][0].time_us,
                "background_intensity": 0.2,
                "primary": "converged temporal window end activation descending",
                "pair_training_end": "exact time of final training frame; no extra trailing interval",
                "runner_sha256": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (ROOT / "lab/explorations/2026-09-29-memory-timescales").glob("*.py")
                },
            },
        )
    else:
        study = Study()
        try:
            study.guard(force=True)
            {"validate": validation, "short": short, "retention": retention}[args.stage](study)
        except Exception as exc:
            if study.active_case is not None:
                try:
                    study.active_case.finish({"budget_stop": True, "error": str(exc)})
                except Exception as save_error:  # noqa: BLE001 -- preserve original failure as well
                    print(f"Could not save interrupted trial: {save_error}", flush=True)
            raise
        finally:
            study.db.close()
