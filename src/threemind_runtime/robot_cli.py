"""Headless robot operations; exact continuation never needs Lab/PostgreSQL."""

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path

from .robot_assets import install, installed, profile, registry, task_for_asset
from .robot_session import RobotSession
from .robot_templates import robot_templates
from .store import SQLiteStore


class EvidenceBudgetReached(Exception):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assets = sub.add_parser("assets")
    assets.add_argument("operation", choices=("list", "install"))
    assets.add_argument("identity", nargs="?", choices=tuple(registry()["profiles"]))
    templates = sub.add_parser("template")
    templates.add_argument("identity", choices=tuple(robot_templates()) + tuple(registry()["profiles"]))
    templates.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--task", type=Path)
    run.add_argument("--store", type=Path)
    run.add_argument("--instance", default="robot")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--model", type=Path)
    run.add_argument("--backend", choices=("native", "reference"), default="native")
    run.add_argument("--seed", type=int)
    run.add_argument("--environment-seed", type=int)
    run.add_argument("--until-us", type=int, required=True)
    run.add_argument("--evidence", type=Path)
    run.add_argument("--export", type=Path)
    run.add_argument("--action", help="Explicit normalized joint action JSON; recorded as external intervention")
    run.add_argument("--wall-seconds", type=float, default=300)
    run.add_argument("--evidence-mib", type=int, default=256)
    args = parser.parse_args(argv)
    if args.command == "assets":
        if args.operation == "install":
            if not args.identity:
                parser.error("asset identity required")
            print(json.dumps(install(args.identity)))
        else:
            print(
                json.dumps(
                    {
                        i: {"sha256": profile(i)["sha256"], "installed": installed(i), "modes": profile(i)["modes"]}
                        for i in registry()["profiles"]
                    }
                )
            )
        return
    if args.command == "template":
        task = robot_templates().get(args.identity) or task_for_asset(args.identity)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(task.model_dump_json(indent=2))
        return
    from .codec import ArtifactCodec

    if args.wall_seconds <= 0 or args.evidence_mib < 1:
        parser.error("positive execution and evidence budgets required")
    if args.resume and (not args.store or args.model):
        parser.error("resume requires --store and cannot replace the brain")
    store = SQLiteStore(args.store) if args.store else None
    context, image, revision = None, None, 0
    if args.resume:
        revision, image, context = store.load(args.instance, with_context=True)
        if not context or context.get("schema") != "threemind.robot-runtime/1":
            parser.error("stored model belongs to another adapter")
        if (args.seed is not None and args.seed != context["seed"]) or (
            args.environment_seed is not None and args.environment_seed != context["environment_seed"]
        ):
            parser.error("resume cannot change saved mapping or environment seeds")
    if not args.task and not context:
        parser.error("new robot sessions require --task")
    task = json.loads(args.task.read_text(encoding="utf-8")) if args.task else context["protocol"]
    if args.model:
        image = ArtifactCodec.decode(args.model.read_bytes())
    action = json.loads(args.action) if args.action else None
    start = time.monotonic()
    stopped = None
    with ExitStack() as resources:
        stream = resources.enter_context(args.evidence.open("x", encoding="utf-8")) if args.evidence else None
        session = resources.enter_context(
            RobotSession(
                task,
                seed=args.seed if args.seed is not None else 20260724,
                environment_seed=args.environment_seed,
                backend=args.backend,
                image=image,
                context=context,
            )
        )

        def record(row):
            if stream:
                text = json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                if stream.tell() + len(text.encode("utf-8")) > args.evidence_mib * 1048576:
                    raise EvidenceBudgetReached("evidence budget reached")
                stream.write(text)

        record(
            {
                "kind": "protocol",
                "protocol": task,
                "context_schema": "threemind.robot-runtime/1",
                "seed": session.seed,
                "environment_seed": session.environment_seed,
                "kernel_id": session.kernel_id,
                "start_us": str(session.engine.time_us),
                "explicit_action": action,
                "mujoco_version": session.world.mj.__version__,
            }
        )
        try:
            while session.engine.time_us < args.until_us and session.engine.life != "dead":
                if time.monotonic() - start >= args.wall_seconds:
                    stopped = "wall_budget"
                    break
                session.advance(min(args.until_us, session.engine.time_us + 10000), record=record, action=action)
                if getattr(session.world, "terminated", False) and session.engine.time_us >= session.next_world_us:
                    stopped = "official_episode_ended"
                    break
        except EvidenceBudgetReached as error:
            stopped = str(error)
        if store:
            revision = store.save(
                args.instance,
                session.engine.capture_state(),
                expected_revision=revision,
                profile=session.profile,
                context=session.context(),
            )
        if args.export:
            with args.export.open("xb") as destination:
                destination.write(
                    ArtifactCodec.encode(session.engine.capture_state(), "tmind", profile=session.profile)
                )
        print(
            json.dumps(
                {
                    "metrics": session.engine.metrics() | session.world.task_metrics(),
                    "revision": revision,
                    "stopped": stopped,
                    "state_hash": session.engine.capture_state().digest,
                    "task_hash": session.world.task.digest,
                }
            )
        )


if __name__ == "__main__":
    main()
