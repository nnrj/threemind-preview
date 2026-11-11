"""Declared simulated body signals, without rewards, semantic wiring or Core mutation."""

import math
from dataclasses import replace
from typing import Literal

from pydantic import Field

from .adapters import channel_id
from .world_schema import Model, Positive, Unit


class BodyStateSenses(Model):
    schema_id: Literal["threemind.body-state-senses/1"] = "threemind.body-state-senses/1"
    enabled: bool = True
    reserve_enabled: bool = True
    damage_enabled: bool = True
    resource_enabled: bool = True
    reserve_port: int = Field(default=4092, ge=0, le=4095)
    damage_port: int = Field(default=4093, ge=0, le=4095)
    resource_port: int = Field(default=4094, ge=0, le=4095)
    reserve_scale: Positive | None = None
    damage_scale: Positive | None = None
    resource_radius_multiplier: Positive = 2.0
    gain: Positive = 1.0
    intensity: Unit = 1.0

    def validate_ports(self, world):
        used = {s.port for s in world.sensors}
        if self.enabled:
            for kind in ("reserve", "damage", "resource"):
                if getattr(self, kind + "_enabled"):
                    port = getattr(self, kind + "_port")
                    if port in used:
                        raise ValueError("body-state sensory ports must not collide with world ports or each other")
                    used.add(port)


def transduce(config, world_spec, physical_frame, ledger, identity, position, seed):
    """Join one complete body sample at its existing timestamp, preserving raw facts.

    The resource field is an explicit radial simulator field, not diffusion or
    occlusion physics. Its formula conveys proximity and stock, never desirability.
    """
    config.validate_ports(world_spec)
    body, rules = ledger.accounts[identity], ledger.rules
    habitat = "shared" if rules.habitat == "shared" else identity
    pools = ledger.pools[habitat]
    patches = [
        {
            "id": patch.id,
            "distance": math.dist(position, patch.position),
            "stock": pools[patch.id],
            "capacity": patch.capacity,
            "sense_radius": patch.radius * config.resource_radius_multiplier,
        }
        for patch in sorted(rules.patches, key=lambda item: item.id)
    ]
    for patch in patches:
        patch["contribution"] = (
            max(0.0, 1.0 - patch["distance"] / patch["sense_radius"]) * patch["stock"] / patch["capacity"]
        )
    normalized = {
        "reserve": body.reserve / (config.reserve_scale or rules.reserve_capacity),
        "damage": body.damage / (config.damage_scale or rules.fatal_damage),
        "resource": math.fsum(patch["contribution"] for patch in patches),
    }
    mask = channel_id(seed, "world-port-v1:" + world_spec.wiring_namespace, 0)
    channels, encoded = list(physical_frame.channels), {}
    if config.enabled:
        for kind, value in normalized.items():
            if getattr(config, kind + "_enabled"):
                channel = (getattr(config, kind + "_port") << 20) ^ mask
                amplitude = min(1.0, config.gain * value) * config.intensity
                encoded[kind] = {"channel": channel, "amplitude": amplitude}
                if amplitude:
                    channels.append((channel, amplitude))
    result = physical_frame if not config.enabled else replace(physical_frame, channels=tuple(sorted(channels)))
    return result, {
        "schema": "threemind.body-state-observation/1",
        "configuration": config.model_dump(mode="json"),
        "time_us": str(ledger.time_us),
        "individual": identity,
        "habitat": habitat,
        "reserve": body.reserve,
        "reserve_capacity": rules.reserve_capacity,
        "damage": body.damage,
        "body_alive": body.alive,
        "patches": patches,
        "normalized": normalized,
        "encoded": encoded,
        "field_model": "radial-linear-stock-field; no diffusion or occlusion solver",
        "core_energy_coupling": False,
        "frame_grouping": "whole-body-sample",
    }
