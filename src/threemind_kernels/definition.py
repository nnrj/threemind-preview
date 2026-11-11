"""Bounded declarative input. No evaluation, imports, callbacks or arbitrary code."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from threemind_core.engine import canonical_bytes

from .registry import creation_kernel, resolve_kernel

DEFINITION_SCHEMA = "threemind.kernel-definition/1"
MAX_DEFINITION_BYTES = 1_048_576


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate definition key: {key}")
        value[key] = item
    return value


def _invalid(value):
    raise ValueError(f"nonfinite definition value: {value}")


@dataclass(frozen=True)
class KernelDefinition:
    """Owned bytes prevent mutation after validation or after computing identity."""

    payload: bytes

    @classmethod
    def parse(cls, value: dict | bytes | str):
        if isinstance(value, dict):
            value = json.dumps(value, allow_nan=False).encode()
        elif isinstance(value, str):
            value = value.encode()
        if not isinstance(value, bytes) or len(value) > MAX_DEFINITION_BYTES:
            raise ValueError("kernel definition exceeds size limit or is not JSON")
        try:
            document = json.loads(value, object_pairs_hook=_pairs, parse_constant=_invalid)
        except (RecursionError, UnicodeError) as exc:
            raise ValueError("invalid or excessively nested kernel definition") from exc
        fields = {"schema", "kernel_id", "state_schema", "hypothesis_id", "operators", "config"}
        if not isinstance(document, dict) or set(document) != fields:
            raise ValueError("unexpected or missing kernel-definition fields")
        if document["schema"] != DEFINITION_SCHEMA:
            raise ValueError("unsupported kernel-definition schema")
        descriptor = resolve_kernel(document["kernel_id"])
        if document["state_schema"] != descriptor.state_schema or document["hypothesis_id"] != descriptor.hypothesis_id:
            raise ValueError("definition contradicts its kernel's state or hypothesis identity")
        operators = [{"id": name, "phase": phase} for name, phase in descriptor.mechanisms]
        if document["operators"] != operators:
            raise ValueError("unsupported operator, version or phase order for this kernel")
        if not isinstance(document["config"], dict):
            raise ValueError("kernel configuration must be an object")  # noqa: TRY004 -- public protocol validation
        document["config"] = descriptor.configuration(document["config"]).to_dict()
        payload = json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
        if len(payload) > MAX_DEFINITION_BYTES:
            raise ValueError("normalized kernel definition exceeds size limit")
        return cls(payload)

    @classmethod
    def default(cls, kernel_id: str | None = None, config=None):
        descriptor = creation_kernel(kernel_id, config)
        return cls.parse(
            {
                "schema": DEFINITION_SCHEMA,
                "kernel_id": descriptor.kernel_id,
                "state_schema": descriptor.state_schema,
                "hypothesis_id": descriptor.hypothesis_id,
                "operators": [{"id": name, "phase": phase} for name, phase in descriptor.mechanisms],
                "config": descriptor.configuration(config).to_dict(),
            }
        )

    def to_dict(self) -> dict:
        return json.loads(self.payload)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.parse(self.payload).to_dict())).hexdigest()

    def create(self, *, backend="native"):
        # Also validate callers that bypass parse() and construct the dataclass.
        checked = self.parse(self.payload).to_dict()
        return resolve_kernel(checked["kernel_id"]).create(checked["config"], backend=backend)
