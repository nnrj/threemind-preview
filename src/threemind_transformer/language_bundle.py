"""Portable language device state. No Torch, Lab, or database imports."""

import hashlib
import io
import json
import zipfile

from threemind_runtime.codec import ArtifactCodec, _json

from .language_assets import registry
from .language_protocol import LanguageProtocol
from .language_session import LanguageSession

SCHEMA = "threemind.language-bundle/1"
MAX_BYTES = 256 * 2**20
ASSETS = {key: key + ".safetensors" for key in ("head", "input", "output")}


def metadata(raw):
    if not 8 < len(raw) <= 64 * 2**20:
        raise ValueError("language weights exceed bounds")
    length = int.from_bytes(raw[:8], "little")
    if not 0 < length < min(len(raw) - 8, 2**20):
        raise ValueError("invalid language weight header")
    try:
        return _json(_json(raw[8 : 8 + length])["__metadata__"]["threemind"])
    except (KeyError, TypeError) as error:
        raise ValueError("missing language weight identity") from error


def validate_assets(protocol, assets):
    if set(assets) - set(ASSETS):
        raise ValueError("unknown language asset role")
    for key in ("input", "output"):
        raw = assets.get(key)
        expected = getattr(protocol, key + "_checkpoint_sha256")
        if expected != (hashlib.sha256(raw).hexdigest() if raw is not None else None):
            raise ValueError(key + " Transformer checkpoint does not match protocol identity")
        if raw is not None:
            row = metadata(raw)
            expected_architecture = {
                "width": protocol.scratch_width,
                "heads": protocol.scratch_heads,
                "layers": protocol.scratch_layers,
                "context": protocol.scratch_context,
                "seed": protocol.seed,
                "tokenization": "utf8-bytes-bos256-eos257/1",
            }
            if row.get("schema") != "threemind.scratch-language/1" or row.get("architecture") != expected_architecture:
                raise ValueError("scratch checkpoint architecture differs from protocol")
    if assets.get("head") is not None and metadata(assets["head"]).get("mapping_hash") != protocol.mapping_hash:
        raise ValueError("conversion head uses a different frozen mapping")


def pack(image, context, assets=None):
    protocol = LanguageProtocol.model_validate(context["protocol"])
    assets = assets or {}
    validate_assets(protocol, assets)
    if context.get("schema") != "threemind.language-runtime/1":
        raise ValueError("missing language recovery context")
    parts = {
        "core.tmind": ArtifactCodec.encode(image),
        "context.json": json.dumps(context, allow_nan=False).encode(),
        **{ASSETS[key]: raw for key, raw in assets.items() if raw is not None},
    }
    if sum(map(len, parts.values())) > MAX_BYTES - 2**20:
        raise ValueError("language bundle exceeds 256 MiB")
    manifest = {
        "schema": SCHEMA,
        "state_hash": image.digest,
        "mapping_hash": protocol.mapping_hash,
        "external_models": {
            key: registry()[key]
            for key, role in (("embedding", "input"), ("decoder", "output"))
            if getattr(protocol, role + "_model") == "qwen"
        },
        "files": {key: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for key, raw in parts.items()},
    }
    output = io.BytesIO()
    # State already uses compressed Arrow. Storing members avoids nested expansion.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, allow_nan=False))
        for key, raw in parts.items():
            archive.writestr(key, raw)
    return output.getvalue()


def unpack(raw, *, backend="native"):
    if len(raw) > MAX_BYTES:
        raise ValueError("language bundle exceeds 256 MiB")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        names = [row.filename for row in rows]
        allowed = {"manifest.json", "core.tmind", "context.json", *ASSETS.values()}
        if len(names) != len(set(names)) or set(names) - allowed or sum(r.file_size for r in rows) > MAX_BYTES:
            raise ValueError("invalid or oversized language bundle members")
        if not {"manifest.json", "core.tmind", "context.json"} <= set(names):
            raise ValueError("incomplete language bundle")
        if archive.getinfo("manifest.json").file_size > 2**20 or archive.getinfo("context.json").file_size > 16 * 2**20:
            raise ValueError("language recovery metadata exceeds budget")
        manifest = _json(archive.read("manifest.json"))
        if manifest.get("schema") != SCHEMA or set(manifest["files"]) != set(names) - {"manifest.json"}:
            raise ValueError("unsupported language bundle identity")
        parts = {name: archive.read(name) for name in manifest["files"]}
    for name, value in parts.items():
        if manifest["files"][name] != {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}:
            raise ValueError("language bundle checksum mismatch")
    image = ArtifactCodec.decode(parts["core.tmind"], max_bytes=MAX_BYTES)
    context = _json(parts["context.json"])
    session = LanguageSession(context["protocol"], image=image, context=context, backend=backend)
    if image.digest != manifest["state_hash"] or session.protocol.mapping_hash != manifest["mapping_hash"]:
        raise ValueError("language recovery identity mismatch")
    expected_models = {
        key: registry()[key]
        for key, role in (("embedding", "input"), ("decoder", "output"))
        if getattr(session.protocol, role + "_model") == "qwen"
    }
    if manifest.get("external_models") != expected_models:
        raise ValueError("external language model identity differs")
    assets = {key: parts.get(name) for key, name in ASSETS.items()}
    validate_assets(session.protocol, assets)
    return session, assets
