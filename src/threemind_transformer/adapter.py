"""Explicit optional external probabilities; no automatic Core subscription."""

import ipaddress
import math
import re
from urllib.parse import urlsplit

from .protocol import Prediction, digest


def validate_response(value, tokens, model_hash=None):
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "model_sha256",
            "request_hash",
            "tokens",
            "probabilities",
            "external_contribution",
            "core_feedback",
        }
        or value["schema"] != "threemind.probabilities/1"
    ):
        raise ValueError("unsupported probability response")
    values = value["probabilities"]
    if (
        not isinstance(values, list)
        or not 2 <= len(values) <= 4096
        or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values)
        or abs(sum(values) - 1) > 1e-5
    ):
        raise ValueError("invalid probability distribution")
    if not isinstance(value["model_sha256"], str) or not re.fullmatch("[a-f0-9]{64}", value["model_sha256"]):
        raise ValueError("invalid model provenance")
    if model_hash is not None and value["model_sha256"] != model_hash:
        raise ValueError("remote model identity changed")
    if (
        value["tokens"] != tokens
        or value["request_hash"] != digest(tokens)
        or value["external_contribution"] is not True
        or value["core_feedback"] is not False
    ):
        raise ValueError("probability provenance mismatch")
    return value


def remote_probabilities(url, tokens, *, model_hash, allow_remote=False, token=None, timeout=10, transport=None):
    import httpx

    tokens = Prediction(tokens=tokens).tokens
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("use an explicit HTTP endpoint without credentials in its URL")
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname.lower() == "localhost"
    if not local and not allow_remote:
        raise ValueError("remote calls require explicit allow_remote; local execution is the default")
    if not 0 < timeout <= 60:
        raise ValueError("timeout must be in (0,60] seconds")
    headers = {"Authorization": "Bearer " + token} if token else {}
    # No environment proxy, redirect or unbounded response buffering.
    with (
        httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False, transport=transport) as client,
        client.stream("POST", url, json={"tokens": tokens}, headers=headers) as response,
    ):
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > 262144:
                raise ValueError("remote probability response exceeds 256 KiB")
    import json

    return validate_response(json.loads(raw), tokens, model_hash)


def probability_frame(response, channel_ids, *, time_us, intensity):
    """Prepare, never submit, an explicit external input with a declared channel map."""
    from threemind_core import Stimulus

    validate_response(response, response["tokens"])
    if (
        not isinstance(channel_ids, list)
        or len(channel_ids) != len(response["probabilities"])
        or len(set(channel_ids)) != len(channel_ids)
    ):
        raise ValueError("every output token requires a distinct declared physical input channel")
    if type(intensity) not in (int, float) or not math.isfinite(intensity) or not 0 <= intensity <= 1:
        raise ValueError("explicit feedback intensity must lie in [0,1]")
    stimulus = Stimulus.from_dict(
        {
            "time_us": str(time_us),
            "channels": list(zip(channel_ids, response["probabilities"], strict=True)),
            "intensity": intensity,
        }
    )
    metadata = {
        "source": "external-transformer-probabilities",
        "adapter_id": "transformer-probability",
        "external_contribution": True,
        "model_sha256": response["model_sha256"],
        "request_hash": response["request_hash"],
        "mapping_hash": digest(channel_ids),
        "explicit_feedback": True,
    }
    return {"stimulus": stimulus, "metadata": metadata}


def contract():
    from threemind_runtime.external_contracts import probability_contract
    return probability_contract()
