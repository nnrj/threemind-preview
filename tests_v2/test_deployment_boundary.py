import json
import tomllib
from pathlib import Path

import pytest

from threemind_core import Config, Engine, Stimulus
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.deployment import declare, inspect_model, verify

ROOT = Path(__file__).resolve().parents[1]


def test_research_masks_are_preserved_and_require_explicit_deployment_declaration():
    engine = Engine(Config())
    engine.inject(Stimulus(0, ((1, 1.0), (2, 0.7))))
    engine.advance_to(100000)
    engine.intervene(nodes=[1])
    initial = engine.capture_state()
    raw = ArtifactCodec.encode(initial, "json")
    assert inspect_model(raw)["has_interventions"]
    with pytest.raises(ValueError, match="silencing"):
        declare(raw)
    manifest = declare(raw, acknowledge_interventions=True)
    assert verify(raw, json.loads(json.dumps(manifest))) == manifest
    assert engine.capture_state().digest == initial.digest
    restored = Engine(state=ArtifactCodec.decode(raw))
    assert restored.capture_state().digest == initial.digest
    assert restored.silenced_nodes == {1}
    with pytest.raises(ValueError, match="does not match"):
        verify(raw, manifest | {"state_hash": "other"})
    # Explicit unsilencing is a separate intervention; never done by the exporter.
    restored.intervene(nodes=[1], action="unsilence")
    clean = ArtifactCodec.encode(restored.capture_state(), "json")
    assert not declare(clean)["has_interventions"]


def test_package_ownership_is_disjoint_and_runtime_does_not_require_lab_services():
    lab = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = tomllib.loads((ROOT / "packages/runtime/pyproject.toml").read_text())
    assert "threemind-runtime==" + runtime["project"]["version"] in lab["project"]["dependencies"]
    assert set(lab["tool"]["setuptools"]["packages"]["find"]["include"]).isdisjoint(
        runtime["tool"]["setuptools"]["packages"]["find"]["include"]
    )
    assert not any(
        name in d
        for d in runtime["project"]["dependencies"]
        for name in ("fastapi", "psycopg", "httpx", "torch", "mujoco", "threemind-lab")
    )
    transformer = tomllib.loads((ROOT / "packages/transformer/pyproject.toml").read_text())
    owned = [set(item["tool"]["setuptools"]["packages"]["find"]["include"]) for item in (lab, runtime, transformer)]
    assert all(owned[i].isdisjoint(owned[j]) for i in range(3) for j in range(i))
    assert "threemind-transformer==" + transformer["project"]["version"] in lab["project"]["dependencies"]
    assert not any("threemind-lab" in dependency for dependency in transformer["project"]["dependencies"])


def test_runtime_adapter_catalogue_does_not_import_external_computation(monkeypatch):
    import builtins

    from threemind_runtime.registry import default_adapter_registry

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("threemind_transformer", "threemind_lab", "torch", "transformers")):
            raise AssertionError("runtime catalogue imported an external computation package")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    assert default_adapter_registry().describe("language-transformer")["contract"]["topology_access"] == "none"
