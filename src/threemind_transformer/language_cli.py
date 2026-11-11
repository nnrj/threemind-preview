"""The same adapter protocol and computation used by the Lab, without PostgreSQL."""

import argparse
import json
from pathlib import Path

from threemind_runtime.store import SQLiteStore

from .language_compute import compute
from .language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining, ScratchTraining
from .language_session import LanguageSession


def read(path, limit=16 * 2**20):
    value = Path(path)
    if value.stat().st_size > limit:
        raise ValueError("input exceeds size budget")
    return value.read_bytes()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    return json.loads(read(path).decode("utf-8-sig"), object_pairs_hook=unique)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("template")
    export = sub.add_parser("export", help="export complete Core, adapter state and optional language weights")
    export.add_argument("--store", required=True)
    export.add_argument("--instance", default="language")
    export.add_argument("--head")
    export.add_argument("--input-checkpoint")
    export.add_argument("--output-checkpoint")
    export.add_argument("--output", required=True)
    restore = sub.add_parser("import", help="restore a portable language device to a new local identity")
    restore.add_argument("bundle")
    restore.add_argument("--store", required=True)
    restore.add_argument("--instance", default="language")
    restore.add_argument("--assets-dir", required=True)
    restore.add_argument("--backend", choices=("native", "reference"), default="native")
    training = sub.add_parser("train")
    training.add_argument("protocol")
    training.add_argument("--kind", choices=("scratch", "head"), required=True)
    training.add_argument("--checkpoint")
    training.add_argument("--output", required=True)
    turn = sub.add_parser("turn")
    turn.add_argument("--protocol", required=True)
    turn.add_argument("--store", required=True)
    turn.add_argument("--instance", default="language")
    turn.add_argument("--resume", action="store_true")
    turn.add_argument("--config", help="initial Core configuration JSON (new consciousness only)")
    turn.add_argument("--kernel")
    turn.add_argument("--text", required=True)
    turn.add_argument("--intensity", type=float, default=1.0)
    turn.add_argument("--head")
    turn.add_argument("--input-checkpoint")
    turn.add_argument("--output-checkpoint")
    turn.add_argument("--compute-device", choices=("cpu", "cuda", "auto"), default="cpu")
    turn.add_argument("--backend", choices=("native", "reference"), default="native")
    turn.add_argument("--output", required=True)
    observe = sub.add_parser(
        "observe", help="stream activity without submitting new stimuli; save each completed window"
    )
    observe.add_argument("--store", required=True)
    observe.add_argument("--instance", default="language")
    observe.add_argument("--windows", type=int, default=20)
    observe.add_argument("--head")
    observe.add_argument("--output-checkpoint")
    observe.add_argument("--compute-device", choices=("cpu", "cuda", "auto"), default="cpu")
    observe.add_argument("--backend", choices=("native", "reference"), default="native")
    observe.add_argument("--output", required=True, help="new JSONL file; each record is also flushed to stdout")
    args = parser.parse_args(argv)
    if args.command == "template":
        print(LanguageProtocol().model_dump_json(indent=2))
        return
    if args.command == "observe":
        if not 1 <= args.windows <= 256:
            raise ValueError("observation requires 1..256 windows")
        # Reserve the destination before advancing the saved instance.
        with Path(args.output).open("x", encoding="utf-8") as destination:
            store = SQLiteStore(args.store)
            revision, image, context = store.load(args.instance, with_context=True)
            if not context:
                raise ValueError("no language recovery context")
            session = LanguageSession(context["protocol"], image=image, context=context, backend=args.backend)
            for result in session.stream(
                args.windows,
                policy=LanguageCompute(compute_device=args.compute_device),
                head=read(args.head, 64 * 2**20) if args.head else None,
                output_checkpoint=read(args.output_checkpoint, 64 * 2**20) if args.output_checkpoint else None,
            ):
                revision = store.save(
                    args.instance,
                    session.engine.capture_state(),
                    expected_revision=revision,
                    profile=session.profile,
                    context=session.context(),
                )
                result["revision"] = revision
                line = json.dumps(result, ensure_ascii=False, allow_nan=False)
                destination.write(line + "\n")
                destination.flush()
                print(line, flush=True)
        return
    if args.command in ("export", "import"):
        from .language_bundle import MAX_BYTES, pack, unpack

        store = SQLiteStore(args.store)
        if args.command == "export":
            _, image, context = store.load(args.instance, with_context=True)
            assets = {
                key: read(getattr(args, flag), 64 * 2**20) if getattr(args, flag) else None
                for key, flag in (("head", "head"), ("input", "input_checkpoint"), ("output", "output_checkpoint"))
            }
            raw = pack(image, context, assets)
            with Path(args.output).open("xb") as destination:
                destination.write(raw)
            print(json.dumps({"state_hash": image.digest, "bytes": len(raw)}))
        else:
            session, assets = unpack(read(args.bundle, MAX_BYTES), backend=args.backend)
            folder = Path(args.assets_dir)
            folder.mkdir(parents=True, exist_ok=False)
            for key, raw in assets.items():
                if raw is not None:
                    (folder / (key + ".safetensors")).write_bytes(raw)
            (folder / "protocol.json").write_text(session.protocol.model_dump_json(indent=2), encoding="utf-8")
            store.save(
                args.instance,
                session.engine.capture_state(),
                expected_revision=0,
                profile=session.profile,
                context=session.context(),
            )
            print(json.dumps({"state_hash": session.engine.capture_state().digest, "assets_dir": str(folder)}))
        return
    # An explicit output must never overwrite an earlier experiment.
    with Path(args.output).open("xb") as destination:
        if args.command == "train":
            cls = ScratchTraining if args.kind == "scratch" else LanguageTraining
            spec = cls.model_validate(read_json(args.protocol))
            result, artifact = compute(
                "scratch_train" if args.kind == "scratch" else "train",
                spec.model_dump(),
                spec.compute,
                checkpoint=read(args.checkpoint, 64 * 2**20) if args.checkpoint else None,
            )
            destination.write(artifact)
        else:
            protocol = LanguageProtocol.model_validate(read_json(args.protocol))
            store = SQLiteStore(args.store)
            revision, image, context = 0, None, None
            if args.resume:
                if args.config:
                    raise ValueError("resumed consciousness retains its saved Core configuration")
                revision, image, context = store.load(args.instance, with_context=True)
                if context is None:
                    raise ValueError("no language recovery context")
            session = LanguageSession(
                protocol.model_dump(),
                image=image,
                context=context,
                backend=args.backend,
                kernel_id=args.kernel,
                config=read_json(args.config) if args.config else None,
            )
            result = session.turn(
                args.text,
                intensity=args.intensity,
                policy=LanguageCompute(compute_device=args.compute_device),
                head=read(args.head, 64 * 2**20) if args.head else None,
                input_checkpoint=read(args.input_checkpoint, 64 * 2**20) if args.input_checkpoint else None,
                output_checkpoint=read(args.output_checkpoint, 64 * 2**20) if args.output_checkpoint else None,
            )
            revision = store.save(
                args.instance,
                session.engine.capture_state(),
                expected_revision=revision,
                profile=session.profile,
                context=session.context(),
            )
            result["revision"] = revision
            destination.write(json.dumps(result, ensure_ascii=False, allow_nan=False).encode())
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ("process", "readouts", "stimuli")}, ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
