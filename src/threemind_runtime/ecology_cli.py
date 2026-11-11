"""Independent ecological training with explicit model import and population recovery."""

import argparse
import json
import math
import time
from contextlib import ExitStack
from pathlib import Path

from .codec import ArtifactCodec
from .ecology_job import EcologyJob, parse_job
from .population_bundle import PopulationBundle, export_bundle
from .population_participant import ParticipantConfig
from .population_store import PopulationStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, help="Portable threemind.ecology-job/1 JSON")
    parser.add_argument("--write-example", type=Path, help="Create a complete default protocol and exit")
    parser.add_argument("--founder", type=Path, help="Explicit new births from a .tmind/JSON founder brain")
    parser.add_argument("--store", type=Path, help="Optional local SQLite population recovery and raw evidence")
    parser.add_argument("--instance", default="ecology")
    parser.add_argument("--resume", action="store_true", help="Continue the complete group in --store")
    parser.add_argument("--bundle", type=Path, help="Continue a complete portable population bundle")
    parser.add_argument("--export", type=Path, help="Explicit final portable population bundle")
    parser.add_argument("--evidence", type=Path, help="Explicit JSONL observation sink for this invocation")
    parser.add_argument("--until-us", type=int, default=1000000, help="Absolute global simulation time")
    parser.add_argument("--checkpoint-us", type=int, default=1000000)
    parser.add_argument("--backend", choices=["native", "reference"], default="native")
    parser.add_argument("--clock", choices=["realtime", "scaled", "unbounded"], default="realtime")
    parser.add_argument("--speed", type=float, default=1)
    args = parser.parse_args()
    if args.write_example:
        from threemind_kernels.registry import DEFAULT_KERNEL

        job = EcologyJob(kernel_id=DEFAULT_KERNEL)
        if args.founder:
            image, profile = ArtifactCodec.decode(args.founder.read_bytes(), with_profile=True)
            if profile is not None:
                value = job.model_dump(mode="json")
                value["sensory_seed"] = profile["sensory_seed"]
                value["runtime_profile"] = profile
                value["participant"].update(
                    {key: profile[key] for key in ParticipantConfig.model_fields if key in profile}
                )
                job = parse_job(value)
        if args.founder and args.founder.resolve() == args.write_example.resolve():
            parser.error("example protocol must not overwrite the founder model")
        with args.write_example.open("x", encoding="utf-8") as stream:
            stream.write(job.model_dump_json(indent=2) + "\n")
        return
    if args.resume and (not args.store or args.founder or args.bundle):
        parser.error("--resume requires --store and cannot replace the population with a founder or bundle")
    if args.bundle and args.founder:
        parser.error("--bundle continues an existing population; --founder creates new individuals")
    if not 0 <= args.until_us <= 10**15 or args.checkpoint_us < 1 or not math.isfinite(args.speed) or args.speed <= 0:
        parser.error("invalid simulation time, checkpoint cadence or clock speed")
    # Resolve aliases before creating outputs; scientific inputs and recovery
    # databases must never be opened as the evidence/export destination.
    paths = [
        value.resolve()
        for value in (args.protocol, args.founder, args.store, args.bundle, args.export, args.evidence)
        if value
    ]
    if len(set(paths)) != len(paths):
        parser.error("protocol, model, store, bundle, evidence and export paths must be distinct")
    for destination in (args.export, args.evidence):
        if destination and destination.exists():
            parser.error(f"output already exists: {destination}")
    with ExitStack() as resources:
        store = PopulationStore(args.store) if args.store else None
        checkpoint, founders, revision = None, None, 0
        if args.resume:
            revision, job, checkpoint = store.load(args.instance)
        elif args.bundle:
            bundle = resources.enter_context(PopulationBundle(args.bundle))
            job, checkpoint = bundle.protocol, bundle.checkpoint
        else:
            if not args.protocol:
                parser.error("a new ecological population requires --protocol")
            job = parse_job(args.protocol.read_bytes())
            if args.founder:
                image, profile = ArtifactCodec.decode(args.founder.read_bytes(), with_profile=True)
                if profile is not None and profile["sensory_seed"] != job.sensory_seed:
                    parser.error("the founder's learned sensory seed differs from the declared population wiring")
                if profile is not None and profile != job.profile:
                    parser.error(
                        "the founder's sensory profile must be preserved; generate its protocol with --write-example PATH --founder MODEL, then configure the environment"
                    )
                founders = [image]
        if args.protocol and parse_job(args.protocol.read_bytes()).digest != job.digest:
            parser.error("exact continuation cannot replace the frozen population protocol")
        if job.participant.trace and store is None:
            parser.error("complete numerical-boundary recording requires --store")
        initial = checkpoint[0]["time_us"] if checkpoint is not None else 0
        if args.until_us < initial:
            parser.error("until-us precedes the restored global population time")
        evidence = resources.enter_context(args.evidence.open("x", encoding="utf-8")) if args.evidence else None
        if evidence:
            evidence.write(
                json.dumps(
                    {
                        "kind": "invocation",
                        "protocol": job.model_dump(mode="json"),
                        "start_us": initial,
                        "backend": args.backend,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        events, buffered_bytes = [], 0

        def record(event):
            nonlocal buffered_bytes
            raw = json.dumps(event, ensure_ascii=False, allow_nan=False)
            if evidence:
                evidence.write(raw + "\n")
            if store:
                events.append(event)
                buffered_bytes += len(raw.encode())

        runtime = resources.enter_context(
            job.open(
                backend=args.backend,
                founders=founders,
                checkpoint=checkpoint,
                record=lambda event: record({"scope": "ecology", **event}),
                participant_record=lambda identity, event: record(
                    {"scope": "individual", "individual": identity, "individual_time_us": event["time_us"], **event}
                ),
            )
        )
        last_saved = runtime.time_us

        def save():
            nonlocal revision, last_saved, buffered_bytes
            saved = runtime.checkpoint()
            revision = store.save(args.instance, job, saved, expected_revision=revision, events=events)
            events.clear()
            buffered_bytes = 0
            last_saved = runtime.time_us
            for identity, agent in runtime.participants.items():
                if not agent.body_enabled and agent.engine.life == "dead" and agent.dead_recorded:
                    agent.archive_engine(store.reference(saved[1][identity].digest))
                agent.readouts.bytes = 0

        if store and not args.resume:
            save()  # Untouched founder/offspring state is durable before any new experience.
        anchor, initial = time.monotonic(), runtime.time_us
        speed = args.speed if args.clock == "scaled" else 1
        while runtime.time_us < args.until_us:
            target = min(
                args.until_us,
                runtime.pending_end_us or runtime.time_us + job.world.physics.sample_us,
                last_saved + args.checkpoint_us if store else args.until_us,
            )
            if job.participant.trace:
                for identity, agent in runtime.participants.items():
                    if agent.engine.life != "dead":
                        boundary = (
                            agent.engine.time_us // agent.engine.config.step_us + 1
                        ) * agent.engine.config.step_us
                        target = min(target, runtime.ledger.accounts[identity].birth_us + boundary)
            if args.clock != "unbounded":
                while True:
                    delay = (target - initial) / 1e6 / speed - (time.monotonic() - anchor)
                    if delay <= 0:
                        break
                    time.sleep(min(0.05, delay))
            before = len(runtime.participants)
            runtime.advance_to(target)
            if store and (
                job.participant.trace
                or len(runtime.participants) != before
                or target - last_saved >= args.checkpoint_us
                or buffered_bytes >= 8 * 1024**2
            ):
                save()
        if store and (runtime.time_us != last_saved or events):
            save()
        # Stopping the host is a resumable boundary; it is not biological death
        # and does not force-close passive readout windows.
        if args.export:
            export_bundle(args.export, job, runtime.checkpoint())
        print(
            json.dumps(
                {
                    "time_us": runtime.time_us,
                    "individuals": len(runtime.participants),
                    "living_bodies": len(runtime.world.members),
                    "dead_cores": sum(a.engine.life == "dead" for a in runtime.participants.values()),
                    "revision": revision if store else None,
                    "resource_balance": runtime.ledger.check_balance(),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
