"""Bounded real-device acceptance through the existing isolated Transformer supervisor."""

import argparse
import json
import os
import sys
from pathlib import Path

from threemind_transformer.protocol import Architecture, Prediction, Training
from threemind_transformer.supervisor import predict_file, train_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--case", action="append", choices=("cpu", "cuda", "auto", "gpu-hidden"))
    parser.add_argument("--predict-existing", type=Path, help="Validate a saved model without retraining it")
    args = parser.parse_args()
    folder = args.folder
    folder.mkdir(parents=True, exist_ok=False)
    os.environ["THREEMIND_TRANSFORMER_PYTHON"] = sys.executable
    rows = {}
    base = Training(
        architecture=Architecture(vocabulary=8, context=8, width=16, heads=2, layers=1, seed=17),
        sequences=[[1, 2, 3], [4, 5, 6]],
        steps=30,
        batch_size=8,
        wall_seconds=60.0,
    )
    for label, device in (("cpu", "cpu"), ("cuda", "cuda"), ("auto", "auto"), ("gpu-hidden", "cuda")):
        if args.case and label not in args.case:
            continue
        original = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            if label == "gpu-hidden":
                # Only children of this command see CUDA hidden. No driver or global setting changes.
                os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
            protocol = base.model_copy(update={"compute_device": device})
            query = Prediction(tokens=[1, 2], compute_device=device)
            requested = query if args.predict_existing else protocol
            (folder / f"{label}-protocol.json").write_text(requested.model_dump_json(indent=2), encoding="utf-8")
            model = args.predict_existing or folder / f"{label}.tmt"
            report = None if args.predict_existing else train_file(protocol, model)
            prediction = predict_file(model, query)
            rows[label] = {"training": report, "prediction": prediction}
            with (folder / f"{label}-result.json").open("x", encoding="utf-8") as stream:
                json.dump(rows[label], stream, ensure_ascii=False, indent=2)
            if report:
                assert report["status"] == "completed" and report["steps_completed"] == 30
                assert prediction["compute"]["resolved"] == report["compute"]["resolved"] or device == "auto"
            evidence = report or prediction
            print(
                json.dumps(
                    {
                        "case": label,
                        "device": evidence["compute"]["resolved"],
                        "wall": evidence["total_wall_seconds"],
                        "vram": evidence["compute"]["peak_vram_bytes"],
                    }
                ),
                flush=True,
            )
        finally:
            if original is None:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = original
    if "cuda" in rows:
        assert rows["cuda"]["prediction"]["compute"]["resolved"] == "cuda", "real CUDA acceptance was not completed"
    if "gpu-hidden" in rows:
        assert rows["gpu-hidden"]["prediction"]["compute"]["resolved"] == "cpu"
    with (folder / "acceptance.json").open("x", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
