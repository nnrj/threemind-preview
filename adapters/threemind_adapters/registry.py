"""Application-side registry for ThreeMind adapters.

The registry is deliberately outside ``threemind.core``.  Buses carry anonymous
frames only; this registry describes installed devices, validates their public
configuration, and lets an application host route configuration to them.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .telemetry import default_telemetry_config, host_signal_names, process_signal_names, runtime_signal_names


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    id: str
    name: str
    direction: str
    bus: str
    description: str
    schema: dict[str, Any]
    default_enabled: bool = True
    dependencies: tuple[str, ...] = ()
    input_ports: tuple[str, ...] = ()
    output_ports: tuple[str, ...] = ()
    ui: dict[str, Any] | None = None

    def public(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "direction": self.direction,
            "bus": self.bus, "description": self.description,
            "schema": deepcopy(self.schema), "dependencies": list(self.dependencies),
            "ports": {"inputs": list(self.input_ports), "outputs": list(self.output_ports)},
            "enabled": bool(state.get("enabled", self.default_enabled)),
            "config": deepcopy(state.get("config", {})),
            "ui": deepcopy(self.ui or {}),
        }


class AdapterRegistry:
    """Registry metadata and JSON-schema-shaped configuration validation.

    It does not execute adapters and does not sit on a bus.  The application
    host owns adapter instances and calls them after a validated update.
    """

    def __init__(self, descriptors: list[AdapterDescriptor]) -> None:
        self._descriptors = {item.id: item for item in descriptors}

    def ids(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    def describe(self, adapter_id: str, state: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._descriptors[adapter_id].public(state.get(adapter_id, {}))
        except KeyError as exc:
            raise ValueError(f"unknown adapter: {adapter_id}") from exc

    def list(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return [descriptor.public(state.get(adapter_id, {})) for adapter_id, descriptor in self._descriptors.items()]

    def update(self, state: dict[str, Any], adapter_id: str, *, enabled: bool | None, config: dict[str, Any] | None) -> dict[str, Any]:
        descriptor = self._descriptors.get(adapter_id)
        if descriptor is None:
            raise ValueError(f"unknown adapter: {adapter_id}")
        entry = state.setdefault(adapter_id, {"enabled": descriptor.default_enabled, "config": {}})
        if enabled is not None:
            entry["enabled"] = bool(enabled)
        if config is not None:
            if not isinstance(config, dict):
                raise ValueError("adapter config must be an object")
            merged = dict(entry.get("config", {}))
            self._validate_object(config, descriptor.schema, path="config")
            self._deep_merge(merged, config)
            entry["config"] = merged
        return descriptor.public(entry)

    @classmethod
    def _deep_merge(cls, target: dict[str, Any], patch: dict[str, Any]) -> None:
        for name, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(name), dict):
                cls._deep_merge(target[name], value)
            else:
                target[name] = deepcopy(value)

    @classmethod
    def _validate_object(cls, value: dict[str, Any], schema: dict[str, Any], *, path: str) -> None:
        if schema.get("type") not in {None, "object"}:
            raise ValueError(f"{path} schema must describe an object")
        allowed = schema.get("properties", {})
        unknown = set(value) - set(allowed)
        if unknown:
            raise ValueError(f"unsupported adapter settings at {path}: {', '.join(sorted(unknown))}")
        for name, child in value.items():
            cls._validate_value(child, allowed[name], path=f"{path}.{name}")

    @classmethod
    def _validate_value(cls, value: Any, rule: dict[str, Any], *, path: str) -> None:
        kind = rule.get("type")
        if kind == "object":
            if not isinstance(value, dict): raise ValueError(f"{path} must be an object")
            cls._validate_object(value, rule, path=path)
            return
        if kind == "boolean" and not isinstance(value, bool): raise ValueError(f"{path} must be boolean")
        if kind == "string" and not isinstance(value, str): raise ValueError(f"{path} must be text")
        if kind in {"number", "integer"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)): raise ValueError(f"{path} must be numeric")
            if kind == "integer" and not float(value).is_integer(): raise ValueError(f"{path} must be an integer")
            if "minimum" in rule and value < rule["minimum"]: raise ValueError(f"{path} is below minimum")
            if "maximum" in rule and value > rule["maximum"]: raise ValueError(f"{path} is above maximum")
        if "enum" in rule and value not in rule["enum"]: raise ValueError(f"{path} is not an allowed value")


def default_adapter_registry() -> AdapterRegistry:
    number = lambda title, minimum, maximum, step: {"type": "number", "title": title, "minimum": minimum, "maximum": maximum, "multipleOf": step}
    telemetry_schema = lambda scope: {
        "type": "object", "properties": {
            "sample_interval_ms": {"type": "integer", "title": "Sampling interval (ms)", "minimum": 250, "maximum": 60000},
            "smoothing": number("Temporal smoothing", 0, .999, .01),
            "levels_enabled": {"type": "boolean", "title": "Enable all levels"},
            "changes_enabled": {"type": "boolean", "title": "Enable all changes"},
            "signals": {"type": "object", "title": "Physical signals", "properties": {
                name: {"type": "object", "title": name, "properties": {
                    "level": {"type": "boolean", "title": "Level"},
                    "change": {"type": "boolean", "title": "Change"},
                    "gain": number("Gain", 0, 100, .05),
                    **({
                        "reference_override": {"type": "boolean", "title": "Override automatic reference"},
                        "reference": number("Normalization reference", 1e-12, 1e18, 1),
                    } if "reference" in default_telemetry_config(scope)["signals"][name] else {}),
                }} for name in (
                    host_signal_names() if scope == "host"
                    else process_signal_names() if scope == "process"
                    else runtime_signal_names()
                )
            }},
        },
    }
    host_groups = [
        {"id": "compute", "signals": ["cpu_load", "cpu_frequency"]},
        {"id": "memory", "signals": ["memory_pressure", "memory_commit_pressure", "swap_pressure", "page_in_rate", "page_out_rate", "page_fault_rate"]},
        {"id": "disk", "signals": ["disk_read_rate", "disk_write_rate", "disk_read_iops", "disk_write_iops"]},
        {"id": "network", "signals": ["network_receive_rate", "network_send_rate", "network_receive_packets", "network_send_packets", "network_error_rate", "network_drop_rate"]},
        {"id": "power", "signals": ["battery_level", "ac_power", "battery_charging"]},
    ]
    process_groups = [
        {"id": "compute", "signals": ["cpu_load"]},
        {"id": "memory", "signals": ["rss_pressure", "private_memory_pressure", "page_fault_rate"]},
        {"id": "io", "signals": ["read_rate", "write_rate"]},
        {"id": "scheduler", "signals": ["thread_count", "handle_count", "scheduler_latency_ms", "tick_execution_time_ms"]},
    ]
    runtime_groups = [
        {"id": "compute", "signals": ["thread_cpu_load", "epoch_busy_ratio", "epoch_execution_time_ms"]},
        {"id": "scheduler", "signals": ["scheduler_latency_ms"]},
    ]
    return AdapterRegistry([
        AdapterDescriptor("body-background", "Body environmental filter", "input", "input", "Filters a supplied ambient field through a simulated body before InputBus.", {
            "type": "object", "properties": {
                "sampling_ticks": {"type": "integer", "title": "Sampling interval (ticks)", "minimum": 1, "maximum": 10000},
                "threshold": number("Sensory threshold", 0, 1, .005), "adaptation": number("Adaptation", 0, 1, .01),
                "noise": number("Amplitude noise", 0, .5, .005), "channel_count": {"type": "integer", "title": "Body sensory channels", "minimum": 1, "maximum": 64},
            }}, False, ("ambient-field",), ("environment.frame",), ("sensory.frame",)),
        AdapterDescriptor("ambient-field", "Ambient environment source", "input", "input", "Continuous stochastic environmental field routed through enabled sensory adapters.", {"type": "object", "properties": {
            "transient_rate": number("Transient event rate", 0, 1, .005),
            "transient_amplitude": number("Transient amplitude", 0, 1, .005),
            "transient_lifetime_min": {"type": "integer", "title": "Minimum transient lifetime (ticks)", "minimum": 1, "maximum": 100000},
            "transient_lifetime_max": {"type": "integer", "title": "Maximum transient lifetime (ticks)", "minimum": 1, "maximum": 100000},
        }}, False, (), (), ("environment.frame",)),
        AdapterDescriptor("interoceptive-field", "Interoceptive body source", "input", "input", "Optional internal-body signal source; it does not replace the environment.", {"type": "object", "properties": {
            "channel_count": {"type": "integer", "title": "Internal channels", "minimum": 1, "maximum": 64}, "amplitude": number("Signal amplitude", 0, 1, .005),
        }}, False, (), (), ("sensory.frame",)),
        AdapterDescriptor("host-telemetry-field", "Host physical telemetry", "input", "input", "Shared physical host telemetry mapped per consciousness to anonymous sensory channels. It is external sensation, never Core energy.", telemetry_schema("host"), True, (), (), ("sensory.frame",), {"component": "telemetry-table", "scope": "host", "groups": host_groups}),
        AdapterDescriptor("process-telemetry-field", "ThreeMind process telemetry", "input", "input", "Opt-in telemetry for the whole ThreeMind service process. It must not be interpreted as per-consciousness resource usage.", telemetry_schema("process"), False, (), (), ("sensory.frame",), {"component": "telemetry-table", "scope": "process", "groups": process_groups}),
        AdapterDescriptor("runtime-telemetry-field", "Consciousness runtime physical feedback", "input", "input", "Opt-in per-consciousness physical feedback measured from that runtime's real thread CPU time and timing cost. It is delayed sensory input and never a Core control signal.", telemetry_schema("runtime"), False, (), (), ("sensory.frame",), {"component": "telemetry-table", "scope": "runtime", "groups": runtime_groups}),
        AdapterDescriptor("text-sensor", "Text sensor", "input", "input", "Encodes external text into anonymous sensory channels and exposes its temporal framing resolution.", {"type": "object", "properties": {
            "frame_characters": {"type": "integer", "title": "Characters per causal frame", "minimum": 1},
            "inter_frame_epochs": {"type": "integer", "title": "Environmental epochs between frames", "minimum": 1},
        }}, True, (), ("text.payload",), ("sensory.frame",)),
        AdapterDescriptor("auditory-sensor", "Auditory sensor", "input", "input", "Encodes decoded physical sound samples into anonymous level/rise/fall sensory frames. It performs no speech recognition.", {"type": "object", "properties": {
            "target_sample_rate": {"type": "integer", "title": "Target sample rate", "minimum": 4000, "maximum": 192000},
            "sensory_frame_rate": number("Sensory frames per second", 1, 200, 1),
            "encoding": {"type": "string", "title": "Physical encoding", "enum": ["band-energy", "waveform"]},
            "band_count": {"type": "integer", "title": "Frequency bands", "minimum": 3, "maximum": 64},
            "minimum_frequency": number("Minimum frequency", 1, 96000, 1),
            "maximum_frequency": number("Maximum frequency", 1, 96000, 1),
            "waveform_bins": {"type": "integer", "title": "Waveform bins", "minimum": 4, "maximum": 256},
            "level_enabled": {"type": "boolean", "title": "Encode current level"},
            "change_enabled": {"type": "boolean", "title": "Encode rise and fall"},
            "gain": number("Sensory gain", 0, 100, .05),
            "inter_frame_epochs": {"type": "integer", "title": "Input epochs between audio frames", "minimum": 1, "maximum": 10000},
            "upload_limit_mb": {"type": "integer", "title": "Upload limit (MB)", "minimum": 1, "maximum": 4096},
            "live_enabled": {"type": "boolean", "title": "Allow live microphone sessions"},
        }}, True, (), ("audio.pcm",), ("sensory.frame",), {"component": "media-adapter", "media_kind": "audio"}),
        AdapterDescriptor("visual-sensor", "Visual sensor", "input", "input", "Encodes decoded image/video pixels as local anonymous retinal patches. It performs no OCR or object recognition.", {"type": "object", "properties": {
            "target_width": {"type": "integer", "title": "Retinal width", "minimum": 2, "maximum": 256},
            "target_height": {"type": "integer", "title": "Retinal height", "minimum": 2, "maximum": 256},
            "sensory_frame_rate": number("Maximum sensory frames per second", .2, 60, .2),
            "patch_width": {"type": "integer", "title": "Local patch width", "minimum": 1, "maximum": 32},
            "patch_height": {"type": "integer", "title": "Local patch height", "minimum": 1, "maximum": 32},
            "filter_mode": {"type": "string", "title": "Physical filter", "enum": ["luminance", "edges", "threshold"]},
            "threshold": number("Threshold", 0, 1, .01),
            "level_enabled": {"type": "boolean", "title": "Encode current level"},
            "change_enabled": {"type": "boolean", "title": "Encode rise and fall"},
            "gain": number("Sensory gain", 0, 100, .05),
            "inter_patch_epochs": {"type": "integer", "title": "Input epochs between retinal patches", "minimum": 1, "maximum": 10000},
            "upload_limit_mb": {"type": "integer", "title": "Upload limit (MB)", "minimum": 1, "maximum": 4096},
            "live_enabled": {"type": "boolean", "title": "Allow live camera sessions"},
        }}, True, (), ("image.pixels", "video.pixels"), ("sensory.frame",), {"component": "media-adapter", "media_kind": "visual"}),
        AdapterDescriptor("structural-readout", "Structural readout", "output", "output", "Observes repeatable anonymous output structures without modifying Core.", {"type": "object", "properties": {}}, True, (), ("activation.frame",), ("readout.event",)),
        AdapterDescriptor("temporal-convergence-readout", "Temporal convergence readout", "output", "output", "Observes stimulus-anchored activation duration, strength and convergence across multiple OutputBus ticks without modifying Core.", {"type": "object", "properties": {}}, True, (), ("activation.frame", "input.envelope"), ("temporal.readout.event",)),
        AdapterDescriptor("acoustic-output-organ", "Acoustic output organ", "output", "output", "Maps anonymous activation to oscillator controls without labels, text-to-speech or semantic decoding.", {"type": "object", "properties": {
            "maximum_voices": {"type": "integer", "title": "Maximum simultaneous voices", "minimum": 1, "maximum": 128},
            "minimum_activation": number("Minimum activation", 0, 1, .01),
            "output_interval_ms": {"type": "integer", "title": "Output interval (ms)", "minimum": 20, "maximum": 10000},
        }}, True, (), ("activation.frame",), ("audio.control",), {"component": "media-output", "media_kind": "audio"}),
        AdapterDescriptor("activation-image-projector", "Activation image projector", "output", "output", "Projects anonymous activation into a deterministic image without semantic labels.", {"type": "object", "properties": {
            "width": {"type": "integer", "title": "Output width", "minimum": 8, "maximum": 512},
            "height": {"type": "integer", "title": "Output height", "minimum": 8, "maximum": 512},
            "output_interval_ms": {"type": "integer", "title": "Output interval (ms)", "minimum": 20, "maximum": 10000},
        }}, True, (), ("activation.frame",), ("image.pixels",), {"component": "media-output", "media_kind": "visual"}),
        AdapterDescriptor("ai-debug-duplex", "AI experiment/debug bridge", "duplex", "input/output", "Host-side research bridge. It can submit explicitly authorized experimental carriers and observe OutputBus evidence, but never changes Core topology or creates automatic feedback.", {"type": "object", "properties": {
            "max_steps": {"type": "integer", "title": "Maximum plan steps", "minimum": 1, "maximum": 200},
            "max_stimuli": {"type": "integer", "title": "Maximum submitted stimuli", "minimum": 1, "maximum": 100},
            "max_text_length": {"type": "integer", "title": "Maximum carrier characters", "minimum": 1, "maximum": 50000},
            "max_wait_ticks": {"type": "integer", "title": "Maximum wait ticks per command", "minimum": 1, "maximum": 1000000},
            "auto_run_default": {"type": "boolean", "title": "Automatic execution default"},
        }}, True, ("text-sensor", "structural-readout"), ("experiment.command", "output.frame"), ("text.payload", "experiment.observation")),
        AdapterDescriptor("energy-budget", "Finite metabolic energy supply", "input", "resource", "Optional finite-rate external supply for Core's explicitly enabled energy simulation. It never ranks or filters stimuli.", {"type": "object", "properties": {
            "supply_per_tick": number("Supply per observed Core tick", 0, 1000000, .001),
            "total_supply_limit": number("Total supply limit (0 = no lifetime cap)", 0, 1000000000, .01),
        }}, False, (), (), ("energy.supply",)),
        AdapterDescriptor("network-transport", "Network transport", "duplex", "input/output", "Authenticated anonymous remote sensory and output transport.", {"type": "object", "properties": {
            "allow_remote_modulation": {"type": "boolean", "title": "Allow remote physiology modulation"}, "modulation_timeout_ticks": {"type": "integer", "title": "Modulation timeout", "minimum": 1, "maximum": 1000000}, "output_interval_ms": {"type": "integer", "title": "Output interval (ms)", "minimum": 20, "maximum": 10000},
        }}, False),
    ])
