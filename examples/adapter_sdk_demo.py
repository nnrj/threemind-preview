"""Offline binary-driver fixture through uniform anonymous wiring; no hardware I/O.

Run: python -X utf8 examples/adapter_sdk_demo.py
Real deployment must replace the fixture source with the device driver, retain
raw measurements/calibration/times, and use the corresponding Runtime host.
"""

import json
import struct

from threemind_core import Stimulus
from threemind_runtime.adapter_checks import check_input_encoder
from threemind_runtime.network import decode_frames

SENSORY_SEED = 23
WIRING_ID = "fefb3009-5c18-4de6-bd60-bdfe781f3393"


def encode_pcm_fixture(raw: bytes):
    """One signed PCM16 sample per channel; normalisation is instrument calibration."""
    if len(raw) != 8:
        raise ValueError("this explicit fixture requires four little-endian PCM16 samples")
    samples = struct.unpack("<hhhh", raw)
    frames, evidence = decode_frames(
        [{"time_us": "0", "channels": [[channel, value / 32768] for channel, value in enumerate(samples)]}],
        seed=SENSORY_SEED,
        wiring_id=WIRING_ID,
    )
    # Production hosts persist the raw carrier and this codec evidence separately
    # from the Core. No semantic region, actuator goal or edge is prescribed here.
    assert evidence["wiring_id"] == WIRING_ID
    return [Stimulus.from_dict(frame) for frame in frames]


if __name__ == "__main__":
    print(json.dumps(check_input_encoder(encode_pcm_fixture, struct.pack("<hhhh", 1000, -2000, 500, 0)), indent=2))
