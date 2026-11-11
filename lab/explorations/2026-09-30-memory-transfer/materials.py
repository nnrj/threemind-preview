"""Versioned physical recordings and declared external research transformations."""

import copy
import math
import random
from collections import defaultdict

from common import WORK, new_json, read_json

from threemind_runtime.adapters import channel_id
from threemind_runtime.stimulus_units import unit_frames
from threemind_runtime.world import PhysicalWorld
from threemind_runtime.world_schema import Force, Motor, parse_world
from threemind_runtime.world_templates import physical_templates

MODES = ("full", "no_imu", "dose_matched", "shuffled_imu")
SEEDS = (930101, 930102, 930103, 930104)
KERNEL = "threemind.continuous-memory/2"
PERIOD = 20_000
CLIP = 400_000
EPISODE = 600_000


def config(preset):
    return {} if preset == "ordinary" else {"stp_facilitation_tau_s": 1.0}


def identities(seed):
    mask = channel_id(seed, "world-port-v1:physical-world-v1", 0)
    return {
        **{name: ((4000 << 20) | i) ^ mask for i, name in enumerate(("A", "B", "C", "X", "Y", "keep"))},
        "position_positive": (2 << 20) ^ mask,
        "position_negative": ((2 << 20) | 1) ^ mask,
    }


def physical_clip(seed, sign, domain="original"):
    path = WORK / "materials" / f"pendulum-{seed}-{sign}-{domain}.json"
    if path.exists():
        return read_json(path)
    raw = physical_templates()["gravity-pendulum"].model_dump(mode="json")
    raw["joints"][0]["initial"] = sign * (0.45 if domain == "angle" else 0.7)
    if domain == "gravity":
        raw["physics"]["gravity"] = [0, 0, -6.0]
    spec = parse_world(raw)
    with PhysicalWorld(spec, seed) as world:
        initial = world.capture()
        units = []
        for t in range(0, CLIP, PERIOD):
            stimulus = world.sample(t)
            units.append(world.stimulus_unit(stimulus, capture_us=world.elapsed_us))
        result = {"spec": raw, "initial": initial, "final": world.capture(), "units": units}
    new_json(path, result)
    return result


def imu_channels(unit):
    return {
        e["channel"]
        for m in unit["measurements"]
        if m.get("kind") in ("accelerometer", "gyroscope")
        for e in m["encoded"]
    }


def dose(units):
    return math.fsum(u["intensity"] * e["value"] for u in units for e in u["elements"])


def channel_dose(units):
    result = defaultdict(float)
    for u in units:
        for e in u["elements"]:
            result[e["channel"]] += e["value"] * u["intensity"]
    return dict(result)


def transform(units, mode, seed):
    out = copy.deepcopy(units)
    original = dose(units)
    retained = math.fsum(
        e["value"] * u["intensity"] for u in units for e in u["elements"] if e["channel"] not in imu_channels(u)
    )
    ratio = retained / original if original else 1.0
    order = list(range(len(units)))
    random.Random(f"imu-shuffle-v1:{seed}").shuffle(order)
    for i, u in enumerate(out):
        own = imu_channels(units[i])
        if mode == "no_imu":
            u["elements"] = [e for e in u["elements"] if e["channel"] not in own]
        elif mode == "dose_matched":
            for e in u["elements"]:
                e["value"] *= ratio
        elif mode == "shuffled_imu":
            other = units[order[i]]
            ids = imu_channels(other)
            u["elements"] = [e for e in u["elements"] if e["channel"] not in own] + [
                copy.deepcopy(e) for e in other["elements"] if e["channel"] in ids
            ]
        elif mode != "full":
            raise ValueError("unknown sensory intervention")
        u["measurements"].append(
            {
                "research_intervention": mode,
                "physical_amplitude_ratio": ratio if mode == "dose_matched" else 1.0,
                "imu_original_sample": order[i] if mode == "shuffled_imu" else i,
            }
        )
        u["elements"].sort(key=lambda e: e["channel"])
    if mode == "dose_matched":
        assert math.isclose(dose(out), retained, rel_tol=1e-12, abs_tol=1e-12)
    if mode == "shuffled_imu":
        a, b = channel_dose(units), channel_dose(out)
        assert a.keys() == b.keys() and all(math.isclose(a[k], b[k], rel_tol=1e-12, abs_tol=1e-12) for k in a)
    return out


def frame(unit):
    return next(iter(unit_frames({"units": [unit]})))["stimulus"]


def cue_unit(at, channel, intensity):
    return {
        "schema_id": "threemind.stimulus-unit/1",
        "kind": "element",
        "time_us": str(at),
        "source": "controlled-experimental-marker",
        "mapping_version": "controlled-marker/1",
        "intensity": intensity,
        "elements": [{"channel": channel, "value": 1.0}],
    }


def cart_spec(force):
    raw = physical_templates()["inertial-cart"].model_dump(mode="json")
    raw["joints"][0].update(limits=[-2.0, 2.0], damping=0.2)
    raw["sensors"][2]["scale"] = 1.0
    raw["sensors"][3]["scale"] = 1.0
    raw["sensors"][0]["scale"] = 1.0
    raw["forces"] = [Force(id="wind", body_id="body", force=(force, 0, 0)).model_dump(mode="json")]
    raw["motors"] = [
        Motor(id="motor", port=0, joint_id="slide", control_limit=0.25, projection_gain=0.3).model_dump(mode="json")
    ]
    return parse_world(raw)
