import sys
import json
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))

from threemind.ai import EnvironmentScheduler, InterpreterScheduler, Provider, environment_prompt


def test_openai_compatible_provider_endpoint() -> None:
    provider = Provider("x", "X", "https://example.test/v1", "model", "secret")
    assert provider.endpoint() == "https://example.test/v1/chat/completions"


def test_environment_prompt_is_external_stimulus_instruction() -> None:
    prompt = environment_prompt(irregularity=0.2, intensity=0.8)
    assert "0.20" in prompt
    assert "0.80" in prompt


def test_environment_scheduler_is_disabled_by_default() -> None:
    scheduler = EnvironmentScheduler(object(), lambda _: None, stimulus_submit=lambda _item, _text, _intensity: None)
    assert scheduler.public()["enabled"] is False
    assert scheduler.public()["running"] is False


def test_interpreter_scheduler_is_disabled_by_default() -> None:
    scheduler = InterpreterScheduler(object(), lambda _: None)
    assert scheduler.public()["enabled"] is False
    assert scheduler.public()["running"] is False


def test_interpreter_scheduler_preserves_trigger_options() -> None:
    scheduler = InterpreterScheduler(object(), lambda _: None)
    saved = scheduler.configure({
        "enabled": False,
        "periodic_enabled": False,
        "on_repeatable_structure": True,
        "active_nodes_enabled": False,
        "on_manual_stimulus": True,
        "listen_background_active_nodes": True,
        "deduplicate_readouts": True,
        "activation_min": .2,
        "activation_max": .7,
    })
    assert saved["periodic_enabled"] is False
    assert saved["on_repeatable_structure"] is True
    assert saved["active_nodes_enabled"] is False
    assert saved["on_manual_stimulus"] is True
    assert saved["listen_background_active_nodes"] is True
    assert saved["deduplicate_readouts"] is True
    assert saved["activation_min"] == .2
    assert saved["activation_max"] == .7


class _RecordingClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def complete(self, _provider: Provider, *, system: str, user: str, **_kwargs: object) -> str:
        assert system
        self.requests.append(json.loads(user))
        return "ordinary external observation"


class _ObservationRuntime:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []
        self.snapshot = {
            "output_frame": {
                "tick": 9,
                "nodes": [
                    {"id": 2, "activation": .2, "stability": .1, "direct_touch": .2, "associative_touch": 0},
                    {"id": 7, "activation": .8, "stability": .3, "direct_touch": .8, "associative_touch": .1},
                    {"id": 3, "activation": .5, "stability": .2, "direct_touch": 0, "associative_touch": .5},
                ],
                "edges": [{"source": 7, "target": 3}, {"source": 2, "target": 3}],
            },
            "metrics": {"tick": 9},
        }

    def observation_snapshot(self) -> dict[str, object]:
        return deepcopy(self.snapshot)

    def record_interpretation(self, text: str, **kwargs: object) -> dict[str, object]:
        row = {"text": text, **kwargs}
        self.recorded.append(row)
        return row


def test_interpreter_trigger_controls_active_node_payload_and_rank() -> None:
    runtime = _ObservationRuntime()
    client = _RecordingClient()
    provider = Provider("test", "Test", "https://example.test", "model", "secret")
    scheduler = InterpreterScheduler(runtime, lambda _provider_id: provider, client)
    scheduler.configure({"enabled": False, "provider_id": "test", "periodic_enabled": False, "on_repeatable_structure": True, "on_manual_stimulus": True, "active_nodes_enabled": True, "activation_min": .1, "activation_max": .9})
    # Invoke synchronously to validate the payload, not the background thread.
    scheduler.enabled = True
    scheduler._interpret("periodic", runtime)
    periodic_frame = client.requests[-1]["snapshot"]["output_frame"]  # type: ignore[index]
    assert "nodes" not in periodic_frame
    scheduler._interpret("repeatable_structure", runtime)
    repeat_frame = client.requests[-1]["snapshot"]["output_frame"]  # type: ignore[index]
    assert [node["id"] for node in repeat_frame["nodes"]] == [7, 3, 2]
    assert repeat_frame["edges"] == [{"source": 7, "target": 3}, {"source": 2, "target": 3}]
    scheduler._interpret("manual_stimulus", runtime)
    manual_frame = client.requests[-1]["snapshot"]["output_frame"]  # type: ignore[index]
    assert [node["id"] for node in manual_frame["nodes"]] == [7, 3, 2]
