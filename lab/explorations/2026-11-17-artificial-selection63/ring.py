"""Declared closed-loop ring apparatus. No production or historical state edits."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from threemind_core import StateImage, Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime.adapters import channel_id
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig
from threemind_runtime.inheritance import birth, birth_metadata
from threemind_runtime.readout_session import ReadoutSession

KERNEL = "threemind.continuous-memory/6.3"
NS = UUID("457932b1-3856-4cfe-87b7-3676bc74ea17")
SUPPLY = EnergySupplyConfig(enabled=True, rate_per_s=10, interval_us=100000, total_supply_limit=None)
MOTOR_NS = "world-motor-v1:ring-study-v1:0"
SENSE_NS = "ring-sensory-v1"
READOUT = {k: {"enabled": False} for k in ("structural_readout", "temporal_readout", "activity_readout")}
STARTS = (.125, .375, .625, .875)
SELECT_STARTS = (.0625, .5625)
TEST_STARTS = (.1875, .4375, .6875, .9375)
SEEDS = tuple(range(1117100, 1117116))
INSTRUMENT_SEED = 1117099


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = encoded(value)
    if path.suffix == ".gz":
        data = gzip.compress(data, compresslevel=1, mtime=0)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError("immutable evidence already differs: " + str(path))
        return
    with path.open("xb") as out:
        out.write(data)


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


class Ring:
    def __init__(self, key, seed, *, whole=None, parent=None, position=None,
                 blank_control=False, backend="native"):
        assert not (whole is not None and parent is not None)
        self.key, self.seed, self.backend = key, seed, backend
        self.events, self.inputs, self.rows = [], [], []
        self.ancestry = {}
        if whole is not None:
            assert whole["seed"] == seed and whole["kernel"] == KERNEL
            image = StateImage.from_dict(whole["core"])
            self.engine = resolve_kernel(KERNEL).create(state=image, backend=backend)
            assert self.engine.capture_state().digest == image.digest
            self.body = copy.deepcopy(whole["body"])
            self.next_sense = whole["next_sense"]
            self.next_background = whole["next_background"]
            self.next_motor = whole["next_motor"]
            self.supplier = EnergySupplier(SUPPLY, self.engine, whole["supplier"])
            self.session = ReadoutSession(self.engine, record=self.events.append,
                                          state=copy.deepcopy(whole["session"]), event_sink=self.sink)
            self.ancestry = {"kind": "exact-state-assessment-copy", "parent_whole_hash": digest(whole),
                             "parent_core_hash": image.digest, "birth_called": False}
        else:
            if parent is not None and not blank_control:
                parent_image = StateImage.from_dict(parent["core"])
                image = birth(parent_image, decay_age="preserve")
                self.engine = resolve_kernel(KERNEL).create(state=image, backend=backend)
                self.ancestry = {"kind": "offspring", "parent_whole_hash": digest(parent),
                                 "parent_core_hash": parent_image.digest,
                                 "birth_called": True, **birth_metadata(parent_image)}
            else:
                config = {"seed": seed, "energy_seed": seed ^ 0xA563, "energy_simulation_enabled": True}
                if parent is not None:
                    config = copy.deepcopy(parent["core"]["config"])
                    self.ancestry = {"kind": "uninherited-control", "parent_whole_hash": digest(parent),
                                     "birth_called": False}
                else:
                    self.ancestry = {"kind": "new-founder", "birth_called": False}
                self.engine = resolve_kernel(KERNEL).create(config, backend=backend)
            assert self.engine.time_us == 0
            self.body = {"x": 0.0, "v": 0.0, "phase": 0.0}
            self.next_sense = self.next_background = self.next_motor = 0
            self.supplier = EnergySupplier(SUPPLY, self.engine)
            self.session = ReadoutSession(self.engine, record=self.events.append, config=READOUT,
                state={"schema": "threemind.cli-readouts/1", "session_id": str(uuid5(NS, key))},
                event_sink=self.sink)
        if position is not None:
            before = copy.deepcopy(self.body)
            self.body.update(x=float(position), v=0.0)
            self.ancestry["declared_body_positioning"] = {"before": before, "after": copy.deepcopy(self.body)}
        assert self.body["phase"] == 0.0
        self.origin = self.snapshot()

    def sink(self, event, delivered):
        if event["kind"] == "energy":
            self.supplier.delivered(event)
            self.events.append(event)
        if delivered:
            self.inputs.append(delivered)

    def snapshot(self):
        return {"schema": "artificial-selection63/whole/1", "kernel": KERNEL, "seed": self.seed,
                "core": self.engine.capture_state().to_dict(), "session": self.session.capture(),
                "supplier": self.supplier.capture(), "body": copy.deepcopy(self.body),
                "next_sense": self.next_sense, "next_background": self.next_background,
                "next_motor": self.next_motor}

    def stimulus(self, now, background=False):
        if background:
            channels = ((channel_id(self.seed, "ring-background-v1", 0), 1.),)
            return Stimulus(now, channels, .2)
        region = int(self.body["x"] >= .5)
        channels = [(channel_id(self.seed, SENSE_NS, region * 4 + i), 1.) for i in range(4)]
        if self.body["v"]:
            channels.append((channel_id(self.seed, SENSE_NS, 8 + int(self.body["v"] < 0)),
                             math.tanh(abs(self.body["v"]) / .375)))
        return Stimulus(now, tuple(channels), .8)

    def schedule(self, stimulus, source):
        # Stable IDs depend on the uninterrupted subject session and actual time.
        identity = uuid5(NS, self.session.host.run_id + ":" + source + ":" + str(self.engine.time_us))
        self.session.schedule([{"stimulus": stimulus}], source=source, adapter_id="fixed-ring-sensor",
                              envelope_id=identity, at=0)

    def control(self, nodes):
        return math.tanh(.5 * math.fsum(
            (1 if channel_id(self.seed, MOTOR_NS, int(n["id"])) & 1 else -1) * n["activation"]
            for n in sorted(nodes, key=lambda n: n["id"])))

    def move(self, control, seconds):
        decay = math.exp(-.8 * seconds)
        terminal = .3 * control / .8
        distance = terminal * seconds + (self.body["v"] - terminal) * (1 - decay) / .8
        self.body["x"] = (self.body["x"] + distance) % 1.
        self.body["v"] = terminal + (self.body["v"] - terminal) * decay
        return distance

    def run(self, seconds=60, *, mode="normal", guard=None):
        begin = self.engine.time_us
        end = begin + round(seconds * 1e6)
        assert begin == self.next_motor
        wall = time.monotonic()
        restored = False
        dead_at = None
        distance = 0.
        while self.next_motor < end:
            if guard:
                guard()
            if time.monotonic() - wall > 180:
                raise RuntimeError("single declared stage exceeded 180 wall seconds")
            now = self.next_motor
            alive = self.engine.life != "dead"
            if alive:
                assert self.engine.time_us == now
                if now == self.next_background:
                    self.schedule(self.stimulus(now, True), "constant-background")
                    self.next_background += 500000
                if now == self.next_sense:
                    self.schedule(self.stimulus(now), "fixed-regions")
                    self.next_sense += 1000000
                self.supplier.prepare(self.engine)
                self.session.advance_to(now)
                nodes = self.engine.observation_nodes()
                control = self.control(nodes)
            else:
                nodes, control = [], 0.
                dead_at = self.engine.time_us if dead_at is None else dead_at
            if mode == "frequent" and alive:
                for _ in range(3):
                    self.engine.observation_nodes()
                    self.engine.metrics()
            row = {"time_us": now, "region": int(self.body["x"] >= .5),
                   "body": copy.deepcopy(self.body), "control": control, "nodes": nodes, "alive": alive}
            self.rows.append(row)
            distance += abs(self.move(control, .1))
            self.next_motor += 100000
            if alive:
                self.session.advance_to(self.next_motor)
            if mode in ("restored", "paused") and not restored and self.next_motor - begin >= 1000000:
                state = self.snapshot()
                if mode == "paused":
                    time.sleep(.01)
                    assert self.snapshot() == state
                else:
                    # Roundtrip ALL components; replacement remains at the same internal time.
                    copy_state = json.loads(encoded(state))
                    replacement = Ring(self.key, self.seed, whole=copy_state, backend=self.backend)
                    old_rows, old_events, old_inputs, old_origin, ancestry = self.rows, self.events, self.inputs, self.origin, self.ancestry
                    self.__dict__.update(replacement.__dict__)
                    self.rows, self.events, self.inputs = old_rows, old_events, old_inputs
                    self.origin, self.ancestry = old_origin, ancestry
                    self.session.event_sink = self.sink
                    self.session.host.record = self.events.append
                    assert self.snapshot() == state
                restored = True
        final = self.snapshot()
        if self.engine.life == "dead" and dead_at is None:
            dead_at = self.engine.time_us
        return {"key": self.key, "kernel": KERNEL, "seed": self.seed, "begin_us": begin,
                "planned_end_us": end, "actual_core_end_us": self.engine.time_us,
                "life": self.engine.life, "death_us": dead_at, "seconds": seconds,
                "region1": sum(r["region"] for r in self.rows) / len(self.rows),
                "travel_distance": distance, "samples": len(self.rows),
                "initial_core_hash": StateImage.from_dict(self.origin["core"]).digest,
                "final_core_hash": StateImage.from_dict(final["core"]).digest,
                "initial_whole_hash": digest(self.origin), "final_whole_hash": digest(final),
                "ancestry": self.ancestry, "wall_seconds": time.monotonic() - wall}


def execute(folder, key, seed, *, whole=None, parent=None, position=None, blank_control=False,
            seconds=60, mode="normal", backend="native", guard=None):
    folder = Path(folder)
    if (folder / "result.json").exists():
        return read(folder / "result.json"), read(folder / "final.json.gz")
    if folder.exists():
        raise RuntimeError("incomplete original is retained, never rerun silently: " + str(folder))
    folder.mkdir(parents=True)
    obj = Ring(key, seed, whole=whole, parent=parent, position=position,
               blank_control=blank_control, backend=backend)
    save(folder / "initial.json.gz", obj.origin)
    save(folder / "ancestry.json", obj.ancestry)
    try:
        result = obj.run(seconds, mode=mode, guard=guard)
    except BaseException:
        save(folder / "interrupted.json.gz", obj.snapshot())
        save(folder / "interrupted-trace.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
        raise
    final = obj.snapshot()
    save(folder / "final.json.gz", final)
    assert read(folder / "final.json.gz") == final
    save(folder / "trajectory.json.gz", {"rows": obj.rows, "events": obj.events, "inputs": obj.inputs})
    save(folder / "result.json", result)
    return result, final
