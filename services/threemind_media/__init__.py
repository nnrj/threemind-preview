"""Host-side media ingress, codec and audit services for ThreeMind.

This package is intentionally outside :mod:`threemind` Core.  It stores raw
carriers, decodes codecs and keeps transport audit records; only anonymous
``SensoryFrame`` objects cross the Core boundary.
"""
from .codec import DecodedAudio, DecodedVideoFrame, MediaCodecService, MediaDependencyError
from .protocol import LiveAudioPacket, LiveVideoPacket, MediaProtocolError, decode_live_packet
from .storage import MediaAsset, MediaAuditStore, MediaSizeLimitError

__all__ = [
    "DecodedAudio", "DecodedVideoFrame", "MediaCodecService", "MediaDependencyError",
    "LiveAudioPacket", "LiveVideoPacket", "MediaProtocolError", "decode_live_packet",
    "MediaAsset", "MediaAuditStore", "MediaSizeLimitError",
]
