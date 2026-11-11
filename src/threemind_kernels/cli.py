from __future__ import annotations

import argparse
import json
from pathlib import Path

from .definition import MAX_DEFINITION_BYTES, KernelDefinition
from .registry import describe_kernel, kernel_catalog


def main():
    parser = argparse.ArgumentParser(description="Inspect and validate versioned ThreeMind kernels")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List implemented kernel identities and supported backends")
    inspect = commands.add_parser("inspect", help="Print identity and complete default definition")
    inspect.add_argument("kernel_id", nargs="?")
    validate = commands.add_parser("validate", help="Validate a declarative definition without executing it")
    validate.add_argument("definition", type=Path)
    build = commands.add_parser("build", help="Compile a standalone runtime with this trusted constructor")
    build.add_argument("definition", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--allow-download", action="store_true", help="Allow Cargo to fetch locked dependencies")
    args = parser.parse_args()
    try:
        if args.command == "list":
            result = {"kernels": kernel_catalog()}
        elif args.command == "inspect":
            definition = KernelDefinition.default(args.kernel_id)
            result = {
                "kernel": describe_kernel(args.kernel_id),
                "definition": definition.to_dict(),
                "definition_hash": definition.digest,
            }
        else:
            with args.definition.open("rb") as stream:
                definition = KernelDefinition.parse(stream.read(MAX_DEFINITION_BYTES + 1))
            if args.command == "build":
                from .build import build_runtime

                result = build_runtime(definition, args.output, offline=not args.allow_download)
            else:
                result = {"valid": True, "definition_hash": definition.digest, "definition": definition.to_dict()}
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
