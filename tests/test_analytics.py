from __future__ import annotations

import copy
import hashlib
import shutil
import sys
import uuid
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
for package_root in ("core", "adapters", "services"):
    sys.path.insert(0, str(ROOT / package_root))

from threemind.frames import OutputFrame, SensoryFrame
from threemind.model import ModelPackage
from threemind.runtime import ConsciousnessRuntime
from threemind_adapters import StructuralReadoutAdapter
from threemind_analytics import AnalyticsService, EvidenceExporter, InterventionPolicy


def _structural_frame(tick: int, *, activation: float = 0.8) -> OutputFrame:
    nodes = (
        {
            "id": 11,
            "activation": activation,
            "inhibition": 0.05,
            "stability": 0.4,
            "touch_count": 4,
            "direct_touch": activation,
            "associative_touch": 0.0,
            "position": [0.0, 0.0, 0.0],
        },
        {
            "id": 12,
            "activation": activation * 0.75,
            "inhibition": 0.02,
            "stability": 0.3,
            "touch_count": 3,
            "direct_touch": 0.0,
            "associative_touch": activation * 0.5,
            "position": [1.0, 0.0, 0.0],
        },
    )
    edges = ({"source": 11, "target": 12, "weight": 0.7, "stability": 0.25},)
    return OutputFrame(
        "evidence-consciousness",
        tick,
        "active",
        {},
        nodes,
        edges,
        {
            # The structural tests deliberately omit touch projections so the
            # adapter's strict induced-subgraph view is the selected current
            # view rather than the independent immediate-activity view.
            "direct_nodes": [],
            "associated_nodes": [],
            "causal_sources": ["manual"],
            "background_only": False,
        },
    )


def _readout_config() -> dict:
    return {
        "activation_threshold": 0.05,
        "min_nodes": 2,
        "max_nodes": 4,
        "min_internal_edges": 1,
        "recurrence_window_ticks": 100,
        "min_occurrences": 2,
        "min_span_ticks": 1,
        "alert_cooldown_ticks": 0,
        "repeatable_structure_readout": True,
    }


def test_structural_readout_exposes_auditable_structure_id_and_frozen_subgraph() -> None:
    adapter = StructuralReadoutAdapter()
    first = adapter.consume(_structural_frame(10), _readout_config())
    second = adapter.consume(_structural_frame(12), _readout_config())

    current = first["current"]
    event = second["new_event"]
    assert current["structure_id"]
    assert current["topology_class_id"]
    assert current["state_signature"] == current["signature"]
    assert current["structure_id"] == event["structure_id"]
    assert event["occurrence_id"]
    assert {node["id"] for node in event["subgraph"]["nodes"]} == {11, 12}
    assert event["subgraph"]["edges"] == [
        {"source": 11, "target": 12, "weight": 0.7, "stability": 0.25}
    ]


def test_structural_readout_restore_preserves_recurrence_without_touching_core() -> None:
    first_adapter = StructuralReadoutAdapter()
    first_view = first_adapter.consume(_structural_frame(20), _readout_config())
    persisted = [{
        "kind": "structural_readout",
        "tick": 20,
        "signature": first_view["current"]["signature"],
        "state_signature": first_view["current"]["state_signature"],
    }]

    restored = StructuralReadoutAdapter()
    restored.restore(persisted)
    result = restored.consume(_structural_frame(22), _readout_config())
    assert result["new_event"] is not None
    assert result["new_event"]["occurrences"] == 2


def _analytics_document() -> dict:
    subgraph = {
        "tick": 7,
        "nodes": [
            {"id": 1, "activation": 0.8, "inhibition": 0.1, "stability": 0.4},
            {"id": 2, "activation": 0.6, "inhibition": 0.0, "stability": 0.3},
        ],
        "edges": [{"source": 1, "target": 2, "weight": 0.7, "stability": 0.2}],
    }
    shared = {
        "tick": 7,
        "signature": "state-a",
        "state_signature": "state-a",
        "structure_id": "structure-a",
        "topology_class_id": "topology-a",
        "occurrence_id": "occurrence-7",
        "node_ids": [1, 2],
        "internal_edges": 1,
        "mean_activation": 0.7,
        "source_provenance": ["manual"],
        "readable_labels": ["甲", "松子"],
        "subgraph": subgraph,
    }
    return {
        "consciousness_id": "evidence-consciousness",
        "consciousness_name": "Evidence subject",
        "tick": 9,
        "life_state": "active",
        "stimuli": [
            {"tick": 6, "source": "manual", "envelope_id": "carrier-1"},
            {"tick": 8, "source": "ambient", "envelope_id": "carrier-2"},
        ],
        "events": [{"tick": 7, "kind": "association"}],
        "interpretations": [],
        "observations": [
            {"kind": "structural_readout", **shared},
            # This is a second record for the same occurrence.  It is an
            # alert, not another observation of the structure.
            {"kind": "repeatable_output_structure", **shared},
            {
                "kind": "structural_readout",
                **{**shared, "tick": 9, "occurrence_id": "occurrence-9", "mean_activation": 0.5},
            },
            {
                "id": "temporal-1",
                "kind": "temporal_convergence_readout",
                "start_tick": 6,
                "delivery_end_tick": 6,
                "end_tick": 9,
                "classification": "converged",
                "signature": "temporal-a",
                "source_provenance": ["manual"],
                "node_ids": [2],
                "rankings": [{"node_id": 2, "score": 0.9}],
            },
        ],
        "trace_entries": [
            {
                "kind": "dynamics_keyframe",
                "tick": 6,
                "node_count": 2,
                "edge_count": 1,
                "nodes": [
                    {"id": 1, "activation": 0.2, "inhibition": 0.0, "support": 0.1},
                    {"id": 2, "activation": 0.1, "inhibition": 0.0, "support": 0.1},
                ],
                "edges": [{"source": 1, "target": 2}],
            },
            {
                "kind": "dynamics_delta",
                "tick": 7,
                "node_dynamics": [
                    {"id": 1, "after": {"activation": 0.8, "inhibition": 0.1, "support": 0.2}},
                    {"id": 2, "after": {"activation": 0.6, "inhibition": 0.0, "support": 0.2}},
                ],
                "created_nodes": [],
                "removed_nodes": [],
                "created_edges": [],
                "removed_edges": [],
                "direct_nodes": [1],
                "associated_nodes": [2],
                "external_energy": 1.0,
            },
        ],
    }


def test_analytics_catalog_deduplicates_alert_record_and_reconstructs_dynamics() -> None:
    analytics = AnalyticsService(_analytics_document(), origin="test")
    overview = analytics.overview()
    catalog = analytics.structure_catalog()
    dynamics = analytics.dynamics(node_ids=[1, 2, 999])

    assert overview["counts"]["repeatable_structures"] == 1
    assert overview["stimulus_sources"] == {"manual": 1, "ambient": 1}
    assert len(catalog) == 1
    assert catalog[0]["occurrences"] == 2
    assert catalog[0]["repeatable_alerts"] == 1
    assert catalog[0]["source_counts"] == {"manual": 2}
    assert catalog[0]["latest_subgraph"]["edges"][0]["source"] == 1
    assert dynamics["trace_available"] is True
    assert dynamics["series"][-1]["total_activation"] == 1.4
    assert dynamics["series"][-1]["active_nodes"] == 2
    final_nodes = {
        row["node_id"]: row
        for row in dynamics["node_series"]
        if row["tick"] == 7
    }
    assert final_nodes[1]["activation"] == 0.8
    assert final_nodes[2]["activation"] == 0.6
    assert final_nodes[999]["present"] is False


def test_evidence_export_is_self_describing_and_checksum_protected() -> None:
    # Keep this test independent of pytest's global Windows temp directory:
    # interrupted local runs can leave that directory owned by another token.
    test_root = ROOT / "test-artifacts" / "pytest-analytics" / str(uuid.uuid4())
    try:
        target = EvidenceExporter(AnalyticsService(_analytics_document(), origin="test")).write(
            test_root / "evidence.zip"
        )
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
            assert {
                "manifest.json",
                "data_dictionary.csv",
                "tables/repeatable_structures.csv",
                "tables/temporal_readouts.csv",
                "tables/dynamics.csv",
                "subgraphs/structure-a.json",
                "checksums.sha256",
            } <= names
            checksum_rows = archive.read("checksums.sha256").decode("ascii").splitlines()
            checksums = dict(row.split("  ", 1)[::-1] for row in checksum_rows)
            for name, digest in checksums.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_empty_intervention_policy_does_not_change_graph_dynamics() -> None:
    seed = ConsciousnessRuntime(ModelPackage.empty(name="policy control"))
    seed.receive_frame(SensoryFrame(source="manual", channels={1: 0.9, 2: 0.7}, intensity=1.0))
    package = copy.deepcopy(seed.package)
    package.state = seed.state_dict()
    control = ConsciousnessRuntime(copy.deepcopy(package))
    intervention = ConsciousnessRuntime(copy.deepcopy(package))
    intervention.set_intervention_policy(InterventionPolicy(node_ids=frozenset(), edge_pairs=frozenset()))

    frame = SensoryFrame(source="manual", channels={1: 0.6}, intensity=1.0)
    control.receive_frame(frame)
    intervention.receive_frame(frame)
    assert control.state_dict()["nodes"] == intervention.state_dict()["nodes"]
    assert control.state_dict()["edges"] == intervention.state_dict()["edges"]


def test_functional_silencing_is_reversible_and_structural_lesion_is_audited() -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="intervention subject"))
    runtime.receive_frame(SensoryFrame(source="manual", channels={3: 0.9, 4: 0.7}, intensity=1.0))
    selected = runtime.receptor_index[3]
    runtime.set_intervention_policy(InterventionPolicy(node_ids=frozenset({selected})))
    runtime.receive_frame(SensoryFrame(source="manual", channels={3: 0.9}, intensity=1.0))
    assert selected not in runtime.latest_output().delta["direct_nodes"]
    runtime.set_intervention_policy(None)
    runtime.receive_frame(SensoryFrame(source="manual", channels={3: 0.9}, intensity=1.0))
    assert selected in runtime.latest_output().delta["direct_nodes"]

    event = runtime.apply_structural_lesion(node_ids=[selected], intervention_id="lesion-1")
    assert selected not in runtime.nodes
    assert event["kind"] == "experimental_structural_lesion"
    assert event["removed_node_ids"] == [selected]
    assert runtime.package.logs["interventions"][-1]["intervention_id"] == "lesion-1"
