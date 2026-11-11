"""Portable anonymous network wiring, containing no credentials or Core state."""

import hashlib
import json
from uuid import UUID

from .network import PROTOCOL, receptor

WIRING_SCHEMA = "threemind.network-wiring/1"
MAX_WIRING_BYTES = 16384


def make_wiring(seed, wiring_id):
    # Use the codec's actual identity constraints, without injecting a stimulus.
    receptor(seed, wiring_id, 0)
    fields = {
        "schema": WIRING_SCHEMA,
        "protocol": PROTOCOL,
        "sensory_seed": seed,
        "wiring_id": str(UUID(str(wiring_id))),
    }
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return fields | {"sha256": digest}


def validate_wiring(value):
    if not isinstance(value, dict) or set(value) != {"schema", "protocol", "sensory_seed", "wiring_id", "sha256"}:
        raise ValueError("missing or unknown network wiring manifest field")
    if value["schema"] != WIRING_SCHEMA or value["protocol"] != PROTOCOL:
        raise ValueError("unsupported network wiring manifest or codec")
    expected = make_wiring(value["sensory_seed"], value["wiring_id"])
    if value != expected:
        raise ValueError("network wiring checksum or canonical identity mismatch")
    return expected


def read_wiring(raw):
    if not isinstance(raw, (str, bytes)) or len(raw.encode() if isinstance(raw, str) else raw) > MAX_WIRING_BYTES:
        raise ValueError("network wiring manifest exceeds 16 KiB")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate network wiring JSON key")
            result[key] = value
        return result

    try:
        return validate_wiring(json.loads(raw, object_pairs_hook=object_pairs))
    except RecursionError as error:
        raise ValueError("network wiring nesting exceeds supported depth") from error
