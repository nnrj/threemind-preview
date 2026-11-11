"""Network boundary adapters and ThreeMind Network Protocol v1.

Transport is intentionally outside InputBus/OutputBus. This module validates
network envelopes, maps remote anonymous channels into a local sensory body,
and serializes anonymous output frames for a remote observer.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict
from typing import Any

from threemind.attention import AttentionAdjustment, AttentionContext
from threemind.frames import OutputFrame, SensoryFrame

PROTOCOL = "threemind-network/1"


class NetworkProtocolError(ValueError):
    pass


class RemoteSensoryAdapter:
    """Projects remote anonymous channel identifiers into local channels."""

    def __init__(self, sensory_seed: int) -> None:
        self.seed = int(sensory_seed)

    def _channel(self, peer_id: str, remote_channel: str) -> int:
        key = self.seed.to_bytes(16, "big", signed=False)
        payload = f"network:{peer_id}:{remote_channel}".encode("utf-8", errors="replace")
        return int.from_bytes(hashlib.blake2b(payload, key=key, digest_size=8).digest(), "big") % 8192

    def decode(self, payload: dict[str, Any], *, peer_id: str) -> SensoryFrame:
        channels = payload.get("channels")
        if not isinstance(channels, dict) or not channels:
            raise NetworkProtocolError("sensory_frame.channels must be a non-empty object")
        if len(channels) > 4096:
            raise NetworkProtocolError("sensory_frame has too many channels")
        local: dict[int, float] = {}
        for remote_channel, raw in channels.items():
            try:
                value = float(raw)
            except (TypeError, ValueError) as error:
                raise NetworkProtocolError("sensory_frame channel values must be numeric") from error
            if not -1.0 <= value <= 1.0:
                raise NetworkProtocolError("sensory_frame channel value outside [-1, 1]")
            channel = self._channel(peer_id, str(remote_channel))
            local[channel] = max(-1.0, min(1.0, local.get(channel, 0.0) + value))
        intensity = max(0.0, min(2.0, float(payload.get("intensity", 1.0))))
        return SensoryFrame(source=f"network:{peer_id}", channels=local, intensity=intensity, bypass_filter=bool(payload.get("bypass_filter", False)))


class RemotePhysiologyModulator:
    """A restricted remote physiological signal for the attention gate.

    It can only globally adjust anonymous gain/budget. It has no node, edge,
    text, tool, or destination privileges.
    """

    id = "remote-physiology"

    def __init__(self, *, timeout_ticks: int = 300) -> None:
        self.timeout_ticks = max(1, int(timeout_ticks))
        self.gain = 1.0
        self.budget = 1.0
        self.updated_tick = -1

    def update(self, payload: dict[str, Any], *, tick: int) -> None:
        self.gain = max(.1, min(2.0, float(payload.get("gain", 1.0))))
        self.budget = max(.1, min(2.0, float(payload.get("budget", 1.0))))
        self.updated_tick = int(tick)

    def begin_tick(self, tick: int, _frames: Any) -> AttentionAdjustment:
        if self.updated_tick < 0 or tick - self.updated_tick > self.timeout_ticks:
            return AttentionAdjustment()
        return AttentionAdjustment(score_multiplier=self.gain, strength_multiplier=self.gain, budget_multiplier=self.budget)

    def adjust(self, _context: AttentionContext) -> AttentionAdjustment:
        return AttentionAdjustment()


class NetworkTransportAdapter:
    """Protocol codec used by a WebSocket/HTTP application transport."""

    def __init__(self, token: str | None) -> None:
        self.token = token or ""

    def authorize_hello(self, envelope: dict[str, Any]) -> str:
        if envelope.get("type") != "hello" or envelope.get("protocol") != PROTOCOL:
            raise NetworkProtocolError("expected threemind-network/1 hello")
        peer_id = str(envelope.get("peer_id") or "")
        token = str(envelope.get("token") or "")
        if not peer_id or len(peer_id) > 128:
            raise NetworkProtocolError("hello.peer_id is required")
        if not self.token or not hmac.compare_digest(token, self.token):
            raise NetworkProtocolError("network authentication failed")
        return peer_id

    @staticmethod
    def validate_message(envelope: dict[str, Any]) -> str:
        if envelope.get("protocol") != PROTOCOL:
            raise NetworkProtocolError("unsupported network protocol")
        message_type = str(envelope.get("type") or "")
        if message_type not in {"sensory_frame", "modulation_frame"}:
            raise NetworkProtocolError("unsupported network message type")
        return message_type

    @staticmethod
    def output_envelope(frame: OutputFrame) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL, "type": "output_frame", "consciousness_id": frame.consciousness_id,
            "tick": frame.tick, "life_state": frame.life_state, "metrics": frame.metrics,
            "nodes": list(frame.nodes), "edges": list(frame.edges), "delta": frame.delta,
        }
