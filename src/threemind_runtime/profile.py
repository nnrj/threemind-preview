"""Portable sensory wiring, separate from the dynamical Core state."""

import hashlib
import json
from dataclasses import asdict, fields

from .media import MEDIA_CONFIGS
from .sensory import TextSensorConfig
from .source_policies import SourcePolicies
from .telemetry import METRICS, TELEMETRY_CONFIGS, SignalConfig

PROFILE_SCHEMA = "threemind.runtime-profile/6"
POLICY_SCHEMAS = ("threemind.runtime-profile/5", PROFILE_SCHEMA)
OUTPUT_CADENCE_SCHEMAS = ("threemind.runtime-profile/4", *POLICY_SCHEMAS)
TELEMETRY_SCHEMAS = ("threemind.runtime-profile/3", *OUTPUT_CADENCE_SCHEMAS)
LEGACY_OUTPUT_FIELDS = {
    "acoustic_output": {"enabled", "maximum_voices", "minimum_activation"},
    "activation_projector": {"enabled", "width", "height"},
}


def profile_config(cls, value):
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls)}:
        raise ValueError(f"missing or unknown {cls.__name__} profile field")
    return cls(**value)


def validate_profile(value):
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or value.get("schema") not in ("threemind.runtime-profile/1", "threemind.runtime-profile/2", *TELEMETRY_SCHEMAS)
        or set(value)
        != (
            {"schema", "sensory_seed", "text_sensor"}
            | (set(MEDIA_CONFIGS) if value.get("schema") != "threemind.runtime-profile/1" else set())
            | (set(TELEMETRY_CONFIGS) if value.get("schema") in TELEMETRY_SCHEMAS else set())
            | ({"source_policies"} if value.get("schema") in POLICY_SCHEMAS else set())
        )
    ):
        raise ValueError("unsupported runtime profile")
    if type(value["sensory_seed"]) is not int or not 0 <= value["sensory_seed"] < 2**32:
        raise ValueError("invalid sensory seed in runtime profile")
    try:
        config = profile_config(TextSensorConfig, value["text_sensor"])
    except (TypeError, KeyError) as error:
        raise ValueError("invalid text sensor profile") from error
    result = {"schema": value["schema"], "sensory_seed": value["sensory_seed"], "text_sensor": asdict(config)}
    if value["schema"] != "threemind.runtime-profile/1":
        for root, cls in MEDIA_CONFIGS.items():
            try:
                if value["schema"] not in OUTPUT_CADENCE_SCHEMAS and root in LEGACY_OUTPUT_FIELDS:
                    saved = value[root]
                    if not isinstance(saved, dict) or set(saved) != LEGACY_OUTPUT_FIELDS[root]:
                        raise ValueError(f"missing or unknown legacy {root} profile field")
                    cfg = asdict(cls(**saved))
                    result[root] = {key: cfg[key] for key in saved}
                else:
                    result[root] = asdict(profile_config(cls, value[root]))
            except TypeError as error:
                raise ValueError(f"invalid {root} profile") from error
    if value["schema"] in TELEMETRY_SCHEMAS:
        for root, cls in TELEMETRY_CONFIGS.items():
            config = value[root]
            if (
                not isinstance(config, dict)
                or not isinstance(config.get("signals"), dict)
                or set(config["signals"]) != set(METRICS[cls.scope])
            ):
                raise ValueError("missing or unknown telemetry profile signal")
            for signal in config["signals"].values():
                profile_config(SignalConfig, signal)
            if value["schema"] != PROFILE_SCHEMA:
                if "intensity" in config:
                    raise ValueError("legacy telemetry profile cannot declare intensity")
                restored = asdict(profile_config(cls, config | {"intensity": 1.0}))
                restored.pop("intensity")
                result[root] = restored
            else:
                result[root] = asdict(profile_config(cls, config))
    if value["schema"] in POLICY_SCHEMAS:
        result["source_policies"] = asdict(profile_config(SourcePolicies, value["source_policies"]))
    return result


def profile_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def read_profile(document):
    profile = document.get("runtime_profile")
    if profile is not None and document.get("runtime_profile_hash") != profile_hash(profile):
        raise ValueError("runtime profile checksum failed")
    if profile is None and "runtime_profile_hash" in document:
        raise ValueError("missing runtime profile")
    return validate_profile(profile)


def profile_fields(profile):
    profile = validate_profile(profile)
    return {"runtime_profile": profile, "runtime_profile_hash": profile_hash(profile)} if profile is not None else {}


def profile_from_spec(spec):
    return validate_profile(
        {
            "schema": PROFILE_SCHEMA,
            "sensory_seed": spec["seed"],
            "text_sensor": asdict(TextSensorConfig(**spec.get("text_sensor", {}))),
            "source_policies": asdict(SourcePolicies(**spec.get("source_policies", {}))),
            **{root: asdict(cls(**spec.get(root, {}))) for root, cls in MEDIA_CONFIGS.items()},
            **{
                root: asdict(
                    cls(
                        **spec.get(
                            root,
                            {"enabled": True} if root == "host_telemetry" and spec.get("environment") == "host" else {},
                        )
                    )
                )
                for root, cls in TELEMETRY_CONFIGS.items()
            },
        }
    )
