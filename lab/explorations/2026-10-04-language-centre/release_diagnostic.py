"""Registered follow-up to measured transmission loss; existing controls only."""

import argparse

from experiment import NAMES, WORDS, WORK, compute_once, curriculum, inputs, protocol, read_json, run_case, study

from lab.tools.service_study import new_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("run", "decode"))
    args = parser.parse_args()
    s = study()
    try:
        vectors = inputs(s)
        seed = 17
        if args.stage == "run":
            for intensity, facilitation in ((4.0, 0.0), (1.0, 1.0), (4.0, 1.0)):
                for condition in ("ordinary", "reversed"):
                    key = f"release-i{int(intensity)}-f{int(facilitation)}-{condition}"
                    run_case(
                        s,
                        vectors,
                        key,
                        seed,
                        lessons=curriculum(seed, condition == "reversed"),
                        intensity=intensity,
                        windows=0,
                        config={"stp_facilitation_tau_s": facilitation},
                    )
                    for i, name in enumerate(NAMES):
                        for suffix in ("", "是"):
                            label = WORDS[::-1][i] if condition == "reversed" else WORDS[i]
                            run_case(
                                s,
                                vectors,
                                key + f"-probe-{i}-{len(suffix)}",
                                seed,
                                source=key,
                                probe=name + suffix,
                                label=label,
                                windows=4,
                                split="diagnostic",
                            )
                    run_case(
                        s, vectors, key + "-spontaneous", seed, source=key, windows=40, split="diagnostic-no-input"
                    )
        else:
            choice = read_json(WORK / "selection-17.json")["chosen"]
            layout = choice["layout"]
            rows = []
            for p in sorted((WORK / "cases").glob("release-*/result.json")):
                case = read_json(p)
                rows.extend(
                    {
                        "key": case["key"],
                        "window": w["window"],
                        "probe": case["probe"],
                        "label": case["label"],
                        "features": w[layout],
                        "raw": w["raw"],
                        "summary": w["summary"],
                    }
                    for w in case["windows"]
                    if w["window"] == 1 or not case["probe"]
                )
            head = (WORK / "computations" / choice["head_key"] / "weights.safetensors").read_bytes()
            for start in range(0, len(rows), 128):
                batch = rows[start : start + 128]
                key = f"release-decoded-{start}"
                index = WORK / "computations" / (key + "-index.json")
                if not index.exists():
                    new_json(index, batch)
                compute_once(
                    s,
                    key,
                    "decode_many",
                    {"protocol": protocol(seed, layout).model_dump(), "windows": [r["features"] for r in batch]},
                    head=head,
                )
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
