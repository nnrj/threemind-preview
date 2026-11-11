from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

from threemind_core import Stimulus

from .codec import ArtifactCodec
from .host import Runtime, create_engine
from .profile import profile_from_spec
from .readout_session import SESSION_VERSION, ReadoutSession
from .sensory import TextSensor, TextSensorConfig
from .source_policies import SourcePolicies
from .stimulus_presets import TEXT_INTENSITY_PRESETS, resolve_intensity
from .store import SQLiteStore


def main():
    parser = argparse.ArgumentParser(description="Independent ThreeMind Runtime (no Lab database required)")
    parser.add_argument("--model", type=Path)
    parser.add_argument(
        "--deployment-manifest", type=Path, help="Verify an exact model and acknowledged intervention declaration"
    )
    parser.add_argument(
        "--kernel", help="Scientific kernel identity (including memory/4); restoration uses saved identity"
    )
    parser.add_argument("--config", type=Path, help="Kernel-specific configuration JSON for a new consciousness")
    parser.add_argument("--definition", type=Path, help="Validated declarative definition for a new consciousness")
    parser.add_argument("--input", type=Path, help="Timestamped anonymous stimuli in JSONL")
    parser.add_argument("--stimulus-units", type=Path, help="Versioned external stimulus units in JSONL")
    parser.add_argument(
        "--text-preset", choices=tuple(TEXT_INTENSITY_PRESETS), help="Normal=1 or strong=4; explicit intensity wins"
    )
    parser.add_argument(
        "--text-input", type=Path, help="UTF-8 text carrier through the model's text sensor and CLI source policy"
    )
    parser.add_argument(
        "--text-intensity", type=float, help="Optional text stimulus intensity (0–100); default remains 1"
    )
    parser.add_argument("--modulation-input", type=Path, help="Explicit timestamped scalar input modulations in JSONL")
    parser.add_argument(
        "--energy-input", type=Path, help="Explicit external supplies in JSONL: time_us, amount, source"
    )
    parser.add_argument("--until-us", type=int, default=1000000)
    parser.add_argument("--backend", choices=["native", "reference"], default="native")
    parser.add_argument("--clock", choices=["realtime", "scaled", "unbounded"], default="realtime")
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--store", type=Path, help="Optional local SQLite recovery store")
    parser.add_argument("--instance", default="default")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--export", type=Path, help="Explicit final model export")
    parser.add_argument(
        "--readouts", type=Path, help="New JSONL readout evidence file; never overwrites an existing file"
    )
    parser.add_argument(
        "--readout-config",
        type=Path,
        help="Explicit structural_readout/temporal_readout/activity_readout configuration JSON",
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        help="Open a V2 observation window without injecting a stimulus; requires --readouts",
    )
    args = parser.parse_args()
    if args.text_preset and not args.text_input:
        parser.error("--text-preset requires --text-input")
    model_bytes = None
    if args.model:
        from .codec import MAX_ARTIFACT_BYTES

        try:
            with args.model.open("rb") as source:
                model_bytes = source.read(MAX_ARTIFACT_BYTES + 1)
            if len(model_bytes) > MAX_ARTIFACT_BYTES:
                parser.error("model exceeds the artifact budget")
        except OSError as exc:
            parser.error(str(exc))
    if args.deployment_manifest:
        if not args.model or args.resume:
            parser.error("--deployment-manifest requires --model, without --resume")
        from .deployment import verify

        try:
            verify(model_bytes, json.loads(args.deployment_manifest.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
    if args.text_intensity is not None:
        if not args.text_input:
            parser.error("--text-intensity requires --text-input")
        if not math.isfinite(args.text_intensity) or not 0 <= args.text_intensity <= 100:
            parser.error("text intensity must be a finite value from 0 to 100")
    if args.resume and (not args.store or args.model):
        parser.error("resume requires --store and cannot also load --model")
    if args.config and (args.resume or args.model):
        parser.error("--config applies to new consciousnesses; restoration uses the saved configuration")
    if args.definition and any((args.resume, args.model, args.config, args.kernel)):
        parser.error("--definition cannot be combined with --resume, --model, --config or --kernel")
    store = SQLiteStore(args.store) if args.store else None
    if args.resume:
        revision, state, profile, context = store.load(args.instance, with_profile=True, with_context=True)
        if context is not None and (context.get("schema") != SESSION_VERSION or not args.readouts):
            parser.error(
                "this instance has external recovery state; resume it through its owning adapter (e.g. threemind-world)"
            )
    else:
        revision = 0
        context = None
        state, profile = ArtifactCodec.decode(model_bytes, with_profile=True) if args.model else (None, None)
    try:
        if args.definition:
            from threemind_kernels.definition import MAX_DEFINITION_BYTES, KernelDefinition

            with args.definition.open("rb") as stream:
                definition = KernelDefinition.parse(stream.read(MAX_DEFINITION_BYTES + 1))
            engine = definition.create(backend=args.backend)
        else:
            config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
            engine = create_engine(config, state=state, backend=args.backend, kernel_id=args.kernel)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.text_input and profile is None:
        profile = profile_from_spec({"seed": engine.config.seed})
    policies = SourcePolicies(**(profile or {}).get("source_policies", {}))
    last_saved = state.digest if args.resume else None
    last_context = context
    if args.until_us < engine.time_us:
        parser.error("until-us precedes the restored model time")
    if (args.readout_config or args.observe) and not args.readouts:
        parser.error("--readout-config/--observe require --readouts")
    evidence = args.readouts.open("x", encoding="utf-8") if args.readouts else None

    def record(value):
        evidence.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        evidence.flush()

    session = (
        ReadoutSession(
            engine,
            record=record,
            policies=policies,
            state=context,
            config=(
                json.loads(args.readout_config.read_text(encoding="utf-8"))
                if args.readout_config
                else {
                    "activity_readout": {
                        "enabled": True,
                        "analysis_version": 2,
                        "interval_us": 20000,
                        "periodic_max_samples": 60,
                    }
                }
                if args.observe and not context
                else None
            ),
        )
        if evidence
        else None
    )
    if evidence:
        record(
            {
                "kind": "readout_manifest",
                "kernel_id": engine.capture_state().to_dict()["dynamics"],
                "schema": SESSION_VERSION,
                "source_hash": engine.capture_state().digest,
                "configuration": session.capture()["configuration"],
                "sensory_profile": profile,
                "until_us": str(args.until_us),
                "continuation": bool(context),
            }
        )
        if args.observe:
            session.begin_observation()
    if args.input:
        with args.input.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    stimulus = policies.frame(Stimulus.from_dict(json.loads(line)), "manual-anonymous")
                    if session:
                        session.schedule(
                            [{"stimulus": stimulus}], at=0, source="manual-anonymous", adapter_id="anonymous-frames"
                        )
                    else:
                        engine.inject(stimulus)
    if args.stimulus_units:
        from .stimulus_units import unit_frames

        with args.stimulus_units.open(encoding="utf-8") as stream:
            raw = []
            size = 0
            for line in stream:
                size += len(line.encode())
                if size > 4 * 1024 * 1024:
                    parser.error("stimulus unit carrier exceeds 4 MiB")
                if line.strip():
                    raw.append(json.loads(line))
        frames = list(unit_frames({"units": raw}))
        if session:
            session.schedule(frames, at=0, source="manual-anonymous", adapter_id="stimulus-units")
        else:
            for frame in frames:
                engine.inject(policies.frame(frame["stimulus"], "manual-anonymous"))
    if args.text_input:
        sensor = TextSensor(profile["sensory_seed"], TextSensorConfig(**profile["text_sensor"]))
        if not sensor.config.enabled:
            parser.error("the model text sensor is disabled")
        if not policies.resolve("manual-cli-text")["enabled"]:
            parser.error("the CLI text input source is disabled by this model's source policy")
        with args.text_input.open(encoding="utf-8") as stream:
            text = stream.read(sensor.config.max_carrier_characters + 1)
        if session:
            session.schedule(sensor.frames(text, resolve_intensity(args.text_intensity, args.text_preset)))
        else:
            for frame in sensor.frames(text, resolve_intensity(args.text_intensity, args.text_preset)):
                stimulus = frame["stimulus"]
                engine.inject(
                    policies.frame(replace(stimulus, time_us=engine.time_us + stimulus.time_us), "manual-cli-text")
                )
    if args.energy_input:
        from threemind_core.energy import supply_payload
        from threemind_core.spec import timestamp

        with args.energy_input.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    item = json.loads(line)
                    if not isinstance(item, dict) or set(item) != {"time_us", "amount", "source"}:
                        raise ValueError("invalid energy input record")
                    payload = supply_payload(item["amount"], item["source"])
                    engine.supply_energy(
                        payload["amount"], time_us=timestamp(item["time_us"]), source=payload["source"]
                    )
    runtime = Runtime(engine, clock=args.clock, speed=args.speed)
    if args.modulation_input:
        from threemind_core.spec import timestamp

        with args.modulation_input.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    item = json.loads(line)
                    if not isinstance(item, dict) or "time_us" not in item:
                        raise ValueError("modulation input requires a timestamped object")
                    engine.modulate_input(time_us=timestamp(item.pop("time_us")), **item)
    while engine.time_us < args.until_us and engine.life != "dead":
        target = min(args.until_us, engine.time_us + 20000)
        if args.clock != "unbounded":
            import time

            while (time.monotonic_ns() - runtime.anchor_host) / 1e9 < (
                target - runtime.anchor_sim
            ) / 1e6 / runtime.speed:
                runtime.pace(target)
        if session:
            session.advance_to(target)
        else:
            engine.advance_to(target)
        if store and (target % 1000000 == 0 or target == args.until_us):
            image = engine.capture_state()
            revision = store.save(
                args.instance,
                image,
                expected_revision=revision,
                profile=profile,
                context=session.capture() if session else None,
            )
            last_saved = image.digest
            last_context = session.capture() if session else None
    # A starvation deadline can end between host slices, before the requested end.
    if store:
        image = engine.capture_state()
        if image.digest != last_saved or (session.capture() if session else None) != last_context:
            revision = store.save(
                args.instance,
                image,
                expected_revision=revision,
                profile=profile,
                context=session.capture() if session else None,
            )
    if session:
        # A recovery store retains open windows for resumption. Without one the
        # finite CLI job records its actual cutoff rather than claiming convergence.
        if not store:
            session.host.close(engine.time_us, "run_ended")
        record(
            {
                "kind": "readout_session_end",
                "time_us": str(engine.time_us),
                "open_windows": len(session.host.temporal.windows),
                "open_activity_windows": len(session.host.activity.windows),
                "recoverable": bool(store),
            }
        )
        evidence.close()
    if args.export:
        if args.model and args.export.resolve() == args.model.resolve():
            parser.error("export must not overwrite the input model")
        with args.export.open("xb") as output:
            output.write(
                ArtifactCodec.encode(
                    engine.capture_state(), "json" if args.export.suffix == ".json" else "tmind", profile=profile
                )
            )
    print(json.dumps(engine.metrics(), ensure_ascii=False))


if __name__ == "__main__":
    main()
