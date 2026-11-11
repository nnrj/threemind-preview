"""Small from-scratch temporal activity-to-language model, entirely outside Core."""

import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .development import TrajectoryBasis
from .language_protocol import LanguageProtocol
from .scratch_language import BOS, EOS, ScratchTransformer


class TemporalLanguage(nn.Module):
    def __init__(self, basis, seed=17, width=64, layers=2):
        super().__init__()
        self.basis, self.seed, self.width, self.layer_count = basis, seed, width, layers
        self.lm = ScratchTransformer(LanguageProtocol(seed=seed, scratch_width=width, scratch_layers=layers,
                                                     scratch_context=256, scratch_heads=4))
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed + 1)
            self.prefix = nn.Linear(basis.width, width)

    def condition(self, values):
        prefix = self.prefix(values)
        start = torch.full((values.shape[0], 1), BOS, device=values.device, dtype=torch.long)
        return torch.cat([prefix, self.lm.token(start)], dim=1)

    @torch.no_grad()
    def decode(self, values, maximum_tokens=32):
        self.eval()
        value = torch.as_tensor(np.asarray(values), device=self.lm.device, dtype=torch.float32)
        if tuple(value.shape[1:]) != (self.basis.bins, self.basis.width):
            raise ValueError("temporal feature shape differs from frozen basis")
        if not 1 <= maximum_tokens <= 128:
            raise ValueError("generation token budget")
        prefix, tokens = self.condition(value), [[] for _ in values]
        finished = torch.zeros(len(values), device=value.device, dtype=torch.bool)
        for _ in range(maximum_tokens):
            next_ids = self.lm(inputs_embeds=prefix).logits[:, -1].argmax(-1)
            for i, token in enumerate(next_ids.tolist()):
                if not bool(finished[i]):
                    tokens[i].append(token)
            finished |= next_ids == EOS
            if bool(finished.all()):
                break
            prefix = torch.cat([prefix, self.lm.token(next_ids[:, None])], dim=1)
        return [
            {"text": bytes(t for t in row if t < 256).decode("utf-8", errors="replace"), "tokens": row,
             "terminated": bool(row and row[-1] == EOS), "exposure": ["anonymous_activity_trajectory"],
             "cross_window_cache": False, "pretrained_weights": False}
            for row in tokens
        ]


def save(model, path, metadata):
    from safetensors.torch import save_file

    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    manifest = {"schema": "threemind.temporal-language/1", "basis": model.basis.to_dict(),
                "seed": model.seed, "width": model.width, "layers": model.layer_count,
                "pretrained_weights": False, **metadata}
    save_file({k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}, str(path),
              metadata={"threemind": json.dumps(manifest)})
    return manifest | {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load(path, device="cpu"):
    from safetensors import safe_open
    from safetensors.torch import load_file

    with safe_open(str(path), framework="pt", device="cpu") as handle:
        meta = json.loads(handle.metadata()["threemind"])
    if meta["schema"] != "threemind.temporal-language/1":
        raise ValueError("temporal decoder identity mismatch")
    model = TemporalLanguage(TrajectoryBasis(**meta["basis"]), meta["seed"], meta["width"], meta["layers"])
    model.load_state_dict(load_file(str(path)), strict=True)
    return model.to(device).eval(), meta


def fit(samples, basis, output, *, seed=17, steps=1200, batch_size=16, device="cpu", initial=None,
        learning_rate=0.001, check=lambda: None, checkpoints=(200,)):
    """Labels describe calibration observations, never a formal test assignment.

    Empty text is an explicit EOS calibration target, not an invisible prompt to
    Core. Callers own split provenance; the model receives no source/label IDs.
    """
    if Path(output).exists():
        raise FileExistsError(output)
    if not 2 <= len(samples) <= 16384 or not 1 <= steps <= 20000 or not 1 <= batch_size <= 128:
        raise ValueError("bounded nonempty training required")
    model = load(initial, device)[0] if initial else TemporalLanguage(basis, seed).to(device)
    if model.basis != basis:
        raise ValueError("cannot change observation basis while continuing a decoder")
    data = torch.tensor(np.asarray([s["values"] for s in samples]), device=device, dtype=torch.float32)
    if tuple(data.shape[1:]) != (basis.bins, basis.width) or not torch.isfinite(data).all():
        raise ValueError("invalid calibration features")
    target_rows = [[*s["text"].encode("utf-8"), EOS] for s in samples]
    if max(map(len, target_rows)) > 128:
        raise ValueError("calibration utterance too long")
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    rng, losses, saved = random.Random(seed), [], []
    started = time.monotonic()
    model.train()
    for step in range(steps):
        indices = [rng.randrange(len(samples)) for _ in range(min(batch_size, len(samples)))]
        rows = [target_rows[i] for i in indices]
        length = max(map(len, rows))
        ids = torch.full((len(rows), length), EOS, dtype=torch.long, device=device)
        labels = torch.full_like(ids, -100)
        for i, row in enumerate(rows):
            ids[i, :len(row)] = torch.tensor(row, device=device)
            labels[i, :len(row)] = ids[i, :len(row)]
        prefix = model.condition(data[indices])
        joined = torch.cat([prefix, model.lm.token(ids)], dim=1)
        target = torch.cat([torch.full(prefix.shape[:2], -100, device=device, dtype=torch.long), labels], dim=1)
        loss = model.lm(inputs_embeds=joined, labels=target).loss
        if not torch.isfinite(loss):
            raise ValueError("nonfinite scratch temporal decoder loss")
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % 100 == 0 or step == steps - 1:
            losses.append({"step": step + 1, "loss": float(loss.detach().cpu())})
            check()
        if step + 1 in checkpoints:
            target_path = Path(output).with_name(Path(output).stem + f"-step{step + 1}.safetensors")
            saved.append(save(model, target_path, {"steps": step + 1, "loss_samples": losses,
                                                  "samples": len(samples), "initial": str(initial)}))
    metadata = save(model, output, {"steps": steps, "samples": len(samples), "loss_samples": losses,
                                   "initial": str(initial), "wall_seconds": time.monotonic() - started,
                                   "parameters": sum(p.numel() for p in model.parameters()), "device": device})
    check()
    return metadata | {"checkpoints": saved}
