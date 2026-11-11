"""Finite peripheral-input study. No Core changes or semantic routing."""

import copy
import gzip
import json
import random
import time
from collections import Counter
from dataclasses import replace

from common import WORK, Case, Study, encoded, load_case, new_json, prepare, read_json

from threemind_core import Stimulus
from threemind_lab.stimulus_diagnostics import diagnose
from threemind_runtime.body import AmbientConfig, AmbientField
from threemind_runtime.random_stimuli import RandomStimuli, RandomStimulusConfig
from threemind_runtime.stimulus_units import unit_frames
from threemind_runtime.telemetry import HostTelemetryConfig, TelemetryEncoder
from threemind_runtime.telemetry_probe import SystemTelemetryProbe
from threemind_runtime.world import PhysicalWorld
from threemind_runtime.world_templates import physical_templates

KERNEL = "threemind.continuous-memory/2"
SEEDS = (93001, 93002)


def saved(study, key):
    return load_case(study, key) if (WORK / "cases" / key / "result.json").exists() else None


def frame(unit):
    return next(iter(unit_frames({"units": [unit]})))["stimulus"]


def record_host():
    path = WORK / "host-recording.json"
    if path.exists():
        return
    probe, rows = SystemTelemetryProbe(), []
    for i in range(48):
        clock = time.perf_counter()
        host, _ = probe.collect(clock, {"host"})
        rows.append({"index": i, "monotonic_s": clock, "measurements": {k: v.to_dict() for k, v in host.items()}})
        time.sleep(0.1)
    new_json(path, rows)


def physical_recording(seed, template):
    path = WORK / f"physical-{template}-{seed}.json"
    if path.exists():
        return read_json(path)
    spec = physical_templates()[template]
    with PhysicalWorld(spec, seed) as world:
        initial, units = world.capture(), []
        for t in range(0, 4000000, 20000):
            stim = world.sample(t)
            units.append(world.stimulus_unit(stim, capture_us=world.elapsed_us))
        value = {"protocol": spec.model_dump(mode="json"), "initial": initial, "final": world.capture(), "units": units}
    new_json(path, value)
    return value


def snapshots(case, target, *, step=100000, trace=False):
    points, spans, alive = [], [], {}
    first = case.engine.time_us
    while True:
        case.guard()
        image = case.engine.capture_state().to_dict()
        keys = {(e["source"], e["target"]) for e in image["edges"]}
        now = case.engine.time_us
        for edge in keys - alive.keys():
            alive[edge] = now
        for edge in alive.keys() - keys:
            spans.append(
                {"edge": list(edge), "start_us": str(alive.pop(edge)), "end_us": str(now), "right_censored": False}
            )
        nodes = case.engine.observation_nodes()
        points.append(
            {
                "time_us": str(now),
                "relative_us": now - first,
                "nodes": nodes if trace else [],
                "metrics": case.engine.metrics(),
            }
        )
        if now >= target or case.engine.life == "dead":
            break
        case.advance(min(target, now + step))
    spans += [
        {"edge": list(edge), "start_us": str(start), "end_us": str(now), "right_censored": True}
        for edge, start in alive.items()
    ]
    return points, spans


def finish(case, meta, points, spans):
    with gzip.open(case.folder / "trajectory.json.gz", "xb") as out:
        out.write(encoded({"points": points, "edge_spans": spans}))
    return case.finish(meta)


def probe(study, key, parent, channels, intensity, duration, **meta):
    # Execution 1 used an ambient-classified label, so it did not open a window.
    # Keep its evidence. Correct only observer registration, from the same parent.
    previous = saved(study, key) if intensity else None
    if intensity:
        key += "/registered"
    if old := saved(study, key):
        return old
    study.guard(force=True)
    c = Case(study, key, KERNEL, parent["seed"], parent=parent, observe=True)
    start = c.engine.time_us
    if intensity:
        c.send_stimulus(Stimulus(start, tuple(channels), intensity), source="manual-registered-probe")
    c.session.advance_to(start, guard=c.guard)
    points, spans = snapshots(c, start + duration, trace=True)
    if previous:
        assert c.engine.capture_state().digest == previous["state_sha256"], "observer registration changed Core"
        meta = meta | {"replaces_observer_registration": previous["id"], "core_hash_reproduced": True}
    if intensity:
        c.session.host.close(c.engine.time_us, "run_ended")
        assert any(e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema") for e in c.events), (
            "probe window missing"
        )
    return finish(
        c,
        {
            **meta,
            "stage": "probe",
            "parent": parent["id"],
            "cue_intensity": intensity,
            "probe_channels": channels,
            "begin_us": str(start),
        },
        points,
        spans,
    )


def backgrounds(study, seed, mode, cfg):
    for condition in ("fresh-single", "fresh-group", "repeated-random", "fixed-amplitude", "synthetic", "telemetry"):
        key = f"background/{seed}/{mode}/{condition}"
        parent = saved(study, key)
        meta = {"family": "background", "condition": condition, "preset": mode}
        if not parent:
            study.guard(force=True)
            c = Case(study, key, KERNEL, seed, config=cfg)
            original = {1001, 1002}
            for i in range(10):
                c.send([1001, 1002], 1, at=i * 100000, source="common-network-history")
            c.advance(1000000)
            random_source = RandomStimuli(
                RandomStimulusConfig(
                    seed=seed,
                    channels=2,
                    mode=condition
                    if condition in ("fresh-single", "fresh-group", "fixed-amplitude")
                    else "fresh-group",
                )
            )
            fixed = [random_source.sample() for _ in range(12)] if condition == "repeated-random" else None
            ambient = AmbientField(AmbientConfig(intensity=0.2), seed)
            encoder = TelemetryEncoder(seed, HostTelemetryConfig(enabled=True, intensity=0.2))
            host = read_json(WORK / "host-recording.json")
            occurrences, dose = Counter(), 0.0
            for i in range(48):
                at = 1000000 + i * 100000
                payload = None
                if condition == "synthetic":
                    frames = [(replace(s, time_us=at), source) for source, s in ambient.sample(i * 100000)]
                elif condition == "telemetry":
                    stim, audit = encoder.encode(
                        host[i]["measurements"], monotonic_s=host[i]["monotonic_s"], delivery_us=at
                    )
                    frames = [(stim, "host-telemetry")] if stim else []
                    payload = {"recording": "host-recording.json", "sample": i, "audit": audit}
                else:
                    unit = copy.deepcopy(fixed[i % 12]) if fixed else random_source.sample()
                    unit["time_us"] = str(at)
                    frames = [(frame(unit), "random-control")]
                    payload = {"units": [unit]}
                for stim, source in frames:
                    assert not original.intersection(ch for ch, _ in stim.channels), "source identity collision"
                    occurrences.update(ch for ch, _ in stim.channels)
                    dose += sum(v for _, v in stim.channels) * stim.intensity
                    c.send_stimulus(
                        stim,
                        source=source,
                        payload=payload,
                        adapter="stimulus-units"
                        if payload and "units" in payload
                        else "host-telemetry"
                        if condition == "telemetry"
                        else "anonymous-frames",
                    )
            points, spans = snapshots(c, 5800000)
            state = c.engine.capture_state().to_dict()
            mapping = {n["id"]: n["channel"] for n in state["nodes"]}
            cross = sum(
                (mapping[e["source"]] in original) != (mapping[e["target"]] in original) for e in state["edges"]
            )
            parent = finish(
                c,
                meta
                | {
                    "stage": "training",
                    "unique_channels": len(occurrences),
                    "reused_channels": sum(v > 1 for v in occurrences.values()),
                    "input_dose": dose,
                    "cross_original_edges": cross,
                },
                points,
                spans,
            )
        for intensity in (0, 0.5):
            probe(study, key + f"/cue{intensity}", parent, [(1001, 1.0)], intensity, 15000000, **meta)


def intensity_cases(study, seed, mode, cfg):
    for history in ("none", "single4", "repeated1"):
        key = f"intensity/{seed}/{mode}/{history}"
        meta = {"family": "intensity", "condition": history, "preset": mode}
        parent = saved(study, key)
        if not parent:
            study.guard(force=True)
            c = Case(study, key, KERNEL, seed, config=cfg)
            for i in range(10 if history == "repeated1" else 1 if history == "single4" else 0):
                c.send([101, 102], 4 if history == "single4" else 1, at=i * 100000, source="registered-history")
            points, spans = snapshots(c, 1000000)
            parent = finish(c, meta | {"stage": "training"}, points, spans)
        for dose in (0, 0.2, 1, 4):
            probe(study, key + f"/cue{dose}", parent, [(101, 1.0)], dose, 5000000, **meta)
    for amplitude, strength in ((1, 1), (0.25, 4)):
        key = f"equal-drive/{seed}/{mode}/{strength}"
        if saved(study, key):
            continue
        study.guard(force=True)
        c = Case(study, key, KERNEL, seed, config=cfg)
        stim = Stimulus(0, ((101, amplitude), (102, amplitude)), strength)
        report = diagnose(c.engine.capture_state(), [stim], 100000)
        new_json(c.folder / "diagnostics.json", report)
        c.send_stimulus(stim, source="equal-drive-control")
        points, spans = snapshots(c, 100000)
        finish(
            c,
            {"family": "equal-drive", "stage": "training", "condition": strength, "preset": mode, "input_dose": 2},
            points,
            spans,
        )


def physical_cases(study, seed, mode, cfg):
    for template in ("inertial-cart", "gravity-pendulum"):
        record = physical_recording(seed, template)
        units = record["units"]
        cue = next(m["encoded"] for m in units[100]["measurements"] if m["kind"] == "joint_position")
        channels = [(v["channel"], v["value"]) for v in cue]
        assert channels
        for condition in ("complete", "no-proprioception", "split", "shuffled", "untrained"):
            key = f"physical/{seed}/{mode}/{template}/{condition}"
            meta = {"family": "physical", "condition": condition, "preset": mode, "template": template}
            parent = saved(study, key)
            if not parent:
                study.guard(force=True)
                c = Case(study, key, KERNEL, seed, config=cfg)
                order = list(range(len(units)))
                if condition == "shuffled":
                    random.Random(seed).shuffle(order)
                dose_by_channel = Counter()
                for cycle in range(2):
                    if condition == "untrained":
                        break
                    for i, source_i in enumerate(order):
                        unit = copy.deepcopy(units[source_i])
                        unit["time_us"] = str((cycle * len(units) + i + 1) * 20000)
                        unit["frame_id"] = f"{cycle}:{source_i}"
                        if condition == "no-proprioception":
                            elements = [
                                e
                                for m in unit["measurements"]
                                if m["kind"] not in ("accelerometer", "gyroscope")
                                for e in m["encoded"]
                            ]
                            unit["elements"] = elements
                        delivered = [unit]
                        if condition == "split":
                            delivered = [
                                unit
                                | {
                                    "kind": "element",
                                    "elements": [e],
                                    "grouping_basis": "research split of recorded joint observation",
                                }
                                for e in unit["elements"]
                            ]
                        for part in delivered:
                            if not part["elements"]:
                                continue
                            stim = frame(part)
                            for ch, v in stim.channels:
                                dose_by_channel[ch] += v * stim.intensity
                            c.send_stimulus(
                                stim,
                                source="physical-recording-replay",
                                payload={"units": [part]},
                                adapter="stimulus-units",
                            )
                points, spans = snapshots(c, 8000000)
                parent = finish(
                    c,
                    meta
                    | {
                        "stage": "training",
                        "input_dose": sum(dose_by_channel.values()),
                        "dose_by_channel": dict(dose_by_channel),
                    },
                    points,
                    spans,
                )
            for intensity in (0, 0.5):
                probe(study, key + f"/cue{intensity}", parent, channels, intensity, 5000000, **meta)


def run():
    study = Study()
    try:
        record_host()
        for seed in SEEDS:
            for mode, cfg in (("ordinary", {}), ("facilitation", {"stp_facilitation_tau_s": 1.0})):
                for task in (backgrounds, intensity_cases, physical_cases):
                    study.guard(force=True)
                    print(json.dumps({"start": task.__name__, "seed": seed, "preset": mode}), flush=True)
                    task(study, seed, mode, cfg)
        new_json(WORK / "simulation-complete.json", {"completed": True})
    except Exception as exc:
        c = study.active_case
        if c and not (c.folder / "result.json").exists():
            c.finish({"budget_stop": True, "failure": type(exc).__name__ + ": " + str(exc)})
        new_json(WORK / f"stop-{time.time_ns()}.json", {"error": str(exc), "case": c.key if c else None})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["run"]:
        run()
    else:
        raise SystemExit("prepare | run")
