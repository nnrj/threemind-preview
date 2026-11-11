"""Offline contract validation and explicitly invoked developer fixtures."""

import argparse
import json
from pathlib import Path

from .adapter_contracts import manifest, negotiate, read_manifest
from .registry import default_adapter_registry


def main(argv=None):
    parser = argparse.ArgumentParser(description="ThreeMind adapter SDK: offline declarations and explicit fixtures")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    describe = commands.add_parser("describe")
    describe.add_argument("adapter")
    validate = commands.add_parser("validate")
    validate.add_argument("file", type=Path)
    validate.add_argument("--protocol")
    validate.add_argument("--transport")
    validate.add_argument("--role", action="append", default=[])
    validate.add_argument("--require-restorable-state", action="store_true")
    probe = commands.add_parser("probe")
    probe.add_argument("adapter", choices=["remote-anonymous", "anonymous-frames", "text-sensor"])
    probe.add_argument("--backend", choices=["reference", "native"], default="reference")
    args = parser.parse_args(argv)
    try:
        registry = default_adapter_registry()
        if args.command == "list":
            result = [manifest(row["contract"]) for row in registry.list()]
        elif args.command == "describe":
            result = manifest(registry.describe(args.adapter)["contract"])
        elif args.command == "validate":
            with args.file.open("rb") as stream:
                value = read_manifest(stream.read(131073))
            result = {"manifest": value, "structurally_valid": True}
            result["negotiation"] = negotiate(
                value["contract"],
                {
                    "protocol": args.protocol or value["contract"]["protocol"],
                    "roles": args.role,
                    "transports": [args.transport] if args.transport else [],
                    "require_restorable_state": args.require_restorable_state,
                },
            )
            if not result["negotiation"]["declared_compatible"]:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
        else:
            from .adapter_checks import builtin_checks

            result = builtin_checks(args.adapter, backend=args.backend)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
