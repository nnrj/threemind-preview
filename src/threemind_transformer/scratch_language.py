"""A byte-level causal Transformer initialized from random weights, without a pretrained tokenizer."""

import hashlib
import json
from types import SimpleNamespace

import torch
from torch import nn

from .protocol import digest

BOS, EOS, VOCABULARY = 256, 257, 258


def architecture(protocol):
    return {
        "width": protocol.scratch_width,
        "heads": protocol.scratch_heads,
        "layers": protocol.scratch_layers,
        "context": protocol.scratch_context,
        "seed": protocol.seed,
        "tokenization": "utf8-bytes-bos256-eos257/1",
    }


class Tokens(dict):
    @property
    def input_ids(self):
        return self["input_ids"]

    def to(self, device):
        return Tokens({key: value.to(device) for key, value in self.items()})


class ByteTokenizer:
    eos_token_id = EOS

    def __call__(self, text, *, add_special_tokens=True, **_):
        texts = [text] if isinstance(text, str) else text
        rows = [([BOS] if add_special_tokens else []) + list(value.encode("utf-8")) for value in texts]
        if len({len(row) for row in rows}) != 1:
            raise ValueError("scratch tokenizer batches must have equal lengths")
        return Tokens(
            input_ids=torch.tensor(rows, dtype=torch.long),
            attention_mask=torch.ones((len(rows), len(rows[0])), dtype=torch.long),
        )

    def decode(self, ids, **_):
        return bytes(int(i) for i in ids if 0 <= int(i) < 256).decode("utf-8", errors="replace")

    def apply_chat_template(self, messages, **_):
        # This scaffold is ordinary UTF-8, with no pretrained role semantics.
        return self("\n".join(message["content"] for message in messages)).input_ids


class ScratchTransformer(nn.Module):
    def __init__(self, protocol):
        super().__init__()
        self.config = SimpleNamespace(hidden_size=protocol.scratch_width)
        self.context = protocol.scratch_context
        width = protocol.scratch_width
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(protocol.seed)
            self.token = nn.Embedding(VOCABULARY, width)
            self.position = nn.Embedding(self.context, width)
            self.layers = nn.ModuleList(
                nn.TransformerEncoderLayer(
                    width,
                    protocol.scratch_heads,
                    dim_feedforward=width * 4,
                    dropout=0.0,
                    activation="gelu",
                    batch_first=True,
                    norm_first=True,
                )
                for _ in range(protocol.scratch_layers)
            )
            self.norm = nn.LayerNorm(width)
            self.output = nn.Linear(width, VOCABULARY, bias=False)

    @property
    def dtype(self):
        return self.token.weight.dtype

    @property
    def device(self):
        return self.token.weight.device

    def get_input_embeddings(self):
        return self.token

    def forward(self, input_ids=None, *, inputs_embeds=None, labels=None, **_):
        value = self.token(input_ids) if inputs_embeds is None else inputs_embeds
        if value.shape[1] > self.context:
            raise ValueError("scratch context exceeded; no silent truncation")
        value = value + self.position(torch.arange(value.shape[1], device=value.device))[None, :, :]
        mask = torch.triu(torch.ones((value.shape[1], value.shape[1]), dtype=torch.bool, device=value.device), 1)
        for layer in self.layers:
            value = layer(value, src_mask=mask)
        hidden = self.norm(value)
        logits = self.output(hidden)
        loss = (
            None
            if labels is None
            else nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, VOCABULARY).float(), labels[:, 1:].reshape(-1), ignore_index=-100
            )
        )
        return SimpleNamespace(last_hidden_state=hidden, logits=logits, loss=loss)

    def generate(self, *, inputs_embeds, max_new_tokens, **_):
        if inputs_embeds.shape[1] + max_new_tokens > self.context:
            raise ValueError("generation would exceed scratch context")
        value, result = inputs_embeds, []
        for _ in range(max_new_tokens):
            token = self(inputs_embeds=value).logits[:, -1].argmax(-1)
            result.append(token)
            if int(token[0]) == EOS:
                break
            value = torch.cat((value, self.token(token[:, None])), dim=1)
        return torch.stack(result, dim=1)


def load(protocol, role, device, checkpoint=None):
    from safetensors import safe_open
    from safetensors.torch import load_file

    expected = getattr(protocol, role + "_checkpoint_sha256")
    model = ScratchTransformer(protocol)
    if expected:
        if checkpoint is None or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != expected:
            raise ValueError("scratch checkpoint is missing or has a different identity")
        with safe_open(str(checkpoint), framework="pt", device="cpu") as handle:
            meta = json.loads(handle.metadata()["threemind"])
        if meta.get("schema") != "threemind.scratch-language/1" or meta.get("architecture") != architecture(protocol):
            raise ValueError("scratch checkpoint architecture mismatch")
        model.load_state_dict(load_file(str(checkpoint)), strict=True)
    elif checkpoint is not None:
        raise ValueError("undeclared scratch checkpoint")
    return ByteTokenizer(), model.to(device).eval().requires_grad_(False)


def train(spec, output, device, check, checkpoint=None):
    from safetensors.torch import save_file

    _tokenizer, model = load(spec.protocol, spec.role, device, checkpoint)
    model.train().requires_grad_(True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=spec.learning_rate)
    rows = [torch.tensor([[BOS, *text.encode("utf-8"), EOS]], device=device) for text in spec.texts]
    losses = []
    for step in range(spec.steps):
        ids = rows[step % len(rows)]
        loss = model(input_ids=ids, labels=ids).loss
        if not torch.isfinite(loss):
            raise ValueError("nonfinite scratch language loss")
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % max(1, spec.steps // 20) == 0 or step == spec.steps - 1:
            losses.append({"step": step, "loss": float(loss.detach().cpu())})
        check()
    metadata = {
        "schema": "threemind.scratch-language/1",
        "architecture": architecture(spec.protocol),
        "training_digest": digest(spec.model_dump()),
        "corpus_digest": digest(spec.texts),
        "rows": len(rows),
        "steps": spec.steps,
        "loss_samples": losses,
        "initial_checkpoint": getattr(spec.protocol, spec.role + "_checkpoint_sha256"),
        "pretrained_weights": False,
        "held_out_validation": "not_claimed",
    }
    save_file(
        {key: value.detach().cpu().contiguous() for key, value in model.state_dict().items()},
        str(output),
        metadata={"threemind": json.dumps(metadata)},
    )
    return metadata | {"checkpoint_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
