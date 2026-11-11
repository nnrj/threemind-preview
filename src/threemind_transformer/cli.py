import argparse
import hashlib
import json
import os
from pathlib import Path

from .protocol import Prediction, Training


def read(path, maximum):
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("file exceeds resource budget")
    return raw


def serve(model_path, *, host="127.0.0.1", port=8997, compute_device="cpu", gpu_memory_mib=2048, gpu_headroom_mib=512):
    import asyncio
    import secrets
    import tempfile

    import torch
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request, Response
    from starlette.concurrency import run_in_threadpool

    from .model import MAX_MODEL_BYTES, decode, probabilities

    torch.set_num_threads(2)

    token = os.environ.get("THREEMIND_TRANSFORMER_TOKEN")
    if host not in ("127.0.0.1", "::1", "localhost") and not token:
        raise ValueError("non-loopback serving requires THREEMIND_TRANSFORMER_TOKEN")
    raw = read(model_path, MAX_MODEL_BYTES)
    model, _ = decode(raw)
    sha = hashlib.sha256(raw).hexdigest()
    app = FastAPI(docs_url=None, redoc_url=None)
    slot = asyncio.Lock()
    latest = {"compute": {"requested": compute_device, "resolved": "not_yet_executed"}}
    temporary = tempfile.TemporaryDirectory(prefix="threemind-transformer-serve-")
    frozen = Path(temporary.name) / "model.tmt"
    frozen.write_bytes(raw)

    def authorize(request):
        if token and not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            raise HTTPException(401, "invalid token")

    @app.get("/compute")
    def compute_evidence(request: Request):
        authorize(request)
        return latest

    @app.post("/probabilities")
    async def prediction(request: Request, response: Response):
        authorize(request)
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 8192:
                raise HTTPException(413, "request exceeds budget")
        try:
            body = Prediction.model_validate_json(payload)
            defaults = {
                "compute_device": compute_device,
                "gpu_memory_mib": gpu_memory_mib,
                "gpu_headroom_mib": gpu_headroom_mib,
            }
            body = body.model_copy(update={k: v for k, v in defaults.items() if k not in body.model_fields_set})
            async with slot:
                if body.compute_device == "cpu":
                    result = await run_in_threadpool(probabilities, model, sha, body.tokens)
                    latest.clear()
                    latest.update(compute={"requested": "cpu", "resolved": "cpu", "reason": "explicit_cpu"})
                else:
                    from .supervisor import predict_file

                    result = await run_in_threadpool(predict_file, frozen, body)
                    latest.clear()
                    latest.update(
                        {k: result[k] for k in ("compute", "compute_attempts", "fallback_from_initial_conditions")}
                    )
            response.headers["X-ThreeMind-Compute-Device"] = latest["compute"]["resolved"]
            # Keep the existing remote probability protocol strict. Execution
            # evidence has its own authenticated endpoint and response header.
            return {
                k: result[k]
                for k in (
                    "schema",
                    "model_sha256",
                    "request_hash",
                    "tokens",
                    "probabilities",
                    "external_contribution",
                    "core_feedback",
                )
            }
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    try:
        uvicorn.run(app, host=host, port=port, access_log=False)
    finally:
        temporary.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description="Local optional Transformer comparison; probabilities, no generated answers"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    training = sub.add_parser("train")
    training.add_argument("protocol", type=Path)
    training.add_argument("--output", type=Path, required=True)
    training.add_argument("--failure-report", type=Path, help="Preserve failed compute attempts as JSON")
    predict = sub.add_parser("predict")
    predict.add_argument("model", type=Path)
    predict.add_argument("--tokens", required=True, help="JSON array of categorical token IDs")
    predict.add_argument("--compute-device", choices=("auto", "cpu", "cuda"), default="cpu")
    predict.add_argument("--gpu-memory-mib", type=int, default=2048)
    predict.add_argument("--gpu-headroom-mib", type=int, default=512)
    predict.add_argument("--failure-report", type=Path)
    server = sub.add_parser("serve")
    server.add_argument("model", type=Path)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8997)
    server.add_argument("--compute-device", choices=("auto", "cpu", "cuda"), default="cpu")
    server.add_argument("--gpu-memory-mib", type=int, default=2048)
    server.add_argument("--gpu-headroom-mib", type=int, default=512)
    remote = sub.add_parser("remote")
    remote.add_argument("url")
    remote.add_argument("--tokens", required=True)
    remote.add_argument("--model-hash", required=True)
    remote.add_argument("--allow-remote", action="store_true")
    sub.add_parser("contract")
    sub.add_parser("compute", help="Probe this Python environment without training a model")
    args = parser.parse_args()
    try:
        if args.command == "compute":
            from .compute import probe

            result = probe()
        elif args.command == "contract":
            from .adapter import contract

            result = contract().model_dump()
        elif args.command == "remote":
            from .adapter import remote_probabilities

            result = remote_probabilities(
                args.url,
                json.loads(args.tokens),
                model_hash=args.model_hash,
                allow_remote=args.allow_remote,
                token=os.environ.get("THREEMIND_TRANSFORMER_TOKEN"),
            )
        elif args.command == "serve":
            policy = Prediction(
                tokens=[0],
                compute_device=args.compute_device,
                gpu_memory_mib=args.gpu_memory_mib,
                gpu_headroom_mib=args.gpu_headroom_mib,
            )
            serve(
                args.model,
                host=args.host,
                port=args.port,
                compute_device=policy.compute_device,
                gpu_memory_mib=policy.gpu_memory_mib,
                gpu_headroom_mib=policy.gpu_headroom_mib,
            )
            return
        else:
            if args.command == "train":
                from .supervisor import train_file

                protocol = Training.model_validate_json(read(args.protocol, 4 * 1024 * 1024))
                result = train_file(protocol, args.output)
            else:
                from .supervisor import predict_file

                result = predict_file(
                    args.model,
                    Prediction(
                        tokens=json.loads(args.tokens),
                        compute_device=args.compute_device,
                        gpu_memory_mib=args.gpu_memory_mib,
                        gpu_headroom_mib=args.gpu_headroom_mib,
                    ),
                )
    except (ValueError, OSError, ImportError) as exc:
        from .supervisor import ComputeExecutionError

        if isinstance(exc, ComputeExecutionError) and getattr(args, "failure_report", None):
            with args.failure_report.open("x", encoding="utf-8") as report:
                json.dump(exc.report, report, ensure_ascii=False, allow_nan=False)
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
