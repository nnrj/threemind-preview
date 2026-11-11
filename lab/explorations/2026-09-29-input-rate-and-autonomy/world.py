"""External ring physics and selection tooling; goals never enter the Core."""

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import asdict, dataclass

from calibrate import KERNELS, Trial, configuration, done
from common import HERE, WORK, Study, encoded, new_json

from threemind_core import Stimulus
from threemind_runtime.adapters import channel_id
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig

SEEDS = (9293201, 9293202)
STARTS = (0.125, 0.375, 0.625, 0.875)
SUPPLY = EnergySupplyConfig(enabled=True, rate_per_s=10, interval_us=100000, total_supply_limit=None)
SPEC = {
    "schema": "ring-study/1",
    "control_interval_us": 100000,
    "sensor_interval_us": 1000000,
    "mass": 1,
    "force_scale": 0.3,
    "drag": 0.8,
    "sensor_intensity": 0.8,
    "pattern_channels": 4,
    "projection_gain": 0.5,
    "velocity_scale": 0.375,
    "motor_namespace": "world-motor-v1:ring-study-v1:0",
    "sensory_namespace": "ring-sensory-v1",
}


@dataclass
class Body:
    x: float
    v: float = 0.0
    phase: float = 0.0

    @property
    def region(self):
        return int((self.x + self.phase) % 1 >= 0.5)

    def move(self, control, seconds):
        decay = math.exp(-SPEC["drag"] * seconds)
        terminal = SPEC["force_scale"] * control / SPEC["drag"]
        distance = terminal * seconds + (self.v - terminal) * (1 - decay) / SPEC["drag"]
        self.x = (self.x + distance) % 1
        self.v = terminal + (self.v - terminal) * decay
        return distance

    def sense(self, seed, at):
        channels = [(channel_id(seed, SPEC["sensory_namespace"], self.region * 4 + i), 1.0) for i in range(4)]
        if self.v:
            channels.append(
                (
                    channel_id(seed, SPEC["sensory_namespace"], 8 + int(self.v < 0)),
                    math.tanh(abs(self.v) / SPEC["velocity_scale"]),
                )
            )
        return Stimulus(at, tuple(channels), SPEC["sensor_intensity"])


def motor(seed, nodes):
    return math.tanh(
        SPEC["projection_gain"]
        * math.fsum(
            (1 if channel_id(seed, SPEC["motor_namespace"], int(n["id"])) & 1 else -1) * n["activation"]
            for n in sorted(nodes, key=lambda n: n["id"])
        )
    )


class WorldTrial(Trial):
    def __init__(self, study, key, seed, *, parent=None, inherited=True, config_override=None):
        super().__init__(
            study,
            key,
            KERNELS["continuous"],
            seed,
            parent=parent,
            config=config_override
            if parent
            else dict(configuration(KERNELS["continuous"]), energy_simulation_enabled=True, **(config_override or {})),
            inherited=bool(parent and inherited),
        )
        self.supply = EnergySupplier(SUPPLY, self.engine)

    def event(self, event, delivered):
        super().event(event, delivered)
        if event["kind"] == "energy":
            self.supply.delivered(event)
            self.events.append(
                {
                    "key": f"supply:{event['event_id']}",
                    "kind": "external_energy",
                    "time_us": event["time_us"],
                    "payload": event,
                }
            )

    def step(self, target):
        while True:
            self.supply.prepare(self.engine)
            deadline = self.supply.deadline
            stop = min(target, deadline) if deadline is not None else target
            super().step(stop)
            if self.engine.life == "dead" or self.engine.time_us >= target:
                break


def run_world(
    study,
    key,
    seed,
    position,
    *,
    parent=None,
    seconds=60,
    phase=0,
    controller="closed",
    playback=None,
    reversal_s=None,
    config_override=None,
):
    if saved := done(study, key):
        return saved
    c = WorldTrial(study, key, seed, parent=parent, config_override=config_override)
    body = Body(position, phase=phase)
    begin = c.engine.time_us
    rows, senses, elapsed, distance, phase_changed = [], [], 0, 0.0, False
    while elapsed < round(seconds * 1e6) and c.engine.life != "dead":
        if reversal_s is not None and not phase_changed and elapsed >= round(reversal_s * 1e6):
            body.phase = (body.phase + 0.5) % 1
            phase_changed = True
        if elapsed % SPEC["sensor_interval_us"] == 0:
            original = body.sense(seed, c.engine.time_us)
            stimulus = (
                Stimulus(
                    c.engine.time_us,
                    tuple(tuple(v) for v in playback["senses"][len(senses)]["channels"]),
                    playback["senses"][len(senses)]["intensity"],
                )
                if controller == "sensory-replay"
                else original
            )
            c.inputs.automatic(
                f"ring:{elapsed}",
                "ring-study",
                stimulus,
                configuration=SPEC,
                transduction={"body": asdict(body), "region": body.region, "controller": controller},
            )
            senses.append(stimulus.to_dict())
            c.step(c.engine.time_us)
        nodes = c.engine.observation_nodes()
        proposed = motor(seed, nodes)
        applied = (
            proposed
            if controller == "closed"
            else playback["rows"][len(rows)]["applied_control"]
            if controller == "motor-replay"
            else float(controller)
            if controller in ("-0.5", "0", "0.5")
            else 0.0
        )
        # Replay removes action feedback explicitly. The Core's proposed action remains recorded.
        rows.append(
            {
                "relative_us": elapsed,
                "body": asdict(body),
                "region": body.region,
                "proposed_control": proposed,
                "applied_control": applied,
                "nodes": nodes,
                "transport": c.engine.metrics()["transport"],
            }
        )
        delta = min(SPEC["control_interval_us"], round(seconds * 1e6) - elapsed)
        distance += abs(body.move(applied, delta / 1e6))
        c.advance(c.engine.time_us + delta)
        elapsed = c.engine.time_us - begin
    with gzip.open(c.folder / "world.json.gz", "xb") as f:
        f.write(
            encoded(
                {"spec": SPEC, "senses": senses, "rows": rows, "final_body": asdict(body), "supply": c.supply.capture()}
            )
        )
    energy = c.engine.capture_state().to_dict()["energy"]
    if energy["unserved_total"] > 1e-10:
        raise RuntimeError("registered plentiful supply failed to cover demand; do not call this unlimited supply")
    return c.finish(
        {
            "kind": "ring_world",
            "controller": controller,
            "intervention": config_override,
            "initial_position": position,
            "initial_phase": phase,
            "reversal_s": reversal_s,
            "parent": parent["id"] if parent else None,
            "seconds": elapsed / 1e6,
            "region1_fraction": sum(r["region"] for r in rows) / max(1, len(rows)),
            "mean_proposed_control": sum(r["proposed_control"] for r in rows) / max(1, len(rows)),
            "min_control": min((r["proposed_control"] for r in rows), default=0),
            "max_control": max((r["proposed_control"] for r in rows), default=0),
            "travel_distance": distance,
            "energy": energy,
            "supply": c.supply.capture(),
        }
    )


def preflight(study):
    if not (WORK / "world-registration.json").exists():
        new_json(
            WORK / "world-registration.json",
            {
                "seeds": SEEDS,
                "starts": STARTS,
                "spec": SPEC,
                "supply": asdict(SUPPLY),
                "config": dict(configuration(KERNELS["continuous"]), energy_simulation_enabled=True),
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("world.*")},
            },
        )
    rows = []
    for seed in SEEDS:
        for i, position in enumerate(STARTS):
            r = run_world(study, f"world/s{seed}/g0/c{i}", seed, position)
            rows.append({"key": r["key"], "id": r["id"], "extra": r["extra"]})
            print(json.dumps(rows[-1]), flush=True)
    positive = any(r["extra"]["max_control"] > 0.01 for r in rows)
    negative = any(r["extra"]["min_control"] < -0.01 for r in rows)
    fixed_bias = all(r["extra"]["region1_fraction"] > 0.85 for r in rows) or all(
        r["extra"]["region1_fraction"] < 0.15 for r in rows
    )
    new_json(
        WORK / "world-preflight.json",
        {
            "rows": rows,
            "both_directions": positive and negative,
            "extreme_uniform_bias": fixed_bias,
            "may_proceed": positive and negative and not fixed_bias,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight"])
    args = parser.parse_args()
    study = Study()
    try:
        preflight(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
