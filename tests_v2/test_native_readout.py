import copy
import numpy as np
import pytest

from threemind_transformer.native_readout import NativeProjection, PrototypeLanguage
from lab.tools.native_expression import FeatureCalibration


def process():
    return {"start_us": "0", "end_us": "100", "planned_end_us": "100", "answer": "not_model_input",
        "trajectory": [
            {"time_us": "0", "nodes": [{"channel": 1, "activation": 1}, {"channel": 2, "activation": 0.2}]},
            {"time_us": "100", "nodes": [{"channel": 2, "activation": 0.4}, {"channel": 3, "activation": 0.1}]}]}


def test_input_mask_metadata_and_source_immutability():
    source = process()
    before = copy.deepcopy(source)
    projection = NativeProjection((2,), (1,), bins=2)
    first = projection.project(source)
    assert source == before
    source["answer"] = "different"
    source["trajectory"][0]["nodes"][0]["activation"] = 999
    assert projection.project(source) == first
    assert first["unknown_channels"] == [3]
    assert first["raw_sum"] == pytest.approx(0.7)
    assert not first["all_nodes_accounted_for"]


def test_time_sequence_is_not_lost_and_weak_noise_is_not_amplified():
    projection = NativeProjection((1, 2, 3), bins=2)
    first = projection.project(process())
    reversed_process = process()
    frames = reversed_process["trajectory"]
    frames[0]["nodes"], frames[1]["nodes"] = frames[1]["nodes"], frames[0]["nodes"]
    assert first["values"] != projection.project(reversed_process)["values"]
    for frame in reversed_process["trajectory"]:
        for node in frame["nodes"]:
            node["activation"] *= 1e-12
    weak = projection.project(reversed_process)
    assert not weak["resolvable"]
    assert np.sum(weak["values"]) == 0


def test_training_partition_and_ambiguous_queries():
    rows = [{"split": "train", "values": [[1, 0]], "text": "甲。"},
            {"split": "train", "values": [[0, 1]], "text": "乙。"}]
    reader = PrototypeLanguage(rows)
    assert reader.decode([[[1, 0]], [[0, 1]], [[0, 0]], [[1, 1]]])[0]["text"] == "甲。"
    assert [r["text"] for r in reader.decode([[[0, 0]], [[1, 1]]])] == ["", ""]
    assert PrototypeLanguage.from_dict(reader.to_dict()).decode([[[0, 1]]])[0]["text"] == "乙。"
    with pytest.raises(ValueError, match="training"):
        PrototypeLanguage(rows + [{"split": "test", "values": [[1, 0]], "text": "leak"}])


def test_channel_scope_and_nonfinite_validation():
    with pytest.raises(ValueError, match="excluded"):
        NativeProjection((1,), (1,))
    with pytest.raises(ValueError):
        NativeProjection((1,), minimum_magnitude=float("nan"))
    with pytest.raises(ValueError, match="nonfinite"):
        PrototypeLanguage([{"split": "train", "values": [[float("nan")]], "text": "a"},
                           {"split": "train", "values": [[1]], "text": "b"}])


def test_feature_calibration_is_frozen_and_split_checked():
    rows = [{"split": "train", "values": [[0.01, 0]]}, {"split": "train", "values": [[0.03, 0]]}]
    calibration = FeatureCalibration.fit(rows)
    saved = calibration.to_dict()
    assert np.allclose(calibration.transform([[[0.02, 0]]]), 0)
    assert np.max(calibration.transform([[[1, 1]]])) <= 20
    assert calibration.to_dict() == saved
    with pytest.raises(ValueError, match="training"):
        FeatureCalibration.fit([{"split": "test", "values": [[0.02, 0]]}])
