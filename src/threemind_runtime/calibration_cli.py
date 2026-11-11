"""Database-free calibration of an exported model; output is written on demand."""

import argparse
import json
from pathlib import Path

from .calibration import MAX_PACKAGE, calibrate, encode, parse_protocol
from .codec import ArtifactCodec
from .sensory import TextSensorConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="New evidence ZIP; existing files are never overwritten"
    )
    parser.add_argument("--seed", type=int, help="Required for a model without a sensory profile")
    parser.add_argument(
        "--sensor-config", type=Path, help="Explicit sensory configuration JSON; otherwise use the model profile"
    )
    parser.add_argument("--backend", choices=("native", "reference"), default="native")
    args = parser.parse_args()
    summary = args.output.with_suffix(".json")
    if args.output.suffix.lower() != ".zip":
        parser.error("--output must be a new .zip path")
    if args.model.stat().st_size > MAX_PACKAGE:
        parser.error("source model exceeds calibration byte budget")
    if args.output.exists() or summary.exists():
        parser.error("output exists; choose a new name")
    image, profile = ArtifactCodec.decode(args.model.read_bytes(), max_bytes=MAX_PACKAGE, with_profile=True)
    seed = args.seed if args.seed is not None else (profile or {}).get("sensory_seed")
    sensor = (
        json.loads(args.sensor_config.read_text(encoding="utf-8"))
        if args.sensor_config
        else (profile or {}).get("text_sensor")
    )
    if seed is None or sensor is None:
        parser.error("a model without a sensory profile requires both --seed and --sensor-config")
    protocol = parse_protocol(json.loads(args.protocol.read_bytes()))
    result, raw = calibrate(
        image,
        seed=seed,
        sensor_config=TextSensorConfig(**sensor),
        protocol=protocol,
        backend=args.backend,
        source_context={"protocol": {"source_policies": (profile or {}).get("source_policies", {})}},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as file:
        file.write(raw)
    with summary.open("xb") as file:
        file.write(encode(result))
    print(
        json.dumps(
            {
                "source_hash": image.digest,
                "source_unchanged": result["source_unchanged"],
                "evidence": str(args.output),
                "result": str(summary),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
