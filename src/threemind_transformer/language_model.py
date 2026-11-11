"""Frozen language models with a trainable, explicitly external activity-to-prefix head."""

import hashlib
import json
import time
from pathlib import Path

from .language_assets import available, folder
from .language_protocol import LanguageTraining
from .protocol import digest


def load(identity, device, protocol, checkpoint=None):
    role = "input" if identity == "embedding" else "output"
    if getattr(protocol, role + "_model") == "scratch":
        from .scratch_language import load as scratch_load

        return scratch_load(protocol, role, device, checkpoint)
    import torch
    from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer

    if not available(identity, verify=True):
        raise ValueError(f"missing/corrupt pinned language model: install {identity} explicitly")
    path = folder(identity)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False, padding_side="left")
    cls = AutoModel if identity == "embedding" else AutoModelForCausalLM
    model = (
        cls.from_pretrained(
            path,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            attn_implementation="sdpa",
        )
        .to(device)
        .eval()
    )
    model.requires_grad_(False)
    return tokenizer, model


def encode(texts, protocol, device, check, checkpoint=None):
    import torch

    if protocol.input_model == "text":
        raise ValueError("text route uses the existing text sensor, not a Transformer")
    tokenizer, model = load("embedding", device, protocol, checkpoint)
    results = []
    for text in texts:
        if not isinstance(text, str) or not 1 <= len(text) <= 2048:
            raise ValueError("language input must contain 1..2048 characters")
        tokens = tokenizer([text], return_tensors="pt", padding=True, truncation=False)
        limit = protocol.scratch_context if protocol.input_model == "scratch" else 512
        if tokens.input_ids.shape[1] > limit:
            raise ValueError("input exceeds model context; no silent truncation")
        with torch.no_grad():
            output = model(**tokens.to(device)).last_hidden_state[:, -1, : protocol.embedding_dimensions].float()
            output = torch.nn.functional.normalize(output, dim=1)
        results.append(output[0].cpu().tolist())
        check()
    return {
        "vectors": results,
        "model_revision": model_identity(protocol, "input"),
        "normalization": "last-token, first configured dimensions, L2",
        "external_contribution": True,
        "pretrained_weights": protocol.input_model == "qwen",
    }


def model_identity(protocol, role):
    if getattr(protocol, role + "_model") == "scratch":
        from .scratch_language import architecture

        return getattr(protocol, role + "_checkpoint_sha256") or "random:" + digest(architecture(protocol))
    return protocol.embedding_revision if role == "input" else protocol.decoder_revision


def make_head(protocol, hidden_size):
    import torch

    torch.manual_seed(protocol.seed)
    head = torch.nn.Linear(protocol.feature_buckets * protocol.feature_bins, protocol.prefix_tokens * hidden_size)
    torch.nn.init.normal_(head.weight, std=0.002)
    torch.nn.init.zeros_(head.bias)
    return head


def prompt(tokenizer):
    # Constant decoder scaffold. No incoming message, lesson, answer or labels.
    return tokenizer.apply_chat_template(
        [
            {"role": "system", "content": "Express the supplied neural activity as a brief utterance. Do not explain."},
            {"role": "user", "content": "Activity:"},
        ],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_tensors="pt",
    )


def embeddings(model, head, features, prefix_ids, protocol):
    import torch

    feature = torch.tensor([features], dtype=torch.float32, device=head.weight.device)
    soft = head(feature).reshape(1, protocol.prefix_tokens, model.config.hidden_size).to(model.dtype)
    fixed = model.get_input_embeddings()(prefix_ids.to(model.device))
    return torch.cat([soft, fixed], dim=1)


def train(spec: LanguageTraining, output: Path, device, check, checkpoint=None):
    import torch
    from safetensors.torch import save_file

    protocol = spec.protocol
    tokenizer, model = load("decoder", device, protocol, checkpoint)
    if spec.train_decoder:
        model.train().requires_grad_(True)
    head = make_head(protocol, model.config.hidden_size).to(device)
    optim = torch.optim.AdamW(
        list(head.parameters()) + (list(model.parameters()) if spec.train_decoder else []), lr=spec.learning_rate
    )
    fixed = prompt(tokenizer)
    targets = [
        torch.cat(
            (
                tokenizer(s.text, return_tensors="pt", add_special_tokens=False).input_ids,
                torch.tensor([[tokenizer.eos_token_id]]),
            ),
            dim=1,
        ).to(device)
        for s in spec.samples
    ]
    if any(v.shape[1] > protocol.maximum_tokens for v in targets):
        raise ValueError("calibration utterance exceeds maximum output tokens")
    initial, final, losses = None, None, []
    started = time.monotonic()
    for step in range(spec.steps):
        if time.monotonic() - started > spec.compute.wall_seconds:
            raise TimeoutError("calibration exhausted wall budget")
        i = step % len(spec.samples)
        prefix = embeddings(model, head, spec.samples[i].features, fixed, protocol)
        target = targets[i]
        joined = torch.cat([prefix, model.get_input_embeddings()(target)], dim=1)
        labels = torch.cat([torch.full(prefix.shape[:2], -100, dtype=torch.long, device=device), target], dim=1)
        result = model(
            inputs_embeds=joined,
            attention_mask=torch.ones(joined.shape[:2], device=device),
            labels=labels,
            use_cache=False,
        )
        if not torch.isfinite(result.loss):
            raise ValueError("nonfinite mapping-head loss")
        optim.zero_grad()
        result.loss.backward()
        torch.nn.utils.clip_grad_norm_(
            list(head.parameters()) + (list(model.parameters()) if spec.train_decoder else []), 1.0
        )
        optim.step()
        final = float(result.loss.detach().cpu())
        if initial is None:
            initial = final
        if step % max(1, spec.steps // 20) == 0:
            losses.append({"step": step, "loss": final})
        check()
    metadata = {
        "schema": "threemind.language-head/1",
        "mapping_hash": protocol.mapping_hash,
        "protocol": protocol.model_dump(),
        "decoder_revision": model_identity(protocol, "output"),
        "hidden_size": model.config.hidden_size,
        "training_digest": digest(spec.model_dump()),
        "rows": len(spec.samples),
        "steps": spec.steps,
        "first_loss": initial,
        "last_loss": final,
        "loss_samples": losses,
        "base_model_frozen": not spec.train_decoder,
        "decoder_weights_embedded": spec.train_decoder,
        "held_out_validation": "not_claimed",
    }
    tensors = {k: v.detach().float().cpu().contiguous() for k, v in head.state_dict().items()}
    if spec.train_decoder:
        tensors.update({"decoder." + k: v.detach().float().cpu().contiguous() for k, v in model.state_dict().items()})
    save_file(tensors, str(output), metadata={"threemind": json.dumps(metadata)})
    return metadata | {"head_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def decode(features, protocol, head_path, device, check, *, assistance=None, checkpoint=None, _cache=None):
    import torch
    from safetensors import safe_open
    from safetensors.torch import load_file

    if len(features) != protocol.feature_bins * protocol.feature_buckets:
        raise ValueError("activity feature dimension mismatch")
    if protocol.mode != "assisted" and assistance is not None:
        raise ValueError("strict decoder cannot receive the input text or conversational history")
    exposure = ["constant_decoder_scaffold"]
    if protocol.mode == "core" or protocol.output_model == "raw":
        return {"text": None, "reason": "core_only_mode", "decoder_exposure": [], "external_contribution": False}
    if not any(features) and protocol.mode == "strict":
        return {
            "text": None,
            "reason": "zero_projected_activity",
            "decoder_exposure": [],
            "external_contribution": False,
        }
    if protocol.mode == "strict" and head_path is None:
        return {
            "text": None,
            "reason": "calibration_head_required",
            "decoder_exposure": [],
            "external_contribution": False,
        }
    key = (protocol.mapping_hash, str(head_path), str(checkpoint), device)
    if _cache is not None and key in _cache:
        tokenizer, model, fixed, head = _cache[key]
    else:
        tokenizer, model = load("decoder", device, protocol, checkpoint)
        fixed = prompt(tokenizer)
        head = None
        if head_path:
            if head_path.stat().st_size > 64 * 2**20:
                raise ValueError("head exceeds 64 MiB")
            with safe_open(str(head_path), framework="pt", device="cpu") as handle:
                meta = json.loads(handle.metadata()["threemind"])
            if meta.get("schema") != "threemind.language-head/1" or meta["mapping_hash"] != protocol.mapping_hash:
                raise ValueError("conversion head mapping identity mismatch")
            if (
                meta["decoder_revision"] != model_identity(protocol, "output")
                or meta["hidden_size"] != model.config.hidden_size
            ):
                raise ValueError("conversion head base model mismatch")
            head = make_head(protocol, model.config.hidden_size).to(device)
            tensors = load_file(str(head_path), device=device)
            if meta.get("decoder_weights_embedded"):
                if protocol.output_model != "scratch":
                    raise ValueError("unexpected trained base weights for pretrained route")
                model.load_state_dict(
                    {k.removeprefix("decoder."): v for k, v in tensors.items() if k.startswith("decoder.")}, strict=True
                )
            head.load_state_dict({k: v for k, v in tensors.items() if not k.startswith("decoder.")}, strict=True)
            head.eval()
        if _cache is not None:
            _cache[key] = (tokenizer, model, fixed, head)
    if head is not None:
        exposure += ["core_process_features", "frozen_conversion_head"]
    with torch.no_grad():
        if protocol.mode == "assisted":
            exposure += ["incoming_user_text"]
            messages = [
                {
                    "role": "system",
                    "content": "You are an explicitly external language assistant. Describe any Core interpretation as an interpretation, not a verified thought.",
                },
                {"role": "user", "content": str(assistance or "")[:2048]},
            ]
            fixed = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, enable_thinking=False, return_tensors="pt"
            )
        values = (
            embeddings(model, head, features, fixed, protocol)
            if head is not None
            else model.get_input_embeddings()(fixed.to(device))
        )
        result = model.generate(
            inputs_embeds=values,
            attention_mask=torch.ones(values.shape[:2], device=device),
            max_new_tokens=protocol.maximum_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        text = tokenizer.decode(result[0], skip_special_tokens=True).strip()
    check()
    return {
        "text": text,
        "decoder_exposure": exposure,
        "external_contribution": True,
        "mode": protocol.mode,
        "interpretation": "converter_output_requires_task_validation",
        "features_hash": digest(features),
        "decoder_revision": model_identity(protocol, "output"),
        "pretrained_weights": protocol.output_model == "qwen",
        "output_tokens": result[0].cpu().tolist(),
        "head_sha256": hashlib.sha256(head_path.read_bytes()).hexdigest() if head_path else None,
    }


def decode_many(windows, protocol, head_path, device, check, *, checkpoint=None):
    """Reuse frozen weights, never generated tokens or KV history, across windows."""
    if not 1 <= len(windows) <= 256 or protocol.mode == "assisted":
        raise ValueError("batch observation requires 1..256 windows and no assisted context")
    cache = {}
    return {
        "windows": [
            decode(row, protocol, head_path, device, check, checkpoint=checkpoint, _cache=cache) for row in windows
        ],
        "shared_generation_context": False,
    }
