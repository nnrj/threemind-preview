"""Optional Lab instrumentation on a REFERENCE CLONE, never on a deployed Core.

Delegates every operation to the original method, and verifies the final hash
against an uninstrumented clone. Private method access stays in research tools.
"""

from __future__ import annotations

from threemind_runtime import create_engine


def diagnose(state, stimuli, until_us, *, max_records=100000):
    engine = create_engine(state=state, backend="reference")
    reference = create_engine(state=state, backend="reference")
    core = getattr(engine, "_engine", engine)
    if not all(hasattr(core, name) for name in ("_touch", "_stimulate", "_associate", "transport")):
        raise ValueError("diagnostics require the causal or continuous family, not a different dynamical model")
    rows, current = [], {}

    def record(value):
        if len(rows) >= max_records:
            raise ValueError("diagnostic record budget exhausted; original model remains unchanged")
        rows.append({"time_us": str(core.time_us), **value})

    original_touch, original_stimulate, original_associate = core._touch, core._stimulate, core._associate

    def touch(node_id, value, *, direct):
        before = dict(core.transport)
        result = original_touch(node_id, value, direct=direct)
        record(
            {
                "kind": "touch",
                "node": node_id,
                "direct": direct,
                "request": value,
                "received": core.transport["received"] - before["received"],
                "touch": result,
                "activation_increment": core.transport["activated"] - before["activated"],
            }
        )
        return result

    def stimulate(stimulus):
        current["stimulus"] = stimulus
        record({"kind": "input", "stimulus": stimulus.to_dict()})
        try:
            return original_stimulate(stimulus)
        finally:
            current.clear()

    def associate(touched):
        stimulus = current.get("stimulus")
        if stimulus is not None:
            channels = dict(stimulus.channels)
            cfg = core.config
            for node_id, amount, impulse in touched:
                n = core.nodes[node_id]
                drive = channels[n.channel] * stimulus.intensity
                request = min(1.0, drive * cfg.direct_gain)
                response = core._inhibitory_response(n)
                fraction = amount / (request * response) if request * response > 0 else 0.0
                factor = drive * fraction * n.local_plasticity
                record(
                    {
                        "kind": "consolidation",
                        "node": node_id,
                        "mapped_drive": drive,
                        "local_plasticity": n.local_plasticity,
                        "first": factor * cfg.first_gain * (n.touches == 0),
                        "repeat": factor * cfg.repeat_gain,
                        "extra_intensity": factor * cfg.intensity_gain * max(0, stimulus.intensity - 1),
                        "capped_impulse": impulse,
                    }
                )
        return original_associate(touched)

    core._touch, core._stimulate, core._associate = touch, stimulate, associate
    for stimulus in stimuli:
        engine.inject(stimulus)
        reference.inject(stimulus)
    engine.advance_to(until_us)
    reference.advance_to(until_us)
    assert engine.capture_state().digest == reference.capture_state().digest, "diagnostic changed state"
    return {
        "schema": "threemind.input-diagnostics/1",
        "source_digest": state.digest,
        "result_digest": reference.capture_state().digest,
        "hash_verified": True,
        "records": rows,
        "novelty": dict(getattr(core, "novelty_audit", {})),
        "novelty_reasons": {
            "ineligible": "no existing neighborhood",
            "disabled": "mechanism disabled",
            "no_reentry": "no associative arrival within the window",
            "reference_reached": "reentry reached reference",
            "awarded": "local arrival conditions met",
            "cancelled": "connection removed before settlement",
        },
        "transport": dict(core.transport),
        "metrics": engine.metrics(),
    }


def main():
    import argparse
    import json
    from pathlib import Path

    from threemind_runtime.codec import ArtifactCodec
    from threemind_runtime.stimulus_units import unit_frames

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--stimulus-units", type=Path, required=True)
    parser.add_argument("--until-us", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.model.stat().st_size > 32 * 1024 * 1024 or args.stimulus_units.stat().st_size > 4 * 1024 * 1024:
        parser.error("diagnostic input budget exceeded (model 32 MiB, stimulus units 4 MiB)")
    state = ArtifactCodec.decode(args.model.read_bytes())
    if len(state.to_dict()["nodes"]) > 300 or len(state.to_dict()["edges"]) > 5000:
        parser.error("diagnostic clone exceeds 300 nodes or 5000 edges")
    if not int(state.to_dict()["time_us"]) <= args.until_us <= int(state.to_dict()["time_us"]) + 1000000:
        parser.error("diagnostic horizon must be within one simulated second of the checkpoint")
    with args.stimulus_units.open(encoding="utf-8") as stream:
        units = [json.loads(line) for line in stream if line.strip()]
    report = diagnose(state, [f["stimulus"] for f in unit_frames({"units": units})], args.until_us)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, allow_nan=False)


if __name__ == "__main__":
    main()
