"""Run a mutable model in an explicit world without a Lab server or PostgreSQL."""

from __future__ import annotations

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path

from .codec import ArtifactCodec
from .host import Runtime, create_engine
from .profile import profile_from_spec
from .source_policies import SourcePolicies
from .store import SQLiteStore
from .world import PhysicalWorld
from .world_schema import default_world, parse_world


def main():
    parser = argparse.ArgumentParser(description="Independent ThreeMind physical-world adapter (no Lab database)")
    parser.add_argument("--world", type=Path, help="Versioned threemind.world/1 JSON protocol")
    parser.add_argument("--write-example", type=Path, help="Explicitly create a starting world protocol and exit")
    parser.add_argument(
        "--template", choices=("inertial-cart", "gravity-pendulum"), help="Physical example for --write-example"
    )
    parser.add_argument("--model", type=Path, help="Optional .tmind or JSON brain model; remains unchanged")
    parser.add_argument("--export", type=Path, help="Explicit final brain model export, separate from world state")
    parser.add_argument("--evidence", type=Path, help="Explicit JSONL stimulus and motor/physical evidence sink")
    parser.add_argument("--store", type=Path, help="Optional local SQLite for atomic brain and world recovery")
    parser.add_argument("--instance", default="world")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--environment-seed", type=int)
    parser.add_argument("--until-us", type=int, default=1000000)
    parser.add_argument("--backend", choices=["native", "reference"], default="native")
    parser.add_argument("--clock", choices=["realtime", "scaled", "unbounded"], default="realtime")
    parser.add_argument("--speed", type=float, default=1)
    args = parser.parse_args()
    if args.write_example:
        from .world_templates import physical_templates

        with args.write_example.open("x", encoding="utf-8") as stream:
            example = physical_templates()[args.template] if args.template else default_world()
            stream.write(example.model_dump_json(indent=2) + "\n")
        return
    if args.resume and (not args.store or args.model):
        parser.error("resume requires --store and cannot also load --model")
    store = SQLiteStore(args.store) if args.store else None
    context, image, profile, revision = None, None, None, 0
    if args.resume:
        revision, image, profile, context = store.load(args.instance, with_profile=True, with_context=True)
        if not context or context.get("schema") != "threemind.world-runtime/1":
            parser.error("stored instance is not a physical-world runtime")
        spec = parse_world(context["world_protocol"])
        if args.world and parse_world(args.world.read_bytes()).digest != spec.digest:
            parser.error("resume cannot replace the recorded world protocol")
        if args.environment_seed is not None and args.environment_seed != context["environment_seed"]:
            parser.error("resume cannot change the recorded environment seed")
        environment_seed = context["environment_seed"]
    else:
        if not args.world:
            parser.error("--world is required for a new physical runtime")
        spec = parse_world(args.world.read_bytes())
        environment_seed = args.environment_seed
        if args.model:
            image, profile = ArtifactCodec.decode(args.model.read_bytes(), with_profile=True)
    engine = create_engine(state=image, backend=args.backend)
    if args.until_us < engine.time_us:
        parser.error("until-us precedes the restored model time")
    profile = profile or profile_from_spec({"seed": engine.config.seed})
    policy = SourcePolicies(**profile.get("source_policies", {}))
    runtime = Runtime(engine, clock=args.clock, speed=args.speed)
    with ExitStack() as resources:
        evidence = resources.enter_context(args.evidence.open("x", encoding="utf-8")) if args.evidence else None
        world = resources.enter_context(
            PhysicalWorld(
                spec,
                profile["sensory_seed"],
                context["world_state"] if context else None,
                environment_seed=environment_seed,
            )
        )
        next_world = context["next_world_us"] if context else engine.time_us
        if next_world < engine.time_us or next_world > engine.time_us + world.period_us:
            parser.error("stored world delivery boundary does not match the model clock")
        if evidence:
            evidence.write(
                json.dumps(
                    {
                        "kind": "protocol",
                        "world": spec.model_dump(mode="json"),
                        "world_hash": spec.digest,
                        "environment_seed": environment_seed,
                        "sensory_seed": profile["sensory_seed"],
                        "start_us": str(engine.time_us),
                        "backend": args.backend,
                        "mujoco_version": world.mj.__version__,
                        "render_calibration": world.render_calibration,
                        "source_policy": policy.resolve("mujoco"),
                    }
                )
                + "\n"
            )
        last_saved = engine.time_us

        def save():
            nonlocal revision, last_saved
            revision = store.save(
                args.instance,
                engine.capture_state(),
                expected_revision=revision,
                profile=profile,
                context={
                    "schema": "threemind.world-runtime/1",
                    "world_protocol": spec.model_dump(mode="json"),
                    "world_state": world.capture(),
                    "next_world_us": next_world,
                    "environment_seed": environment_seed,
                },
            )
            last_saved = engine.time_us

        while engine.time_us < args.until_us and engine.life != "dead":
            if engine.time_us == next_world:
                raw = world.sample(engine.time_us, engine.activations())
                resolved = policy.resolve("mujoco")
                event = engine.inject(policy.frame(raw, "mujoco")) if resolved["enabled"] else None
                next_world = raw.time_us
                if evidence:
                    evidence.write(
                        json.dumps(
                            {
                                "kind": "physical_sample",
                                "raw_stimulus": raw.to_dict(),
                                "core_event_id": event,
                                "source_policy": resolved,
                                "observation": world.observation(),
                                **(
                                    {"stimulus_unit": world.stimulus_unit(raw, capture_us=world.elapsed_us)}
                                    if spec.schema_id == "threemind.world/2" and raw.channels
                                    else {}
                                ),
                            },
                            allow_nan=False,
                        )
                        + "\n"
                    )
            target = min(args.until_us, next_world, engine.time_us + 20000)
            if args.clock != "unbounded":
                while (time.monotonic_ns() - runtime.anchor_host) / 1e9 < (
                    target - runtime.anchor_sim
                ) / 1e6 / runtime.speed:
                    runtime.pace(target)
            engine.advance_to(target)
            if store and engine.time_us - last_saved >= 1000000:
                save()
        if store and (not args.resume or engine.time_us != last_saved):
            save()
        if args.export:
            with args.export.open("xb") as output:
                output.write(
                    ArtifactCodec.encode(
                        engine.capture_state(), "json" if args.export.suffix == ".json" else "tmind", profile=profile
                    )
                )
        print(
            json.dumps(
                {
                    "metrics": engine.metrics(),
                    "world_hash": spec.digest,
                    "physical_time_us": str(world.elapsed_us),
                    "next_delivery_us": str(next_world),
                    "revision": revision if store else None,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
