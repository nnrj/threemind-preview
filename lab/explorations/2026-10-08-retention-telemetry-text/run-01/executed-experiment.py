"""Preregistered text-memory comparison; immutable physical background replay."""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import math
import platform
import subprocess
import time
from collections import Counter
from dataclasses import asdict, replace
from itertools import pairwise
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.retention import RetentionConfig, RetentionEngine
from threemind_kernels.retention_native import NativeRetentionEngine
from threemind_runtime.sensory import TextSensor, TextSensorConfig

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / ".work/language-spaced-20261004/physical-telemetry.jsonl"
NATIVE = ROOT / ".work/native-repair/_threemind_native.pyd"
SEED = 20261004
WORDS = ("苹果", "树叶", "天空", "雪花")
COLORS = ("红", "绿", "蓝", "白")
SENTENCES = tuple(f"{word}是{color}色的。" for word, color in zip(WORDS, COLORS))
CONFIG = TextSensorConfig(encoding="literal-character", frame_characters=1, frame_interval_us=50_000)
STAGES = (24, 48, 80, 144, 272, 530, 560, 650, 830, 834, 864, 954, 1134, 2034)
PROBES = (530, 560, 650, 830, 1134, 2034)
BACKGROUND_END = 834_000_000
MODES = ("adaptive-half-life", "legacy-stability")


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


def sha(body):
    return hashlib.sha256(body).hexdigest()


class Evidence:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory, self.start, self.bytes = directory, time.monotonic(), 0

    def guard(self):
        if time.monotonic() - self.start > 1800 or self.bytes > 512 * 2**20:
            raise RuntimeError("explicit host experiment limit reached; no internal events skipped")
        if (self.directory / "STOP").exists():
            raise RuntimeError("explicit experiment STOP")

    def write(self, relative, obj, *, zipped=False, raw=False):
        self.guard()
        body = obj if raw else encoded(obj)
        if zipped:
            body = gzip.compress(body, mtime=0)
        p = self.directory / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("xb") as stream:
            stream.write(body)
        self.bytes += len(body)
        return sha(body)


def curriculum(kind):
    result = []
    if kind == "repeat":
        for i, text in enumerate(SENTENCES):
            result.extend((i * 6_000_000 + j * 500_000, text) for j in range(12))
        for start, rounds, gap in ((24, 12, 2), (48, 8, 4), (80, 8, 8), (144, 8, 16), (272, 8, 32)):
            for j in range(rounds):
                result.extend((int((start + j * gap + i * gap / 4) * 1e6), text) for i, text in enumerate(SENTENCES))
    result.extend((528_000_000 + i * 500_000, text) for i, text in enumerate(SENTENCES))
    result.sort()
    assert Counter(text for _, text in result) == {text: 57 if kind == "repeat" else 1 for text in SENTENCES}
    return result


def prepare(evidence):
    # Refuse a stale native build or different Core source before creating any subject.
    old = json.loads((ROOT / "lab/explorations/2026-10-08-retention-repair/verification.json").read_text("utf-8"))
    assert sha(NATIVE.read_bytes()) == old["executable_sha256"][NATIVE.relative_to(ROOT).as_posix()]
    core_hashes = {k: v for k, v in old["source_sha256"].items() if k.startswith(("src/", "crates/"))}
    for name, expected in core_hashes.items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    body = SOURCE.read_bytes()
    metadata = json.loads(SOURCE.with_suffix(".metadata.json").read_text("utf-8"))
    complete = json.loads(SOURCE.with_suffix(".complete.json").read_text("utf-8"))
    assert complete["samples"] == 841 and complete["elapsed_seconds"] >= 840
    rows = [json.loads(line) for line in body.splitlines() if line.strip()]
    rows = [row for row in rows if row["scope"] == "host"]
    assert len(rows) == 841 and all(int(a["time_us"]) < int(b["time_us"]) for a, b in pairwise(rows))
    sensor = TextSensor(SEED, CONFIG)
    text_channels = {c for text in SENTENCES for f in sensor.frames(text) for c, _ in f["stimulus"].channels}
    background = []
    for row in rows:
        if int(row["time_us"]) < BACKGROUND_END and row["stimulus"]:
            stimulus = Stimulus.from_dict(row["stimulus"])
            assert stimulus.time_us == int(row["time_us"]) and stimulus.intensity == 0.2
            background.append({"source": "recorded-host", "stimulus": stimulus.to_dict()})
    background_channels = {int(c) for event in background for c, _ in event["stimulus"]["channels"]}
    assert not text_channels & background_channels
    evidence.write("host-telemetry.jsonl.gz", b"\n".join(encoded(row) for row in rows) + b"\n", zipped=True, raw=True)
    evidence.write("source-metadata.json", metadata)
    evidence.write("source-complete.json", complete)
    events, lessons, input_hashes = {}, {}, {}
    for kind in ("repeat", "single"):
        lessons[kind] = curriculum(kind)
        events[kind] = list(background)
        for t, text in lessons[kind]:
            for frame in sensor.frames(text, intensity=1.0):
                stimulus = replace(frame["stimulus"], time_us=t + frame["stimulus"].time_us)
                assert stimulus.time_us < 530_000_000
                events[kind].append({"source": "lesson", "carrier": text, "stimulus": stimulus.to_dict()})
        events[kind].sort(key=lambda event: int(event["stimulus"]["time_us"]))
        input_hashes[kind] = evidence.write(f"inputs-{kind}.json.gz", events[kind], zipped=True)
    evidence.write("curriculum.json", lessons)
    evidence.write("registered-protocol.md", (HERE / "protocol.md").read_bytes(), raw=True)
    evidence.write("executed-experiment.py", Path(__file__).read_bytes(), raw=True)
    availability = {key: sum(bool(row["raw"][key]["available"]) for row in rows) for key in rows[0]["raw"]}
    manifest = {
        "schema": "threemind.retention-telemetry-text/1",
        "registered_protocol_sha256": sha((HERE / "protocol.md").read_bytes()),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "kernel_sources": core_hashes,
        "native_sha256": sha(NATIVE.read_bytes()),
        "python": platform.python_version(),
        "physical_source": str(SOURCE.relative_to(ROOT)),
        "physical_source_sha256": sha(body),
        "source_metadata_sha256": sha(SOURCE.with_suffix(".metadata.json").read_bytes()),
        "source_complete_sha256": sha(SOURCE.with_suffix(".complete.json").read_bytes()),
        "used_scope": "host",
        "background_end_us": str(BACKGROUND_END),
        "background_frames": len(background),
        "background_channels": sorted(background_channels),
        "source_host_samples": len(rows),
        "metric_available_samples": availability,
        "text_sensor": asdict(CONFIG),
        "sensory_seed": SEED,
        "text_channels": sorted(text_channels),
        "input_hashes": input_hashes,
        "stage_seconds": STAGES,
        "probe_seconds": PROBES,
        "defaults_exception": {"quiescence_death_us": 10**12},
        "background_note": "Previously measured E43 host telemetry, exact replay; no new OS sampling, no process/runtime feedback",
        "main_subjects": 4,
        "prototype_or_shape_test": False,
    }
    evidence.write("manifest.json", manifest)
    print(
        json.dumps(
            {
                "prepared": True,
                "host_frames": len(background),
                "text_channels": len(text_channels),
                "host_channels": len(background_channels),
                "source_sha256": sha(body),
            }
        ),
        flush=True,
    )
    return manifest, events, sensor, text_channels


def create(mode, events, factory=NativeRetentionEngine):
    e = factory(RetentionConfig(consolidation_mode=mode, quiescence_death_us=10**12))
    for event in events:
        e.inject(Stimulus.from_dict(event["stimulus"]))
    return e


def close(a, b, path="state"):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for key in a:
            close(a[key], b[key], path + "/" + key)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}/{i}")
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14), (path, a, b)
    else:
        assert a == b, (path, a, b)


def parity(evidence, events):
    rows = []
    for mode in MODES:
        start = time.perf_counter()
        a, b = create(mode, events, RetentionEngine), create(mode, events)
        for t in (1_000_001, 6_000_000, 12_000_000, 24_000_000):
            evidence.guard()
            a.advance_to(t)
            b.advance_to(t)
            close(a.capture_state().to_dict(), b.capture_state().to_dict())
            close(a.graph(), b.graph())
        for factory, e in ((RetentionEngine, a), (NativeRetentionEngine, b)):
            checkpoint = e.capture_state()
            restored = factory(state=checkpoint)
            e.advance_to(24_117_771)
            restored.advance_to(24_117_771)
            assert e.capture_state().digest == restored.capture_state().digest
        rows.append(
            {
                "mode": mode,
                "full_state_matches": True,
                "same_backend_restore_exact": True,
                "until_us": "24000000",
                "wall_seconds": time.perf_counter() - start,
            }
        )
        print(json.dumps({"parity": mode, "passed": True, "seconds": rows[-1]["wall_seconds"]}), flush=True)
    evidence.write("backend-validation.json", rows)


def edge_key(edge):
    return edge["source"], edge["target"], edge["birth_us"]


def partition(graph, text_channels):
    nodes = {n["id"]: n["channel"] for n in graph["nodes"]}
    groups = {"TT": [], "TB": [], "BB": []}
    for edge in graph["edges"]:
        flags = [nodes[edge[k]] in text_channels for k in ("source", "target")]
        groups["TT" if all(flags) else "TB" if any(flags) else "BB"].append(edge)
    return groups


def statistics(e, graph, groups, cohort, sensor):
    m = e.metrics()
    result = {k: m[k] for k in ("time_us", "life", "nodes", "edges", "mean_weight", "transport", "retention")}
    current = {edge_key(edge): edge for edge in graph["edges"]}
    result["partitions"] = {}
    for name, group in groups.items():
        row = {
            "count": len(group),
            "weight_sum": sum(x["weight"] for x in group),
            "mean_weight": sum(x["weight"] for x in group) / len(group) if group else None,
        }
        if cohort is not None:
            originals = cohort[name]
            surviving = [current[key] for key in originals if key in current]
            base_weight = sum(originals.values())
            row["cohort"] = {
                "initial": len(originals),
                "surviving": len(surviving),
                "fraction": len(surviving) / len(originals) if originals else None,
                "weight_sum": sum(edge["weight"] for edge in surviving),
                "relative_weight": sum(edge["weight"] for edge in surviving) / base_weight if base_weight else None,
                "new_edges": sum(edge_key(x) not in originals for x in group),
            }
        result["partitions"][name] = row
    nodes = {n["channel"]: n for n in graph["nodes"]}
    edges = {(x["source"], x["target"]): x for x in graph["edges"]}
    pairs = []
    for word, color in zip(WORDS, COLORS):
        for character in word:
            a = nodes.get(sensor.identity(0x400000 + ord(character)))
            b = nodes.get(sensor.identity(0x400000 + ord(color)))
            for source, target, label in ((a, b, f"{character}->{color}"), (b, a, f"{color}->{character}")):
                edge = edges.get((source["id"], target["id"])) if source and target else None
                pairs.append({"label": label, "present": edge is not None, "edge": edge})
    result["paired_character_edges"] = pairs
    text_channels = sensor_channels(sensor)
    result["text_nodes"] = [n for n in graph["nodes"] if n["channel"] in text_channels]
    return result


def sensor_channels(sensor):
    return {channel for text in SENTENCES for f in sensor.frames(text) for channel, _ in f["stimulus"].channels}


def checkpoint(evidence, relative, engine, context, times):
    start = time.perf_counter()
    state = engine.capture_state()
    digest = state.digest
    times["capture_hash"] += time.perf_counter() - start
    start = time.perf_counter()
    evidence.write(relative + ".json.gz", state.payload, zipped=True, raw=True)
    evidence.write(relative + ".context.json", context | {"state_hash": digest, "time_us": str(engine.time_us)})
    times["gzip_write"] += time.perf_counter() - start
    return state


def probe(evidence, case, seconds, state, cue, sensor, times):
    start = time.perf_counter()
    e = NativeRetentionEngine(state=state)
    times["restore"] += time.perf_counter() - start
    origin = e.time_us + 1  # Newly arriving cue, never inserted before the parent checkpoint's event phase.
    if cue:
        for frame in sensor.frames(cue, intensity=1.0):
            e.inject(replace(frame["stimulus"], time_us=origin + frame["stimulus"].time_us))
    channels = [sensor.identity(0x400000 + ord(c)) for c in COLORS]
    trajectory = []
    for dt in range(0, 2_000_001, 20_000):
        start = time.perf_counter()
        e.advance_to(origin + dt)
        times["core"] += time.perf_counter() - start
        start = time.perf_counter()
        nodes = e.observation_nodes()
        values = {n["channel"]: n["activation"] for n in nodes}
        trajectory.append(
            {
                "offset_us": dt,
                "nodes": [[n["id"], n["channel"], n["activation"]] for n in nodes],
                "color_activation": [values.get(c, 0.0) for c in channels],
            }
        )
        times["observation"] += time.perf_counter() - start
    integrals = {}
    for name, lo, hi in (("primary", 500_000, 1_000_000), ("full", 0, 2_000_000)):
        integrals[name] = [
            sum(
                (a["color_activation"][i] + b["color_activation"][i]) / 2 * (b["offset_us"] - a["offset_us"]) / 1e6
                for a, b in pairwise(trajectory)
                if lo <= a["offset_us"] and b["offset_us"] <= hi
            )
            for i in range(4)
        ]
    name = f"{case}/probes/t{seconds}-{cue or 'no-cue'}"
    start = time.perf_counter()
    evidence.write(name + ".trajectory.json.gz", trajectory, zipped=True)
    times["gzip_write"] += time.perf_counter() - start
    end = checkpoint(evidence, name, e, {"parent_hash": state.digest, "cue": cue, "cue_us": str(origin)}, times)
    return {
        "cue": cue,
        "origin_us": str(origin),
        "parent_hash": state.digest,
        "integrals": integrals,
        "final_hash": end.digest,
        "trajectory": name + ".trajectory.json.gz",
    }


def score(probes):
    baseline = probes[0]
    assert baseline["cue"] == ""
    for row in probes[1:]:
        delta = [a - b for a, b in zip(row["integrals"]["primary"], baseline["integrals"]["primary"])]
        order = sorted(range(4), key=lambda i: delta[i], reverse=True)
        best, second = order[:2]
        chosen = COLORS[best] if delta[best] > 1e-6 and delta[best] - delta[second] > 1e-6 else None
        expected = COLORS[WORDS.index(row["cue"])] if row["cue"] in WORDS else None
        row.update(
            primary_delta=delta,
            diagnostic_choice=chosen,
            expected=expected,
            diagnostic_match=chosen == expected if expected is not None else None,
        )


def run(evidence, mode, kind, events, sensor, text_channels, input_hash):
    name = ("scheme1" if mode == MODES[0] else "scheme2") + "-" + kind
    start_wall = time.monotonic()
    e = create(mode, events)
    source_context = {
        "input_file": f"inputs-{kind}.json.gz",
        "input_sha256": input_hash,
        "text_sensor": asdict(CONFIG),
        "sensory_seed": SEED,
        "background": "frozen host replay until 834s",
        "all_future_inputs_saved_in_core_queue": True,
    }
    totals = {k: 0.0 for k in ("core", "observation", "capture_hash", "gzip_write", "restore")}
    evidence.write(name + "/config.json", e.config.to_dict())
    stages, cohort, parent = [], None, None
    input_times = [int(x["stimulus"]["time_us"]) for x in events]
    checkpoint(evidence, name + "/birth", e, source_context | {"input_cursor": 0}, totals)
    try:
        for seconds in STAGES:
            evidence.guard()
            start = time.perf_counter()
            e.advance_to(seconds * 1_000_000)
            totals["core"] += time.perf_counter() - start
            start = time.perf_counter()
            graph = e.graph()
            groups = partition(graph, text_channels)
            if seconds == 530:
                cohort = {k: {edge_key(edge): edge["weight"] for edge in group} for k, group in groups.items()}
                evidence.write(name + "/cohort.json.gz", groups, zipped=True)
            row = statistics(e, graph, groups, cohort, sensor)
            row["seconds"] = seconds
            totals["observation"] += time.perf_counter() - start
            context = source_context | {
                "parent_hash": parent,
                "input_cursor": bisect.bisect_right(input_times, e.time_us),
            }
            state = checkpoint(evidence, f"{name}/t{seconds}", e, context, totals)
            row["state_hash"] = parent = state.digest
            anchors = {(a, b): (h, int(t)) for a, b, h, t in state.to_dict()["operator_state"]["retention"]["edges"]}
            for pair in row["paired_character_edges"]:
                if pair["present"]:
                    edge = pair["edge"]
                    h, anchor = anchors[(edge["source"], edge["target"])]
                    pair["half_life_s"] = max(
                        e.config.memory_half_life_min_s,
                        h - e.config.memory_half_life_decay_rate * (e.time_us - anchor) / 1e6,
                    )
                    pair["half_life_controls_forgetting"] = mode == MODES[0]
            if seconds == 530:
                # Test exact continuation, including the saved pending background and internal events.
                a, b = NativeRetentionEngine(state=state), NativeRetentionEngine(state=state)
                a.advance_to(e.time_us + 117_771)
                b.advance_to(e.time_us + 50_123)
                b.capture_state()
                b.graph()
                b.advance_to(e.time_us + 117_771)
                assert a.capture_state().digest == b.capture_state().digest
                row["restore_and_observation_exact"] = True
            if seconds in PROBES:
                row["probes"] = [
                    probe(evidence, name, seconds, state, cue, sensor, totals) for cue in ("", *WORDS, "石桥")
                ]
                score(row["probes"])
                assert e.capture_state().digest == state.digest, "probe modified parent"
            stages.append(row)
            evidence.write(f"{name}/summary-t{seconds}.json", row)
            print(
                json.dumps(
                    {
                        "case": name,
                        "seconds": seconds,
                        "nodes": row["nodes"],
                        "edges": row["edges"],
                        "text_edges": row["partitions"]["TT"]["count"],
                        "cohort": row["partitions"]["TT"].get("cohort"),
                        "elapsed": round(time.monotonic() - start_wall, 2),
                    }
                ),
                flush=True,
            )
        result = {
            "case": name,
            "mode": mode,
            "curriculum": kind,
            "config": e.config.to_dict(),
            "stages": stages,
            "timing_seconds": totals,
            "wall_seconds": time.monotonic() - start_wall,
        }
        evidence.write(name + "/result.json", result)
        return result
    except Exception as error:
        # Preserve this separate partial subject; never restart it over the same directory.
        (evidence.directory / name / "failure.json").write_bytes(encoded({"error": repr(error), "time_us": e.time_us}))
        (evidence.directory / name / "stopped-state.json.gz").write_bytes(
            gzip.compress(e.capture_state().payload, mtime=0)
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence = Evidence(args.out)
    manifest, events, sensor, text_channels = prepare(evidence)
    parity(evidence, events["repeat"])
    results = []
    for kind in ("repeat", "single"):
        for mode in MODES:
            results.append(
                run(evidence, mode, kind, events[kind], sensor, text_channels, manifest["input_hashes"][kind])
            )
    evidence.write(
        "results.json",
        {
            "schema": manifest["schema"],
            "runs": results,
            "wall_seconds": time.monotonic() - evidence.start,
            "bytes_before_summary": evidence.bytes,
        },
    )
    evidence.write(
        "checksums.json",
        {
            str(p.relative_to(evidence.directory)).replace("\\", "/"): sha(p.read_bytes())
            for p in sorted(evidence.directory.rglob("*"))
            if p.is_file()
        },
    )
    print(json.dumps({"complete": True, "subjects": len(results), "evidence_bytes": evidence.bytes}), flush=True)


if __name__ == "__main__":
    main()
