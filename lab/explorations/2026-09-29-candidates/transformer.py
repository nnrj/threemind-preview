"""Independent local probability control. Never feeds a ThreeMind core."""

from common import WORK, Study, new_json, read_json

from threemind_transformer.protocol import Architecture, Prediction, Training
from threemind_transformer.supervisor import predict_file, train_file


def main():
    study = Study()
    try:
        results = []
        for block in range(6):
            for swap in (False, True):
                study.guard(force=True)
                folder = WORK / f"transformer-{block}-{int(swap)}"
                folder.mkdir(exist_ok=True)
                result_file = folder / "result.json"
                if result_file.exists():
                    results.append(read_json(result_file))
                    continue
                sequences = [[0, 1, 4 if swap else 2], [3, 1, 2 if swap else 4]]
                corpus = [s for count in (20, 10, 5) for s in sequences for _ in range(count)]
                protocol = Training(
                    architecture=Architecture(
                        vocabulary=5, context=8, width=32, heads=4, layers=2, seed=9291000 + block
                    ),
                    sequences=corpus,
                    steps=200,
                    batch_size=8,
                    wall_seconds=30.0,
                    threads=2,
                    compute_device="auto",
                )
                model = folder / "model.tmt"
                new_json(folder / "protocol.json", protocol.model_dump())
                training = train_file(protocol, model)
                predictions = [predict_file(model, Prediction(tokens=s[:2], compute_device="auto")) for s in sequences]
                result = {
                    "block": block,
                    "swap": swap,
                    "training": training,
                    "predictions": predictions,
                    "expected": [s[2] for s in sequences],
                    "frequency_target_probability": 1 / 6,
                    "first_order_target_probability": 0.5,
                    "generalization_claim": False,
                    "core_feedback": False,
                }
                new_json(result_file, result)
                results.append(result)
                print(f"CPU probability control block={block} swap={swap} completed", flush=True)
        new_json(WORK / "transformer-results.json", results)
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
