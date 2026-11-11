"""Individual continual expression learning; no ownership of Core state.

Supervision and replay live outside the inference process. Every update creates
a new checkpoint. This is gradient-based continual fitting, not Core plasticity
or an implementation of a fast-weight Transformer.
"""

from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

from .graph_expression import GraphExpressionConfig, fit, load, pack_graphs
from .local_activity import FIELDS

VERSION = "threemind.adaptive-expression/1"


class AdaptiveExpression:
    def __init__(self, *, capacity=64, device="cpu", config=None):
        if type(capacity) is not int or not 2 <= capacity <= 128:
            raise ValueError("teaching replay capacity must be 2..128")
        self.capacity = capacity
        self.device = device
        self.config = config or GraphExpressionConfig(node_fields=FIELDS, use_edges=False)
        self.samples = []
        self.model = None
        self.checkpoint = None
        self.revision = 0

    def teach(self, process, text, *, receipt):
        """Register an external teacher's example, without delivering any input."""
        if not isinstance(receipt, str) or not receipt or len(receipt) > 256:
            raise ValueError("bounded teaching receipt required")
        if not isinstance(text, str) or not text or len(text.encode("utf-8")) + 1 > self.config.maximum_tokens:
            raise ValueError("bounded nonempty teaching utterance required")
        if any(row["receipt"] == receipt for row in self.samples):
            raise ValueError("duplicate teaching receipt")
        # Validate the same input contract used by inference; never add labels.
        pack_graphs([process], self.config, "cpu")
        self.samples.append({"process": copy.deepcopy(process), "text": text, "receipt": receipt})
        evicted = self.samples.pop(0)["receipt"] if len(self.samples) > self.capacity else None
        return {"receipt": receipt, "evicted_from_adapter_replay": evicted, "core_changed": False}

    def adapt(self, folder, *, steps=500, learning_rate=0.001, check=lambda: None):
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError(folder)
        if len(self.samples) < 2:
            raise ValueError("at least two teaching examples required")
        folder.mkdir(parents=True)
        # Partial failures remain reviewable; do not overwrite a failed attempt.
        with gzip.open(folder / "teaching.jsonl.gz", "xt", encoding="utf-8") as stream:
            for row in self.samples:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        model, result = fit(
            self.samples, folder / "model.safetensors", config=self.config,
            initial=self.checkpoint, steps=steps, learning_rate=learning_rate,
            device=self.device, check=check,
        )
        manifest = {
            "schema": VERSION, "revision": self.revision + 1,
            "parent_checkpoint": str(self.checkpoint) if self.checkpoint else None,
            "capacity": self.capacity, "training": result,
            "learning": "continual weights with bounded FIFO teacher replay; Adam restarted per update",
            "cross_window_fact_cache": False, "core_parameters_updated": False,
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.model, self.checkpoint = model, folder / "model.safetensors"
        self.revision += 1
        return manifest

    def decode(self, processes):
        if self.model is None:
            raise ValueError("expression adapter is not calibrated")
        # pack_graphs rejects target/label/object/history fields in observations.
        return self.model.decode(processes)

    @classmethod
    def restore(cls, folder, *, device="cpu"):
        folder = Path(folder)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest["schema"] != VERSION:
            raise ValueError("adaptive expression version mismatch")
        model, _ = load(folder / "model.safetensors", device)
        instance = cls(capacity=manifest["capacity"], device=device, config=model.config)
        with gzip.open(folder / "teaching.jsonl.gz", "rt", encoding="utf-8") as stream:
            total = 0
            for index, line in enumerate(stream):
                total += len(line.encode("utf-8"))
                if index >= instance.capacity or total > 128 * 2**20:
                    raise ValueError("checkpoint teaching replay budget exceeded")
                row = json.loads(line)
                if set(row) != {"process", "text", "receipt"}:
                    raise ValueError("teaching record contract")
                instance.teach(**row)
        instance.model, instance.checkpoint = model, folder / "model.safetensors"
        instance.revision = int(manifest["revision"])
        return instance


def return_utterance(reader, utterance, encode, *, at=None, enabled=False):
    """Explicit optional self-hearing through the caller's unchanged encoder.

    The exact generated text is returned. No target, confidence threshold or
    semantic correction is consulted. Empty text is silence. The evidence
    receipt is not a stimulus channel.
    """
    if not isinstance(utterance, str) or len(utterance) > 2048:
        raise ValueError("bounded generated utterance required")
    if not enabled or not utterance:
        return {"enabled": enabled, "text": utterance, "frames": 0, "envelope": None}
    frames = list(encode(utterance))
    envelope = reader.schedule(frames, at=at, source="self-expression", adapter_id=VERSION)
    return {"enabled": True, "text": utterance, "frames": len(frames), "envelope": envelope}
