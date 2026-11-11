import copy

import numpy as np
import pytest

from threemind_transformer.development import StreamInput, TrajectoryBasis, activity_changes, character_vectors
from threemind_transformer.language_protocol import LanguageProtocol


def test_stream_causal_prefix_and_normalization_and_measured_dose():
    torch = pytest.importorskip("torch")
    from threemind_transformer.scratch_language import ScratchTransformer

    torch.set_num_threads(1)
    model = ScratchTransformer(LanguageProtocol(scratch_width=64)).eval()
    short = character_vectors("甲是", model)
    long = character_vectors("甲是红球。", model)
    np.testing.assert_allclose(short, long[:2], atol=2e-6)
    np.testing.assert_allclose(character_vectors("甲？", model), character_vectors("甲?", model), atol=1e-6)
    spec = StreamInput(top_k=4)
    frame = spec.frame(long[0], 2)["stimulus"]
    assert frame.time_us == 40000 and len(frame.channels) == 4
    assert sum(v for _, v in frame.channels) == pytest.approx(1)
    with pytest.raises(ValueError):
        spec.frame(np.zeros(64), 0)


def test_basis_keeps_unfamiliar_activity_without_mutation():
    process = {"start_us": "0", "planned_end_us": "20", "trajectory": [
        {"time_us": "0", "nodes": [{"id": "1", "channel": 5, "activation": 0.2}]},
        {"time_us": "20", "nodes": [{"id": "2", "channel": 8, "activation": 0.7}]}]}
    before = copy.deepcopy(process)
    basis = TrajectoryBasis((5,), bins=2, residual_buckets=2)
    projected = basis.project(process)
    assert projected["unknown_channels"] == [8]
    assert projected["node_samples"] == 2 and projected["unknown_node_samples"] == 1
    assert np.asarray(projected["values"])[1].sum() == pytest.approx(0.7)
    assert process == before
    process["trajectory"].reverse()
    with pytest.raises(ValueError, match="ordered"):
        basis.project(process)


def test_rises_do_not_invent_a_causal_source():
    process = {"trajectory": [
        {"nodes": [{"id": "1", "activation": 0.2}]}, {"nodes": []},
        {"nodes": [{"id": "1", "activation": 0.3}]}]}
    result = activity_changes(process)
    assert result["reentries"] == 1
    assert "description_only" in result["interpretation"]


def test_scratch_trajectory_decoder_roundtrip_and_no_context(tmp_path):
    torch = pytest.importorskip("torch")
    from threemind_transformer.development_model import fit, load

    torch.set_num_threads(1)
    basis = TrajectoryBasis((5, 8), bins=2, residual_buckets=2)
    values = np.zeros((2, 4)).tolist()
    target = tmp_path / "model.safetensors"
    result = fit([{"values": values, "text": ""}, {"values": values, "text": "甲"}],
                 basis, target, steps=2, checkpoints=())
    assert not result["pretrained_weights"]
    model, _ = load(target)
    before = model.decode([values], maximum_tokens=3)
    model.decode([np.ones((2, 4)).tolist()], maximum_tokens=3)
    assert model.decode([values], maximum_tokens=3) == before
    assert before[0]["exposure"] == ["anonymous_activity_trajectory"]
    with pytest.raises(FileExistsError):
        fit([{"values": values, "text": "a"}] * 2, basis, target, steps=1, checkpoints=())


def test_visual_teaching_has_physical_rays_and_distinct_materials():
    pytest.importorskip("mujoco")
    from lab.tools.language_teaching_world import TeachingWorld

    world = TeachingWorld()
    samples = [world.sample(i, 0) for i in range(4)]
    assert all(s["rays"][0]["distance_m"] > 0 for s in samples)
    assert len({tuple(s["rays"][0]["rgb"]) for s in samples}) == 4
    assert all(sum(v for _, v in world.frame(s).channels) == pytest.approx(2) for s in samples)


def test_observation_and_projection_leave_runtime_dynamics_unchanged():
    from threemind_core import Stimulus
    from threemind_transformer.language_session import LanguageSession

    sessions = [LanguageSession(LanguageProtocol().model_dump(), seed=17) for _ in range(2)]
    frames = [{"stimulus": Stimulus(0, ((1001, 0.5), (1002, 0.4))), "labels": {}}]
    for value in sessions:
        value.reader.schedule(frames, source="observer-invariance", adapter_id="test")
    basis = TrajectoryBasis((1001, 1002))
    observed = []
    for when in range(0, 1000001, 20000):
        for value in sessions:
            value.reader.advance_to(when)
        observed.append({"time_us": str(when), "nodes": [
            {"id": str(n["id"]), "channel": n["channel"], "activation": n["activation"]}
            for n in sessions[0].engine.observation_nodes()]})
        process = {"start_us": "0", "planned_end_us": "1000000", "trajectory": observed}
        basis.project(process)
        activity_changes(process)
    assert sessions[0].engine.capture_state().digest == sessions[1].engine.capture_state().digest
