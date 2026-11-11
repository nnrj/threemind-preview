"""Isolated factorial study. No kernel patches or private model-state edits."""

import argparse
import copy
import gzip
import hashlib
import itertools
import json
import random
import shutil
from dataclasses import replace
from uuid import UUID, uuid5

from common import HERE, ROOT, WORK, Case, Study, encoded, load_case, new_json, prepare, read_json

from threemind_core import Stimulus
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER
from threemind_lab.inputs import envelope_record

KERNEL = "threemind.continuous/1"
BASELINE = "threemind.causal/9"
SEED = 9291000
TOKENS = dict(zip("ABCDE", random.Random(SEED).sample(range(1000, 9000), 16)[8:13]))
FLAGS = ("stp_enabled", "fast_enabled", "context_enabled")
COMBINATIONS = ["".join(map(str, bits)) for bits in itertools.product((1, 0), repeat=3)]
PROBES = {"AB": [(0, "A"), (1, "B")], "DB": [(0, "D"), (1, "B")],
          "B": [(1, "B")], "A": [(0, "A")], "D": [(0, "D")], "none": []}


def flags(bits):
    return dict(zip(FLAGS, (x == "1" for x in bits)))


def finished(key):
    return (WORK / "cases" / key / "result.json").exists()


class Observer:
    """Public observer stream only; delegate every operation to the same engine."""

    def __init__(self, engine):
        self.engine, self.events = engine, []

    def __getattr__(self, name):
        return getattr(self.engine, name)

    def advance_to(self, target, observer=None, *, inputs_only=False):
        def observed(event):
            self.events.append(event)
            if observer:
                observer(event)
        self.engine.advance_to(target, observed, inputs_only=False)


def train(study, key, bits="111", *, swap=False, reverse=False, background=False, baseline=False):
    if finished(key):
        return load_case(study, key)
    c = Case(study, key, BASELINE if baseline else KERNEL, SEED, config={} if baseline else flags(bits))
    if background:
        c.add_background(0)
    c.advance(2_200_000)
    seqs = [("A", "B", "E" if swap else "C"), ("D", "B", "C" if swap else "E")]
    if reverse:
        seqs.reverse()
    for count in (20, 10, 5):
        for seq in seqs:
            for _ in range(count):
                for index, symbol in enumerate(seq):
                    frame = [symbol] if index == 0 else [seq[index - 1], symbol]
                    if not c.pulse([TOKENS[x] for x in frame], 1.0, 1_000_000):
                        raise RuntimeError("training unexpectedly died; preserve and diagnose")
    extra = {"bits": bits, "swap": swap, "reverse": reverse, "background": background,
             "tokens": TOKENS, "frames": 210, "baseline": baseline}
    return c.finish(extra)


def trace_sample(c, start):
    return {"relative_us": c.engine.time_us - start, "time_us": str(c.engine.time_us),
            "life": c.engine.life, "nodes": c.engine.observation_nodes(), "transport": c.engine.metrics()["transport"]}


def phase_metrics(trace, start_us, end_us):
    selected = [r for r in trace if start_us <= r["relative_us"] < end_us]
    values = {}
    for symbol in "CE":
        pairs = [(r["relative_us"], next((n["activation"] for n in r["nodes"]
                                         if n["channel"] == TOKENS[symbol]), 0.0)) for r in selected]
        peak_time, peak = max(pairs, key=lambda v: v[1], default=(None, 0.0))
        area = sum((b[0] - a[0]) / 1e6 * (a[1] + b[1]) / 2 for a, b in zip(pairs, pairs[1:]))
        values[symbol] = {"peak": peak, "peak_us": peak_time, "area": area}
    return values


def probe(study, parent, key, name, *, test_bits=None, quantum=10_000, observe=True):
    if finished(key):
        return read_json(WORK / "cases" / key / "result.json")
    c = Case(study, key, parent["kernel"], SEED, parent=parent)
    intervention = None
    if test_bits is not None:
        before = c.engine.capture_state().digest
        previous_config = c.engine.config.to_dict()
        c.engine.reconfigure(replace(c.engine.config, **flags(test_bits)))
        intervention = {"time_us": str(c.engine.time_us), "before": before,
                        "after": c.engine.capture_state().digest, "before_config": previous_config,
                        "after_config": c.engine.config.to_dict(), "method": "public reconfigure"}
        c.events.append({"key": "study:reconfigure", "time_us": str(c.engine.time_us),
                         "kind": "research_intervention", "payload": intervention})
    c.advance(c.engine.time_us + 1_000_000)
    start = c.engine.time_us
    observer = Observer(c.engine) if observe else None
    if observer:
        c.session.engine = observer
    snapshots = {"before_probe": c.engine.capture_state().to_dict()}
    carrier = None
    if PROBES[name] and c.engine.life != "dead":
        frames = [{"stimulus": Stimulus(start + sec * 1_000_000, ((TOKENS[symbol], 1.0),), 0.5)}
                  for sec, symbol in PROBES[name]]
        item = envelope_record(uuid5(UUID(c.id), "sequence-probe"), "anonymous-frames", "manual-probe",
                               {"frames": [f["stimulus"].to_dict() for f in frames]}, {"dose": 0.5},
                               len(frames), len(frames))
        c.inputs.changes["envelopes"].append(item)
        c.inputs.schedule(item, frames)
        carrier = item["id"]
    trace = [trace_sample(c, start)]
    c.session.advance_to(start, guard=c.guard)
    trace.append(trace_sample(c, start))
    milestones = {0, 100_000, 500_000, 900_000, 990_000, 1_000_000, 1_010_000, 1_100_000,
                  1_500_000, 2_000_000, 3_000_000, 5_000_000, 12_000_000}
    snapshots["0"] = c.engine.capture_state().to_dict()
    while c.engine.time_us < start + 12_000_000 and c.engine.life != "dead":
        c.guard()
        c.session.advance_to(min(start + 12_000_000, c.engine.time_us + quantum), guard=c.guard)
        trace.append(trace_sample(c, start))
        c.sample()
        relative = c.engine.time_us - start
        if relative in milestones:
            snapshots[str(relative)] = c.engine.capture_state().to_dict()
        if observer and len(observer.events) > 100_000:
            raise RuntimeError("observer event budget")
    snapshots["end"] = c.engine.capture_state().to_dict()
    c.session.host.close(c.engine.time_us, "run_ended")
    windows = [e["payload"] for e in c.events if e["kind"] == "temporal_readout"
               and e["payload"]["envelope_id"] == carrier] if carrier else []
    window = windows[-1] if windows else None
    id_to_symbol = {n["id"]: next((s for s, ch in TOKENS.items() if ch == n["channel"]), str(n["channel"]))
                    for n in c.engine.observation_nodes()}
    final, reader_peaks = {"C": 0.0, "E": 0.0}, {"C": 0.0, "E": 0.0}
    if window:
        for node in window["nodes"]:
            symbol = id_to_symbol.get(node["node_id"])
            if symbol in final:
                final[symbol] = node["last_activation"]
                reader_peaks[symbol] = node["peak_activation"]
    extra = {"parent_id": parent["id"], "training": parent["extra"], "probe": name,
             "test_bits": test_bits or parent["extra"]["bits"], "intervention": intervention,
             "start_us": start, "quantum_us": quantum, "observer": observe,
             "classification": window["classification"] if window else "no_window",
             "reason": window["reason"] if window else "no_window", "end_activation": final,
             "reader_peak": reader_peaks, "primary_available": bool(window and window["classification"] == "converged"),
             "pre_B": phase_metrics(trace, 0, 1_000_000), "post_B": phase_metrics(trace, 1_000_000, 12_000_001),
             "whole": phase_metrics(trace, 0, 12_000_001), "samples": len(trace),
             "transmission_events": len(observer.events) if observer else 0}
    for filename, rows in (("trajectory.jsonl.gz", trace), ("transmissions.jsonl.gz", observer.events if observer else [])):
        with gzip.open(c.folder / filename, "xb") as out:
            for row in rows:
                out.write(encoded(row) + b"\n")
    new_json(c.folder / "snapshots.json", snapshots)
    return c.finish(extra)


def normalize_reader(result):
    value = copy.deepcopy(result["session"]["readouts"])
    # Provenance identifiers differ between independent descendants, never dynamics.
    def norm(x):
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items() if k not in ("run_id", "envelope_id", "window_id", "id")}
        if isinstance(x, list):
            return [norm(v) for v in x]
        return x
    return norm(value)


def validate(study):
    parent = train(study, "validation/train")
    oldwork = ROOT / ".work/candidates-20260929"
    oldroot = oldwork / "cases/block-0/continuous-1/sequence-bg0-overlap1-swap0"
    oldparent = read_json(oldroot / "result.json")
    assert parent["state_sha256"] == oldparent["state_sha256"], "training failed exact old-state reproduction"
    comparisons = []
    for index, name in enumerate(("AB", "DB")):
        fine = probe(study, parent, f"validation/{name}-fine", name)
        coarse = probe(study, parent, f"validation/{name}-coarse", name, quantum=100_000, observe=False)
        assert fine["state_sha256"] == coarse["state_sha256"], "observation changed final Core state"
        for field in ("reader_peak", "end_activation", "classification", "reason"):
            assert fine["extra"][field] == coarse["extra"][field], f"readout changed: {field}"
        assert normalize_reader(fine) == normalize_reader(coarse), "saved readout state changed"
        previous = read_json(oldroot / f"cue-{index}/result.json")["extra"]
        assert fine["extra"]["reader_peak"] == {s: previous["peak_activation"][str(TOKENS[s])] for s in "CE"}
        assert fine["extra"]["classification"] == previous["classification"]
        comparisons.append({"probe": name, "final_state_equal": True, "reader_equal": True,
                            "old_peak_equal": True, "state_sha256": fine["state_sha256"]})
    new_json(WORK / "validation.json", {"training_state_equal": True, "comparisons": comparisons})
    print("VALIDATED: exact training reproduction; observer/sampling neutral; previous peaks reproduced", flush=True)


def group(study, phase, bits=None):
    if not (WORK / "validation.json").exists():
        raise RuntimeError("instrumentation validation required before formal experiment")
    rows = []
    if phase == "factorial":
        for swap, reverse in itertools.product((False, True), repeat=2):
            key = f"factorial/{bits}/swap{int(swap)}-reverse{int(reverse)}"
            p = train(study, key, bits, swap=swap, reverse=reverse)
            for name in PROBES:
                r = probe(study, p, key + "/" + name, name)
                rows.append({"key": r["key"], "id": r["id"], **r["extra"]})
    elif phase == "test-switch":
        for swap, reverse in itertools.product((False, True), repeat=2):
            p = load_case(study, f"factorial/111/swap{int(swap)}-reverse{int(reverse)}")
            for test in COMBINATIONS[1:]:
                for name in ("AB", "DB"):
                    key = f"test-switch/swap{int(swap)}-reverse{int(reverse)}/{test}/{name}"
                    r = probe(study, p, key, name, test_bits=test)
                    rows.append({"key": r["key"], "id": r["id"], **r["extra"]})
    elif phase == "baseline":
        for swap, reverse in itertools.product((False, True), repeat=2):
            key = f"baseline/swap{int(swap)}-reverse{int(reverse)}"
            p = train(study, key, "000", swap=swap, reverse=reverse, baseline=True)
            for name in ("AB", "DB"):
                r = probe(study, p, key + "/" + name, name)
                rows.append({"key": r["key"], "id": r["id"], **r["extra"]})
    elif phase == "background":
        for mask in COMBINATIONS:
            key = f"background/{mask}"
            p = train(study, key, mask, background=True)
            for name in ("AB", "DB", "B"):
                r = probe(study, p, key + "/" + name, name)
                rows.append({"key": r["key"], "id": r["id"], **r["extra"]})
    output = WORK / f"{phase}{'-' + bits if bits else ''}.json"
    if not output.exists():
        new_json(output, rows)
    study.guard(force=True)
    print(f"COMPLETE {phase} {bits or ''}: {len(rows)} probes", flush=True)


def freeze():
    prepare()
    study = Study()
    try:
        sources = {}
        for path in HERE.glob("*"):
            if path.suffix in (".py", ".md"):
                destination = WORK / "frozen-sources" / path.name
                destination.parent.mkdir(exist_ok=True)
                shutil.copy2(path, destination)
                sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        notebooks.save_note(study.db, study.project, LOCAL_USER, study.identity("design-en"), {
            "operation_id": study.identity("design-en:write"), "expected_revision": 0, "kind": "note",
            "collection_id": study.meta["notebook_id"], "title": "Design: continuous-kernel mechanism attribution",
            "body": {"format": "markdown", "text": (HERE / "design.en.md").read_text(encoding="utf-8")}})
        new_json(WORK / "freeze.json", {"sources": sources, "tokens": TOKENS, "combinations": COMBINATIONS,
                                        "old_project": "cb3a2d4a-f8a2-440e-9182-75148e9454a8"})
    finally:
        study.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "validate", "factorial", "test-switch", "baseline", "background"))
    parser.add_argument("--bits", choices=COMBINATIONS)
    args = parser.parse_args()
    if args.phase == "prepare":
        freeze()
        return
    if args.phase == "factorial" and args.bits is None:
        parser.error("factorial requires --bits")
    study = Study()
    try:
        for name in ("run.py", "common.py"):
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == read_json(WORK / "freeze.json")["sources"][name]
        if args.phase == "validate":
            validate(study)
        else:
            group(study, args.phase, args.bits)
    except Exception as error:
        if study.active_case:
            study.active_case.finish({"budget_stop": str(error)})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
