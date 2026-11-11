"""Small, anonymous baseline experiments, independent of sensory encoders and databases."""

CASES = {
    "birth_repeat_and_propagation": {
        "config": {},
        "actions": [
            ["input", 0, [[11, 0.7], [22, 0.5]], 1.0],
            ["advance", 0],
            ["input", 70_000, [[11, 0.7], [22, 0.5]], 1.0],
            ["advance", 110_000],
            ["input", 123_457, [[11, 0.3], [33, 0.6]], 1.0],
            ["advance", 400_001],
            ["advance", 2_500_000],
        ],
    },
    "saturation_consumes_energy": {
        "config": {"energy_simulation_enabled": True, "inhibition": False},
        "actions": [
            ["input", 0, [[1, 1.0], [2, 1.0]], 1.0],
            ["input", 0, [[1, 1.0], [2, 1.0]], 1.0],
            ["advance", 0],
            ["advance", 210_000],
        ],
    },
    "weak_lanes_inhibition_and_forgetting": {
        "config": {"delay_us": 17_311},
        "actions": [
            ["input", 0, [[4, 0.1], [5, 0.2], [6, 0.05]], 1.0],
            ["advance", 133_371],
            ["input", 199_991, [[5, 0.8], [7, 0.4]], 1.0],
            ["advance", 500_000],
            ["advance", 5_000_000],
        ],
    },
    "waiting_quiet_death": {
        "config": {"propagation_rate": 0.0},
        "actions": [
            ["advance", 2_000_000],
            ["input", 2_000_000, [[99, 0.7]], 1.0],
            ["advance", 2_000_000],
            ["advance", 5_000_000],
        ],
    },
    "disconnect_delete_new_identity": {
        "config": {},
        "actions": [
            ["input", 0, [[1, 0.7], [2, 0.8]], 1.0],
            ["advance", 100_000],
            ["intervene", {"action": "disconnect_edges", "edges": [[1, 2]]}],
            ["advance", 105_000],
            ["intervene", {"action": "delete_nodes", "nodes": [2]}],
            ["input", 106_000, [[2, 0.6]], 1.0],
            ["advance", 110_000],
        ],
    },
    "isolated_pruning": {
        "config": {"energy_simulation_enabled": True, "energy_initial_reserve": 0.0, "node_prune_after_us": 100_000},
        "actions": [
            ["input", 0, [[71, 0.5]], 1.0],
            ["advance", 0],
            ["advance", 200_000],
        ],
    },
}


def exercise(case, *, config_type, stimulus_type, factory):
    engine = factory(config_type(**case["config"]))
    snapshots = []
    for action in case["actions"]:
        if action[0] == "input":
            engine.inject(stimulus_type(action[1], tuple(map(tuple, action[2])), action[3]))
        elif action[0] == "advance":
            engine.advance_to(action[1])
            snapshots.append(engine.capture_state().to_dict())
        elif action[0] == "intervene":
            engine.intervene(**action[1])
        else:
            raise AssertionError(action)
    return snapshots
