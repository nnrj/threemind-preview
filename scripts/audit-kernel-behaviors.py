"""Small, reproducible old/new counterexamples and complete parameter inventory.

Reads only the named source files. No database, network, data/ or user models.
These are behavioral witnesses, not equivalence tests or AGI experiments.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ("core", "src")]

from threemind.frames import SensoryFrame
from threemind.model import ModelManifest, ModelPackage
from threemind.runtime import ConsciousnessRuntime, RuntimeConfig

from threemind_core import Config, Stimulus
from threemind_runtime import create_engine


def old_runtime(**changes):
    package = ModelPackage(ModelManifest(), consciousness_id="kernel-audit-fixture")
    return ConsciousnessRuntime(package, config=replace(RuntimeConfig(), **changes))


def snapshot(old, new):
    def legacy_node(n):
        return {k: n[k] for k in ("activation", "inhibition", "support", "stability", "plasticity", "touch_count")}

    state = new.capture_state().to_dict()
    return {
        "old": {
            "tick": old.tick,
            "life": old.life_state,
            "nodes": [legacy_node(n) for n in old.nodes.values()],
            "edges": [{k: e[k] for k in ("weight", "stability", "eligibility")} for e in old.edges.values()],
        },
        "new": {
            "time_us": state["time_us"],
            "life": state["life"],
            "nodes": [
                {k: n[k] for k in ("activation", "inhibition", "support", "stability", "touches")}
                for n in state["nodes"]
            ],
            "edges": [{k: e[k] for k in ("weight", "stability", "eligibility")} for e in state["edges"]],
        },
    }


def probes(backend):
    results = {}
    old, new = old_runtime(), create_engine(backend=backend)
    for i in range(3):
        old.receive_frame(SensoryFrame("manual", {11: 0.7, 22: 0.5}))
        new.inject(Stimulus(i * 100000, ((11, 0.7), (22, 0.5))))
        new.advance_to(i * 100000)
        if i == 0:
            results["first_pair"] = snapshot(old, new)
    results["three_repetitions"] = snapshot(old, new)

    old = old_runtime(energy_simulation_enabled=True, energy_initial_reserve=0)
    new = create_engine(Config(energy_simulation_enabled=True, energy_initial_reserve=0), backend=backend)
    old.receive_frame(SensoryFrame("manual", {11: 0.7}))
    new.inject(Stimulus(0, ((11, 0.7),)))
    new.advance_to(0)
    results["zero_energy_receptor_allocation"] = snapshot(old, new)

    old, new = old_runtime(), create_engine(backend=backend)
    old.receive_frame(SensoryFrame("manual", {11: 0.7}))
    new.inject(Stimulus(0, ((11, 0.7),)))
    new.advance_to(0)
    for _ in range(100):
        old.step()
    new.advance_to(10_000_000)
    results["silent_but_ports_open"] = snapshot(old, new)
    for source in ("manual", "ambient", "ai"):
        old.set_source(source, False, confirm_last=True)
    old.step()
    new.close_inputs()
    results["explicitly_closed_after_silence"] = snapshot(old, new)

    new = create_engine(backend=backend)
    new.close_inputs()
    new.advance_to(1_000_000)
    results["never_activated_closed"] = {"life": new.life, "time_us": str(new.time_us)}

    old, new = old_runtime(), create_engine(backend=backend)
    for channel in (11, 22):
        old.enqueue_frame(SensoryFrame("manual", {channel: 0.7}))
        new.inject(Stimulus(100_000, ((channel, 0.7),)))
    old.step()
    new.advance_to(100_000)
    results["two_frames_one_epoch_timestamp"] = snapshot(old, new)

    old, new = old_runtime(), create_engine(backend=backend)
    old.receive_frame(SensoryFrame("manual", {11: 0.7, 22: 0.5}))
    new.inject(Stimulus(0, ((11, 0.7), (22, 0.5))))
    new.advance_to(0)
    old.apply_structural_lesion(node_ids=[old.receptor_index[11]])
    new.intervene(nodes=[1], lesion=True)
    results["node_structural_lesion"] = snapshot(old, new)
    return results


def inventory():
    tree = ast.parse((ROOT / "scripts/audit-legacy-parameters.py").read_text(encoding="utf-8"))
    mapping = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "mapped" for t in statement.targets
        ):
            mapping.update(ast.literal_eval(statement.value))
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "mapped"
                and call.func.attr == "update"
            ):
                mapping.update(ast.literal_eval(call.args[0]))
    old, new = asdict(RuntimeConfig()), asdict(Config())
    assert set(old) == set(mapping), "Parameter coverage drift: review every old field."
    rows = []
    for name, value in old.items():
        target = mapping[name][1]
        candidates = [word.strip() for word in target.split("/")]
        rows.append(
            {
                "old": name,
                "old_default": value,
                "new": target,
                "new_defaults": {k: new[k] for k in candidates if k in new},
            }
        )
    return {
        "old_field_count": len(old),
        "new_field_count": len(new),
        "old_to_new": rows,
        "new_defaults": new,
        "new_fields_without_direct_same_name": sorted(set(new) - set(old)),
    }


def write_parameter_tables(data):
    references = {
        "tick_seconds": "K01–K04",
        "activation_decay": "K01, K12",
        "propagation_gain": "K03, K26",
        "propagation_activation_min": "K26",
        "node_activation_floor": "K12, K26, K29",
        "direct_gain": "K07, K17",
        "learning_rate": "K16",
        "edge_decay": "K21",
        "edge_birth_weight": "K15",
        "stability_gain": "K09, K19",
        "stability_decay": "K20",
        "consolidation_first_gain": "K10, K17",
        "consolidation_repeat_gain": "K10, K17",
        "consolidation_intensity_gain": "K17",
        "consolidation_associative_gain": "K18, K19",
        "consolidation_cap": "K15, K17",
        "prune_threshold": "K24",
        "node_support_gain": "K07, K11",
        "node_support_decay": "K11",
        "node_support_prune_threshold": "K24",
        "node_prune_after": "K24",
        "association_window": "K14",
        "edge_birth_policy": "K13, K14",
        "attention_budget": "K40",
        "attention_competition_enabled": "K40",
        "edge_adaptation_limit": "K18, K23, K39",
        "propagation_limit": "K26, K39",
        "edge_birth_activation_product_min": "K23",
        "local_novelty_gain": "K22",
        "novelty_touch_reference": "K08, K22",
        "homeostasis_enabled": "K31",
        "target_total_activation": "K31",
        "topology_inhibition_enabled": "K27–K30, K41",
        "inhibition_generation_gain": "K28",
        "inhibition_decay": "K29",
        "inhibition_diffusion": "K29",
        "inhibition_response_gain": "K27, K29",
        "inhibition_saturation": "K29",
        "inhibition_propagation_min": "K29",
        "energy_simulation_enabled": "K06, K34",
        "energy_initial_reserve": "K34, R15",
        "energy_capacity": "K34",
        "energy_direct_cost": "K06, K07, K34",
        "energy_associative_cost": "K26, K34",
        "energy_inhibition_cost": "K29, K34",
        "irreversible_energy_death_enabled": "K35",
        "energy_maintenance_cost_per_node": "K35",
        "energy_maintenance_cost_per_edge": "K35",
        "energy_starvation_structural_decay": "K35",
        "energy_starvation_death_ticks": "K35",
        "response_epsilon": "K36",
        "unresponsive_window": "K36",
        "max_nodes": "K06, K39",
        "max_edges": "K39",
        "random_seed": "K32, R02",
    }
    assert set(references) == {row["old"] for row in data["old_to_new"]}
    special = {"node_prune_after", "response_epsilon", "unresponsive_window"}
    added = {
        "trace_tau": "K08, K20",
        "plasticity": "K10, K25",
        "spatial_embedding": "K32",
        "spatial_dimensions": "K32",
        "neighborhood_enabled": "K32",
        "spatial_radius": "K32",
        "spatial_competition_rate": "K33",
    }
    for language in ("zh", "en"):
        header = (
            "| 旧字段 | 旧默认 | 新字段与默认 | 差异索引 |"
            if language == "zh"
            else "| Legacy field | Legacy default | Current field and default | Behavior IDs |"
        )
        lines = [header, "| --- | --- | --- | --- |"]
        covered = set()
        for row in data["old_to_new"]:
            name = row["old"]
            target = row["new"]
            if name in special:
                rendered = "—"
            else:
                keys = [key.strip().removeprefix("Config.") for key in target.split("/")]
                present = {key: data["new_defaults"][key] for key in keys if key in data["new_defaults"]}
                covered.update(present)
                rendered = "; ".join(f"`{key}={json.dumps(v, ensure_ascii=False)}`" for key, v in present.items())
                if name == "tick_seconds":
                    rendered += "; Runtime.clock / speed (R15)"
                if name == "random_seed":
                    rendered += "; RunSpec.seed=20260724; environment_seed=null"
            lines.append(
                f"| `{name}` | `{json.dumps(row['old_default'], ensure_ascii=False)}` | {rendered} | {references[name]} |"
            )
        assert covered | set(added) == set(data["new_defaults"]), "Current parameter coverage drift"
        lines += [
            "",
            (
                "新增的独立字段／从 Manifest 移入 Core 的字段："
                if language == "zh"
                else "Additional independent fields / fields moved from Manifest into Core:"
            ),
            "",
            ("| 当前字段 | 默认值 | 差异索引 |" if language == "zh" else "| Current field | Default | Behavior IDs |"),
            "| --- | --- | --- |",
        ]
        for key, ref in added.items():
            lines.append(f"| `{key}` | `{json.dumps(data['new_defaults'][key])}` | {ref} |")
        path = ROOT / f"docs/{language}/v2-kernel-behavior-audit.md"
        text = path.read_text(encoding="utf-8").split("<!-- PARAMETER_AUDIT_TABLE -->")[0]
        path.write_text(
            text + "<!-- PARAMETER_AUDIT_TABLE -->\n\n" + "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )


def main():
    paths = [
        "core/threemind/runtime.py",
        "core/threemind/model.py",
        "core/threemind/attention.py",
        "core/threemind/frames.py",
        "src/threemind_core/engine.py",
        "src/threemind_core/spec.py",
        "src/threemind_core/attention.py",
        "src/threemind_core/energy.py",
        "src/threemind_core/spatial.py",
        "src/threemind_core/resources.py",
        "crates/threemind-core/src/lib.rs",
        "crates/threemind-core/src/attention.rs",
        "crates/threemind-core/src/energy.rs",
        "crates/threemind-core/src/spatial.rs",
        "crates/threemind-core/src/resources.rs",
        "src/threemind_lab/protocols.py",
        "src/threemind_lab/run_cycle.py",
        "src/threemind_lab/configuration.py",
        "src/threemind_lab/conversation_api.py",
        "src/threemind_runtime/sensory.py",
        "src/threemind_runtime/readout_config.py",
        "src/threemind_runtime/readouts.py",
        "src/threemind_runtime/bus.py",
        "src/threemind_runtime/inheritance.py",
        "src/threemind_runtime/adapters.py",
        "src/threemind_runtime/cli.py",
        "adapters/threemind_adapters/sensors.py",
        "adapters/threemind_adapters/outputs.py",
        "legacy/ui/src/ManagementPages.tsx",
        "threemind-ui/src/v2/inputs.tsx",
        "threemind-ui/src/v2/conversation.tsx",
    ]
    evidence = {
        "schema": "threemind.kernel-behavior-audit/1",
        "baseline_commit": "95a6db5",
        "duration_fix_commit": "0d334e7",
        "native_extension_sha256": hashlib.sha256(
            Path(importlib.util.find_spec("_threemind_native").origin).read_bytes()
        ).hexdigest(),
        "scope": "Frozen local legacy unified runtime versus current causal/7; no cross-version equivalence claim.",
        "sources": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        "inventory": inventory(),
        "probes": {b: probes(b) for b in ("reference", "native")},
    }
    output = ROOT / "docs/benchmarks/2026-09-08-kernel-behavior-audit.json"
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    write_parameter_tables(evidence["inventory"])
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "old_fields": evidence["inventory"]["old_field_count"],
                "new_fields": evidence["inventory"]["new_field_count"],
                "probe_names": list(evidence["probes"]["reference"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
