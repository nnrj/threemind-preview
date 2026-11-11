import copy
from pathlib import Path
from uuid import uuid4

import pytest
import torch

from threemind_core import Stimulus
from threemind_runtime.graph_observation import EDGE_FIELDS, VERSION
from threemind_transformer.adaptive_expression import AdaptiveExpression, return_utterance
from threemind_transformer.graph_expression import GraphExpressionConfig
from threemind_transformer.local_activity import FIELDS


def observation(value=.2):
    return {"schema": VERSION, "node_fields": list(FIELDS), "edge_fields": list(EDGE_FIELDS),
            "start_us": "0", "end_us": "20000", "frames": [
                {"time_us": str(t), "nodes": [{"id": "1", "channel": 17,
                 "values": [value, .1, 0., 0., 0., 0.]}], "edges": []} for t in (0, 20000)]}


def test_teaching_is_copied_and_bounded_without_mutating_observation():
    model = AdaptiveExpression(capacity=2)
    first = observation()
    model.teach(first, "甲。", receipt="teacher-1")
    first["frames"][0]["nodes"][0]["values"][0] = .9
    assert model.samples[0]["process"]["frames"][0]["nodes"][0]["values"][0] == .2
    model.teach(observation(.3), "乙。", receipt="teacher-2")
    result = model.teach(observation(.4), "丁。", receipt="teacher-3")
    assert result["evicted_from_adapter_replay"] == "teacher-1"
    with pytest.raises(ValueError, match="duplicate"):
        model.teach(observation(), "甲。", receipt="teacher-3")
    bad = observation() | {"target": "甲。"}
    with pytest.raises(ValueError):
        model.teach(bad, "甲。", receipt="not-admissible")


def test_adaptation_resume_keeps_teacher_state_and_does_not_overwrite():
    torch.set_num_threads(2)
    cfg = GraphExpressionConfig(width=32, heads=2, node_fields=FIELDS, use_edges=False)
    adapter = AdaptiveExpression(config=cfg)
    a = observation(.2)
    before = copy.deepcopy(a)
    adapter.teach(a, "甲。", receipt="a")
    adapter.teach(observation(.8), "乙。", receipt="b")
    root = Path(__file__).resolve().parents[1] / ".work"
    temp = root / ('test-adaptive-' + uuid4().hex)
    temp.mkdir()
    try:
        folder = Path(temp) / "r1"
        adapter.adapt(folder, steps=1)
        expected = adapter.decode([a])
        restored = AdaptiveExpression.restore(folder)
        assert restored.decode([a]) == expected
        assert restored.samples == adapter.samples
        restored.adapt(Path(temp) / "r2", steps=1)
        assert restored.revision == 2 and adapter.revision == 1
        assert AdaptiveExpression.restore(folder).decode([a]) == expected
        with pytest.raises(FileExistsError):
            restored.adapt(folder, steps=1)
        with pytest.raises(ValueError):
            restored.decode([a | {"answer": "甲。"}])
    finally:
        for part in temp.iterdir():
            for file in part.iterdir():
                file.unlink()
            part.rmdir()
        temp.rmdir()
    assert a == before


def test_self_hearing_preserves_generated_words_and_encoder_payload():
    from threemind_runtime.host import create_engine
    from threemind_runtime.readout_session import ReadoutSession

    engine = create_engine(backend="native")
    reader = ReadoutSession(engine, record=lambda _: None, config={})
    calls = []
    frames = [{"stimulus": Stimulus(20000, ((912, .3),), intensity=.8), "labels": {}}]
    def encode(text):
        calls.append(text)
        return frames
    original = engine.capture_state().to_dict()
    return_utterance(reader, "并不正确的词。", encode, enabled=False)
    assert calls == [] and engine.capture_state().to_dict() == original
    receipt = return_utterance(reader, "并不正确的词。", encode, enabled=True)
    assert calls == ["并不正确的词。"] and receipt["frames"] == 1
    assert frames[0]["stimulus"].channels == ((912, .3),)
    assert reader.bus.pending_count() == 1
    reader.advance_to(20000)
    assert any(n["channel"] == 912 for n in engine.observation_nodes())
