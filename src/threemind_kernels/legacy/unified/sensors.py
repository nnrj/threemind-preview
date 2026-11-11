"""Replaceable external carrier adapters for ThreeMind."""
from __future__ import annotations

import hashlib
import math
import random
import secrets
import unicodedata

from .frames import SensoryFrame


class TextSensorAdapter:
    """External text carrier adapter with immutable per-model encodings.

    ``anonymous-distributed`` is the standard V2/V3 carrier.  It never creates
    readable labels.  ``labeled-observation`` uses precisely the same channel
    pulses while attaching display-only labels to existing channels.  In
    ``literal-character`` mode, each normalized Unicode character projects to
    one stable, readable channel.  Labels are external sensory metadata; they
    never participate in Core dynamics.
    """

    ENCODINGS = {"anonymous-distributed", "labeled-observation", "literal-character", "legacy-labeled"}

    def __init__(self, seed: int, *, labeled: bool = False, channels: int = 192, encoding: str | None = None) -> None:
        self.seed, self.labeled, self.channels = int(seed), bool(labeled), max(32, int(channels))
        self.encoding = encoding or ("legacy-labeled" if labeled else "anonymous-distributed")
        if self.encoding not in self.ENCODINGS:
            raise ValueError(f"unsupported text sensory encoding: {self.encoding}")
        self.labeled = self.encoding != "anonymous-distributed"
        self.channel_labels: dict[int, str] = {}

    def _channel(self, payload: bytes) -> int:
        return int.from_bytes(hashlib.blake2b(payload, key=self.seed.to_bytes(16, "big", signed=False), digest_size=8).digest(), "big") % self.channels

    def _literal_channel(self, character: str) -> int:
        # Do not fold literal characters into the finite distributed channel
        # bank.  A readable baseline needs a stable one-character receptor
        # identity, while the runtime's max-node limit remains the resource
        # boundary.
        digest = hashlib.blake2b(
            ("literal-character:\0" + character).encode("utf-8", errors="replace"),
            key=self.seed.to_bytes(16, "big", signed=False), digest_size=8,
        ).digest()
        return int.from_bytes(digest, "big")

    def _encode_normalized(
        self,
        carrier: str,
        *,
        intensity: float = 1.0,
        source: str = "manual",
        bypass_filter: bool = False,
        byte_offset: int = 0,
        previous_byte: int | None = None,
        total_payload_length: int | None = None,
        include_length_feature: bool = True,
        previous_symbol: str | None = None,
    ) -> SensoryFrame:
        """Encode one already-normalised temporal carrier fragment."""
        payload = carrier.encode("utf-8", errors="replace"); pulses: dict[int, float] = {}
        def add(channel: int, value: float, label: str | None = None) -> None:
            # Do not clip before normalising.  Sparse carriers need natural
            # sensory overlap to create a co-active field; early clipping made
            # long input distribute into many sub-threshold, unrelated pulses.
            pulses[channel] = pulses.get(channel, 0.0) + value
            if self.labeled and label: self.channel_labels[channel] = label[:80]
        if self.encoding == "literal-character":
            for character in carrier:
                add(self._literal_channel(character), 0.72, character)
            scale = max(1.0, math.sqrt(len(carrier) or 1))
            return SensoryFrame(source=source, channels={channel: min(1.0, value / scale) for channel, value in pulses.items()}, intensity=max(0.0, min(2.0, float(intensity))), bypass_filter=bypass_filter)
        if self.encoding == "legacy-labeled":
            symbols = [item for item in carrier.split() if item] or list(carrier)
            for index, symbol in enumerate(symbols):
                add(self._channel(b"symbol:" + symbol.encode("utf-8", errors="replace")), .58, symbol)
                prior = symbols[index - 1] if index else previous_symbol
                if prior: add(self._channel(b"pair:" + f"{prior}\u241f{symbol}".encode("utf-8", errors="replace")), .34, f"{prior}\u241f{symbol}")
        for index, byte in enumerate(payload):
            byte_channel = self._channel(b"b" + bytes([byte]))
            add(byte_channel, .42)
            prior_byte = payload[index - 1] if index else previous_byte
            if prior_byte is not None: add(self._channel(b"p" + bytes([prior_byte, byte])), .32)
            add(self._channel(b"t" + bytes([(byte_offset + index) % 11, byte])), .18)
        if self.encoding == "labeled-observation":
            # Attach labels to already-emitted byte channels only.  No extra
            # channel, pulse, or weight is introduced, so this mode preserves
            # the anonymous distributed dynamics exactly.
            for character in carrier:
                first_byte = character.encode("utf-8", errors="replace")[:1]
                if first_byte:
                    self.channel_labels[self._channel(b"b" + first_byte)] = character
        if include_length_feature and payload:
            length = total_payload_length if total_payload_length is not None else len(payload)
            add(self._channel(b"l" + bytes([min(length // 4, 31)])), .20)
        scale = max(1.0, math.sqrt(len(payload) or 1))
        return SensoryFrame(source=source, channels={channel: min(1.0, value / scale) for channel, value in pulses.items()}, intensity=max(0.0, min(2.0, float(intensity))), bypass_filter=bypass_filter)

    def encode(self, text: str, *, intensity: float = 1.0, source: str = "manual", bypass_filter: bool = False) -> SensoryFrame:
        # Normalisation is a property of the external text carrier, not of the
        # associative graph.  Do not strip the carrier: spaces and line breaks
        # are part of the external record and a temporal input stream must not
        # silently erase them.
        carrier = unicodedata.normalize("NFKC", str(text))
        return self._encode_normalized(carrier, intensity=intensity, source=source, bypass_filter=bypass_filter)

    def encode_stream(
        self,
        text: str,
        *,
        intensity: float = 1.0,
        source: str = "manual",
        bypass_filter: bool = False,
        frame_characters: int = 24,
    ) -> tuple[SensoryFrame, ...]:
        """Project a textual carrier onto a causally ordered frame stream.

        Framing belongs to the sensory device rather than Core.  It is not a
        size limit: every normalised character is represented exactly once in
        one fragment, the caller retains the original carrier in its audit
        record, and the InputBus schedules all returned frames in order.
        ``frame_characters`` merely defines the temporal resolution of this
        particular sensory channel.
        """
        carrier = unicodedata.normalize("NFKC", str(text))
        width = int(frame_characters)
        if width < 1:
            raise ValueError("frame_characters must be positive")
        if not carrier:
            return (self._encode_normalized("", intensity=intensity, source=source, bypass_filter=bypass_filter),)
        # Character boundaries avoid splitting UTF-8 code units.  Context is
        # carried across fragments so byte-pair / positional sensory features
        # retain the same ordering information as the unframed carrier.
        fragments = [carrier[offset:offset + width] for offset in range(0, len(carrier), width)]
        total_bytes = len(carrier.encode("utf-8", errors="replace"))
        byte_offset = 0
        previous_byte: int | None = None
        previous_symbol: str | None = None
        stream: list[SensoryFrame] = []
        for index, fragment in enumerate(fragments):
            payload = fragment.encode("utf-8", errors="replace")
            stream.append(self._encode_normalized(
                fragment, intensity=intensity, source=source,
                bypass_filter=bypass_filter, byte_offset=byte_offset,
                previous_byte=previous_byte, total_payload_length=total_bytes,
                include_length_feature=index == len(fragments) - 1,
                previous_symbol=previous_symbol,
            ))
            if payload:
                previous_byte = payload[-1]
                byte_offset += len(payload)
            symbols = [item for item in fragment.split() if item] or list(fragment)
            if symbols:
                previous_symbol = symbols[-1]
        return tuple(stream)

    def label_for_channel(self, channel: int) -> str | None: return self.channel_labels.get(int(channel))


class AmbientSensorAdapter:
    """Default environmental sensory adapter.

    The old V2 slow/fast/drift field remains the baseline.  It is accompanied
    by sparse, finite-lived anonymous disturbances: a continuous environment
    must be able to present things that have not been seen before, without
    assigning them a meaning or directly changing Core topology.  Their
    lifetime belongs to the sensory carrier, just as a gust or heartbeat-like
    fluctuation can disappear before it becomes a learned pattern.
    """

    def __init__(
        self,
        seed: int,
        *,
        transient_rate: float = .04,
        transient_amplitude: float = .12,
        transient_lifetime_min: int = 2,
        transient_lifetime_max: int = 14,
    ) -> None:
        self.seed = int(seed) ^ secrets.randbits(63)
        self._rng = random.Random(self.seed)
        self._slow_phase = self._rng.uniform(0.0, math.tau)
        self._fast_offset = self._rng.randrange(11)
        self._drift = self._rng.random()
        self.transient_rate = float(transient_rate)
        self.transient_amplitude = float(transient_amplitude)
        self.transient_lifetime_min = int(transient_lifetime_min)
        self.transient_lifetime_max = int(transient_lifetime_max)
        self._transients: dict[int, int] = {}

    def configure(self, values: dict[str, object]) -> None:
        self.transient_rate = max(0.0, min(1.0, float(values.get("transient_rate", self.transient_rate))))
        self.transient_amplitude = max(0.0, min(1.0, float(values.get("transient_amplitude", self.transient_amplitude))))
        self.transient_lifetime_min = max(1, int(values.get("transient_lifetime_min", self.transient_lifetime_min)))
        self.transient_lifetime_max = max(self.transient_lifetime_min, int(values.get("transient_lifetime_max", self.transient_lifetime_max)))

    def _channel(self, payload: bytes) -> int:
        return int.from_bytes(hashlib.blake2b(payload, key=self.seed.to_bytes(16, "big", signed=False), digest_size=8).digest(), "big") % 8192

    def _transient_channel(self) -> int:
        # This token is anonymous and exists only in the adapter.  It is not
        # text, a semantic category, or a hidden Core-side preference.
        return self._channel(b"ambient:transient:" + self._rng.getrandbits(128).to_bytes(16, "big"))

    def frames(self, tick: int, *, intensity: float, bypass_filter: bool = False) -> tuple[SensoryFrame, ...]:
        # Preserve the V2 field: slow, fast and drift each define only local
        # carrier regularity, never semantic structure.
        self._drift = max(0.0, min(1.0, self._drift * .86 + self._rng.random() * .14))
        slow_bucket = int((math.sin(tick / 47.0 + self._slow_phase) + 1.0) * 4)
        fast_bucket = (tick + self._fast_offset) % 11
        drift_bucket = min(12, int(self._drift * 13.0))
        baseline = {
            self._channel(f"ambient:slow:{slow_bucket}".encode()): .42,
            self._channel(f"ambient:fast:{fast_bucket}".encode()): .20,
            self._channel(f"ambient:drift:{drift_bucket}".encode()): .30,
        }
        self._transients = {channel: lifetime - 1 for channel, lifetime in self._transients.items() if lifetime > 1}
        if self._rng.random() < self.transient_rate:
            channel = self._transient_channel()
            self._transients[channel] = self._rng.randint(self.transient_lifetime_min, self.transient_lifetime_max)
        transient = {channel: self.transient_amplitude for channel in self._transients}
        bounded_intensity = max(0.0, min(2.0, float(intensity)))
        frames = [SensoryFrame(source="ambient-environment", channels=baseline, intensity=bounded_intensity, bypass_filter=bypass_filter)]
        # Disturbances are independent local sensory events.  Keeping them out
        # of the baseline frame lets a one-channel event remain an isolated,
        # forgettable trace under the default local-coactivation policy.
        if transient:
            frames.append(SensoryFrame(source="ambient-disturbance", channels=transient, intensity=bounded_intensity, bypass_filter=bypass_filter))
        return tuple(frames)

    def frame(self, tick: int, *, intensity: float, bypass_filter: bool = False) -> SensoryFrame:
        """Compatibility convenience: merge fields for simple external callers.

        The ThreeMind host uses :meth:`frames` so event boundaries are retained.
        """
        frames = self.frames(tick, intensity=intensity, bypass_filter=bypass_filter)
        channels: dict[int, float] = {}
        for frame in frames:
            for channel, value in frame.channels.items():
                channels[channel] = channels.get(channel, 0.0) + value
        return SensoryFrame(source="ambient-environment", channels=channels, intensity=frames[0].intensity, bypass_filter=bypass_filter)
