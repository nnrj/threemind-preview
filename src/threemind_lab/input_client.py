"""Small database-independent CLI client; provenance is logical, not an access credential."""

import math

from threemind_runtime.sensory import TextSensorConfig

from .client_auth import client_from_arguments


def submit_text(args, request_id):
    intensity = getattr(args, "intensity", None)
    preset = getattr(args, "preset", None)
    if preset is not None:
        from threemind_runtime.stimulus_presets import resolve_intensity

        intensity = resolve_intensity(intensity, preset)
    if intensity is not None and (
        isinstance(intensity, bool) or not math.isfinite(intensity) or not 0 <= intensity <= 100
    ):
        raise ValueError("刺激强度必须为 0 至 100 的有限数值。")
    with client_from_arguments(args) as client:
        root = f"/api/v2/projects/{args.project}/runs/{args.run}"
        run = client.request("GET", root)
        limit = TextSensorConfig(**run["spec"].get("text_sensor", {})).max_carrier_characters
        with args.file.open(encoding="utf-8") as stream:
            text = stream.read(limit + 1)
        if len(text) > limit:
            raise ValueError(f"text carrier exceeds the model limit of {limit} characters")
        return client.request(
            "POST", root + "/inputs",
            body={
                "adapter_id": "text-sensor",
                "source_id": "cli-text",
                "payload": {"text": text} | ({"intensity": intensity} if intensity is not None else {}),
                "request_id": str(request_id),
                "delay_us": args.delay_us,
            },
        )
