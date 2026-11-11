"""Anonymous network codec. No database, credentials, labels or topology privileges."""

import hashlib
import json
import math
from uuid import UUID

from threemind_core import Stimulus
from threemind_core.spec import timestamp

PROTOCOL = "threemind-network/2"
MAX_MESSAGE_BYTES = 131072


def read_message(raw):
    if not isinstance(raw, (str, bytes)) or len(raw.encode() if isinstance(raw, str) else raw) > MAX_MESSAGE_BYTES:
        raise ValueError("network message exceeds 128 KiB")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-finite JSON value")

    try:
        value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=constant)
    except RecursionError as error:
        raise ValueError("network JSON nesting exceeds supported depth") from error
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise ValueError("expected threemind-network/2 message")
    return value


def sequence(value):
    number = timestamp(value)
    if number > 2**63 - 2:
        raise ValueError("network sequence exceeds supported range")
    return number


def receptor(seed, wiring_id, channel, *, negative=False):
    if type(seed) is not int or not 0 <= seed < 2**32 or type(channel) is not int or not 0 <= channel < 2**32:
        raise ValueError("network seeds and channels must be unsigned 32-bit integers")
    wiring = UUID(str(wiring_id))
    raw = (
        b"threemind-network/2\0"
        + seed.to_bytes(4, "big")
        + wiring.bytes
        + channel.to_bytes(4, "big")
        + bytes([negative])
    )
    return int.from_bytes(hashlib.blake2s(raw, digest_size=4).digest(), "big")


def decode_frames(frames, *, seed, wiring_id, maximum_channels=4096, maximum_span_us=10000000):
    if not isinstance(frames, list) or not 1 <= len(frames) <= 256:
        raise ValueError("network input requires 1 to 256 frames")
    values, mapping, count = [], {}, 0
    first = prior = None
    for raw in frames:
        if not isinstance(raw, dict) or set(raw) - {"time_us", "channels", "intensity"} or "time_us" not in raw:
            raise ValueError("network frame requires time_us, channels and optional intensity")
        when = timestamp(raw["time_us"])
        first = when if first is None else first
        if (prior is not None and when < prior) or when - first > maximum_span_us:
            raise ValueError("network frame times must be ordered and within the packet span")
        prior = when
        channels = raw.get("channels")
        if not isinstance(channels, list) or len(channels) > maximum_channels:
            raise ValueError("invalid network channels or per-packet capacity")
        count += len(channels)
        if count > maximum_channels:
            raise ValueError("network packet channel-entry capacity exceeded")
        local, seen = {}, set()
        for pair in channels:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("network channels require [unsigned id, signed amplitude] pairs")
            remote, value = pair
            if type(remote) is not int or not 0 <= remote < 2**32 or remote in seen:
                raise ValueError("network channel ids must be unique unsigned 32-bit integers per frame")
            if type(value) not in (int, float) or not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError("network amplitudes must be finite numbers in [-1,1]")
            seen.add(remote)
            if not value:
                continue
            node = receptor(seed, wiring_id, remote, negative=value < 0)
            mapping[f"{remote}:{'-' if value < 0 else '+'}"] = node
            local[node] = min(1.0, local.get(node, 0.0) + abs(value))
        intensity = raw.get("intensity", 1)
        if type(intensity) not in (int, float):
            raise ValueError("network intensity must be numeric")
        values.append(Stimulus(when, tuple(local.items()), intensity).to_dict())
    return values, {
        "protocol": PROTOCOL,
        "wiring_id": str(wiring_id),
        "seed": seed,
        "raw_channel_entries": count,
        "mapped_channel_entries": sum(len(f["channels"]) for f in values),
        "polarity_receptors": mapping,
        "collision_rule": "sum magnitudes, cap at one; keep first mapped occurrence",
    }
