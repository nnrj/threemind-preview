import json
from uuid import UUID

import pytest

from threemind_runtime.network import MAX_MESSAGE_BYTES, PROTOCOL, decode_frames, read_message, receptor, sequence

WIRING = UUID("a235d106-17d1-433f-81c9-a2734230265f")


def test_remote_signed_receptors_are_stable_and_preserve_raw_time_order():
    frames = [
        {"time_us": "100", "channels": [[12, -0.7], [3, 0.8], [6, 0]]},
        {"time_us": "100", "channels": [[12, 0.5]]},
    ]
    before = json.loads(json.dumps(frames))
    encoded, proof = decode_frames(frames, seed=11, wiring_id=WIRING)
    assert frames == before
    assert encoded[0]["channels"] == [[receptor(11, WIRING, 12, negative=True), 0.7], [receptor(11, WIRING, 3), 0.8]]
    assert encoded[1]["channels"] == [[receptor(11, WIRING, 12), 0.5]]
    assert encoded[0]["time_us"] == encoded[1]["time_us"] == "100"
    assert proof["raw_channel_entries"] == 4 and proof["mapped_channel_entries"] == 3
    assert encoded == decode_frames(frames, seed=11, wiring_id=str(WIRING))[0]
    assert encoded != decode_frames(frames, seed=12, wiring_id=WIRING)[0]


def test_network_json_and_codec_reject_ambiguous_or_over_budget_inputs():
    assert read_message(json.dumps({"protocol": PROTOCOL, "type": "hello"}))["type"] == "hello"
    for raw in (
        "{}",
        "[]",
        f'{{"protocol":"{PROTOCOL}","value":NaN}}',
        f'{{"protocol":"{PROTOCOL}","value":{{"x":1,"x":2}}}}',
        "x" * (MAX_MESSAGE_BYTES + 1),
    ):
        with pytest.raises(ValueError):
            read_message(raw)
    for values in ([[1, True]], [[1, float("nan")]], [[1, 1.01]], [[True, 0.1]], [[1, 0.1], [1, 0.2]], [[2**32, 0.1]]):
        with pytest.raises(ValueError):
            decode_frames([{"time_us": "0", "channels": values}], seed=11, wiring_id=WIRING)
    for frames in (
        [],
        [{"time_us": "1", "channels": []}, {"time_us": "0", "channels": []}],
        [{"time_us": "0", "channels": []}, {"time_us": "10000001", "channels": []}],
        [{"time_us": "0", "channels": [], "set_nodes": []}],
    ):
        with pytest.raises(ValueError):
            decode_frames(frames, seed=11, wiring_id=WIRING)
    with pytest.raises(ValueError, match="capacity"):
        decode_frames([{"time_us": "0", "channels": [[1, 0.1]]}] * 2, seed=11, wiring_id=WIRING, maximum_channels=1)
    assert sequence(str(2**63 - 2)) == 2**63 - 2
    for seq in (True, -1, 2**63 - 1):
        with pytest.raises(ValueError):
            sequence(seq)
