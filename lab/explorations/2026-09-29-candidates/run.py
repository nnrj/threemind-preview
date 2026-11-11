"""Bounded candidate study. Run prepare, calibrate, capture, then block 0..5."""

import argparse
import json
import math
import random
import time
from datetime import UTC, datetime

from common import HERE, KERNELS, WORK, Case, Study, encoded, load_case, new_json, prepare, read_json

from threemind_runtime.telemetry_probe import SystemTelemetryProbe


def done(key):
    return (WORK / "cases" / key / "result.json").exists()


def calibration(study):
    rows = []
    for kernel in KERNELS:
        for gap in (10000, 100000, 1000000, 10000000):
            for dose in (0.125, 0.25, 0.5, 1.0, 2.0, 4.0):
                key = f"calibration/{kernel.split('.')[-1].replace('/', '-')}/{gap}-{dose}"
                if done(key):
                    r = read_json(WORK / "cases" / key / "result.json")
                else:
                    c = Case(study, key, kernel, 9290099)
                    for _ in range(5):
                        if not c.pulse([390001, 390002], dose, gap, measure=True):
                            break
                    r = c.finish({"dose": dose, "gap_us": gap})
                pulses = r["pulses"]
                observable = (
                    sum(p["spikes_delta"] for p in pulses) > 0
                    if kernel.endswith("lif/1")
                    else max(p["peak_mean"] for p in pulses) > 0.055
                    and sum(p["saturated_sample_fraction"] for p in pulses) / len(pulses) < 0.2
                )
                rows.append(
                    {
                        "kernel": kernel,
                        "gap_us": gap,
                        "dose": dose,
                        "observable": observable,
                        "alive_after_five": r["life"] != "dead" and len(pulses) == 5,
                        "run_id": r["id"],
                        "peak_mean": max(p["peak_mean"] for p in pulses),
                        "spikes": sum(p["spikes_delta"] for p in pulses),
                    }
                )
                print(f"calibrated {kernel} gap={gap} dose={dose} observable={observable}", flush=True)
    if not (WORK / "calibration.json").exists():
        new_json(WORK / "calibration.json", rows)
    choices = {}
    for gap in (100000, 1000000):
        for dose in (0.125, 0.25, 0.5, 1.0, 2.0, 4.0):
            group = [r for r in rows if r["gap_us"] == gap and r["dose"] == dose]
            if len(group) == 3 and all(r["observable"] and r["alive_after_five"] for r in group):
                choices = {k: {"dose": dose, "gap_us": gap} for k in KERNELS}
                break
        if choices:
            break
    if not choices:
        for kernel in KERNELS:
            candidates = [
                r
                for r in rows
                if r["kernel"] == kernel
                and r["gap_us"] in (100000, 1000000)
                and r["observable"]
                and r["alive_after_five"]
            ]
            if not candidates:
                raise RuntimeError(f"{kernel}: no admissible calibration; stop rather than inventing settings")
            chosen = min(candidates, key=lambda r: (r["gap_us"], r["dose"]))
            choices[kernel] = {"dose": chosen["dose"], "gap_us": chosen["gap_us"]}
    longest = max(v["gap_us"] for v in choices.values())
    # 140 paired inputs, forty remapping inputs, retention 100 s, readout 12 s.
    capture_seconds = math.ceil(180 * longest / 1e6 + 120)
    new_json(
        WORK / "frozen.json",
        {
            "choices": choices,
            "capture_seconds": capture_seconds,
            "blocks": 6,
            "selection_rule": "design.md; lowest common admissible dose at 0.1 s then 1 s",
            "runner_sha256": __import__("hashlib").sha256((HERE / "run.py").read_bytes()).hexdigest(),
        },
    )
    print("FROZEN " + json.dumps(choices), flush=True)


def capture(study):
    duration = read_json(WORK / "frozen.json")["capture_seconds"]
    probe = SystemTelemetryProbe()
    for block in range(6):
        path = WORK / f"host-{block}.jsonl"
        if path.with_suffix(".complete.json").exists():
            continue
        if path.exists():
            raise RuntimeError("partial recording exists; preserve it and explicitly choose a fresh segment")
        probe.reset_rate_baselines({"host"})
        start = time.monotonic()
        with path.open("xb") as f:
            for index in range(1, duration + 1):
                while time.monotonic() < start + index:
                    time.sleep(min(0.2, start + index - time.monotonic()))
                study.guard()
                now = time.monotonic()
                if now - start > duration + 30:
                    raise RuntimeError("capture delayed beyond its time budget")
                host, _ = probe.collect(now, {"host"})
                f.write(
                    encoded(
                        {
                            "index": index,
                            "captured_at": datetime.now(UTC).isoformat(),
                            "elapsed_us": round((now - start) * 1e6),
                            "monotonic_s": now,
                            "backend": probe.backend,
                            "measurements": {k: v.to_dict() for k, v in host.items()},
                        }
                    )
                    + b"\n"
                )
                f.flush()
                if index % 30 == 0:
                    print(f"real host block {block}: {index}/{duration}s", flush=True)
        new_json(
            path.with_suffix(".complete.json"),
            {"samples": duration, "duration_s": time.monotonic() - start, "repeated_or_interpolated": False},
        )
        print(f"host block {block} complete", flush=True)


def tokens(block):
    values = random.Random(9291000 + block).sample(range(1000 + block * 10000, 9000 + block * 10000), 16)
    return values


def train_case(study, key, kernel, block, background, fn, config=None):
    if done(key):
        return load_case(study, key)
    c = Case(study, key, kernel, 9291000 + block, config=config)
    if background:
        c.add_background(block)
    c.advance(2_200_000)
    fn(c)
    return c.finish({"background": background, "block": block})


def probe(study, parent, key, kernel, block, channels, targets, dose, hold, *, sequence_gap=None):
    if done(key):
        return read_json(WORK / "cases" / key / "result.json")["extra"]
    c = Case(study, key, kernel, 9291000 + block, parent=parent, observe=True)
    mapping = {n["id"]: n["channel"] for n in c.engine.observation_nodes()}
    c.advance(c.engine.time_us + hold)
    baseline_life = c.engine.life
    spikes_before = c.engine.metrics().get("spikes", 0)
    envelope = None
    if c.engine.life != "dead":
        # One-frame carrier for pairs; one multi-frame carrier for A->B probes.
        if sequence_gap is None:
            envelope = c.send(channels, dose, source="manual-probe")
        else:
            from uuid import UUID, uuid5

            from threemind_core import Stimulus
            from threemind_lab.inputs import envelope_record

            frames = [
                {"stimulus": Stimulus(c.engine.time_us + i * sequence_gap, ((ch, 1.0),), dose)}
                for i, ch in enumerate(channels)
            ]
            item = envelope_record(
                uuid5(UUID(c.id), "sequence-probe"),
                "anonymous-frames",
                "manual-probe",
                {"frames": [f["stimulus"].to_dict() for f in frames]},
                {"dose": dose},
                len(frames),
                len(frames),
            )
            c.inputs.changes["envelopes"].append(item)
            c.inputs.schedule(item, frames)
            envelope = item["id"]
        c.advance(c.engine.time_us + 12_000_000)
    # Close outstanding windows with explicit censoring, retaining all nodes.
    c.session.host.close(c.engine.time_us, "run_ended")
    windows = [
        e["payload"] for e in c.events if e["kind"] == "temporal_readout" and e["payload"]["envelope_id"] == envelope
    ]
    window = windows[-1] if windows else None
    mapping.update({n["id"]: n["channel"] for n in c.engine.observation_nodes()})
    values = {str(ch): 0.0 for ch in targets}
    peaks = dict(values)
    if window:
        for row in window["nodes"]:
            channel = mapping.get(row["node_id"])
            if str(channel) in values:
                values[str(channel)] = row["last_activation"]
                peaks[str(channel)] = row["peak_activation"]
    result = {
        "targets": targets,
        "channels": channels,
        "hold_us": hold,
        "dose": dose,
        "run_id": c.id,
        "classification": window["classification"] if window else "not_observed",
        "reason": window["reason"] if window else ("death_before_probe" if baseline_life == "dead" else "no_window"),
        "final_activation": values,
        "peak_activation": peaks,
        "primary_available": bool(window and window["classification"] == "converged"),
        "primary": values if window and window["classification"] == "converged" else None,
        "life_at_probe": baseline_life,
        "final_life": c.engine.life,
        "spikes": c.engine.metrics().get("spikes"),
        "probe_spikes_delta": c.engine.metrics().get("spikes", 0) - spikes_before,
        "coverage": window["coverage"] if window else None,
    }
    c.finish(result)
    return result


def block_run(study, block):
    frozen = read_json(WORK / "frozen.json")
    rows = []
    tok = tokens(block)
    pairs = list(zip(tok[:4], tok[4:8]))
    for kernel in KERNELS:
        cfg = frozen["choices"][kernel]
        dose, gap = cfg["dose"], cfg["gap_us"]
        root = f"block-{block}/{kernel.split('.')[-1].replace('/', '-')}"
        variants = {"default": {}}
        if kernel.endswith("continuous/1"):
            variants |= {
                "no-stp": {"stp_enabled": False},
                "no-fast": {"fast_enabled": False},
                "no-context": {"context_enabled": False},
            }
        if kernel.endswith("lif/1"):
            variants |= {"no-stp": {"stp_enabled": False}, "no-adaptation": {"adaptation_jump_na": 0.0}}
        for bg in (False, True):
            for name, config in variants.items():
                key = f"{root}/adapt-bg{int(bg)}-{name}"

                def repeated(c, dose=dose, gap=gap):
                    for _ in range(20):
                        if not c.pulse(list(pairs[0]), dose, gap, measure=True):
                            break

                parent = train_case(study, key, kernel, block, bg, repeated, config)
                rows.append(
                    {
                        "kind": "adaptation",
                        "kernel": kernel,
                        "background": bg,
                        "variant": name,
                        "run_id": parent["id"],
                        "pulses": parent["pulses"],
                        "block": block,
                    }
                )
                for hold in (100000, 1000000, 10000000):
                    recovery = key + f"/rest-{hold}"
                    if done(recovery):
                        r = read_json(WORK / "cases" / recovery / "result.json")
                    else:
                        c = Case(study, recovery, kernel, 9291000 + block, parent=parent)
                        c.advance(c.engine.time_us + hold)
                        c.pulse(list(pairs[0]), dose, gap, measure=True)
                        r = c.finish({"hold_us": hold})
                    rows.append(
                        {
                            "kind": "recovery",
                            "kernel": kernel,
                            "background": bg,
                            "variant": name,
                            "hold_us": hold,
                            "pulses": r["pulses"],
                            "life": r["life"],
                            "run_id": r["id"],
                            "block": block,
                        }
                    )
            for condition in ("trained", "untrained", "no-plasticity", "remapped", "trained-aged"):
                key = f"{root}/pair-bg{int(bg)}-{condition}"

                def pairing(c, condition=condition, dose=dose, gap=gap):
                    if condition == "untrained":
                        c.advance(c.engine.time_us + 140 * gap)
                        return
                    for count in (20, 10, 5):
                        for a, b in pairs:
                            for _ in range(count):
                                if not c.pulse([a, b], dose, gap):
                                    return
                    if condition == "remapped":
                        for i, (a, _) in enumerate(pairs):
                            for _ in range(10):
                                if not c.pulse([a, pairs[(i + 1) % 4][1]], dose, gap):
                                    return
                    elif condition == "trained-aged":
                        c.advance(c.engine.time_us + 40 * gap)

                parent = train_case(
                    study,
                    key,
                    kernel,
                    block,
                    bg,
                    pairing,
                    {"plasticity": False} if condition == "no-plasticity" else {},
                )
                for hold in (1000000, 10000000, 100000000):
                    for i, (a, b) in enumerate(pairs):
                        item = probe(
                            study, parent, key + f"/hold-{hold}-cue{i}", kernel, block, [a], tok[4:8], dose / 2, hold
                        )
                        rows.append(
                            item
                            | {
                                "kind": "pair",
                                "kernel": kernel,
                                "background": bg,
                                "condition": condition,
                                "expected": b,
                                "new_expected": pairs[(i + 1) % 4][1],
                                "block": block,
                            }
                        )
            for overlap in (False, True):
                for swap in (False, True):
                    a, b, c, d, e = tok[8:13]
                    seqs = [[a, b, e if swap else c], [d, b, c if swap else e]]
                    key = f"{root}/sequence-bg{int(bg)}-overlap{int(overlap)}-swap{int(swap)}"

                    def sequence(ca, seqs=seqs, overlap=overlap, dose=dose, gap=gap):
                        for count in (20, 10, 5):
                            for seq in seqs:
                                for _ in range(count):
                                    for i, ch in enumerate(seq):
                                        channels = seq[i - 1 : i + 1] if overlap and i else [ch]
                                        if not ca.pulse(channels, dose, gap):
                                            return

                    parent = train_case(study, key, kernel, block, bg, sequence)
                    for index, seq in enumerate(seqs):
                        item = probe(
                            study,
                            parent,
                            key + f"/cue-{index}",
                            kernel,
                            block,
                            seq[:2],
                            [c, e],
                            dose / 2,
                            1000000,
                            sequence_gap=gap,
                        )
                        rows.append(
                            item
                            | {
                                "kind": "sequence",
                                "kernel": kernel,
                                "background": bg,
                                "overlap": overlap,
                                "swap": swap,
                                "expected": seq[2],
                                "block": block,
                            }
                        )
        print(f"block {block}: {kernel} complete, {len(rows)} result rows", flush=True)
    new_json(WORK / f"block-{block}.json", rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=("prepare", "calibrate", "capture", "block"))
    p.add_argument("--block", type=int, choices=range(6))
    args = p.parse_args()
    if args.phase == "prepare":
        prepare()
        return
    study = Study()
    try:
        if args.phase == "calibrate":
            calibration(study)
        elif args.phase == "capture":
            capture(study)
        elif args.phase == "block":
            if args.block is None:
                p.error("--block is required")
            block_run(study, args.block)
    except RuntimeError as error:
        if any(word in str(error) for word in ("budget", "reserve", "hard limit")):
            (WORK / "STOP").write_text(str(error), encoding="utf-8")
            if study.active_case:
                study.active_case.finish({"budget_stop": str(error)})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
