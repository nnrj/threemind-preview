"""Public-runtime calibration. New independent project; old states are read-only."""

import argparse
import bisect
import gzip
import hashlib
import json
import sys
from dataclasses import asdict

from common import HERE, ROOT, WORK, Case, Study, encoded, load_case, new_json, prepare, read_json

OLD = HERE.parent / "2026-09-29-input-rate-and-autonomy"
sys.path.append(str(OLD))
from calibrate import background
from world import SPEC, SUPPLY, Body, motor

from threemind_core import StateImage
from threemind_runtime.adapters import channel_id
from threemind_runtime.energy_supply import EnergySupplier

SEEDS = (9293201, 9293202)
OLD_KERNEL = "threemind.continuous-memory/1"
NEW_KERNEL = "threemind.continuous-memory/2"
AGES = (1, 10, 30, 100, 300)
FORGETTING = {
    "normal": {},
    "weight_off": {"forgetting_rate": 0.0},
    "slow_off": {"forgetting_rate": 0.0, "stability_decay_enabled": False, "support_decay_enabled": False},
}


def symbols(seed):
    return {c: channel_id(seed, SPEC["sensory_namespace"], i) for c, i in zip("ABCD", (0, 1, 4, 5))}


def done(study, key):
    key = "execution2/" + key
    path = WORK / "cases" / key / "result.json"
    if path.exists():
        value = load_case(study, key)
        if value["extra"].get("budget_stop"):
            raise RuntimeError("interrupted case requires a separately named retry")
        return value
    return None


def external(folder):
    value = read_json(folder / "result.json")
    image = StateImage(gzip.decompress((folder / "parent-state.json.gz").read_bytes()))
    if image.digest != value["state_sha256"]:
        raise RuntimeError("historical parent hash mismatch")
    return value | {"image": image, "external_project": "read-only historical parent"}


def old_memory(seed, protocol):
    return external(ROOT / f".work/experience-autonomy-20260929/cases/memory/s{seed}/{protocol}/train")


def warm(seed):
    return external(ROOT / f".work/internal-activity-20260929/cases/warm/s{seed}/region0")


def gzwrite(path, value):
    with gzip.open(path, "xb") as f:
        f.write(encoded(value))


class Trial(Case):
    def __init__(self, study, key, seed, *, parent=None, config=None, kernel=OLD_KERNEL, observe=False, bg=True):
        self.bg = bg
        super().__init__(
            study,
            "execution2/" + key,
            parent["kernel"] if parent else kernel,
            seed,
            parent=parent,
            config=config,
            observe=observe,
        )
        self.bg_cursor = bisect.bisect_right(background(seed)[1], self.engine.time_us)
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
        self.guard()
        if self.bg:
            frames, times, sha = background(self.seed)
            if target > times[-1]:
                raise RuntimeError("registered telemetry coverage exhausted")
            stop = bisect.bisect_right(times, target)
            for stim, index, cycle in frames[self.bg_cursor : stop]:
                self.send_stimulus(
                    stim,
                    source="host-telemetry",
                    adapter="host-telemetry",
                    payload={"recording_sha256": sha, "sample": index, "cycle": cycle, "frames": [stim.to_dict()]},
                )
            self.bg_cursor = stop
        while True:
            self.supply.prepare(self.engine)
            end = min(target, self.supply.deadline) if self.supply.deadline is not None else target
            self.session.advance_to(end, guard=self.guard)
            if self.engine.life == "dead" or self.engine.time_us >= target:
                break

    def advance(self, target, **kwargs):
        while self.engine.time_us < target and self.engine.life != "dead":
            self.step(min(target, self.engine.time_us + 100_000))
            self.sample()
        return self.engine.life != "dead"


def finish(c, extra):
    state = c.engine.capture_state().to_dict()
    if state["energy"]["unserved_total"] > 1e-10:
        raise RuntimeError("external supply failed to cover demand")
    return c.finish(extra | {"supply": c.supply.capture(), "energy": state["energy"]})


def probe(study, key, parent, cue=0.5, channels=None, **meta):
    if saved := done(study, key):
        return saved
    seed = parent["seed"]
    c = Trial(study, key, seed, parent=parent, observe=True)
    start = c.engine.time_us
    initial = c.engine.capture_state()
    channels = channels or [symbols(seed)["A"]]
    if cue:
        c.send(channels, cue, source="manual-probe")
    c.step(start)
    rows, body = [], Body(0.3125)
    for elapsed in range(0, 5_000_000, 100_000):
        nodes = c.engine.observation_nodes()
        control = motor(seed, nodes)
        rows.append({"relative_us": elapsed, "nodes": nodes, "control": control, "body": asdict(body)})
        body.move(control, 0.1)
        c.advance(start + elapsed + 100_000)
    gzwrite(c.folder / "response.json.gz", {"rows": rows, "final_body": asdict(body)})
    return finish(
        c,
        {
            "stage": "probe",
            "begin_us": start,
            "initial_hash": initial.digest,
            "cue_intensity": cue,
            "probe_channels": channels,
            "parent": parent["id"],
            **meta,
        },
    )


def age(study, key, parent, seconds, changes=None, **meta):
    if saved := done(study, key):
        return saved
    c = Trial(study, key, parent["seed"], parent=parent, config=changes)
    target = parent["extra"]["last_training_us"] + seconds * 1_000_000
    if target < c.engine.time_us:
        raise RuntimeError("age cannot precede saved parent")
    c.advance(target)
    return finish(
        c,
        {
            "stage": "retention",
            "age_s": seconds,
            "last_training_us": parent["extra"]["last_training_us"],
            "parent": parent["id"],
            **meta,
        },
    )


def schedule(protocol):
    if protocol == "none":
        return []
    if protocol.startswith("single"):
        return [(128, float(protocol.split("_")[1]))]
    times = range(119, 129) if protocol == "massed" else (0, 1, 2, 4, 8, 16, 32, 64, 96, 128)
    return [(t, 0.4) for t in times]


def intensity(study):
    protocols = ("none", "single_0.4", "single_1", "single_1.5", "single_2", "single_4", "massed", "spaced")
    for seed in SEEDS:
        for gain in (0.0, 0.075):
            for protocol in protocols:
                key = f"intensity/s{seed}/g{gain}/{protocol}"
                trained = done(study, key + "/train")
                if not trained:
                    c = Trial(study, key + "/train", seed, parent=warm(seed), config={"intensity_gain": gain})
                    begin = c.engine.time_us
                    deliveries = []
                    for t, dose in schedule(protocol):
                        c.advance(begin + t * 1_000_000)
                        before = c.engine.capture_state().to_dict()
                        envelope = c.send([symbols(seed)[s] for s in "AD"], dose, source="controlled-experience")
                        c.step(c.engine.time_us)
                        after = c.engine.capture_state().to_dict()
                        deliveries.append(
                            {
                                "envelope": envelope,
                                "raw_intensity": dose,
                                "before_transport": before["transport"],
                                "after_transport": after["transport"],
                                "before_energy": before["energy"],
                                "after_energy": after["energy"],
                                "before_nodes": before["nodes"],
                                "after_nodes": after["nodes"],
                                "before_edges": before["edges"],
                                "after_edges": after["edges"],
                            }
                        )
                    c.advance(begin + 129_000_000)
                    gzwrite(c.folder / "direct-effects.json.gz", deliveries)
                    trained = finish(
                        c,
                        {
                            "stage": "training",
                            "family": "intensity",
                            "protocol": protocol,
                            "gain": gain,
                            "last_training_us": begin + 128_000_000,
                            "schedule": schedule(protocol),
                        },
                    )
                for seconds in (1, 30, 300):
                    parent = trained if seconds == 1 else age(study, key + f"/age{seconds}", trained, seconds)
                    for cue in (0, 0.5):
                        probe(
                            study,
                            key + f"/probe{seconds}/cue{cue}",
                            parent,
                            cue,
                            family="intensity",
                            protocol=protocol,
                            gain=gain,
                            age_s=seconds,
                        )
                print(json.dumps({"stage": "intensity", "seed": seed, "gain": gain, "protocol": protocol}), flush=True)


def forgetting(study):
    for seed in SEEDS:
        for protocol in ("none", "spaced_ordinary"):
            trained = old_memory(seed, protocol)
            for condition, changes in FORGETTING.items():
                key = f"forgetting/s{seed}/{protocol}/{condition}"
                for seconds in AGES:
                    parent = age(
                        study,
                        key + f"/age{seconds}",
                        trained,
                        seconds,
                        changes,
                        family="forgetting",
                        condition=condition,
                        protocol=protocol,
                    )
                    for cue in (0, 0.5, 1.0):
                        probe(
                            study,
                            key + f"/probe{seconds}/cue{cue}",
                            parent,
                            cue,
                            family="forgetting",
                            condition=condition,
                            protocol=protocol,
                            age_s=seconds,
                        )
                print(
                    json.dumps({"stage": "forgetting", "seed": seed, "protocol": protocol, "condition": condition}),
                    flush=True,
                )


def adaptation(study):
    for seed in SEEDS:
        trained = old_memory(seed, "spaced_ordinary")
        for condition, changes in FORGETTING.items():
            parent = age(study, f"adaptation/s{seed}/{condition}/age300", trained, 300, changes)
            for stage, pair in enumerate(("AB", "AD"), 1):
                key = f"adaptation/s{seed}/{condition}/stage{stage}"
                saved = done(study, key)
                if not saved:
                    c = Trial(study, key, seed, parent=parent)
                    for _ in range(10):
                        c.send([symbols(seed)[s] for s in pair], 0.4, source="reversal-training")
                        c.step(c.engine.time_us)
                        c.advance(c.engine.time_us + 1_000_000)
                    saved = finish(
                        c,
                        {
                            "stage": "adaptation-training",
                            "family": "adaptation",
                            "pair": pair,
                            "condition": condition,
                            "phase": stage,
                            "last_training_us": c.engine.time_us - 1_000_000,
                        },
                    )
                parent = saved
                for cue in (0, 0.5):
                    probe(study, key + f"/cue{cue}", parent, cue, family="adaptation", condition=condition, phase=stage)


def novelty(study):
    for seed in SEEDS:
        channels = [channel_id(seed, "novelty-calibration/1", i) for i in range(4)]
        for dose in (0.2, 0.4, 0.8):
            for phase in (70_000, 110_000, 170_000):
                for mode in ("immediate", "arrival-window"):
                    for gain in (0.0, 0.018):
                        key = f"novelty/s{seed}/i{dose}/p{phase}/{mode}/g{gain}"
                        trained = done(study, key + "/train")
                        if not trained:
                            c = Trial(
                                study,
                                key + "/train",
                                seed,
                                kernel=NEW_KERNEL,
                                config={
                                    "novelty_mode": mode,
                                    "local_novelty_gain": gain,
                                    "energy_simulation_enabled": True,
                                    "stp_facilitation_tau_s": 1.0,
                                },
                            )
                            c.send(channels[:2], dose, source="familiar-pattern")
                            c.step(0)
                            c.advance(phase)
                            c.send([channels[0], channels[2]], dose, source="new-overlapping-pattern")
                            c.step(phase)
                            c.advance(phase + 300_000)
                            gzwrite(c.folder / "first-window.json.gz", c.engine.capture_state().to_dict())
                            # Similar and distinct stimuli after the frozen birth window; no handcrafted state.
                            for _ in range(5):
                                c.send([channels[0], channels[2]], dose, source="repeat-pattern")
                                c.step(c.engine.time_us)
                                c.advance(c.engine.time_us + 1_000_000)
                            trained = finish(
                                c,
                                {
                                    "family": "novelty",
                                    "mode": mode,
                                    "gain": gain,
                                    "dose": dose,
                                    "phase_us": phase,
                                    "channels": channels,
                                    "last_training_us": c.engine.time_us - 1_000_000,
                                },
                            )
                        probe(
                            study,
                            key + "/probe",
                            trained,
                            0.5,
                            [channels[0]],
                            family="novelty",
                            mode=mode,
                            gain=gain,
                            dose=dose,
                            phase_us=phase,
                            pattern_channels=channels,
                        )
            print(json.dumps({"stage": "novelty", "seed": seed, "dose": dose}), flush=True)


def register():
    prepare()
    sources = list(HERE.glob("*.py")) + list(HERE.glob("design.*.md")) + [OLD / n for n in ("calibrate.py", "world.py")]
    hashes = {}
    for path in sources:
        raw = path.read_bytes()
        dest = WORK / "frozen-tools" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
    new_json(
        WORK / "registration.json",
        {
            "files": hashes,
            "seeds": SEEDS,
            "ages": AGES,
            "expected_cases": 714,
            "background_sha256": background(SEEDS[0])[2],
            "normal_inhibition_and_forgetting_preserved": True,
            "novelty_default_not_selected_yet": True,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "intensity", "forgetting", "novelty", "adaptation"))
    args = parser.parse_args()
    if args.command == "register":
        return register()
    study = Study()
    try:
        globals()[args.command](study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
