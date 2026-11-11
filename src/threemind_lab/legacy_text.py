"""Original unified frame text transport, isolated from modern receptor wiring."""

import hashlib

from threemind_kernels.legacy.unified.sensors import TextSensorAdapter
from threemind_kernels.legacy.unified_adapter import LegacyStimulus
from threemind_runtime.stimulus_presets import resolve_intensity

VERSION = "legacy-unified-text/97d8592"


def configuration(spec, run_id):
    # The original runtime derives sensory wiring from its package UUID. New Lab
    # births use the run UUID as that package UUID, before runtime construction.
    seed = int.from_bytes(hashlib.blake2b(str(run_id).encode(), digest_size=8).digest(), "big")
    return {"legacy_unified": True, "sensory_seed": seed, "encoding": spec.config["sensory_encoding"],
            "frame_characters": spec.text_sensor.frame_characters,
            "max_carrier_characters": spec.text_sensor.max_carrier_characters,
            "inter_frame_epochs": 1, "runtime_revision": "97d8592"}


def frames(payload, config):
    if set(payload) - {"text", "intensity", "preset"}:
        raise ValueError("unknown historical text carrier fields")
    text = payload.get("text")
    if not isinstance(text, str) or not text or len(text) > config["max_carrier_characters"]:
        raise ValueError("historical text carrier must be nonempty and within the declared limit")
    text.encode("utf-8")
    intensity = resolve_intensity(payload.get("intensity"), payload.get("preset"))
    if intensity > 2:
        raise ValueError("original unified text intensity cannot exceed 2; no silent clipping")
    adapter = TextSensorAdapter(config["sensory_seed"], encoding=config["encoding"])
    values = adapter.encode_stream(text, intensity=intensity, frame_characters=config["frame_characters"])
    for index, value in enumerate(values):
        yield {"stimulus": LegacyStimulus(0, value.channels, value.intensity,
                                         source=value.source, external=value.external,
                                         delay_epochs=index * config["inter_frame_epochs"]),
               "labels": {str(channel): [label] for channel, label in adapter.channel_labels.items()}}
