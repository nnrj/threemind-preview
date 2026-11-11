"""Continuous /5.3 plus its own established temporal Transformer and actuator.

Only declared teaching, questioning and body-feedback operations advance Core.
Labels supervise the personal external reader, never its inference call.
"""

import copy
import gzip
import hashlib
import json
import random
from pathlib import Path
import sys

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / ".work/native53-release"), str(ROOT), str(HERE.parent)]
from threemind_core import StateImage, Stimulus
from threemind_kernels.local53 import Local53Config, KERNEL_ID
from threemind_kernels.registry import resolve_kernel
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.activity_controller import FIELDS

SYMBOLS = ("background", "P0", "P1", "A0", "A1", "B0", "B1", "out0", "out1", "body0", "body1")
INDEX = np.rint(np.linspace(0, 19, 8)).astype(int).tolist()
STAGES = ("initial", "new", "reversal", "return")


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tup(v):
    return tuple(tup(x) for x in v) if isinstance(v, list) else v


def tensor_digest(value):
    h = hashlib.sha256()

    def visit(x):
        if torch.is_tensor(x):
            x = x.detach().cpu().contiguous()
            h.update(str(x.dtype).encode())
            h.update(str(tuple(x.shape)).encode())
            h.update(x.numpy().tobytes())
        elif isinstance(x, dict):
            for k in sorted(x, key=str):
                h.update(str(k).encode())
                visit(x[k])
        elif isinstance(x, (list, tuple)):
            for x2 in x:
                visit(x2)
        else:
            h.update(encoded(x))

    visit(value)
    return h.hexdigest()


def pairs(stage):
    values = {"P0": 0, "P1": 1, "A0": 0, "A1": 1}
    if stage != "initial":
        values.update(B0=0, B1=1)
    if stage == "reversal":
        values.update(A0=1, A1=0)
    return values


class Learner:
    def __init__(self, seed, curve, identity):
        self.seed, self.curve, self.identity = seed, curve, identity
        self.rng = random.Random(seed)
        self.mapping = dict(zip(SYMBOLS, self.rng.sample(range(1, 2**32), len(SYMBOLS))))
        self.core = resolve_kernel(KERNEL_ID).create(
            Local53Config(seed=seed, energy_seed=seed ^ 0x1634AB, decay_curve=curve), backend="native"
        )
        self.reader = CalibratedActivity(
            [self.mapping["out0"], self.mapping["out1"]], ("choice-0", "choice-1"), identity, seed=seed
        )
        self.next_background = 0
        self.events = []
        self.samples = []
        self.recent = []
        self.adapter_ref = None
        self.body = dict(position=0, last_command=None, moves=0)
        self.world = dict(stage="birth", presented=None)
        self.cursor = dict(stage="birth", operation="birth")
        self.learning = dict(teacher_lessons=0, queries=0, correction_rounds=0)

    def reader_digest(self):
        return tensor_digest(
            [
                self.reader.state_dict(),
                self.reader.optimizer.state_dict(),
                self.reader.learning_rng,
                self.reader.committed_updates,
                self.reader.computed_updates,
            ]
        )

    def state(self):
        return dict(
            schema="threemind.retention-joint/1",
            seed=self.seed,
            curve=self.curve,
            identity=self.identity,
            mapping=self.mapping.copy(),
            core=self.core.capture_state().to_dict(),
            rng=json.loads(encoded(self.rng.getstate())),
            torch_rng=torch.get_rng_state().tolist(),
            next_background=self.next_background,
            events=copy.deepcopy(self.events),
            samples=copy.deepcopy(self.samples),
            recent=copy.deepcopy(self.recent),
            adapter_ref=copy.deepcopy(self.adapter_ref),
            reader_digest=self.reader_digest(),
            body=copy.deepcopy(self.body),
            world=copy.deepcopy(self.world),
            cursor=copy.deepcopy(self.cursor),
            learning=self.learning.copy(),
        )

    def checkpoint(self, work, relative):
        value = self.reader_digest()
        if self.adapter_ref is None or self.adapter_ref["digest"] != value:
            path = Path("adapters") / value
            if not (work / path).exists():
                self.reader.save(work / path)
            self.adapter_ref = dict(
                path=path.as_posix(), digest=value, files={p.name: sha(p) for p in (work / path).iterdir()}
            )
        state = self.state()
        p = work / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("xb") as f:
            f.write(gzip.compress(encoded(state), mtime=0))
        return dict(path=str(relative), sha256=sha(p), state_sha256=digest(state))

    @classmethod
    def restore(cls, work, value):
        if value["schema"] != "threemind.retention-joint/1" or value["core"]["dynamics"] != KERNEL_ID:
            raise ValueError("identity")
        s = cls.__new__(cls)
        for name in (
            "seed",
            "curve",
            "identity",
            "mapping",
            "next_background",
            "events",
            "samples",
            "recent",
            "adapter_ref",
            "body",
            "world",
            "cursor",
            "learning",
        ):
            setattr(s, name, copy.deepcopy(value[name]))
        s.core = resolve_kernel(KERNEL_ID).create(state=StateImage.from_dict(value["core"]), backend="native")
        s.rng = random.Random()
        s.rng.setstate(tup(value["rng"]))
        for name, expected in s.adapter_ref["files"].items():
            assert sha(work / s.adapter_ref["path"] / name) == expected
        s.reader = CalibratedActivity.restore(work / s.adapter_ref["path"])
        torch.set_rng_state(torch.tensor(value["torch_rng"], dtype=torch.uint8))
        assert s.state() == value, "whole-state restore mismatch"
        return s

    def inject(self, t, values, role):
        row = dict(
            time_us=t, channels=[[self.mapping[k], float(v)] for k, v in values.items()], intensity=1.0, role=role
        )
        self.core.inject(Stimulus(t, tuple(tuple(x) for x in row["channels"]), 1.0))
        self.events.append(row)

    def advance(self, t):
        if t < self.core.time_us:
            raise ValueError("no rollback")
        while self.next_background <= t:
            self.inject(self.next_background, {"background": 0.2}, "background")
            self.next_background += 500_000
        self.core.advance_to(t)
        if self.core.life == "dead":
            raise RuntimeError("new death: preserve complete current state and in-flight")

    def lesson(self, cue, target, role):
        start = self.core.time_us
        self.world.update(presented=cue)
        for i in range(5):
            t = start + i * 250_000
            self.advance(t)
            self.inject(t, {cue: 0.4, f"out{target}": 0.4}, role)
        self.advance(start + 1_500_000)
        self.learning["teacher_lessons"] += 1

    def teach(self, stage, wrong=None):
        start = self.core.time_us
        old_events = len(self.events)
        mapping = pairs(stage)
        self.world["stage"] = stage
        selected = list(mapping) if wrong is None else sorted(set(wrong))
        if not selected:
            raise ValueError("empty correction")
        for _ in range(8 if wrong is None else 5):
            order = selected.copy()
            self.rng.shuffle(order)
            for cue in order:
                self.lesson(cue, mapping[cue], "teaching" if wrong is None else "correction")
        # Old correct examples remain in each spaced review and learning pool.
        for gap in (2, 6, 18):
            self.advance(self.core.time_us + gap * 1_000_000)
            order = list(mapping)
            self.rng.shuffle(order)
            for cue in order:
                self.lesson(cue, mapping[cue], "spaced-review")
        if wrong is not None:
            self.learning["correction_rounds"] += 1
        self.cursor = dict(stage=stage, operation="taught")
        return dict(
            start_us=start,
            end_us=self.core.time_us,
            selected=selected,
            events=self.events[old_events:],
            corrective=wrong is not None,
        )

    def query(self, cue, amplitude, role):
        start = self.core.time_us
        self.advance(start)
        event_start = len(self.events)
        self.world["presented"] = cue
        self.inject(start, {cue: amplitude}, role)
        frames = []
        raw = []
        for i in range(20):
            self.advance(start + (i + 1) * 50_000)
            before = self.core.capture_state().digest
            nodes = self.core.observation_nodes()
            by = {n["channel"]: n for n in nodes}
            declared = [n for n in nodes if n["channel"] in self.reader.layout.index]
            frames.append(self.reader.layout.frame(dict(nodes=declared)).tolist())
            raw.append({s: {f: by.get(ch, {}).get(f, 0.0) for f in FIELDS} for s, ch in self.mapping.items()})
            assert self.core.capture_state().digest == before
        selected = [frames[i] for i in INDEX]
        logits = self.reader.predict([selected])[0].tolist()
        choice = int(np.argmax(logits))
        old_position = self.body["position"]
        self.body.update(position=choice, last_command=choice, moves=self.body["moves"] + int(choice != old_position))
        # Proprioception reports actual actuator output, never the scoring answer.
        self.inject(self.core.time_us, {f"body{choice}": 0.2}, "body-feedback")
        self.advance(self.core.time_us)
        self.recent = copy.deepcopy(raw)
        self.learning["queries"] += 1
        return dict(
            cue=cue,
            amplitude=amplitude,
            role=role,
            start_us=start,
            end_us=self.core.time_us,
            frames=raw,
            reader_frames=selected,
            logits=logits,
            choice=choice,
            body=self.body.copy(),
            events=self.events[event_start:],
        )

    def sample(self, stage):
        mapping = pairs(stage)
        order = [(c, a) for c in mapping for a in (0.76, 0.8, 0.84, 0.8)]
        self.rng.shuffle(order)
        rows = []
        for cue, amplitude in order:
            row = self.query(cue, amplitude, "calibration-question")
            row["target"] = mapping[cue]
            self.samples.append(
                dict(x=row["reader_frames"], label=row["target"], stage=stage, cue=cue, time_us=row["start_us"])
            )
            rows.append(row)
        self.cursor = dict(stage=stage, operation="sampled")
        return dict(rows=rows, total_samples=len(self.samples))

    def fit(self, stage, steps=1200, check=lambda: None):
        before = self.core.capture_state().digest
        time = self.core.time_us
        result = self.reader.continue_calibration(
            [s["x"] for s in self.samples], [s["label"] for s in self.samples], steps=steps, check=check
        )
        assert self.core.capture_state().digest == before and self.core.time_us == time
        self.cursor = dict(stage=stage, operation="fitted")
        return result

    def exam(self, stage, kind):
        if kind not in ("development", "immediate", "delayed"):
            raise ValueError(kind)
        self.world["stage"] = stage
        mapping = pairs(stage)
        amplitudes = (0.76, 0.84) if kind == "development" else (0.72, 0.78, 0.86, 0.9)
        order = [(cue, amp) for cue in mapping for amp in amplitudes]
        self.rng.shuffle(order)
        rows = []
        reader = self.reader_digest()
        for cue, amp in order:
            row = self.query(cue, amp, kind + "-question")
            row["target"] = mapping[cue]
            row["correct"] = row["choice"] == row["target"]
            rows.append(row)
        assert self.reader_digest() == reader
        self.cursor = dict(stage=stage, operation=kind + "-exam")
        return dict(
            rows=rows,
            correct=sum(r["correct"] for r in rows),
            n=len(rows),
            wrong=sorted({r["cue"] for r in rows if not r["correct"]}),
            reader_unchanged=True,
        )

    def delay(self, stage, seconds=300):
        start = self.core.time_us
        self.advance(start + seconds * 1_000_000)
        self.cursor = dict(stage=stage, operation="delayed")
        return dict(start_us=start, end_us=self.core.time_us, seconds=seconds)
