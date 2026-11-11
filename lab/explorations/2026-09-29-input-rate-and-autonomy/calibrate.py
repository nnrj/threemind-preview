"""Public-API stimulus timing experiments; no kernel equations are modified."""

import argparse
import bisect
import gzip
import hashlib
import json
import random
from dataclasses import replace
from uuid import UUID, uuid5

from common import HERE, ROOT, WORK, Case, Study, encoded, load_case, new_json, prepare

from threemind_core import Stimulus
from threemind_lab.inputs import envelope_record
from threemind_runtime import birth, create_engine
from threemind_runtime.telemetry import HostTelemetryConfig, TelemetryEncoder

KERNELS = {"continuous": "threemind.continuous-memory/1", "lif": "threemind.lif/1"}
INTERVALS = (1000000, 100000, 20000, 5000, 1000)
SEEDS = (9293001, 9293002)
HOLDOUT = 9293003
BACKGROUND = {}


def configuration(kernel):
    return (
        {"depletion_enabled": True, "stp_facilitation_tau_s": 1.0, "edge_consolidation_enabled": True}
        if kernel == KERNELS["continuous"]
        else {}
    )


def tokens(seed):
    return dict(zip("ACDEN", random.Random(seed).sample(range(1000, 9000), 5)))


def background(seed):
    if seed not in BACKGROUND:
        path = ROOT / ".work/candidates-20260929/host-0.jsonl"
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        period = round(json.loads(path.with_suffix(".complete.json").read_bytes())["duration_s"] * 1e6)
        encoder = TelemetryEncoder(seed, HostTelemetryConfig(enabled=True))
        frames = []
        for line in raw.splitlines():
            row = json.loads(line)
            stim, _ = encoder.encode(
                row["measurements"], monotonic_s=row["monotonic_s"], delivery_us=row["elapsed_us"] + 1_000_000
            )
            if stim:
                assert not {ch for ch, _ in stim.channels} & set(tokens(seed).values())
                frames.append((replace(stim, intensity=0.2), row["index"]))
        repeated = [
            (replace(s, time_us=s.time_us + cycle * period), index, cycle) for cycle in range(6) for s, index in frames
        ]
        BACKGROUND[seed] = repeated, [s.time_us for s, _, _ in repeated], sha
    return BACKGROUND[seed]


def done(study, key):
    if not (WORK / "cases" / key / "result.json").exists():
        return None
    saved = load_case(study, key)
    if saved["extra"].get("budget_stop"):
        raise RuntimeError("interrupted instance requires registered retry, not overwrite")
    return saved


class Trial(Case):
    def __init__(self, study, key, kernel, seed, *, parent=None, config=None, bg=True, inherited=False):
        self.bg = bg
        super().__init__(
            study,
            key,
            kernel,
            seed,
            parent=parent,
            config=config if config is not None else configuration(kernel) if not parent else None,
            inherited=inherited,
        )
        self.bg_cursor = bisect.bisect_right(background(seed)[1], self.engine.time_us)

    def step(self, target):
        self.guard()
        if self.bg:
            frames, times, sha = background(self.seed)
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
        quantum = 1000 if fast_sample else 100000
        while self.engine.time_us < target and self.engine.life != "dead":
            self.step(min(target, self.engine.time_us + quantum))
            self.sample()
        return self.engine.life != "dead"

    def pulse(self, channels, dose, gap, **kwargs):
        if self.engine.life == "dead":
            return False
        at = self.engine.time_us
        envelope = self.send(channels, dose, source=kwargs.get("source", "training"))
        self.step(at)
        self.sample()
        self.advance(at + gap)
        self.pulses.append(
            {
                "envelope": envelope,
                "start_us": str(at),
                "end_us": str(self.engine.time_us),
                "channels": channels,
                "dose": dose,
            }
        )
        return self.engine.life != "dead"


def train(study, kernel_name, seed, interval, *, prefix="rate", balanced=False):
    key = f"{prefix}/{kernel_name}/s{seed}/i{interval}/train"
    if saved := done(study, key):
        return saved
    c = Trial(study, key, KERNELS[kernel_name], seed)
    c.advance(2_200_000)
    pairs = ("AC", "DE") if not balanced else ("AC", "AE", "DC", "DE")
    frames = [pair for n in ((20, 10, 10) if not balanced else (10, 5, 5)) for pair in pairs for _ in range(n)]
    last = None
    for i, pair in enumerate(frames):
        last = c.engine.time_us
        if not c.pulse([tokens(seed)[s] for s in pair], 1.0, interval if i + 1 < len(frames) else 0):
            break
    state = c.engine.capture_state().to_dict()
    with gzip.open(c.folder / "training-end.json.gz", "xb") as f:
        f.write(encoded(state))
    c.advance(c.engine.time_us + 1_000_000)
    task_delivered = [r for r in c.inputs.changes["delivered"] if r.get("source") == "training"]
    return c.finish(
        {
            "kind": "rate_training",
            "interval_us": interval,
            "tokens": tokens(seed),
            "balanced": balanced,
            "last_training_us": str(last),
            "requested_frames": len(frames),
            "delivery_rows": len(task_delivered),
            "background_sha256": background(seed)[2],
        }
    )


def sample(c, start):
    value = {
        "relative_us": c.engine.time_us - start,
        "life": c.engine.life,
        "nodes": c.engine.observation_nodes(),
        "transport": c.engine.metrics()["transport"],
    }
    if c.kernel == KERNELS["lif"]:
        value["physical_nodes"] = c.engine.physical_nodes()
    return value


def probe(study, parent, name, *, key=None, wait_us=0, bg=True, duration_us=15_000_000, config=None):
    key = key or parent["key"].rsplit("/", 1)[0] + "/" + name
    if saved := done(study, key):
        return saved
    c = Trial(study, key, parent["kernel"], parent["seed"], parent=parent, bg=bg, config=config)
    c.advance(c.engine.time_us + wait_us)
    start, carrier = c.engine.time_us, None
    before = c.engine.capture_state().to_dict()
    if name != "none" and c.engine.life != "dead":
        symbol = name[-1]
        count = 5 if name.startswith("burst") else 1
        frames = [{"stimulus": Stimulus(start + i * 5000, ((tokens(c.seed)[symbol], 1.0),), 0.5)} for i in range(count)]
        carrier = str(uuid5(UUID(c.id), "probe"))
        item = envelope_record(
            carrier,
            "anonymous-frames",
            "manual-probe",
            {"frames": [f["stimulus"].to_dict() for f in frames]},
            {"dose": 0.5, "frame_count": count},
            count,
            count,
        )
        c.inputs.changes["envelopes"].append(item)
        c.inputs.schedule(item, frames)
    trace = [sample(c, start)]
    c.step(start)
    trace.append(sample(c, start))
    while c.engine.time_us < start + duration_us and c.engine.life != "dead":
        elapsed = c.engine.time_us - start
        quantum = (
            (250 if c.kernel == KERNELS["lif"] else 1000)
            if elapsed < 50000
            else 1000
            if elapsed < 200000
            else 10000
            if elapsed < 2000000
            else 100000
        )
        c.step(min(start + duration_us, c.engine.time_us + quantum))
        trace.append(sample(c, start))
        if c.engine.time_us - start >= (len(c.observations) - 1) * 100000:
            c.sample()
    c.session.host.close(c.engine.time_us, "run_ended")
    windows = (
        [e["payload"] for e in c.events if e["kind"] == "temporal_readout" and e["payload"]["envelope_id"] == carrier]
        if carrier
        else []
    )
    window = windows[-1] if windows else None
    peaks = {
        s: max((next((n["activation"] for n in r["nodes"] if n["channel"] == ch), 0) for r in trace), default=0)
        for s, ch in tokens(c.seed).items()
    }
    with gzip.open(c.folder / "trajectory.jsonl.gz", "xb") as f:
        for row in trace:
            f.write(encoded(row) + b"\n")
    with gzip.open(c.folder / "before-probe.json.gz", "xb") as f:
        f.write(encoded(before))
    deliveries = [r for r in c.inputs.changes["delivered"] if r.get("envelope_id") == carrier]
    return c.finish(
        {
            "kind": "rate_probe",
            "probe": name,
            "parent": parent["id"],
            "interval_us": parent["extra"].get("interval_us"),
            "start_us": str(start),
            "wait_us": wait_us,
            "background": bg,
            "peaks": peaks,
            "samples": len(trace),
            "delivered": deliveries,
            "window": window,
            "classification": window["classification"] if window else "no_window",
            "end_activation_ranking": sorted(
                (window or {}).get("nodes", []), key=lambda n: (-n["last_activation"], n["node_id"])
            ),
        }
    )


def register():
    prepare()
    new_json(
        WORK / "rate-manifest.json",
        {
            "kernels": {k: create_engine(configuration(v), kernel_id=v).config.to_dict() for k, v in KERNELS.items()},
            "intervals_us": INTERVALS,
            "screen_seeds": SEEDS,
            "holdout": HOLDOUT,
            "probe_modes": ["singleA", "singleD", "burstA", "burstD", "none"],
            "background_sha256": background(SEEDS[0])[2],
            "scripts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("*.py")},
        },
    )


def validate(study):
    rows = []
    for name, kernel in KERNELS.items():
        key = f"validation/{name}/delivery"
        c = Trial(study, key, kernel, SEEDS[0], bg=False)
        for at in (1000, 2000, 3000):
            c.send([tokens(c.seed)["A"], tokens(c.seed)["C"]], 1.0, at=at)
        c.advance(10000, fast_sample=True)
        deliveries = c.inputs.changes["delivered"].copy()
        assert len(deliveries) == 3, deliveries
        saved = c.finish({"kind": "delivery_validation", "deliveries": deliveries})
        child = Trial(study, f"validation/{name}/birth", kernel, SEEDS[0], parent=saved, inherited=True, bg=False)
        assert child.engine.time_us == 0 and child.engine.life == "waiting"
        assert all(n["activation"] == 0 for n in child.engine.observation_nodes())
        assert child.engine.capture_state().digest == birth(saved["image"]).digest
        child.finish({"kind": "birth_validation", "source": saved["state_sha256"]})
        rows.append({"kernel": kernel, "deliveries": deliveries, "birth_valid": True})
    new_json(WORK / "validation.json", rows)
    print(json.dumps(rows), flush=True)


def screen(study):
    for kernel in KERNELS:
        for seed in SEEDS:
            for interval in INTERVALS:
                parent = train(study, kernel, seed, interval)
                for name in ("singleA", "singleD", "burstA", "burstD", "none"):
                    probe(study, parent, name)
                study.guard(force=True)
                print(
                    json.dumps({"kernel": kernel, "seed": seed, "interval_us": interval, "complete": True}), flush=True
                )


def analyze():
    result = {"groups": {}, "selected": {}}
    for kernel in KERNELS:
        groups = {}
        for interval in INTERVALS:
            seeds = {}
            for seed in SEEDS:
                base = WORK / "cases" / f"rate/{kernel}/s{seed}/i{interval}"
                if not (base / "none/result.json").exists():
                    continue
                data = {
                    n: json.loads((base / n / "result.json").read_bytes())["extra"]
                    for n in ("singleA", "singleD", "burstA", "burstD", "none")
                }
                modes = {}
                for mode in ("single", "burst"):
                    margins = []
                    for symbol, target, other in (("A", "C", "E"), ("D", "E", "C")):
                        p = data[mode + symbol]["peaks"]
                        q = data["none"]["peaks"]
                        margins.append(p[target] - p[other] - (q[target] - q[other]))
                    modes[mode] = {
                        "margins": margins,
                        "mean": sum(margins) / 2,
                        "classifications": [data[mode + s]["classification"] for s in "AD"],
                    }
                seeds[str(seed)] = modes
            groups[str(interval)] = seeds
        result["groups"][kernel] = groups
        choices = []
        if len(groups["1000000"]) == len(SEEDS):
            for interval in INTERVALS[1:]:
                for mode in ("single", "burst"):
                    gains = []
                    for seed in SEEDS:
                        row = groups[str(interval)].get(str(seed), {}).get(mode)
                        baseline = groups["1000000"][str(seed)][mode]["mean"]
                        gains.append(
                            bool(
                                row
                                and min(row["margins"]) > 0
                                and row["mean"] - baseline > max(0.0001, 0.2 * abs(baseline))
                            )
                        )
                    if all(gains):
                        choices.append({"interval_us": interval, "mode": mode})
        result["selected"][kernel] = choices[0] if choices else {"interval_us": 1000000, "mode": None}
    (WORK / "rate-analysis.json").write_bytes(encoded(result))
    print(json.dumps(result), flush=True)
    return result


def holdout(study):
    selection = analyze()["selected"]
    new_json(WORK / "holdout-registration.json", selection)
    for kernel, row in selection.items():
        if row["mode"] is None:
            continue
        for interval in (1000000, row["interval_us"]):
            parent = train(study, kernel, HOLDOUT, interval, prefix="holdout")
            for name in ("singleA", "singleD", "burstA", "burstD", "none"):
                probe(study, parent, name)
        print(json.dumps({"holdout_complete": kernel}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["register", "validate", "screen", "analyze", "holdout"])
    stage = p.parse_args().stage
    if stage == "register":
        register()
    elif stage == "analyze":
        analyze()
    else:
        study = Study()
        try:
            {"validate": validate, "screen": screen, "holdout": holdout}[stage](study)
        except Exception as error:
            if study.active_case and not (study.active_case.folder / "result.json").exists():
                study.active_case.finish({"budget_stop": True, "error": str(error)})
            raise
        finally:
            study.db.close()
