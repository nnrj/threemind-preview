import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind.frames import OutputFrame
from threemind.runtime import ConsciousnessRuntime
from threemind_adapters import TemporalConvergenceReadoutAdapter, TextSensorAdapter


def _frame(
    tick: int,
    activations: dict[int, float],
    *,
    context: dict | None = None,
    direct: tuple[int, ...] = (),
    associated: tuple[int, ...] = (),
) -> OutputFrame:
    direct_set, associated_set = set(direct), set(associated)
    nodes = tuple(
        {
            "id": node_id,
            "activation": activation,
            "inhibition": 0.0,
            "stability": .2,
            "touch_count": int(node_id in direct_set or node_id in associated_set),
            "direct_touch": activation if node_id in direct_set else 0.0,
            "associative_touch": activation if node_id in associated_set else 0.0,
        }
        for node_id, activation in activations.items()
    )
    delta = {
        "input_envelopes": [context] if context else [],
        "direct_nodes": list(direct),
        "associated_nodes": list(associated),
    }
    return OutputFrame("test-consciousness", tick, "active", {}, nodes, (), delta)


def _fast_config(**overrides):
    return {
        "enabled": True,
        "trigger_manual": True,
        "trigger_ai": False,
        "trigger_ambient": False,
        "consider_activation_strength": True,
        "ranking_mode": "composite",
        "candidate_scope": "associative-or-persistent",
        "baseline_ticks": 2,
        "min_response_ticks": 3,
        "max_response_ticks": 8,
        "settle_ticks": 3,
        "activation_threshold": .05,
        "excess_activation_min": .005,
        "baseline_noise_gain": 1.0,
        "convergence_jaccard_min": .8,
        "convergence_drift_max": .12,
        "display_limit": 7,
        **overrides,
    }


def test_temporal_readout_emits_auditable_converged_response() -> None:
    adapter = TemporalConvergenceReadoutAdapter()
    adapter.consume(_frame(1, {99: .4}), _fast_config())
    context = {
        "envelope_id": "carrier-1",
        "frame_index": 0,
        "frame_count": 1,
        "adapter_id": "text-sensor",
        "source": "ui-text",
    }
    adapter.consume(_frame(2, {1: .9, 2: .65, 99: .4}, context=context, direct=(1,), associated=(2,)), _fast_config())
    adapter.consume(_frame(3, {1: .03, 2: .62, 99: .4}), _fast_config())
    adapter.consume(_frame(4, {1: .02, 2: .61, 99: .4}), _fast_config())
    result = adapter.consume(_frame(5, {1: .01, 2: .60, 99: .4}), _fast_config())

    assert len(result["new_events"]) == 1
    event = result["new_events"][0]
    assert event["kind"] == "temporal_convergence_readout"
    assert event["classification"] == "converged"
    assert event["envelope_id"] == "carrier-1"
    assert event["start_tick"] == 2 and event["end_tick"] == 5
    assert event["rankings"][0]["node_id"] == 2
    # The unchanged pre-stimulus baseline node must not dominate the result.
    assert 99 not in event["node_ids"]
    assert event["node_metrics"][0]["active_ticks"] == 4


def test_temporal_readout_strength_weighting_is_an_explicit_presentation_option() -> None:
    context = {"envelope_id": "carrier-2", "frame_index": 0, "frame_count": 1, "adapter_id": "text-sensor", "source": "manual"}
    frames = [
        _frame(1, {}),
        _frame(2, {1: .9, 2: .3}, context=context, associated=(1, 2)),
        _frame(3, {1: .9, 2: .3}),
        _frame(4, {1: .01, 2: .3}),
        _frame(5, {1: .01, 2: .3}),
        _frame(6, {1: .01, 2: .3}),
    ]
    strong = TemporalConvergenceReadoutAdapter()
    duration = TemporalConvergenceReadoutAdapter()
    strong_result = duration_result = None
    for frame in frames:
        strong_result = strong.consume(frame, _fast_config(consider_activation_strength=True, ranking_mode="activation-integral"))
        duration_result = duration.consume(frame, _fast_config(consider_activation_strength=False, ranking_mode="duration"))
    assert strong_result and duration_result
    strong_event = strong_result["new_events"][0]
    duration_event = duration_result["new_events"][0]
    assert strong_event["configuration_snapshot"]["consider_activation_strength"] is True
    assert duration_event["configuration_snapshot"]["consider_activation_strength"] is False
    assert strong_event["rankings"][0]["node_id"] == 1
    assert duration_event["rankings"][0]["node_id"] == 2


def test_runtime_output_frame_preserves_input_envelope_only_as_audit_context() -> None:
    runtime = ConsciousnessRuntime()
    sensor = TextSensorAdapter(runtime.sensory_seed)
    frames = sensor.encode_stream("causal carrier", source="manual", frame_characters=4)
    receipt = runtime.enqueue_frames(frames, metadata={"carrier": "test"}, adapter_id="text-sensor")
    observed: list[OutputFrame] = []
    runtime.output_bus.subscribe(observed.append)
    consciousness_id = runtime.consciousness_id
    runtime.step(ticks=len(frames))

    delivered = [frame for frame in observed if frame.delta.get("input_envelopes")]
    assert len(delivered) == len(frames)
    assert {row["envelope_id"] for frame in delivered for row in frame.delta["input_envelopes"]} == {receipt["envelope_id"]}
    assert [frame.delta["input_envelopes"][0]["frame_index"] for frame in delivered] == list(range(len(frames)))
    # The audit identity is not written into graph nodes or edges.
    after = runtime.state_dict()
    assert receipt["envelope_id"] not in repr(after["nodes"])
    assert receipt["envelope_id"] not in repr(after["edges"])
    assert runtime.consciousness_id == consciousness_id
