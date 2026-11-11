"""Explicit deployment declaration, outside the plastic kernel.

Research snapshots retain intervention masks exactly. Deployment may acknowledge
them, but never silently clears them or passes them off as endogenous dynamics.
"""

import argparse
import hashlib
import json
from pathlib import Path

from .codec import MAX_ARTIFACT_BYTES, ArtifactCodec

SCHEMA = "threemind.deployment-declaration/1"


def inspect_model(raw):
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("model exceeds the artifact budget")
    image, profile = ArtifactCodec.decode(raw, with_profile=True)
    state = image.to_dict()
    masks = {key: state.get(key, []) for key in ("silenced_nodes", "silenced_edges")}
    return {
        "schema": SCHEMA,
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "state_hash": image.digest,
        "kernel_id": state["dynamics"],
        "time_us": state["time_us"],
        "interventions": masks,
        "has_interventions": any(masks.values()),
        "runtime_profile_present": profile is not None,
    }


def declare(raw, *, acknowledge_interventions=False):
    value = inspect_model(raw)
    if value["has_interventions"] and not acknowledge_interventions:
        raise ValueError(
            "snapshot contains research silencing; explicitly acknowledge it or unsilence an isolated copy"
        )
    return value | {"acknowledged_interventions": bool(acknowledge_interventions)}


def verify(raw, declaration):
    if not isinstance(declaration, dict) or declaration.get("schema") != SCHEMA:
        raise ValueError("invalid deployment declaration")
    expected = declare(raw, acknowledge_interventions=declaration.get("acknowledged_interventions") is True)
    if expected != declaration:
        raise ValueError("deployment declaration does not match the exact model and interventions")
    return expected


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and explicitly declare a Runtime model; never edits the model"
    )
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path, help="New declaration JSON, must not already exist")
    parser.add_argument("--acknowledge-interventions", action="store_true")
    args = parser.parse_args()
    try:
        with args.model.open("rb") as source:
            raw = source.read(MAX_ARTIFACT_BYTES + 1)
        value = (
            declare(raw, acknowledge_interventions=args.acknowledge_interventions)
            if args.output
            else inspect_model(raw)
        )
        text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text + "\n")
        print(text)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
