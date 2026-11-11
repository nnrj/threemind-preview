"""Vary existing local recovery, retaining consumption and refractory mechanisms."""

import gzip
import hashlib
import json

from calibrate import KERNELS, Trial, done, tokens
from common import HERE, WORK, Study, encoded, load_case, new_json
from world import SUPPLY

from threemind_runtime.energy_supply import EnergySupplier

TAUS = (0.8, 0.2, 0.08, 0.02)


class RecoveryTrial(Trial):
    def __init__(self, study, key, parent, tau):
        super().__init__(
            study,
            key,
            KERNELS["continuous"],
            parent["seed"],
            parent=parent,
            bg=False,
            config={"energy_simulation_enabled": True, "stp_recovery_tau_s": tau},
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
            stop = min(target, self.supply.deadline) if self.supply.deadline is not None else target
            super().step(stop)
            if self.engine.life == "dead" or self.engine.time_us >= target:
                break


def observe(study, parent, tau):
    teaching = "balanced" if parent["extra"]["balanced"] else "paired"
    key = f"recovery/{teaching}/tau{tau}"
    if saved := done(study, key):
        return saved
    c = RecoveryTrial(study, key, parent, tau)
    begin = c.engine.time_us
    task = set(tokens(c.seed).values())
    last_active = last_task = None
    with gzip.open(c.folder / "recovery.jsonl.gz", "xb") as f:
        while True:
            nodes = c.engine.observation_nodes()
            state = c.engine.capture_state().to_dict()
            row = {
                "relative_us": c.engine.time_us - begin,
                "life": c.engine.life,
                "nodes": nodes,
                "local_energy": state["operator_state"],
                "energy": state["energy"],
                "transport": state["transport"],
            }
            if any(n["activation"] > 0 for n in nodes):
                last_active = row["relative_us"]
            if any(n["activation"] > 0 and n["channel"] in task for n in nodes):
                last_task = row["relative_us"]
            f.write(encoded(row) + b"\n")
            if c.engine.life == "dead" or c.engine.time_us >= begin + 60_000_000:
                break
            c.advance(min(begin + 60_000_000, c.engine.time_us + 20000))
    return c.finish(
        {
            "kind": "recovery_speed",
            "teaching": teaching,
            "tau_s": tau,
            "last_sample_with_any_activation_us": last_active,
            "last_sample_with_task_activation_us": last_task,
            "end_relative_us": c.engine.time_us - begin,
            "energy": state["energy"],
            "end_task_activation": sum(n["activation"] for n in nodes if n["channel"] in task),
            "supply": c.supply.capture(),
        }
    )


def run(study):
    if not (WORK / "recovery-registration.json").exists():
        new_json(
            WORK / "recovery-registration.json",
            {
                "seed": 9293101,
                "taus_s": TAUS,
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("recovery.*")},
            },
        )
    results = []
    for teaching in ("paired", "balanced"):
        parent = load_case(study, f"activity-{teaching}/continuous/s9293101/i1000000/train")
        for tau in TAUS:
            result = observe(study, parent, tau)
            results.append({k: result[k] for k in ("id", "key", "life", "extra")})
            print(json.dumps(results[-1]), flush=True)
    new_json(WORK / "recovery-analysis.json", results)


if __name__ == "__main__":
    study = Study()
    try:
        run(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
