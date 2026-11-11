"""Shared declarations and exact protocol negotiation, with no transport or Core dependency.

A declaration is not an executable driver or a certificate of its behaviour.
Payload schemas stay owned by the specialised codecs and ports.
"""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .world_schema import Model

VERSION = "threemind.adapter-contract/1"
MANIFEST = "threemind.adapter-manifest/1"
MAX_BYTES = 131072
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.:/-]{0,127}$")]
Text = Annotated[str, Field(min_length=1, max_length=1200)]
Role = Literal["input", "actuator", "observer", "filter", "control", "resource"]
Transport = Literal["in_process", "http", "websocket", "browser_media", "device_driver", "shared_memory"]
Clock = Literal["model_us", "physical_us", "host_capture", "host_monotonic"]


class Signal(Model):
    payload: Identifier
    direction: Literal["receives", "emits"]
    units: Text


class AdapterContract(Model):
    version: Literal["threemind.adapter-contract/1"] = VERSION
    adapter_id: Identifier
    protocol: Identifier
    roles: list[Role] = Field(min_length=1, max_length=6)
    transports: list[Transport] = Field(min_length=1, max_length=6)
    signals: list[Signal] = Field(min_length=1, max_length=32)
    clocks: list[Clock] = Field(min_length=1, max_length=4)
    identity_fields: list[Identifier] = Field(max_length=16)
    identity_rule: Text
    mapping: Literal[
        "uniform_codec",
        "recorded_channels",
        "explicit_source_policy",
        "fixed_engineering_projection",
        "read_only",
        "explicit_control",
        "resource_accounting",
    ]
    recovery: Literal["state_and_inputs", "recorded_inputs", "external_state_required", "stateless"]
    recovery_rule: Text
    backpressure: Text
    lifecycle: Text
    errors: Text
    required_capabilities: list[Identifier] = Field(max_length=16)
    topology_access: Literal["none"] = "none"

    @model_validator(mode="after")
    def consistent(self):
        for key in ("roles", "transports", "clocks", "identity_fields", "required_capabilities"):
            values = getattr(self, key)
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate contract {key}")
        if len({(s.direction, s.payload) for s in self.signals}) != len(self.signals):
            raise ValueError("duplicate signal direction and payload")
        if self.mapping == "explicit_control" and "control" not in self.roles:
            raise ValueError("explicit control mapping requires a separately declared control role")
        if self.mapping == "resource_accounting" and "resource" not in self.roles:
            raise ValueError("resource accounting requires a separately declared resource role")
        if self.mapping == "fixed_engineering_projection" and not {"actuator", "observer"}.intersection(self.roles):
            raise ValueError("fixed projection must declare its actuator or observer role")
        return self


class Negotiation(Model):
    protocol: Identifier
    roles: list[Role] = Field(default_factory=list, max_length=6)
    transports: list[Transport] = Field(default_factory=list, max_length=6)
    require_restorable_state: bool = False
    clocks: list[Clock] = Field(default_factory=list, max_length=4)
    signals: list[Signal] = Field(default_factory=list, max_length=32)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def manifest(contract):
    body = (contract if isinstance(contract, AdapterContract) else AdapterContract.model_validate(contract)).model_dump(
        mode="json"
    )
    return {"schema": MANIFEST, "contract": body, "sha256": hashlib.sha256(canonical(body)).hexdigest()}


def read_manifest(raw):
    if not isinstance(raw, (str, bytes)) or len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_BYTES:
        raise ValueError("adapter manifest exceeds 128 KiB")

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate adapter manifest JSON key")
            value[key] = item
        return value

    def constant(_):
        raise ValueError("non-finite adapter manifest value")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(value, dict) or set(value) != {"schema", "contract", "sha256"} or value["schema"] != MANIFEST:
            raise ValueError("unsupported adapter manifest or fields")
        expected = manifest(value["contract"])
        if value != expected:
            raise ValueError("adapter manifest checksum or canonical fields differ")
        return expected
    except (RecursionError, UnicodeError) as error:
        raise ValueError("adapter manifest encoding or nesting invalid") from error


def negotiate(contract, request):
    contract = contract if isinstance(contract, AdapterContract) else AdapterContract.model_validate(contract)
    request = request if isinstance(request, Negotiation) else Negotiation.model_validate(request)
    issues = []
    if request.protocol != contract.protocol:
        issues.append("protocol_mismatch")
    if set(request.roles) - set(contract.roles):
        issues.append("roles_unavailable")
    selected = next((p for p in request.transports if p in contract.transports), None)
    if request.transports and selected is None:
        issues.append("transport_unavailable")
    if request.require_restorable_state and contract.recovery != "state_and_inputs":
        issues.append("restorable_state_not_declared")
    if set(request.clocks) - set(contract.clocks):
        issues.append("clock_unavailable")
    offered = {(signal.direction, signal.payload): signal.units for signal in contract.signals}
    for required in request.signals:
        key = (required.direction, required.payload)
        if key not in offered and "signal_unavailable" not in issues:
            issues.append("signal_unavailable")
        elif key in offered and offered[key] != required.units and "signal_units_mismatch" not in issues:
            issues.append("signal_units_mismatch")
    return {
        "declared_compatible": not issues,
        "issues": issues,
        "selected_transport": selected,
        "execution_authorized": False,
        "capabilities_to_check": contract.required_capabilities,
        "scope": "Declaration comparison only; no device opened, code loaded or Core modified.",
    }


# Each installed adapter has an explicit policy. A new registry entry must add
# a reviewed contract here instead of silently inheriting guessed capabilities.
POLICIES = {
    "input-bus": (["input"], "recorded_channels", "state_and_inputs"),
    "anonymous-frames": (["input"], "recorded_channels", "recorded_inputs"),
    "stimulus-units": (["input"], "recorded_channels", "recorded_inputs"),
    "source-policy": (["filter"], "explicit_source_policy", "state_and_inputs"),
    "text-sensor": (["input"], "uniform_codec", "recorded_inputs"),
    "mujoco-environment": (["input", "actuator"], "fixed_engineering_projection", "state_and_inputs"),
    "physical-world": (["input", "actuator"], "fixed_engineering_projection", "state_and_inputs"),
    "robot-task": (["input", "actuator"], "fixed_engineering_projection", "state_and_inputs"),
    "ambient-field": (["input"], "uniform_codec", "state_and_inputs"),
    "body-filter": (["filter"], "uniform_codec", "state_and_inputs"),
    "simulated-interoception": (["input"], "uniform_codec", "state_and_inputs"),
    "replay": (["input"], "recorded_channels", "recorded_inputs"),
    "host-telemetry": (["input"], "uniform_codec", "external_state_required"),
    "process-telemetry": (["input"], "uniform_codec", "external_state_required"),
    "runtime-telemetry": (["input"], "uniform_codec", "external_state_required"),
    "auditory-sensor": (["input"], "uniform_codec", "recorded_inputs"),
    "visual-sensor": (["input"], "uniform_codec", "recorded_inputs"),
    "microphone": (["input"], "uniform_codec", "external_state_required"),
    "camera": (["input"], "uniform_codec", "external_state_required"),
    "acoustic-output-organ": (["actuator"], "fixed_engineering_projection", "external_state_required"),
    "activation-image-projector": (["observer"], "fixed_engineering_projection", "stateless"),
    "structural-readout": (["observer"], "read_only", "state_and_inputs"),
    "temporal-readout": (["observer"], "read_only", "state_and_inputs"),
    "activity-readout": (["observer"], "read_only", "state_and_inputs"),
    "energy-supply": (["resource"], "resource_accounting", "state_and_inputs"),
    "input-modulation": (["control"], "explicit_control", "state_and_inputs"),
    "remote-anonymous": (["input", "observer", "control", "resource"], "uniform_codec", "external_state_required"),
}


SIGNAL_UNITS = {
    "core.stimulus": "time_us: integer us; channel amplitude: dimensionless [0,1]; intensity: finite nonnegative",
    "numeric.frames": "time_us: integer us; anonymous amplitude: dimensionless [0,1]",
    "remote.numeric": "time_us: integer us; remote signed amplitude: dimensionless [-1,1]",
    "recorded.frames": "Original recorded stimulus units and integer model us; no rescaling implied",
    "audio.pcm": "Normalised PCM amplitude [-1,1]; sample_rate: Hz; frame time: us",
    "audio.control": "Oscillator frequency: Hz; amplitude: dimensionless; model time: us",
    "image.pixels": "Pixel channel levels per payload format; image dimensions: px",
    "video.pixels": "Pixel channel levels per payload format; image dimensions: px; frame time: us",
    "activation.frame": "Anonymous Core activation values, dimensionless; model time: us",
    "anonymous.output": "Recorded anonymous output values and model time in us; projection scope is explicit",
    "energy.supply": "Abstract Core energy units and model time in us; not joules without an explicit calibration",
    "physical.counter": "Source-specific counter units, availability and calibration retained with each measurement",
    "physical.measurement": "Named physical measurement units and port calibration from the world/body protocol",
    "synthetic.measurement": "Declared synthetic field coordinates and amplitude; not physical measurements",
    "scalar.modulation": "Named scalar ranges from the control protocol; time and expiry in model us",
    "remote.scalar": "Named modulation or energy scalar units from the separately authorised control/resource port",
    "core.modulation": "Named scalar ranges from the control protocol; time and expiry in model us",
    "carrier.envelope": "Versioned carrier identity and model timestamps in us; payload-owned measurement units",
    "input.envelope": "Provenance identity and model timestamps in us; no semantic or causal labels in Core",
    "text.carrier": "Unicode carrier and declared normalisation; encoded frame intervals in us",
    "carrier.source": "Source identity; no physical unit",
    "source.policy": "Admission and competition policy; no physical unit",
    "admission.decision": "Admission status and explicit budget counts; no physical unit",
    "observation.labels": "External observer labels; no physical unit or Core semantics",
    "readout.evidence": "Recorded raw activation, derived measures and model times in us; per-column units retained",
    "receipt.evidence": "Receipt identity, sequence and declared clock timestamps; not a physical response guarantee",
}


def installed_contract(descriptor):
    if descriptor.contract is not None:
        value = AdapterContract.model_validate(descriptor.contract)
        expected = {("receives", p) for p in descriptor.inputs} | {("emits", p) for p in descriptor.outputs}
        if (
            value.adapter_id != descriptor.id
            or value.protocol != descriptor.version
            or {(p.direction, p.payload) for p in value.signals} != expected
        ):
            raise ValueError("custom adapter contract identity, protocol or signals differ from its descriptor")
        return value
    if descriptor.id not in POLICIES:
        raise ValueError("custom adapters require an explicit reviewed contract declaration")
    roles, mapping, recovery = POLICIES[descriptor.id]
    identity = ["sensory_seed"] if mapping in ("uniform_codec", "fixed_engineering_projection") else []
    if descriptor.root:
        identity.append("configuration." + descriptor.root)
    clocks, transports = ["model_us"], ["in_process"]
    if descriptor.id == "remote-anonymous":
        identity += ["wiring_id", "codec.polarity"]
        transports = ["in_process", "http", "websocket"]
        clocks += ["host_capture"]
    if descriptor.id in ("mujoco-environment", "physical-world", "robot-task"):
        clocks += ["physical_us"]
        identity += ["environment.protocol"]
        if descriptor.id == "physical-world":
            identity += ["world.version", "world.sensor_ids", "world.actuator_ids"]
        if descriptor.id == "robot-task":
            identity += ["robot_protocol", "robot_protocol.asset_sha256", "robot_protocol.control"]
    if descriptor.id.endswith("-telemetry"):
        clocks += ["host_monotonic"]
    if descriptor.id in ("microphone", "camera", "acoustic-output-organ"):
        transports += ["browser_media"]
        clocks += ["host_capture"]
    recovery_rule = {
        "state_and_inputs": "Restore complete owner Runtime context, pending inputs and adapter state with the same protocol and numerical backend; a Core model alone is insufficient.",
        "recorded_inputs": "Replay explicitly retained carriers or delivered frames and their timing; live physical history cannot be reconstructed from the model.",
        "external_state_required": "External device, process, transport session or playback state is not restored by the Core model; reconnect explicitly and preserve logical identity.",
        "stateless": "Recompute this projection from the same recorded input; this does not recover display or external hardware state.",
    }[recovery]
    signals = [
        Signal(payload=p, direction=direction, units=SIGNAL_UNITS[p])
        for direction, values in (("receives", descriptor.inputs), ("emits", descriptor.outputs))
        for p in values
    ]
    return AdapterContract(
        adapter_id=descriptor.id,
        protocol=descriptor.version,
        roles=roles,
        transports=transports,
        signals=signals,
        clocks=clocks,
        identity_fields=identity,
        identity_rule="Preserve declared codec identity and effective configuration. Labels and credentials do not define meanings or graph edges. This contract contains no deployment wiring values.",
        mapping=mapping,
        recovery=recovery,
        recovery_rule=recovery_rule,
        backpressure="InputBus rejects over-budget admission; callers reserve the whole carrier. OutputBus evidence consumers fail visibly; LatestOutput and UI views explicitly count skips. Transport-specific receipt and loss rules still apply.",
        lifecycle="Enable, configure and reconnect through the owning adapter host. Keep accepted in-flight inputs and observation provenance. Explicit stateful recovery is separate from new birth.",
        errors="Report invalid payloads, unavailable dependencies, time/calibration errors, capacity refusal and lost confirmation. Never replace missing observations with zero or silently invent physical input.",
        required_capabilities=list(descriptor.capabilities),
    )
