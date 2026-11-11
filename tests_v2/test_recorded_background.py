import json
from types import SimpleNamespace

import pytest

from lab.tools.recorded_background import RecordedBackground


def test_recorded_time_dose_and_sources_survive_checkpoint_boundary(tmp_path):
    path = tmp_path / "tape.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "time_us": str(t),
                    "scope": s,
                    "stimulus": {
                        "time_us": str(t),
                        "channels": [[42, 0.7]],
                        "intensity": 0.2,
                    },
                }
            )
            for t, s in [(10, "host"), (10, "process"), (20, "host")]
        ),
        encoding="utf-8",
    )
    scheduled = []
    reader = SimpleNamespace(
        engine=SimpleNamespace(time_us=0), schedule=lambda frames, **kw: scheduled.append((frames, kw))
    )
    tape = RecordedBackground(path)
    cursor = tape.queue_before(reader, 0, 20)
    assert cursor == 2
    reader.engine.time_us = 20
    assert tape.queue_before(reader, cursor, 30) == 3
    assert [kw["at"] for _, kw in scheduled] == [10, 10, 20]
    assert [kw["source"] for _, kw in scheduled[:2]] == ["recorded-physical-host", "recorded-physical-process"]
    assert all(frames[0]["stimulus"].intensity == 0.2 for frames, _ in scheduled)
    assert all(frames[0]["stimulus"].time_us == 0 for frames, _ in scheduled)
    with pytest.raises(ValueError, match="late or twice"):
        tape.queue_before(reader, 0, 30)


def test_secondary_basis_probe_preserves_full_background_trajectory():
    from lab.tools.language_observation import embedding_basis_peaks
    from threemind_transformer.language_protocol import LanguageProtocol
    from threemind_transformer.language_senses import ProcessFeatures, embedding_frame

    protocol = LanguageProtocol(embedding_dimensions=32)
    language = embedding_frame([0.1] * 32, protocol).channels[0][0]
    frame = {
        "time_us": 0,
        "nodes": [
            {"id": 1, "channel": language, "activation": 0.2},
            {"id": 2, "channel": language ^ 0x10000, "activation": 0.7},
        ],
    }
    observer = ProcessFeatures(protocol, 0, 500000)
    observer.observe_frame(frame)
    full = observer.result()
    before = json.dumps(full)
    probe = embedding_basis_peaks(full, protocol)
    assert probe["outside_basis_node_samples"] == 1
    assert probe["outside_basis_peak_total"] == 0.7
    assert max(probe["values"]) == 0.2
    assert len(full["trajectory"][0]["nodes"]) == 2
    assert json.dumps(full) == before
