"""Preregistered, bounded follow-ups to distinguish history and test-time learning."""

import argparse
import time

from common import WORK, Study, load_case, new_json
from run import Trial, done, flags, probe


def register():
    new_json(
        WORK / "extension-manifest.json",
        {
            "registered_at_epoch": time.time(),
            "maximum_additional_instances": 116,
            "rationale": [
                "After the registered 20 s settling, the previous prefix-dependent rank switch is absent.",
                "The first L-on retention block recalls paired targets at 30 and 300 s; separate stored history from test-time learning.",
            ],
            "history": {
                "bits": ["001", "101"],
                "swap": [False, True],
                "delay_s": [1, 3],
                "cues": ["AB", "DB"],
                "instances": 16,
                "other_flags": "F remains off to avoid changing utilization interpretation before short waits",
            },
            "readout": {
                "training_bits": ["001", "011", "101", "111"],
                "swap": [False, True],
                "balanced": [False, True],
                "delay_s": [30, 300],
                "cues": ["A", "D"],
                "instances": 96,
                "change": "L on during training and waiting; switch only immediately before the test via public reconfigure",
            },
            "diagnostic": {
                "bits": ["101", "111"],
                "swap": False,
                "gap_s": 1,
                "cues": ["AB", "DB"],
                "instances": 4,
                "change": "public observer stream only; final state must equal existing counterpart",
            },
            "unchanged": "Forgetfulness, inhibition, fast trace, context, mapping, background and all other parameters",
        },
    )


def history(s):
    for swap in (False, True):
        p = load_case(s, f"short/train-{int(swap)}")
        for bits in ("001", "101"):
            for delay in (1, 3):
                for cue in ("AB", "DB"):
                    probe(
                        s,
                        p,
                        f"history/s{int(swap)}/{bits}/d{delay}/{cue}",
                        cue,
                        delay=delay,
                        config=flags(bits),
                        scope="task",
                    )
        print(f"history swap={swap} complete", flush=True)


def readout(s):
    for swap in (False, True):
        for bits in ("001", "011", "101", "111"):
            for balanced in (False, True):
                curriculum = "balanced" if balanced else "paired"
                parent = load_case(s, f"retention/s{int(swap)}/{bits}/{curriculum}/train")
                for delay in (30, 300):
                    key = f"readout/s{int(swap)}/{bits}/{curriculum}/d{delay}"
                    waited = done(s, key + "/wait")
                    if not waited:
                        c = Trial(s, key + "/wait", parent=parent)
                        assert c.advance(c.engine.time_us + delay * 1_000_000)
                        waited = c.finish(parent["extra"] | {"kind": "readout_wait", "retention_delay_s": delay})
                    for cue in ("A", "D"):
                        probe(
                            s, waited, key + "/" + cue, cue, config={"edge_consolidation_enabled": False}, scope="task"
                        )
            s.guard(force=True)
            print(f"test-time L off: swap={swap} trained DFL={bits} complete", flush=True)


def diagnostic(s):
    checks = []
    for bits in ("101", "111"):
        parent = load_case(s, f"short/s0/{bits}/warm")
        for cue in ("AB", "DB"):
            case = probe(s, parent, f"diagnostic/{bits}/{cue}", cue, gap=1, scope="task", transmission_log=True)
            original = load_case(s, f"short/s0/{bits}/g1/{cue}")
            assert case["state_sha256"] == original["state_sha256"]
            checks.append({"key": case["key"], "state_equal": True, "events": case["extra"]["transmission_events"]})
    new_json(WORK / "observer-validation.json", checks)


def residual(s):
    from run import BITS

    for swap in (False, True):
        for bits in BITS:
            for balanced in (False, True):
                curriculum = "balanced" if balanced else "paired"
                parent = load_case(s, f"retention/s{int(swap)}/{bits}/{curriculum}/train")
                probe(s, parent, f"residual/s{int(swap)}/{bits}/{curriculum}", "none", delay=1, scope="task")
        print(f"no-cue residual controls swap={swap} complete", flush=True)


def sustain(s):
    variants = {
        "unchanged": {},
        "depletion-on": {"depletion_enabled": True},
        "facilitation-off": {"stp_facilitation_tau_s": 0.0},
        "both": {"depletion_enabled": True, "stp_facilitation_tau_s": 0.0},
        "consolidation-off": {"edge_consolidation_enabled": False},
    }
    for swap in (False, True):
        parent = load_case(s, f"readout/s{int(swap)}/011/paired/d300/wait")
        for name, config in variants.items():
            probe(s, parent, f"sustain/s{int(swap)}/{name}", "none", config=config, scope="task")
        print(f"persistent activity controls swap={swap} complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("register", "history", "readout", "diagnostic", "residual", "sustain"))
    args = parser.parse_args()
    if args.stage == "register":
        register()
    else:
        s = Study()
        try:
            s.guard(force=True)
            {
                "history": history,
                "readout": readout,
                "diagnostic": diagnostic,
                "residual": residual,
                "sustain": sustain,
            }[args.stage](s)
        finally:
            s.db.close()
