"""Small real-device engineering gate; no research or existing model data is touched."""

import argparse
import json
from pathlib import Path

from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    folder = Path(args.output or (".work/language-gpu-fallback" if args.fallback else ".work/language-gpu-gate"))
    folder.mkdir(parents=True, exist_ok=False)
    protocol = LanguageProtocol(input_model="qwen", output_model="qwen", mode="strict", maximum_tokens=12)
    policy = LanguageCompute(compute_device="cuda", wall_seconds=180.0, gpu_memory_mib=128 if args.fallback else 3072)
    encoded, _ = compute("encode", {"protocol": protocol.model_dump(), "texts": ["甲是松子。", "乙是铃铛。"]}, policy)
    (folder / "encoding.json").write_text(json.dumps(encoded, ensure_ascii=False), encoding="utf-8")
    if args.fallback:
        assert encoded["compute"]["resolved"] == "cpu" and encoded["fallback_from_initial_conditions"]
        print(
            json.dumps(
                {
                    "cpu_fallback_verified": True,
                    "attempts": encoded["compute_attempts"],
                    "seconds": encoded["elapsed_seconds"],
                }
            )
        )
        return
    spec = LanguageTraining(
        protocol=protocol,
        samples=[{"features": [0.01] * 256, "text": "甲"}, {"features": [0.02] * 256, "text": "乙"}],
        steps=2,
        compute=policy,
    )
    trained, head = compute("train", spec.model_dump(), policy)
    (folder / "head.safetensors").write_bytes(head)
    (folder / "training.json").write_text(json.dumps(trained, ensure_ascii=False), encoding="utf-8")
    decoded, _ = compute("decode", {"protocol": protocol.model_dump(), "features": [0.01] * 256}, policy, head=head)
    (folder / "decoding.json").write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                key: {
                    "device": value["compute"]["resolved"],
                    "dtype": value["compute"]["dtype"],
                    "peak_vram_bytes": value["compute"]["peak_vram_bytes"],
                    "seconds": value["elapsed_seconds"],
                }
                for key, value in (("encoding", encoded), ("training", trained), ("decoding", decoded))
            }
        )
    )


if __name__ == "__main__":
    main()
