"""Portable optional Transformer; numeric artifacts, CPU reference and bounded CUDA attempts."""

from __future__ import annotations

import hashlib
import io
import json
import math
import random
import time
import zipfile

import numpy as np
import psutil
import torch
from torch import nn

from .compute import DeviceFailure, device_session, representative_benchmark
from .protocol import MODEL_SCHEMA, Architecture, Prediction, Training, canonical, digest

PROBABILITY_SCHEMA = "threemind.probabilities/1"
MAX_MODEL_BYTES = 64 * 1024 * 1024


class TinyTransformer(nn.Module):
    def __init__(self, architecture: Architecture):
        super().__init__()
        self.architecture = architecture
        a = architecture
        # Keep optional-tool initialization from perturbing other users of torch's RNG.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(a.seed)
            self.tokens = nn.Embedding(a.vocabulary, a.width)
            self.positions = nn.Embedding(a.context, a.width)
            block = nn.TransformerEncoderLayer(
                a.width, a.heads, a.width * 4, dropout=0, batch_first=True, norm_first=True, activation="gelu"
            )
            self.blocks = nn.TransformerEncoder(block, a.layers, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(a.width)
            self.output = nn.Linear(a.width, a.vocabulary, bias=False)
            # Encoder clones otherwise start identically. Initialize each matrix independently.
            for name, parameter in self.named_parameters():
                if parameter.ndim > 1:
                    nn.init.xavier_uniform_(parameter)
                elif name.endswith("weight"):
                    nn.init.ones_(parameter)
                else:
                    nn.init.zeros_(parameter)

    def forward(self, tokens):
        length = tokens.shape[1]
        mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=tokens.device), diagonal=1)
        x = self.tokens(tokens) + self.positions(torch.arange(length, device=tokens.device))
        return self.output(self.norm(self.blocks(x, mask=mask)))

    def predict(self, tokens):
        tokens = Prediction(tokens=tokens).tokens
        if len(tokens) > self.architecture.context or max(tokens) >= self.architecture.vocabulary:
            raise ValueError("prediction exceeds model context or vocabulary")
        self.eval()
        with torch.inference_mode():
            device = next(self.parameters()).device
            values = self(torch.tensor([tokens], dtype=torch.long, device=device))[0, -1].softmax(dim=-1).tolist()
        return values


def batch(sequences, device="cpu"):
    length = max(len(s) - 1 for s in sequences)
    x = torch.zeros((len(sequences), length), dtype=torch.long)
    y = torch.full_like(x, -100)
    for i, s in enumerate(sequences):
        x[i, : len(s) - 1] = torch.tensor(s[:-1])
        y[i, : len(s) - 1] = torch.tensor(s[1:])
    return x.to(device), y.to(device)


def evaluate(model, sequences, guard=lambda: None):
    if not sequences:
        return None
    total, correct, count = 0.0, 0, 0
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(sequences), 16):
            guard()
            x, y = batch(sequences[start : start + 16], next(model.parameters()).device)
            logits = model(x)
            loss = nn.functional.cross_entropy(logits.flatten(0, 1), y.flatten(), ignore_index=-100, reduction="sum")
            total += loss.item()
            correct += int(((logits.argmax(dim=-1) == y) & (y != -100)).sum())
            count += int((y != -100).sum())
    return {"negative_log_likelihood": total / count, "next_token_accuracy": correct / count, "tokens": count}


def train(protocol: Training, *, guard=lambda: None):
    """One attempt. CLI supervisor retries a recognized GPU fault in a fresh CPU child."""
    start = time.monotonic()
    torch.set_num_threads(protocol.threads)

    def benchmark(gpu_guard):
        deadline = min(start + protocol.wall_seconds / 4, time.monotonic() + 3)

        def check():
            guard()
            gpu_guard()
            if psutil.Process().memory_info().rss > protocol.memory_mib * 1024 * 1024:
                raise BudgetStop("memory_budget")
            if time.monotonic() > deadline:
                raise BudgetStop("benchmark_budget")

        def operation(model, count):
            optimizer = torch.optim.AdamW(model.parameters(), lr=protocol.learning_rate)
            # Representative fixed sampler; does not consume the formal training RNG.
            sample = [protocol.sequences[i % len(protocol.sequences)] for i in range(protocol.batch_size)]
            for _ in range(count):
                check()
                x, y = batch(sample, next(model.parameters()).device)
                optimizer.zero_grad(set_to_none=True)
                loss = nn.functional.cross_entropy(model(x).flatten(0, 1), y.flatten(), ignore_index=-100)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
                optimizer.step()

        try:
            return representative_benchmark(lambda: TinyTransformer(protocol.architecture), operation, check)
        except BudgetStop as exc:
            return {"cpu_seconds": [], "cuda_seconds": [], "status": str(exc)}

    with device_session(protocol, benchmark) as (compute, gpu_guard):
        try:
            model, metadata = _train_attempt(protocol, start, compute, lambda: (guard(), gpu_guard()))
        except RuntimeError as exc:
            from .compute import device_fault

            if compute["resolved"] == "cuda" and device_fault(exc):
                raise DeviceFailure(str(exc), compute) from exc
            raise
        metadata["compute"] = compute
        return model, metadata


def _train_attempt(protocol, start, compute, guard):
    process = psutil.Process()
    rng = random.Random(protocol.architecture.seed)
    model = TinyTransformer(protocol.architecture).to(compute["resolved"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=protocol.learning_rate)
    history, reason, completed, peak = [], "completed", 0, process.memory_info().rss

    def check():
        nonlocal peak
        guard()
        peak = max(peak, process.memory_info().rss)
        if peak > protocol.memory_mib * 1024 * 1024:
            raise BudgetStop("memory_budget")
        if time.monotonic() - start > protocol.wall_seconds:
            raise BudgetStop("wall_time_budget")

    try:
        check()
        for step in range(protocol.steps):
            check()
            model.train()
            x, y = batch([rng.choice(protocol.sequences) for _ in range(protocol.batch_size)], compute["resolved"])
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(x).flatten(0, 1), y.flatten(), ignore_index=-100)
            if not torch.isfinite(loss):
                raise ValueError("nonfinite loss; model was not published")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            completed = step + 1
            if step % max(1, protocol.steps // 100) == 0 or completed == protocol.steps:
                history.append({"step": completed, "loss": loss.item()})
        training = evaluate(model, protocol.sequences, check)
        evaluation = evaluate(model, protocol.evaluation, check)
    except BudgetStop as exc:
        reason, training, evaluation = str(exc), None, None
    except RuntimeError as exc:
        from .compute import device_fault

        if compute["resolved"] == "cuda" and device_fault(exc):
            raise DeviceFailure(
                str(exc),
                compute
                | {
                    "steps_completed": completed,
                    "loss_history": history,
                    "wall_seconds": time.monotonic() - start,
                    "peak_rss_bytes": peak,
                },
            ) from exc
        raise
    metadata = {
        "schema": "threemind.transformer-training/1",
        "algorithm": "causal-self-attention-next-token-adamw/1",
        "protocol": protocol.model_dump(),
        "protocol_hash": digest(protocol.model_dump()),
        "training_hash": digest(protocol.sequences),
        "evaluation_hash": digest(protocol.evaluation),
        "status": reason,
        "steps_completed": completed,
        "training": training,
        "evaluation": evaluation,
        "loss_history": history,
        "wall_seconds": time.monotonic() - start,
        "peak_rss_bytes": peak,
        "parameters": sum(p.numel() for p in model.parameters()),
        "torch_version": str(torch.__version__),
        "device": compute["resolved"],
        "external_contribution": True,
        "core_feedback": False,
    }
    return model, metadata


class BudgetStop(Exception):
    pass


def encode(model, metadata=None):
    pieces = {}
    for i, (key, tensor) in enumerate(model.state_dict().items()):
        data = io.BytesIO()
        np.save(data, tensor.detach().cpu().numpy(), allow_pickle=False)
        pieces[f"{i}.npy"] = (key, data.getvalue())
    manifest = {
        "schema": MODEL_SCHEMA,
        "architecture": model.architecture.model_dump(),
        "metadata": metadata or {},
        "arrays": [{"file": f, "key": k, "sha256": hashlib.sha256(raw).hexdigest()} for f, (k, raw) in pieces.items()],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", canonical(manifest))
        for file, (_, raw) in pieces.items():
            archive.writestr(file, raw)
    if output.tell() > MAX_MODEL_BYTES:
        raise ValueError("Transformer artifact exceeds size budget")
    return output.getvalue()


def decode(raw):
    if len(raw) > MAX_MODEL_BYTES:
        raise ValueError("Transformer artifact exceeds size budget")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if (
            len(infos) > 256
            or len({i.filename for i in infos}) != len(infos)
            or sum(i.file_size for i in infos) > MAX_MODEL_BYTES
        ):
            raise ValueError("invalid or oversized numeric model archive")
        manifest = json.loads(archive.read("manifest.json"))
        if set(manifest) != {"schema", "architecture", "arrays", "metadata"} or manifest["schema"] != MODEL_SCHEMA:
            raise ValueError("unsupported numeric model schema")
        model = TinyTransformer(Architecture.model_validate(manifest["architecture"]))
        expected = model.state_dict()
        rows = manifest["arrays"]
        if {r["key"] for r in rows} != set(expected) or len(rows) != len(expected):
            raise ValueError("model tensor set differs from architecture")
        if {i.filename for i in infos} != {"manifest.json"} | {f"{i}.npy" for i in range(len(rows))}:
            raise ValueError("unexpected numeric model members")
        actual = {}
        for i, row in enumerate(rows):
            if set(row) != {"file", "key", "sha256"} or row["file"] != f"{i}.npy":
                raise ValueError("invalid tensor manifest")
            data = archive.read(row["file"])
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("model tensor checksum mismatch")
            # Check shape and byte count before np.load can allocate a claimed large array.
            header = io.BytesIO(data)
            version = np.lib.format.read_magic(header)
            if version not in ((1, 0), (2, 0)):
                raise ValueError("unsupported numeric tensor header")
            reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
            shape, fortran, dtype = reader(header, max_header_size=1024)
            expected_shape = tuple(expected[row["key"]].shape)
            if (
                shape != expected_shape
                or fortran
                or dtype != np.float32
                or len(data) - header.tell() != math.prod(shape) * 4
            ):
                raise ValueError("numeric tensor header does not match architecture")
            array = np.load(io.BytesIO(data), allow_pickle=False, max_header_size=1024)
            if (
                array.dtype != np.float32
                or tuple(array.shape) != tuple(expected[row["key"]].shape)
                or not np.isfinite(array).all()
            ):
                raise ValueError("invalid tensor dtype, shape or values")
            actual[row["key"]] = torch.from_numpy(array.copy())
        model.load_state_dict(actual, strict=True)
        return model, manifest["metadata"]


def probabilities(model, model_hash, tokens):
    values = model.predict(tokens)
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values) or abs(sum(values) - 1) > 1e-5:
        raise ValueError("invalid probability distribution")
    return {
        "schema": PROBABILITY_SCHEMA,
        "model_sha256": model_hash,
        "request_hash": digest(tokens),
        "tokens": list(tokens),
        "probabilities": values,
        "external_contribution": True,
        "core_feedback": False,
    }
