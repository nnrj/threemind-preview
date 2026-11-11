import json
import subprocess
import sys
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from threemind_core import Stimulus
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_runtime.adapter_checks import builtin_checks, check_input_encoder
from threemind_runtime.adapter_contracts import POLICIES, AdapterContract, manifest, negotiate, read_manifest
from threemind_runtime.registry import AdapterRegistry, default_adapter_registry


def test_all_installed_contracts_are_complete_and_round_trip_without_credentials():
    registry = default_adapter_registry()
    assert {key for key, descriptor in registry.descriptors.items() if descriptor.contract is None} == set(POLICIES)
    assert registry.describe("transformer-probability")["contract"]["mapping"] == "recorded_channels"
    for row in registry.list():
        contract = row["contract"]
        assert contract["adapter_id"] == row["id"] and contract["protocol"] == row["version"]
        assert contract["topology_access"] == "none"
        assert contract["signals"] and contract["backpressure"] and contract["recovery_rule"]
        frozen = manifest(contract)
        assert read_manifest(json.dumps(frozen)) == frozen
        assert not {"password", "token", "secret", "wiring_id"}.intersection(frozen)
    assert registry.describe("physical-world")["contract"]["mapping"] == "fixed_engineering_projection"
    assert "control" in registry.describe("input-modulation")["contract"]["roles"]


def test_manifest_rejects_duplicate_keys_corruption_unknown_fields_and_unbounded_input():
    value = manifest(default_adapter_registry().describe("remote-anonymous")["contract"])
    for invalid in (
        json.dumps(value | {"sha256": "0" * 64}),
        json.dumps(value | {"secret": "fixture"}),
        json.dumps(value).replace('"schema":', '"schema":"wrong", "schema":', 1),
        " " * 131073,
        b"\xff",
    ):
        with pytest.raises(ValueError):
            read_manifest(invalid)
    with pytest.raises(ValueError):
        AdapterContract.model_validate(value["contract"] | {"roles": ["input", "input"]})
    with pytest.raises(ValueError):
        AdapterContract.model_validate(value["contract"] | {"topology_access": "arbitrary_nodes"})


def test_protocol_negotiation_never_grants_device_permission_or_guesses_other_protocols():
    contract = default_adapter_registry().describe("remote-anonymous")["contract"]
    accepted = negotiate(
        contract, {"protocol": contract["protocol"], "roles": ["input"], "transports": ["shared_memory", "websocket"]}
    )
    assert accepted["declared_compatible"] and accepted["selected_transport"] == "websocket"
    assert accepted["execution_authorized"] is False
    wrong_units = negotiate(
        contract,
        {
            "protocol": contract["protocol"],
            "clocks": ["physical_us"],
            "signals": [contract["signals"][0] | {"units": "incompatible-unit"}],
        },
    )
    assert set(wrong_units["issues"]) == {"clock_unavailable", "signal_units_mismatch"}
    result = negotiate(
        contract,
        {
            "protocol": "other/2",
            "roles": ["actuator"],
            "transports": ["shared_memory"],
            "require_restorable_state": True,
        },
    )
    assert set(result["issues"]) == {
        "protocol_mismatch",
        "roles_unavailable",
        "transport_unavailable",
        "restorable_state_not_declared",
    }


def test_custom_binary_adapter_is_not_forced_through_network_or_json_payloads():
    base = default_adapter_registry().descriptors["anonymous-frames"]
    contract = base.public()["contract"] | {
        "adapter_id": "custom-binary",
        "protocol": "custom-dma/3",
        "transports": ["shared_memory", "device_driver"],
        "signals": [
            {"payload": "vendor.binary", "direction": "receives", "units": "signed 16-bit sample, calibrated pascals"},
            {"payload": "core.stimulus", "direction": "emits", "units": "dimensionless amplitude"},
        ],
    }
    descriptor = replace(base, id="custom-binary", version="custom-dma/3", inputs=("vendor.binary",), contract=contract)
    row = AdapterRegistry([descriptor]).describe("custom-binary")
    assert row["contract"]["transports"] == ["shared_memory", "device_driver"]
    with pytest.raises(ValueError, match="explicit reviewed"):
        AdapterRegistry([replace(descriptor, contract=None)]).describe("custom-binary")
    with pytest.raises(ValueError, match="identity"):
        replace(descriptor, version="custom-dma/4").public()


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("adapter", ["remote-anonymous", "anonymous-frames", "text-sensor"])
def test_executable_sdk_checks_actual_pending_recovery_and_raw_observation(backend, adapter):
    result = builtin_checks(adapter, backend=backend)
    assert all(result["checks"].values()) and result["delivered_events"] > 0
    assert len(result["state_hash"]) == 64


def test_sdk_rejects_mutating_nondeterministic_and_unordered_encoders():
    def mutated(value):
        value["fixture"] = 2
        return [Stimulus(0, ((1, 0.2),))]

    with pytest.raises(ValueError, match="mutated"):
        check_input_encoder(mutated, {"fixture": 1})
    counter = 0

    def changing(value):
        nonlocal counter
        counter += 1
        return [Stimulus(counter, ((1, 0.2),))]

    with pytest.raises(ValueError, match="deterministic"):
        check_input_encoder(changing, b"binary fixture")
    with pytest.raises(ValueError, match="ordered"):
        check_input_encoder(lambda _: [Stimulus(10, ()), Stimulus(0, ())], "fixture")


def test_contract_api_validates_declaration_without_creating_tasks_or_installed_plugins(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        response = client.get("/api/v2/adapters/remote-anonymous/manifest")
        assert response.status_code == 200
        value = response.json()
        validated = client.post(
            "/api/v2/adapters/validate",
            json={
                "manifest_json": json.dumps(value),
                "negotiation": {"protocol": value["contract"]["protocol"], "transports": ["websocket"]},
            },
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["matches_installed_declaration"] and not validated.json()["execution_authorized"]
        changed = manifest(value["contract"] | {"adapter_id": "my-custom", "protocol": "custom/1"})
        custom = client.post("/api/v2/adapters/validate", json={"manifest_json": json.dumps(changed)})
        assert custom.status_code == 200 and not custom.json()["matches_installed_declaration"]
        assert (
            client.post(
                "/api/v2/adapters/validate", json={"manifest_json": json.dumps(value | {"sha256": "tampered"})}
            ).status_code
            == 422
        )
        assert client.get("/api/v2/adapters").json()["adapters"][0]["contract"]
        with database.tx(ai_admin=True) as db:
            assert not db.execute("SELECT 1 FROM jobs").fetchone()
            assert not db.execute("SELECT 1 FROM runs").fetchone()


def test_sdk_cli_offline_roundtrip_and_declared_mismatch_exit_code(tmp_path):
    command = [sys.executable, "-X", "utf8", "-m", "threemind_runtime.adapter_cli"]
    described = subprocess.run(command + ["describe", "remote-anonymous"], check=True, capture_output=True)
    path = tmp_path / "adapter.json"
    path.write_bytes(described.stdout)
    checked = subprocess.run(
        command + ["validate", str(path), "--transport", "websocket"], capture_output=True, check=False
    )
    assert checked.returncode == 0 and json.loads(checked.stdout)["structurally_valid"]
    mismatch = subprocess.run(
        command + ["validate", str(path), "--protocol", "different/1"], capture_output=True, check=False
    )
    assert mismatch.returncode == 2 and "protocol_mismatch" in json.loads(mismatch.stdout)["negotiation"]["issues"]
