from dataclasses import asdict, replace

import pytest

from threemind_lab.protocols import RunSpec
from threemind_runtime.registry import AdapterRegistry, default_adapter_registry


def test_registry_uses_executable_defaults_strict_validation_and_no_aliases():
    registry = default_adapter_registry()
    spec = RunSpec().model_dump()
    for descriptor in registry.descriptors.values():
        row = registry.describe(descriptor.id, spec)
        if descriptor.config_type:
            expected = asdict(descriptor.config_type())
            if descriptor.id == "activity-readout":
                # Omitted historical RunSpec leaves the newer reader disabled;
                # explicit creation defaults may enable it without upgrading old runs.
                expected["enabled"] = False
            assert row["configuration"] == expected
            row["configuration"]["changed"] = True
            assert "changed" not in registry.describe(descriptor.id, spec)["configuration"]
            with pytest.raises(ValueError):
                descriptor.configuration({"made_up_parameter": 1})
    assert registry.describe("mujoco-environment", spec)["configured_enabled"]
    assert not registry.describe("ambient-field", spec)["configured_enabled"]
    assert not registry.describe("remote-anonymous", spec)["configured_enabled"]
    assert registry.describe("input-modulation", spec)["configured_enabled"]
    for root in ("text_sensor", "auditory_sensor", "body_filter", "host_telemetry"):
        changed = spec | {root: spec[root] | {"enabled": "false"}}
        with pytest.raises(ValueError):
            registry.list(changed)


def test_registry_rejects_duplicate_identity_and_preserves_explicit_selection():
    registry = default_adapter_registry()
    first = next(iter(registry.descriptors.values()))
    with pytest.raises(ValueError, match="duplicate"):
        AdapterRegistry([first, first])
    with pytest.raises(ValueError, match="direction"):
        AdapterRegistry([replace(first, direction="meaning")])
    with pytest.raises(ValueError, match="unknown"):
        registry.describe("invented")
    spec = RunSpec(environment="manual", interoception={"enabled": True}, body_filter={"enabled": True}).model_dump()
    rows = {r["id"]: r for r in registry.list(spec)}
    assert rows["simulated-interoception"]["configured_enabled"]
    assert rows["body-filter"]["configured_enabled"]  # Configuration is distinct from an active environment binding.
    assert rows["body-filter"]["dependencies"] == ["environment:mujoco|ambient|world|robot"]
    assert not rows["mujoco-environment"]["configured_enabled"]
    roots = {d.root for d in registry.descriptors.values() if d.root}
    expected = {key for key in spec if key not in {"config", "intervention"} and isinstance(spec[key], dict)}
    assert roots == expected


def test_capability_failures_remain_distinct_from_partial_and_available(monkeypatch):
    from threemind_runtime import capabilities

    def unavailable():
        raise ImportError("missing optional package in isolated probe")

    monkeypatch.setattr(capabilities, "image_probe", unavailable)
    monkeypatch.setattr(capabilities, "av_probe", lambda names: unavailable())
    result = capabilities.probe_api()
    assert result["scope"] == "api" and result["checked_at"]
    assert result["features"]["api.media_image"]["state"] == "unavailable"
    assert result["features"]["api.media_audio"]["state"] == "partial"
    assert result["features"]["api.media_audio"]["pcm_wav"]["state"] == "available"
    assert result["features"]["api.media_video"]["state"] == "unavailable"
    assert "missing optional package" in result["features"]["api.media_image"]["reason"]
    monkeypatch.setattr(capabilities, "av_probe", lambda names: {"state": "available"})
    assert capabilities.probe_api()["features"]["api.media_video"]["state"] == "unavailable"
    assert (
        capabilities.check("partial", lambda: {"state": "partial", "reason": "some signals absent"})["state"]
        == "partial"
    )
    monkeypatch.setattr(capabilities, "physics_probe", unavailable)
    result = capabilities.probe_worker("reference")
    assert result["features"]["worker.core"]["state"] == "available"
    assert result["features"]["worker.mujoco"]["state"] == "unavailable"
    for scope in ("host", "process"):
        assert all("raw_value" not in r for r in result["features"][f"worker.telemetry_{scope}"]["readings"].values())
