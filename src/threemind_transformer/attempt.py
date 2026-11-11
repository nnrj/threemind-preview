"""Private, isolated compute attempt. No database, networking, credentials or Core IO."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from .compute import DeviceFailure, device_session, representative_benchmark
from .protocol import Prediction, Training


def predict(raw, query):
    from .model import decode, probabilities

    model, _ = decode(raw)

    def benchmark(check):
        deadline = time.monotonic() + 3

        def bounded_check():
            check()
            if time.monotonic() > deadline:
                raise TimeoutError("benchmark_budget")

        def operation(candidate, count):
            for _ in range(count):
                bounded_check()
                candidate.predict(query.tokens)

        try:
            return representative_benchmark(lambda: decode(raw)[0], operation, bounded_check)
        except TimeoutError:
            return {"cpu_seconds": [], "cuda_seconds": [], "status": "benchmark_budget"}

    with device_session(query, benchmark) as (compute, check):
        model.to(compute["resolved"])
        check()
        result = probabilities(model, hashlib.sha256(raw).hexdigest(), query.tokens)
        check()
        return result | {"compute": compute}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("train", "predict"))
    parser.add_argument("protocol", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    from .cli import read

    try:
        import torch

        torch.set_num_threads(2)
        if args.operation == "train":
            from .model import encode, train

            protocol = Training.model_validate_json(read(args.protocol, 4 * 1024 * 1024))
            model, result = train(protocol)
            with args.model.open("xb") as output:
                output.write(encode(model, result))
        else:
            from .model import MAX_MODEL_BYTES

            query = Prediction.model_validate_json(read(args.protocol, 8192))
            result = predict(read(args.model, MAX_MODEL_BYTES), query)
        code = 0
    except DeviceFailure as exc:
        result = {"status": "device_failed", "reason": str(exc)[:500], "compute": exc.evidence}
        code = 86
    # Other exceptions deliberately remain failures; the supervisor must not retry them on CPU.
    with args.report.open("x", encoding="utf-8") as report:
        json.dump(result, report, ensure_ascii=False, allow_nan=False)
    return code


if __name__ == "__main__":
    sys.exit(main())
