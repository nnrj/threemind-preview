import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind.model import ModelManifest, ModelPackage
from threemind.runtime import ConsciousnessRuntime
from threemind.frames import OutputFrame, SensoryFrame
from threemind_adapters import AmbientSensorAdapter, BodyAdapter, CharacterDriver, InteroceptiveAdapter, MetabolicEnergyAdapter, NetworkProtocolError, NetworkTransportAdapter, RemotePhysiologyModulator, RemoteSensoryAdapter, StructuralReadoutAdapter, TextSensorAdapter


# Tests use a carrier adapter, exactly as API/CLI clients do.  Core itself has
# no text-input method.
def _send(runtime: ConsciousnessRuntime, text: str, *, source: str = "manual", intensity: float = 1.0) -> None:
    adapter = TextSensorAdapter(runtime.sensory_seed, labeled=runtime.manifest.node_payload == "labeled")
    kind = "ai" if source.startswith("ai") else "ambient" if source.startswith("ambient") else "manual"
    runtime.receive_frame(adapter.encode(text, source=source, intensity=intensity, bypass_filter=kind in runtime.filter_bypass_sources), metadata={"carrier": "test"})


ConsciousnessRuntime.stimulate = _send  # type: ignore[attr-defined]


def test_empty_package_round_trip() -> None:
    artifact_dir = Path("test-artifacts")
    artifact_dir.mkdir(exist_ok=True)
    path = artifact_dir / "empty.tmind"
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(spatial_embedding=True, spatial_dimensions=3), name="test"))
    runtime.save_package(str(path))
    loaded = ModelPackage.load(path)
    assert loaded.consciousness_name == "test"
    assert loaded.manifest.package_schema_version == "3.0.0"
    assert loaded.manifest.spatial_dimensions == 3
    path.unlink(missing_ok=True)


def test_snapshot_archive_keeps_manual_or_automatic_provenance() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="archive provenance"))
    runtime.stimulate("an auditable carrier")
    path = Path("test-artifacts") / "automatic-snapshot-provenance.tmind"
    path.unlink(missing_ok=True)
    runtime.snapshot(str(path), label="repeatable structure", automatic=True, reason="repeatable_structure")

    loaded = ModelPackage.load(path)
    assert loaded.archive["kind"] == "snapshot"
    assert loaded.archive["automatic"] is True
    assert loaded.archive["reason"] == "repeatable_structure"
    assert loaded.snapshots[-1]["automatic"] is True
    assert loaded.snapshots[-1]["reason"] == "repeatable_structure"
    assert any(event.get("kind") == "archive_created" for event in loaded.state["events"])
    path.unlink(missing_ok=True)


def test_stimulus_creates_graph_without_plaintext_in_anonymous_nodes() -> None:
    runtime = ConsciousnessRuntime()
    runtime.stimulate("hello world")
    runtime.step(ticks=2)
    assert runtime.metrics()["node_count"] >= 1
    assert all("hello" not in str(node).lower() and "world" not in str(node).lower() for node in runtime.nodes.values())


def test_unspaced_stimulus_creates_a_path_without_plaintext_nodes() -> None:
    runtime = ConsciousnessRuntime()
    runtime.stimulate("你好我是人类")
    assert runtime.metrics()["node_count"] > 2
    assert runtime.metrics()["edge_count"] > 1
    assert all("你" not in str(node) and "人类" not in str(node) for node in runtime.nodes.values())


def test_spatial_model_assigns_positions() -> None:
    manifest = ModelManifest(spatial_embedding=True, spatial_dimensions=3)
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    runtime.stimulate("a b")
    assert all(len(node["position"]) == 3 for node in runtime.nodes.values())
    assert all(len(node["position"]) == 3 for node in runtime.graph()["nodes"])


def test_death_prevents_further_stimulus() -> None:
    runtime = ConsciousnessRuntime()
    runtime.die("test")
    try:
        runtime.stimulate("x")
    except RuntimeError:
        pass
    else:
        raise AssertionError("dead consciousness accepted a stimulus")


def test_continuous_runtime_advances_and_can_pause() -> None:
    runtime = ConsciousnessRuntime()
    runtime.start()
    import time
    time.sleep(0.15)
    assert runtime.running()
    assert runtime.tick > 0
    before = runtime.tick
    runtime.pause()
    time.sleep(0.15)
    assert runtime.tick == before
    runtime.stop("test")


def test_package_clone_gets_new_identity() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="parent"))
    runtime.stimulate("one two")
    clone = ModelPackage.load(runtime.save_package("test-artifacts/parent.tmind")).clone(name="child")
    assert clone.consciousness_id != runtime.consciousness_id
    assert clone.consciousness_name == "child"
    Path("test-artifacts/parent.tmind").unlink(missing_ok=True)


def test_sources_and_spatial_edges_are_model_data() -> None:
    manifest = ModelManifest(spatial_embedding=True, spatial_dimensions=3)
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    runtime.stimulate("one two")
    assert runtime.source_status()["manual"] is True
    assert all(len(edge["vector"]) == 3 for edge in runtime.edges.values())
    runtime.set_source("manual", False)
    try:
        runtime.stimulate("blocked")
    except RuntimeError:
        pass
    else:
        raise AssertionError("disabled source accepted a stimulus")


def test_spatial_neighborhoods_and_clusters_are_exposed() -> None:
    manifest = ModelManifest(spatial_embedding=True, spatial_dimensions=3, parameters={"spatial_radius": 10.0})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    runtime.stimulate("one two three")
    neighbors = runtime.spatial_neighbors()
    assert neighbors
    assert runtime.spatial_cluster_count() >= 1
    assert runtime.graph()["neighbors"]


def test_manifest_parameters_drive_runtime() -> None:
    manifest = ModelManifest(parameters={"activation_decay": 0.5, "max_nodes": 321, "tick_seconds": 0.02})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    assert runtime.config.activation_decay == 0.5
    assert runtime.config.max_nodes == 321
    assert runtime.config.tick_seconds == 0.02


def test_anonymous_sensory_mapping_is_individual_and_never_stores_carrier() -> None:
    first = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(node_payload="anonymous")))
    second = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(node_payload="anonymous")))
    first.stimulate("same external carrier")
    second.stimulate("same external carrier")
    assert first.receptor_index != second.receptor_index
    assert all("same external carrier" not in str(node) for node in first.nodes.values())


def test_temporal_association_connects_separate_stimuli() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(node_payload="anonymous")))
    runtime.stimulate("first sensory event")
    before = runtime.edge_count
    runtime.stimulate("second sensory event")
    assert runtime.edge_count > before
    assert runtime.metrics()["last_delta"]["created_edges"]


def test_untraversed_edges_forget_and_are_pruned() -> None:
    manifest = ModelManifest(parameters={"edge_decay": 0.5, "prune_threshold": 0.02})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    runtime.stimulate("a small pattern")
    runtime.stimulate("another pattern")
    assert runtime.edge_count > 0
    runtime.step(ticks=20)
    assert runtime.edge_count == 0


def test_structural_observer_records_repeatable_anonymous_pattern() -> None:
    runtime = ConsciousnessRuntime()
    runtime.stimulate("recurrent signal")
    config = {"activation_threshold": 0.001, "min_nodes": 2, "max_nodes": 8, "min_internal_edges": 1, "recurrence_window_ticks": 100, "min_occurrences": 2, "min_span_ticks": 0, "alert_cooldown_ticks": 0}
    runtime.observe(config)
    observed = runtime.observe(config)
    assert observed["current"]["repeatable"]
    assert runtime.package.logs["observations"]


def test_attention_filter_can_be_explicitly_bypassed_per_external_source() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={"attention_budget": 1})))
    runtime.set_filter_bypass_sources(["manual"])
    runtime.stimulate("a deliberately broad external carrier")
    assert runtime.metrics()["last_delta"]["accepted_features"] > 1


def test_repeated_direct_stimulus_consolidates_and_survives_an_idle_interval() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest()))
    sensor = TextSensorAdapter(runtime.sensory_seed)
    for _ in range(10):
        runtime.receive_frame(sensor.encode("repeated associative carrier"), metadata={"carrier": "test"})
    learned_edges = list(runtime.edges.values())
    assert learned_edges
    learned_stability = max(float(edge["stability"]) for edge in learned_edges)
    assert learned_stability > .15
    runtime.step(ticks=900)
    assert runtime.edges
    assert max(float(edge["stability"]) for edge in runtime.edges.values()) > .15


def test_long_carrier_reaches_the_transparent_default_gate_and_forms_connections() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest()))
    sensor = TextSensorAdapter(runtime.sensory_seed)
    carrier = "the quick brown fox jumps over the lazy dog while a second independent sentence adds many distinctive letters, punctuation, and temporal fragments for an extended input test"
    for _ in range(4):
        runtime.receive_frame(sensor.encode(carrier), metadata={"carrier": "test"})
    delta = runtime.metrics()["last_delta"]
    assert delta["accepted_features"] > runtime.config.attention_budget
    assert delta["filtered_features"] == 0
    assert delta["attention_mode"] == "transparent"
    assert runtime.edges


def test_environmental_competition_is_opt_in_and_has_no_hidden_channel_bias() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={"attention_budget": 2, "attention_competition_enabled": True})))
    runtime.receive_frame(SensoryFrame(source="test", channels={11: .2, 12: .2, 13: .2}), metadata={"carrier": "test"})
    delta = runtime.metrics()["last_delta"]
    assert delta["attention_mode"] == "environmental_competition"
    assert delta["accepted_features"] == 2
    # Equal scores retain frame insertion order rather than a fixed channel hash.
    assert set(runtime.receptor_index) == {11, 12}


def test_delta_marks_direct_nodes_for_live_visualisation() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest()))
    runtime.receive_frame(SensoryFrame(source="test", channels={71: .45, 72: .25}), metadata={"carrier": "test"})
    delta = runtime.metrics()["last_delta"]
    assert set(delta["direct_nodes"])
    assert set(delta["direct_nodes"]).issubset(runtime.nodes)


def test_trace_records_real_dynamical_deltas_only_when_enabled() -> None:
    runtime = ConsciousnessRuntime()
    runtime.step(ticks=1)
    assert not runtime.trace_entries
    runtime.set_trace(True)
    runtime.stimulate("trace this external stimulus")
    assert runtime.trace_entries
    assert runtime.trace_entries[-1]["tick"] == runtime.tick


def test_stronger_external_energy_creates_a_more_consolidated_initial_trace() -> None:
    def strongest_stability(intensity: float) -> float:
        runtime = ConsciousnessRuntime()
        runtime.stimulate("identical external carrier", intensity=intensity)
        return max(edge["stability"] for edge in runtime.edges.values())

    assert strongest_stability(2.0) > strongest_stability(1.0)


def test_strong_reactivation_consolidates_existing_association() -> None:
    runtime = ConsciousnessRuntime()
    runtime.stimulate("returning carrier", intensity=1.0)
    before = max(edge["stability"] for edge in runtime.edges.values())
    runtime.stimulate("returning carrier", intensity=2.0)
    assert max(edge["stability"] for edge in runtime.edges.values()) > before


def test_core_accepts_anonymous_sensor_frames_without_text_or_labels() -> None:
    runtime = ConsciousnessRuntime()
    sensor = TextSensorAdapter(runtime.sensory_seed, labeled=True)
    frame = sensor.encode("human-readable shortcut")
    runtime.receive_frame(frame, metadata={"carrier": "text"})
    assert runtime.nodes
    assert all("label" not in node for node in runtime.nodes.values())
    assert sensor.channel_labels


def test_v3_labeled_observation_preserves_distributed_frame_and_dynamics() -> None:
    anonymous_sensor = TextSensorAdapter(91, encoding="anonymous-distributed", channels=192)
    observed_sensor = TextSensorAdapter(91, encoding="labeled-observation", channels=192)
    carrier = "你好, ThreeMind"
    anonymous_frame = anonymous_sensor.encode(carrier)
    observed_frame = observed_sensor.encode(carrier)
    assert observed_frame.channels == anonymous_frame.channels

    anonymous = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(kernel_id="anonymous-spatial-v3", spatial_embedding=True, spatial_dimensions=3, parameters={"sensory_encoding": "anonymous-distributed"})))
    observed = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(kernel_id="anonymous-spatial-v3", node_payload="anonymous", spatial_embedding=True, spatial_dimensions=3, parameters={"sensory_encoding": "labeled-observation"})))
    # The two packages use their own seeds in ordinary operation.  Set a common
    # seed here to test the encoder/dynamics equivalence directly.
    anonymous.sensory_seed = observed.sensory_seed = 91
    observed.register_channel_labels(observed_sensor.channel_labels)
    anonymous.receive_frame(anonymous_frame)
    observed.receive_frame(observed_frame)
    assert [(edge["source"], edge["target"], edge["weight"]) for edge in anonymous.edges.values()] == [(edge["source"], edge["target"], edge["weight"]) for edge in observed.edges.values()]
    assert [node["activation"] for node in anonymous.nodes.values()] == [node["activation"] for node in observed.nodes.values()]
    assert all("label" not in node for node in observed.nodes.values())
    assert any(observed.node_label(node_id) for node_id in observed.nodes)


def test_v3_literal_character_mode_keeps_readable_labels_out_of_dynamics() -> None:
    manifest = ModelManifest(kernel_id="anonymous-spatial-v3", node_payload="anonymous", spatial_embedding=True, spatial_dimensions=3, parameters={"sensory_encoding": "literal-character"})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    sensor = TextSensorAdapter(runtime.sensory_seed, encoding="literal-character")
    frame = sensor.encode("你好")
    runtime.register_channel_labels(sensor.channel_labels)
    runtime.receive_frame(frame)
    assert {runtime.node_label(node_id) for node_id in runtime.nodes} >= {"你", "好"}
    assert all("label" not in node for node in runtime.nodes.values())
    driver = CharacterDriver(runtime.node_label)
    rendered = driver.render(sorted(runtime.nodes), "fallback")
    assert "你" in rendered and "好" in rendered
    assert all("label" not in str(edge) for edge in runtime.edges.values())


def test_output_bus_publishes_anonymous_activity_without_carrier_text() -> None:
    runtime = ConsciousnessRuntime()
    _send(runtime, "carrier text must remain outside the output frame")
    output = runtime.latest_output()
    assert output.tick == runtime.tick
    assert output.nodes
    assert "carrier text" not in str(output.nodes)
    assert "carrier text" not in str(output.edges)


def test_structural_readout_adapter_consumes_output_frame_without_runtime_access() -> None:
    runtime = ConsciousnessRuntime()
    _send(runtime, "an anonymous recurring signal")
    adapter = StructuralReadoutAdapter()
    config = {"activation_threshold": 0.001, "min_nodes": 2, "max_nodes": 8, "min_internal_edges": 1, "recurrence_window_ticks": 100, "min_occurrences": 2, "min_span_ticks": 0, "alert_cooldown_ticks": 0}
    adapter.consume(runtime.latest_output(), config)
    runtime.step(ticks=1)
    view = adapter.consume(runtime.latest_output(), config)
    assert view["current"]["tick"] == runtime.tick
    assert "events" in view


def test_structural_readout_preserves_anonymous_and_display_layers() -> None:
    manifest = ModelManifest(parameters={"sensory_encoding": "literal-character"})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    sensor = TextSensorAdapter(runtime.sensory_seed, encoding="literal-character")
    frame = sensor.encode("ab")
    runtime.register_channel_labels(sensor.channel_labels)
    runtime.receive_frame(frame)
    adapter = StructuralReadoutAdapter()
    driver = CharacterDriver(runtime.node_label)
    view = adapter.consume(runtime.latest_output(), {
        "activation_threshold": .001, "min_nodes": 2, "max_nodes": 8,
        "min_internal_edges": 1, "recurrence_window_ticks": 100,
        "min_occurrences": 1, "min_span_ticks": 0, "alert_cooldown_ticks": 0,
    }, render=driver.render, describe=driver.describe)
    event = view["new_event"]
    assert event is not None
    assert event["readout"] == event["anonymous_readout"]
    assert event["anonymous_readout"].startswith("anonymous structure ")
    assert event["display_readout"] != event["anonymous_readout"]
    assert event["label_entries"]
    assert {entry["label"] for entry in event["label_entries"]} >= {"a", "b"}
    assert event["readable_labels"]


def test_passive_readout_projects_direct_activity_even_without_a_repeatable_subgraph() -> None:
    """A small local response must not be hidden by recurrence thresholds."""
    manifest = ModelManifest(parameters={"sensory_encoding": "literal-character"})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    sensor = TextSensorAdapter(runtime.sensory_seed, encoding="literal-character")
    frame = sensor.encode("ab")
    runtime.register_channel_labels(sensor.channel_labels)
    runtime.receive_frame(frame)
    adapter = StructuralReadoutAdapter()
    driver = CharacterDriver(runtime.node_label)
    view = adapter.consume(runtime.latest_output(), {
        # Deliberately make a repeatable subgraph impossible for this frame.
        "activation_threshold": .99,
        "min_nodes": 8,
        "max_nodes": 8,
        "min_internal_edges": 8,
        "min_occurrences": 99,
        "read_touched_activity": True,
    }, render=driver.render, describe=driver.describe)
    event = view["new_passive_event"]
    assert event is not None
    assert event["kind"] == "activated_node_readout"
    assert event["node_ids"]
    assert event["label_entries"]
    assert view["current"]["readout_kind"] == "touched_activity"


def test_passive_readout_label_order_is_configurable_without_changing_nodes() -> None:
    """Sorting labels changes presentation only, not the anonymous record."""
    nodes = (
        {"id": 2, "activation": .9, "stability": .2, "touch_count": 3, "direct_touch": .3, "associative_touch": .0},
        {"id": 1, "activation": .2, "stability": .4, "touch_count": 2, "direct_touch": .2, "associative_touch": .0},
    )
    def frame(tick: int) -> OutputFrame:
        return OutputFrame(
            consciousness_id="test", tick=tick, life_state="active", metrics={}, nodes=nodes, edges=(),
            delta={"direct_nodes": [2, 1], "associated_nodes": [], "causal_sources": ["manual"]},
        )
    labels = {1: "first", 2: "second"}
    describe = lambda selected: [{**node, "node_id": node["id"], "label": labels[node["id"]]} for node in selected]
    by_activation = StructuralReadoutAdapter().consume(frame(1), {"label_sort_by_activation": True}, describe=describe)
    by_identity = StructuralReadoutAdapter().consume(frame(2), {"label_sort_by_activation": False}, describe=describe)
    assert by_activation["current"]["readable_labels"] == ["second", "first"]
    assert by_identity["current"]["readable_labels"] == ["first", "second"]
    assert set(by_activation["current"]["node_ids"]) == set(by_identity["current"]["node_ids"])


def test_repeatable_structure_immediate_readout_can_be_disabled_without_disabling_detection() -> None:
    nodes = (
        {"id": 1, "activation": .8, "stability": .2, "touch_count": 3, "direct_touch": .0, "associative_touch": .0},
        {"id": 2, "activation": .7, "stability": .2, "touch_count": 3, "direct_touch": .0, "associative_touch": .0},
    )
    edges = ({"source": 1, "target": 2, "weight": .8, "stability": .2},)
    def frame(tick: int) -> OutputFrame:
        return OutputFrame("test", tick, "active", {}, nodes, edges, {"causal_sources": ["manual"]})
    config = {
        "activation_threshold": .1, "min_nodes": 2, "max_nodes": 4,
        "min_internal_edges": 1, "recurrence_window_ticks": 10,
        "min_occurrences": 2, "min_span_ticks": 0, "alert_cooldown_ticks": 0,
        "repeatable_structure_readout": False,
    }
    adapter = StructuralReadoutAdapter()
    adapter.consume(frame(1), config)
    disabled = adapter.consume(frame(2), config)
    assert disabled["current"]["repeatable"] is True
    assert disabled["new_event"] is None
    enabled = StructuralReadoutAdapter()
    enabled.consume(frame(1), {**config, "repeatable_structure_readout": True})
    assert enabled.consume(frame(2), {**config, "repeatable_structure_readout": True})["new_event"] is not None


def test_background_activity_readout_uses_output_provenance_and_optional_strict_deduplication() -> None:
    runtime = ConsciousnessRuntime()
    _send(runtime, "background observer seed")
    output = runtime.latest_output()
    frame = type(output)(
        consciousness_id=output.consciousness_id,
        tick=output.tick + 1,
        life_state=output.life_state,
        metrics=output.metrics,
        nodes=output.nodes,
        edges=output.edges,
        delta={"background_only": True},
    )
    adapter = StructuralReadoutAdapter()
    config = {"activation_min": 0, "activation_max": 1, "max_nodes": 7, "strict_deduplicate": True}
    first = adapter.consume_background_activity(frame, config)
    assert first["new_event"] is not None
    assert first["new_event"]["kind"] == "background_active_nodes"
    duplicate_frame = type(frame)(
        consciousness_id=frame.consciousness_id,
        tick=frame.tick + 1,
        life_state=frame.life_state,
        metrics=frame.metrics,
        nodes=frame.nodes,
        edges=frame.edges,
        delta={"background_only": True},
    )
    assert adapter.consume_background_activity(duplicate_frame, config)["new_event"] is None


def test_runtime_marks_background_output_provenance_without_changing_source_rules() -> None:
    runtime = ConsciousnessRuntime()
    runtime.receive_frame(SensoryFrame(source="ambient-environment", channels={5: .3}, intensity=.1))
    assert runtime.latest_output().delta["background_only"] is True
    # A readout can happen one quiet tick after the carrier was delivered.
    # Its provenance must remain environmental for presentation adapters,
    # without becoming a graph-dynamics input.
    runtime.step(ticks=1)
    assert runtime.latest_output().delta["background_only"] is True
    assert runtime.latest_output().delta["causal_sources"] == ["ambient-environment"]
    runtime.receive_frame(SensoryFrame(source="manual", channels={6: .3}, intensity=.1))
    assert runtime.latest_output().delta["background_only"] is False


def test_structural_readout_exports_background_provenance() -> None:
    runtime = ConsciousnessRuntime()
    runtime.receive_frame(SensoryFrame(source="ambient-environment", channels={31: .4, 32: .35, 33: .3}, intensity=.1))
    adapter = StructuralReadoutAdapter()
    view = adapter.consume(runtime.latest_output(), {
        "activation_threshold": .001, "min_nodes": 2, "max_nodes": 8,
        "min_internal_edges": 1, "recurrence_window_ticks": 100,
        "min_occurrences": 99, "min_span_ticks": 0, "alert_cooldown_ticks": 0,
    })
    event = view["new_passive_event"]
    assert event is not None
    assert event["background"] is True
    assert event["source_provenance"] == ["ambient-environment"]


def test_body_adapter_filters_background_before_it_reaches_input_bus() -> None:
    body = BodyAdapter(7, sampling_ticks=2, threshold=0.01, adaptation=.5, noise=0)
    raw = SensoryFrame(source="ambient-environment", channels={1: .3, 2: .15}, intensity=.1)
    assert body.filter_frame(raw, 1) is None
    frame = body.filter_frame(raw, 2)
    assert frame is not None
    assert frame.source == "body-filtered-environment"
    assert frame.channels


def test_environment_source_and_interoception_are_separate_from_body_filter() -> None:
    source = AmbientSensorAdapter(7)
    raw = source.frame(1, intensity=.1)
    assert raw.source == "ambient-environment"
    body = BodyAdapter(7, threshold=0, noise=0)
    filtered = body.filter_frame(raw, 1)
    assert filtered is not None and filtered.source == "body-filtered-environment"
    internal = InteroceptiveAdapter(7).frame(1, intensity=.1)
    assert internal.source == "interoceptive-body"
    assert internal.channels


def test_environment_sensor_changes_its_anonymous_receptors_over_time() -> None:
    """The default world is not a permanently co-active receptor clique."""
    source = AmbientSensorAdapter(7)
    signatures = {tuple(sorted(source.frame(tick, intensity=.1).channels)) for tick in range(1, 80)}
    assert len(signatures) > 8


def test_environment_sensor_injects_finite_lived_anonymous_disturbances() -> None:
    source = AmbientSensorAdapter(7, transient_rate=1.0, transient_lifetime_min=2, transient_lifetime_max=2)
    baseline = source.frame(1, intensity=.1)
    disturbed = source.frame(2, intensity=.1)
    # Three V2 baseline channels remain, while finite-lived carrier events
    # contribute extra anonymous receptors without labels or Core access.
    assert len(baseline.channels) >= 4
    assert len(disturbed.channels) >= 4


def test_background_only_run_retains_low_plasticity_after_early_time() -> None:
    runtime = ConsciousnessRuntime()
    source = AmbientSensorAdapter(runtime.sensory_seed)
    for tick in range(1, 301):
        runtime.receive_frame(source.frame(tick, intensity=.08), metadata={"carrier": "test environment"})
    metrics = runtime.metrics()
    assert metrics["node_count"] > 30
    assert metrics["mean_stability"] < .05


def test_local_coactivation_leaves_a_single_disturbance_unconnected() -> None:
    runtime = ConsciousnessRuntime()
    source = AmbientSensorAdapter(runtime.sensory_seed, transient_rate=1.0, transient_lifetime_min=1, transient_lifetime_max=1)
    runtime._advance(list(source.frames(1, intensity=.08)))  # event grouping is Core input semantics
    connected = {node_id for edge in runtime.edges for node_id in edge}
    assert any(node_id not in connected for node_id in runtime.nodes)


def test_temporal_association_policy_retains_the_broad_linking_experiment() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={"edge_birth_policy": "temporal-association"})))
    source = AmbientSensorAdapter(runtime.sensory_seed, transient_rate=1.0, transient_lifetime_min=1, transient_lifetime_max=1)
    runtime._advance(list(source.frames(1, intensity=.08)))
    connected = {node_id for edge in runtime.edges for node_id in edge}
    assert len(connected) == len(runtime.nodes)


def test_default_runtime_has_no_implicit_propagation_or_edge_adaptation_budget() -> None:
    runtime = ConsciousnessRuntime()
    assert runtime.config.edge_adaptation_limit is None
    assert runtime.config.propagation_limit is None
    assert runtime.config.edge_birth_activation_product_min is None
    assert runtime.config.propagation_activation_min is None
    assert runtime.config.max_nodes is None
    assert runtime.config.max_edges is None


def test_legacy_implicit_budget_fields_are_removed_on_load() -> None:
    manifest = ModelManifest(parameters={"max_edge_adaptations": 256, "max_propagations": 256, "propagation_threshold": .08})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    assert runtime.config.edge_adaptation_limit is None
    assert runtime.config.propagation_limit is None
    assert runtime.config.propagation_activation_min is None
    assert "max_edge_adaptations" not in runtime.manifest.parameters


def test_null_parameter_removes_an_explicit_runtime_limit() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={"edge_adaptation_limit": 9})))
    assert runtime.config.edge_adaptation_limit == 9
    runtime.configure_model(parameters={"edge_adaptation_limit": None})
    assert runtime.config.edge_adaptation_limit is None
    assert "edge_adaptation_limit" not in runtime.manifest.parameters


def test_novel_carrier_can_form_edges_after_a_stable_repeated_structure() -> None:
    manifest = ModelManifest(kernel_id="anonymous-spatial-v3", spatial_embedding=True, spatial_dimensions=3, parameters={"spatial_radius": 2.5, "neighborhood_enabled": True})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    sensor = TextSensorAdapter(runtime.sensory_seed)
    for _ in range(50):
        runtime.receive_frame(sensor.encode("repeated carrier", intensity=1.0), metadata={"carrier": "test"})
        runtime.step(ticks=2)
    edges_before = runtime.edge_count
    nodes_before = len(runtime.nodes)
    runtime.receive_frame(sensor.encode("distinct novel carrier with other symbols 9Q zebra", intensity=1.0), metadata={"carrier": "test"})
    assert len(runtime.nodes) > nodes_before
    assert runtime.edge_count > edges_before


def test_graph_and_output_bus_are_complete_by_default() -> None:
    runtime = ConsciousnessRuntime()
    _send(runtime, "complete projection check")
    graph = runtime.graph()
    output = runtime.latest_output()
    assert len(graph["nodes"]) == len(runtime.nodes)
    assert len(graph["edges"]) == len(runtime.edges)
    assert len(output.nodes) == len(runtime.nodes)
    assert len(output.edges) == len(runtime.edges)


def test_energy_simulation_is_independent_of_attention_and_has_no_internal_recovery() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={
        "energy_simulation_enabled": True,
        "energy_initial_reserve": .05,
        "energy_capacity": 1.0,
        "energy_direct_cost": 1.0,
    })))
    frame = SensoryFrame(source="manual", channels={101: 1.0}, intensity=1.0)
    runtime.receive_frame(frame, metadata={"carrier": "test"})
    first_activation = max(float(node["activation"]) for node in runtime.nodes.values())
    assert 0.0 < first_activation <= .05
    assert runtime.metrics()["energy_reserve"] == 0.0
    assert runtime.metrics()["attention_modulators"] == []
    runtime.step(ticks=5)
    assert runtime.metrics()["energy_reserve"] == 0.0
    runtime.supply_energy(.25, source="test-supply")
    runtime.receive_frame(frame, metadata={"carrier": "test"})
    assert runtime.metrics()["energy_reserve"] < .25


def test_depleted_energy_does_not_create_zero_activity_receptors() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={
        "energy_simulation_enabled": True,
        "energy_initial_reserve": 0.0,
        "energy_capacity": 1.0,
        "energy_direct_cost": 1.0,
    })))
    runtime.receive_frame(SensoryFrame(source="manual", channels={77: 1.0}), metadata={"carrier": "test"})
    assert runtime.nodes == {}
    assert runtime.receptor_index == {}


def test_energy_depletion_remains_reversible_unless_irreversible_mode_is_enabled() -> None:
    reversible_package = ModelPackage.empty(ModelManifest(parameters={
        "energy_simulation_enabled": True,
        "energy_initial_reserve": 0.0,
        "irreversible_energy_death_enabled": False,
        "energy_starvation_death_ticks": 2,
    }))
    reversible_package.state = {"nodes": [{"id": 1, "support": .8}], "next_node_id": 2}
    reversible = ConsciousnessRuntime(reversible_package)
    reversible.step(ticks=4)
    assert reversible.life_state != "dead"
    reversible.supply_energy(.2, source="test-supply")
    assert reversible.metrics()["energy_reserve"] == .2

    irreversible_package = ModelPackage.empty(ModelManifest(parameters={
        "energy_simulation_enabled": True,
        "energy_initial_reserve": 0.0,
        "irreversible_energy_death_enabled": True,
        "energy_starvation_death_ticks": 2,
    }))
    irreversible_package.state = {"nodes": [{"id": 1, "support": .8}], "next_node_id": 2}
    irreversible = ConsciousnessRuntime(irreversible_package)
    irreversible.step(ticks=2)
    assert irreversible.life_state == "dead"
    assert irreversible.death_reason == "irreversible energy starvation"


def test_metabolic_adapter_supplies_at_most_once_per_observed_tick() -> None:
    adapter = MetabolicEnergyAdapter(supply_per_tick=.1, total_supply_limit=.25)
    first = adapter.supply_for_tick(4)
    assert first == .1
    adapter.record_accepted(first)
    assert adapter.supply_for_tick(4) == 0.0
    second = adapter.supply_for_tick(5)
    assert second == .1
    adapter.record_accepted(second)
    final = adapter.supply_for_tick(6)
    assert abs(final - .05) < 1e-9
    adapter.record_accepted(final)
    assert adapter.supply_for_tick(7) == 0.0


def test_topology_inhibition_uses_physical_adjacency_without_reversing_excitation() -> None:
    manifest = ModelManifest(parameters={
        "topology_inhibition_enabled": True,
        "inhibition_generation_gain": .8,
        "inhibition_diffusion": .5,
        "inhibition_decay": 0.0,
        "inhibition_response_gain": 2.0,
    })
    package = ModelPackage.empty(manifest)
    package.state = {
        "nodes": [{"id": 1}, {"id": 2}],
        "edges": [{"source": 1, "target": 2, "weight": 1.0}],
        "receptor_index": {101: 1},
        "next_node_id": 3,
    }
    runtime = ConsciousnessRuntime(package)
    runtime.receive_frame(SensoryFrame(source="manual", channels={101: 1.0}), metadata={"carrier": "test"})
    assert runtime.nodes[2]["pending_inhibition"] > 0.0
    # The inhibitory physical-neighbour relation did not create a reverse
    # excitatory edge.
    assert (2, 1) not in runtime.edges
    runtime.step(ticks=1)
    assert runtime.nodes[2]["inhibition"] > 0.0


def test_topology_inhibition_divides_finite_potential_across_branches() -> None:
    manifest = ModelManifest(parameters={
        "topology_inhibition_enabled": True,
        "activation_decay": 0.0,
        "propagation_gain": 0.0,
        "inhibition_generation_gain": 1.0,
        "inhibition_diffusion": .5,
        "inhibition_decay": 0.0,
        "inhibition_saturation": 100.0,
    })
    package = ModelPackage.empty(manifest)
    package.state = {
        "nodes": [{"id": 1}, {"id": 2}, {"id": 3}],
        # Include one edge in each direction relative to node 1.  Both are
        # physical neighbours for inhibition, while excitation stays directed.
        "edges": [
            {"source": 1, "target": 2, "weight": .75},
            {"source": 3, "target": 1, "weight": .25},
        ],
        "receptor_index": {101: 1},
        "next_node_id": 4,
    }
    runtime = ConsciousnessRuntime(package)
    runtime.receive_frame(SensoryFrame(source="manual", channels={101: 1.0}), metadata={"carrier": "test"})
    transferred = float(runtime.metrics()["last_delta"]["inhibition_transferred"])
    received = float(runtime.nodes[2]["pending_inhibition"]) + float(runtime.nodes[3]["pending_inhibition"])
    # Recipient saturation may dissipate a tiny amount but may never create
    # more potential than the source actually transferred.
    assert transferred * .99 <= received <= transferred + 1e-12
    assert transferred <= float(runtime.metrics()["last_delta"]["inhibition_generated"])


def test_retained_local_inhibition_produces_refractory_like_response() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={
        "topology_inhibition_enabled": True,
        "activation_decay": 0.0,
        "inhibition_generation_gain": 1.0,
        "inhibition_diffusion": 0.0,
        "inhibition_decay": 0.0,
        "inhibition_response_gain": 4.0,
    })))
    frame = SensoryFrame(source="manual", channels={17: 1.0})
    runtime.receive_frame(frame, metadata={"carrier": "test"})
    first_touch = max(float(node["direct_touch"]) for node in runtime.nodes.values())
    runtime.receive_frame(frame, metadata={"carrier": "test"})
    second_touch = max(float(node["direct_touch"]) for node in runtime.nodes.values())
    assert 0.0 < second_touch < first_touch


def test_topology_inhibition_is_enabled_by_default() -> None:
    runtime = ConsciousnessRuntime()
    runtime.receive_frame(SensoryFrame(source="manual", channels={7: 1.0}), metadata={"carrier": "test"})
    assert runtime.metrics()["topology_inhibition_enabled"] is True
    assert runtime.metrics()["total_inhibition"] > 0.0


def test_topology_inhibition_can_be_explicitly_disabled() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={
        "topology_inhibition_enabled": False,
    })))
    runtime.receive_frame(SensoryFrame(source="manual", channels={7: 1.0}), metadata={"carrier": "test"})
    assert runtime.metrics()["topology_inhibition_enabled"] is False
    assert runtime.metrics()["total_inhibition"] == 0.0


def test_topology_inhibition_parameters_can_be_changed_at_runtime() -> None:
    runtime = ConsciousnessRuntime()
    parameters = {
        "topology_inhibition_enabled": True,
        "inhibition_generation_gain": 0.41,
        "inhibition_decay": 0.22,
        "inhibition_diffusion": 0.53,
        "inhibition_response_gain": 3.75,
        "inhibition_saturation": 1.8,
        "inhibition_propagation_min": 0.006,
    }
    runtime.configure_model(parameters=parameters)
    for key, value in parameters.items():
        assert getattr(runtime.config, key) == value
        assert runtime.manifest.parameters[key] == value


def test_dynamics_trace_starts_with_keyframe_and_records_sparse_node_changes() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={
        "topology_inhibition_enabled": True,
    })))
    runtime.set_trace(True)
    assert runtime.trace_entries[0]["kind"] == "dynamics_keyframe"
    assert runtime.metrics()["trace_enabled"] is True
    runtime.receive_frame(SensoryFrame(source="manual", channels={7: 1.0}), metadata={"carrier": "test"})
    latest = runtime.trace_entries[-1]
    assert latest["tick"] == runtime.tick
    assert latest["node_dynamics"]
    assert "inhibition" in latest["node_dynamics"][0]["after"]
    entry_count = len(runtime.trace_entries)
    runtime.set_trace(True)
    assert len(runtime.trace_entries) == entry_count
    runtime.set_trace(False)
    assert runtime.metrics()["trace_enabled"] is False


def test_network_transport_accepts_only_authenticated_anonymous_sensory_frames() -> None:
    transport = NetworkTransportAdapter("a sufficiently long shared token")
    assert transport.authorize_hello({"type": "hello", "protocol": "threemind-network/1", "peer_id": "sensor-a", "token": "a sufficiently long shared token"}) == "sensor-a"
    sensor = RemoteSensoryAdapter(99)
    frame = sensor.decode({"channels": {"alpha": .3, "beta": -.2}, "intensity": .7}, peer_id="sensor-a")
    assert frame.source == "network:sensor-a"
    assert all("alpha" not in str(channel) for channel in frame.channels)
    try:
        transport.authorize_hello({"type": "hello", "protocol": "threemind-network/1", "peer_id": "sensor-a", "token": "wrong"})
    except NetworkProtocolError:
        pass
    else:
        raise AssertionError("network transport accepted a wrong token")


def test_remote_physiology_modulator_is_scalar_and_expires() -> None:
    modulator = RemotePhysiologyModulator(timeout_ticks=2)
    modulator.update({"gain": .5, "budget": .4}, tick=10)
    active = modulator.begin_tick(11, [])
    expired = modulator.begin_tick(13, [])
    assert active.strength_multiplier == .5 and active.budget_multiplier == .4
    assert expired == type(expired)()


def test_external_stimulus_bus_is_delivered_by_continuous_core() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(ModelManifest(parameters={"tick_seconds": 0.02})))
    runtime.start()
    sensor = TextSensorAdapter(runtime.sensory_seed)
    runtime.enqueue_frame(sensor.encode("queued signal", source="ambient"), metadata={"text": "queued signal", "carrier": "test"})
    import time
    time.sleep(0.08)
    runtime.stop("test")
    assert any(event.get("text") == "queued signal" for event in runtime.stimuli)


def test_text_stream_is_delivered_as_ordered_causal_frames() -> None:
    runtime = ConsciousnessRuntime()
    sensor = TextSensorAdapter(runtime.sensory_seed)
    carrier = "first second third fourth fifth"
    frames = sensor.encode_stream(carrier, source="manual", frame_characters=6)
    receipt = runtime.enqueue_frames(
        frames,
        metadata={"text": carrier, "carrier": "test"},
        adapter_id="text-sensor",
        inter_frame_epochs=1,
    )
    assert receipt["frame_count"] == len(frames)
    assert runtime.queue_size() == len(frames)
    runtime.step(ticks=1)
    assert runtime.queue_size() == len(frames) - 1
    runtime.step(ticks=len(frames) - 1)
    delivered = [event for event in runtime.events if event.get("kind") == "stimulus_frame_delivered"]
    assert [event["frame_index"] for event in delivered] == list(range(len(frames)))
    assert runtime.stimuli[-1]["text"] == carrier


def test_long_literal_carrier_does_not_form_one_global_coactivation() -> None:
    manifest = ModelManifest(parameters={"sensory_encoding": "literal-character"})
    runtime = ConsciousnessRuntime(ModelPackage.empty(manifest))
    sensor = TextSensorAdapter(runtime.sensory_seed, encoding="literal-character")
    carrier = "".join(chr(0x4E00 + index) for index in range(120))
    frames = sensor.encode_stream(carrier, source="manual", frame_characters=8)
    runtime.enqueue_frames(frames, metadata={"text": carrier}, adapter_id="text-sensor")
    runtime.step(ticks=len(frames))
    deliveries = [event for event in runtime.events if event.get("kind") == "stimulus_frame_delivered"]
    assert len(deliveries) == len(frames)
    assert max(event["feature_count"] for event in deliveries) <= 8
    # A 120-character all-at-once event would create 14,280 directed pairs.
    # Temporal framing produces local 8-character encounters instead.
    assert runtime.edge_count < 2_000


def test_pending_input_frames_survive_a_package_state_round_trip() -> None:
    runtime = ConsciousnessRuntime()
    sensor = TextSensorAdapter(runtime.sensory_seed)
    frames = sensor.encode_stream("durable transport queue", frame_characters=4)
    runtime.enqueue_frames(frames, metadata={"text": "durable transport queue"}, adapter_id="text-sensor")
    runtime.step(ticks=1)
    runtime.package.state = runtime.state_dict()
    resumed = ConsciousnessRuntime(runtime.package)
    assert resumed.queue_size() == len(frames) - 1
    resumed.step(ticks=len(frames) - 1)
    assert resumed.queue_size() == 0


def test_invalid_model_package_is_rejected() -> None:
    path = Path("test-artifacts/invalid.tmind")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"not a zip")
    try:
        ModelPackage.load(path)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid package was accepted")
    path.unlink(missing_ok=True)
