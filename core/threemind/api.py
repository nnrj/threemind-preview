from __future__ import annotations

import os
import json
import hashlib
import asyncio
import uuid
import sqlite3
import sys
import copy
import time
import base64
import csv
import io
from datetime import datetime, timezone
from queue import SimpleQueue
from threading import Event, RLock, Thread, current_thread
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .model import (
    MODEL_PACKAGE_SUFFIX,
    READABLE_MODEL_PACKAGE_SUFFIXES,
    ModelManifest,
    ModelPackage,
    is_model_package_path,
)
from .runtime import ConsciousnessRuntime
from .frames import OutputFrame
from threemind_adapters import AcousticOutputOrgan, ActivationImageProjector, AdapterRegistry, AmbientSensorAdapter, AuditorySensorAdapter, BodyAdapter, CharacterDriver, DEFAULT_AUDITORY_CONFIG, DEFAULT_TEMPORAL_CONFIG, DEFAULT_VISUAL_CONFIG, HostTelemetryAdapter, HostTelemetryCollector, InteroceptiveAdapter, MetabolicEnergyAdapter, MetricReading, NetworkProtocolError, NetworkTransportAdapter, ProcessTelemetryAdapter, RemotePhysiologyModulator, RemoteSensoryAdapter, RuntimeTelemetryAdapter, StructuralReadoutAdapter, TelemetryAuditStore, TelemetrySample, TemporalConvergenceReadoutAdapter, TextSensorAdapter, VisualSensorAdapter, default_adapter_registry, default_telemetry_config
from threemind_media import MediaAuditStore, MediaCodecService, MediaProtocolError, MediaSizeLimitError, LiveAudioPacket, LiveVideoPacket, decode_live_packet
from threemind_adapters.notifications import NotificationService
from .ai import ChatClient, ENVIRONMENT_SYSTEM, EnvironmentScheduler, InterpreterScheduler, Provider, environment_prompt
from .security import SecretStore
from .manager import RuntimeManager
from .persistence import FileBackendTooLarge, build_backend
from .archive import ArchiveIndexer, ArchiveRepository, ArchiveWriter
from .history import HistoryCheckpointWriter
from .experiments import ExperimentController, ExperimentError, ExperimentStore, TEMPLATE_DEFINITIONS
from .storage import direct_child, scan_data_directory
from threemind_analytics import AnalyticsService, EvidenceExporter, InterventionPolicy, InterventionStore


class _HostObservedRuntime(ConsciousnessRuntime):
    """Application-owned, read-only timing wrapper for physical telemetry.

    The counters in this class observe real execution cost around Core calls.
    They do not participate in graph dynamics.  An opt-in sensory adapter may
    later encode a completed measurement window and enqueue it for a future
    input epoch, which prevents synchronous recursion.
    """

    def __init__(self, package: ModelPackage, *, monotonic_clock: Any = time.perf_counter, thread_cpu_clock: Any = time.thread_time) -> None:
        super().__init__(package)
        self._host_monotonic_clock = monotonic_clock
        self._host_thread_cpu_clock = thread_cpu_clock
        self._host_epoch_execution_ms: float | None = None
        self._host_tick_scheduler_latency_ms: float | None = None
        self._host_last_tick_started: float | None = None
        self._host_continuity_revision = 0
        self._runtime_telemetry_lock = RLock()
        self._runtime_telemetry_window_started = float(self._host_monotonic_clock())
        self._runtime_telemetry_cpu_seconds = 0.0
        self._runtime_telemetry_wall_seconds = 0.0
        self._runtime_telemetry_epoch_count = 0
        self._runtime_telemetry_scheduler_latency_ms = 0.0
        self._runtime_telemetry_scheduler_count = 0
        self._runtime_telemetry_tick_start: int | None = None
        self._runtime_telemetry_tick_end: int | None = None
        self._runtime_telemetry_input_envelopes: dict[str, dict[str, Any]] = {}
        self._runtime_telemetry_last_sample: TelemetrySample | None = None

    def _advance(self, frames: list[Any], *, delivery_contexts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        result = super()._advance(frames, delivery_contexts=delivery_contexts)
        if delivery_contexts:
            with self._runtime_telemetry_lock:
                for raw in delivery_contexts:
                    envelope_id = str(raw.get("envelope_id") or "")
                    if not envelope_id:
                        continue
                    # Keep transport provenance only. Carrier text, labels and
                    # semantic metadata never enter this audit relationship.
                    self._runtime_telemetry_input_envelopes[envelope_id] = {
                        "envelope_id": envelope_id,
                        "adapter_id": str(raw.get("adapter_id") or "unknown"),
                        "source": str(raw.get("source") or "unknown"),
                        "frame_index": raw.get("frame_index"),
                        "frame_count": raw.get("frame_count"),
                        "tick": int(self.tick),
                    }
        return result

    def _advance_input_epoch(self) -> None:
        # Keep each measured epoch and its opaque input-envelope links in the
        # same observation window. The RLock is application-side only; Core
        # never reads it or any resulting counter.
        with self._runtime_telemetry_lock:
            started = float(self._host_monotonic_clock())
            thread_cpu_started = float(self._host_thread_cpu_clock())
            scheduler_latency: float | None = None
            tick_before = int(self.tick)
            if current_thread() is self._thread:
                previous = self._host_last_tick_started
                scheduler_latency = (
                    max(0.0, started - previous - max(.002, self.config.tick_seconds)) * 1000.0
                    if previous is not None
                    else None
                )
                self._host_tick_scheduler_latency_ms = scheduler_latency
                self._host_last_tick_started = started
            try:
                super()._advance_input_epoch()
            finally:
                finished = float(self._host_monotonic_clock())
                wall_seconds = max(0.0, finished - started)
                cpu_seconds = max(0.0, float(self._host_thread_cpu_clock()) - thread_cpu_started)
                self._host_epoch_execution_ms = wall_seconds * 1000.0
                self._runtime_telemetry_cpu_seconds += cpu_seconds
                self._runtime_telemetry_wall_seconds += wall_seconds
                self._runtime_telemetry_epoch_count += 1
                if scheduler_latency is not None:
                    self._runtime_telemetry_scheduler_latency_ms += scheduler_latency
                    self._runtime_telemetry_scheduler_count += 1
                tick_after = int(self.tick)
                if tick_after > tick_before:
                    first_tick = tick_before + 1
                    self._runtime_telemetry_tick_start = first_tick if self._runtime_telemetry_tick_start is None else min(self._runtime_telemetry_tick_start, first_tick)
                    self._runtime_telemetry_tick_end = tick_after if self._runtime_telemetry_tick_end is None else max(self._runtime_telemetry_tick_end, tick_after)

    def host_epoch_execution_ms(self) -> float | None:
        return self._host_epoch_execution_ms

    def host_tick_scheduler_latency_ms(self) -> float | None:
        return self._host_tick_scheduler_latency_ms

    def host_continuity_revision(self) -> int:
        """Host-only marker for sensory discontinuities such as pause/resume."""
        return self._host_continuity_revision

    def reset_runtime_telemetry_window(self, *, monotonic_seconds: float | None = None) -> None:
        """Discard only external measurement baselines and pending audit links."""
        with self._runtime_telemetry_lock:
            self._runtime_telemetry_window_started = float(monotonic_seconds if monotonic_seconds is not None else self._host_monotonic_clock())
            self._runtime_telemetry_cpu_seconds = 0.0
            self._runtime_telemetry_wall_seconds = 0.0
            self._runtime_telemetry_epoch_count = 0
            self._runtime_telemetry_scheduler_latency_ms = 0.0
            self._runtime_telemetry_scheduler_count = 0
            self._runtime_telemetry_tick_start = None
            self._runtime_telemetry_tick_end = None
            self._runtime_telemetry_input_envelopes.clear()

    def consume_runtime_telemetry(self, monotonic_seconds: float | None = None) -> TelemetrySample:
        """Close one real-time measurement window for this consciousness."""
        sample_started = float(self._host_monotonic_clock())
        captured_monotonic = float(monotonic_seconds if monotonic_seconds is not None else sample_started)
        with self._runtime_telemetry_lock:
            elapsed = max(1e-9, captured_monotonic - self._runtime_telemetry_window_started)
            cpu_seconds = self._runtime_telemetry_cpu_seconds
            wall_seconds = self._runtime_telemetry_wall_seconds
            epoch_count = self._runtime_telemetry_epoch_count
            scheduler_total = self._runtime_telemetry_scheduler_latency_ms
            scheduler_count = self._runtime_telemetry_scheduler_count
            tick_start = self._runtime_telemetry_tick_start
            tick_end = self._runtime_telemetry_tick_end
            input_envelopes = list(self._runtime_telemetry_input_envelopes.values())
            self._runtime_telemetry_window_started = captured_monotonic
            self._runtime_telemetry_cpu_seconds = 0.0
            self._runtime_telemetry_wall_seconds = 0.0
            self._runtime_telemetry_epoch_count = 0
            self._runtime_telemetry_scheduler_latency_ms = 0.0
            self._runtime_telemetry_scheduler_count = 0
            self._runtime_telemetry_tick_start = None
            self._runtime_telemetry_tick_end = None
            self._runtime_telemetry_input_envelopes.clear()
        thread_cpu_load = min(1.0, max(0.0, cpu_seconds / elapsed))
        epoch_busy_ratio = min(1.0, max(0.0, wall_seconds / elapsed))
        execution_ms = (wall_seconds * 1000.0 / epoch_count) if epoch_count else None
        scheduler_ms = (scheduler_total / scheduler_count) if scheduler_count else None
        runtime_metrics = {
            "thread_cpu_load": MetricReading.ratio(thread_cpu_load, reference_source="measured runtime thread CPU time / monotonic sample interval"),
            "epoch_busy_ratio": MetricReading.ratio(epoch_busy_ratio, reference_source="measured runtime epoch wall time / monotonic sample interval"),
            "epoch_execution_time_ms": MetricReading.scaled(execution_ms, unit="ms", reference=250, reference_source="configured reference") if execution_ms is not None else MetricReading.unavailable("ms", "no runtime epoch completed during sample window"),
            "scheduler_latency_ms": MetricReading.scaled(scheduler_ms, unit="ms", reference=250, reference_source="configured reference") if scheduler_ms is not None else MetricReading.unavailable("ms", "no scheduled runtime epoch completed during sample window"),
        }
        sample = TelemetrySample(
            sample_id=str(uuid.uuid4()),
            captured_at_utc=datetime.now(timezone.utc).isoformat(),
            monotonic_seconds=captured_monotonic,
            backend="python-thread-time+monotonic",
            host={},
            process={},
            duration_ms=max(0.0, float(self._host_monotonic_clock()) - sample_started) * 1000.0,
            runtime=runtime_metrics,
            scope="runtime",
            owner_consciousness_id=self.consciousness_id,
            context={
                "sample_interval_seconds": elapsed,
                "thread_cpu_seconds": cpu_seconds,
                "epoch_wall_seconds": wall_seconds,
                "epoch_count": epoch_count,
                "tick_start": tick_start,
                "tick_end": tick_end,
                "input_envelopes": input_envelopes,
            },
        )
        with self._runtime_telemetry_lock:
            self._runtime_telemetry_last_sample = sample
        return sample

    def runtime_telemetry_status(self) -> dict[str, Any]:
        with self._runtime_telemetry_lock:
            sample = self._runtime_telemetry_last_sample
        if sample is None:
            return {
                "backend": "python-thread-time+monotonic", "dependency": "full",
                "last_sample_time": None, "available_metrics": [],
                "unavailable_metrics": {}, "recent_error": None,
            }
        return {
            "backend": sample.backend, "dependency": "full",
            "last_sample_time": sample.captured_at_utc,
            "last_sample_id": sample.sample_id,
            "last_duration_ms": sample.duration_ms,
            "available_metrics": [name for name, value in sample.runtime.items() if value.available],
            "unavailable_metrics": {name: value.unavailable_reason for name, value in sample.runtime.items() if not value.available},
            "recent_error": sample.recent_error,
        }

    def _mark_host_discontinuity(self) -> None:
        self._host_continuity_revision += 1
        self._host_last_tick_started = None
        self._host_tick_scheduler_latency_ms = None
        self.reset_runtime_telemetry_window()

    def start(self, *, paused: bool = False) -> None:
        was_paused = self._paused
        super().start(paused=paused)
        if was_paused != self._paused:
            self._mark_host_discontinuity()

    def pause(self) -> None:
        was_paused = self._paused
        super().pause()
        if not was_paused:
            self._mark_host_discontinuity()

    def resume(self) -> None:
        was_paused = self._paused
        super().resume()
        if was_paused:
            self._mark_host_discontinuity()


def _new_runtime(package: ModelPackage) -> ConsciousnessRuntime:
    """Create a Core runtime wrapped by non-semantic host instrumentation."""
    return _HostObservedRuntime(package)


_project_root = Path(__file__).resolve().parents[2]
_configured_data = os.getenv("THREEMIND_DATA", "data")
DATA_DIR = Path(_configured_data)
if not DATA_DIR.is_absolute():
    DATA_DIR = _project_root / DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = DATA_DIR / "ui-settings.json"


def _default_adapter_preferences() -> dict[str, dict[str, Any]]:
    """Return a fresh, explicit application-side adapter configuration.

    The adapter registry describes valid fields, while this function is the
    single source for their runtime defaults.  Keeping the values explicit
    also makes the checked-in example settings useful without making runtime
    startup depend on that repository file.
    """
    return {
        "body-background": {
            "enabled": False,
            "config": {"sampling_ticks": 1, "threshold": .035, "adaptation": .55, "noise": .02, "channel_count": 3},
        },
        "ambient-field": {
            "enabled": False,
            "config": {"transient_rate": .04, "transient_amplitude": .12, "transient_lifetime_min": 2, "transient_lifetime_max": 14},
        },
        "interoceptive-field": {"enabled": False, "config": {"channel_count": 2, "amplitude": .08}},
        "host-telemetry-field": {"enabled": True, "config": default_telemetry_config("host")},
        "process-telemetry-field": {"enabled": False, "config": default_telemetry_config("process")},
        "runtime-telemetry-field": {"enabled": False, "config": default_telemetry_config("runtime")},
        "auditory-sensor": {"enabled": True, "config": copy.deepcopy(DEFAULT_AUDITORY_CONFIG)},
        "visual-sensor": {"enabled": True, "config": copy.deepcopy(DEFAULT_VISUAL_CONFIG)},
        "acoustic-output-organ": {"enabled": True, "config": {"maximum_voices": 12, "minimum_activation": .08, "output_interval_ms": 100}},
        "activation-image-projector": {"enabled": True, "config": {"width": 48, "height": 32, "output_interval_ms": 150}},
        "text-sensor": {"enabled": True, "config": {"frame_characters": 24, "inter_frame_epochs": 1}},
        "structural-readout": {"enabled": True, "config": {}},
        "temporal-convergence-readout": {"enabled": True, "config": {}},
        "ai-debug-duplex": {
            "enabled": True,
            "config": {"max_steps": 24, "max_stimuli": 12, "max_text_length": 2000, "max_wait_ticks": 5000, "auto_run_default": False},
        },
        "energy-budget": {"enabled": False, "config": {"supply_per_tick": .004, "total_supply_limit": 0.0}},
        "network-transport": {
            "enabled": False,
            "config": {"allow_remote_modulation": False, "modulation_timeout_ticks": 300, "output_interval_ms": 150},
        },
    }


DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "notifications": {"enabled": False, "sender": "ThreeMind <onboarding@resend.dev>", "recipients": [], "language": "follow-ui", "resend_api_key_configured": False, "resend_api_key_hint": ""},
    "ui": {"locale": "zh-CN"},
    "observer": {
        "snapshot_enabled": True,
        "activation_threshold": .055,
        "min_nodes": 3,
        "max_nodes": 7,
        "min_internal_edges": 2,
        "recurrence_window_ticks": 240,
        "min_occurrences": 4,
        "min_span_ticks": 8,
        "alert_cooldown_ticks": 1200,
        # These are output-adapter choices only.  They never feed a value
        # back into the consciousness runtime or alter its graph dynamics.
        "read_touched_activity": True,
        "repeatable_structure_readout": True,
        "label_sort_by_activation": True,
        "label_display_limit": 0,
        # The temporal reader starts at a causal input envelope and observes
        # the subsequent OutputBus frames.  It is read-only and independent
        # from the existing single-tick structural reader above.
        "temporal": dict(DEFAULT_TEMPORAL_CONFIG),
    },
    "visualization": {"mode": "3d", "renderer": "threejson", "canvas_shape": "circle", "three_shape": "glow", "style": "organic", "continuous_motion": False},
    "archive": {"prompt_for_snapshot_name": True},
    "ai": {
        "environment": {"enabled": False, "provider_id": "", "frequency_ticks": 120, "random_frequency": True, "intensity": .7, "irregularity": .65},
        "interpreter": {"enabled": False, "provider_id": "", "frequency_ticks": 300, "periodic_enabled": True, "on_repeatable_structure": False, "active_nodes_enabled": True, "on_manual_stimulus": False, "listen_background_active_nodes": False, "deduplicate_readouts": False, "activation_min": .08, "activation_max": 1.0, "language": "auto"},
        "auto_snapshot": {"enabled": False, "frequency_ticks": 0, "on_repeatable_structure": True, "on_interpreter_important": True},
    },
    "stimuli": {
        "manual_enabled": True, "ai_enabled": True, "background_enabled": True,
        "submit_on_enter": True, "bypass_filter_sources": [],
        # Exact source policies are an application-side control surface.  They
        # never alter carrier encoding or graph state; they decide whether an
        # already-defined source may submit a frame and whether that frame
        # competes at the attention gate.
        "source_policies": {
            "ui-text": {"enabled": True, "bypass_attention": False},
            "cli-text": {"enabled": True, "bypass_attention": False},
            "ai-environment": {"enabled": True, "bypass_attention": False},
            # The research bridge is an ordinary external source.  It is
            # intentionally visible and separately controllable; it never
            # grants an experiment planner privileged Core access.
            "ai-debug": {"enabled": True, "bypass_attention": False},
            "ui-audio": {"enabled": True, "bypass_attention": False},
            "ui-image": {"enabled": True, "bypass_attention": False},
            "ui-video": {"enabled": True, "bypass_attention": False},
            "live-microphone": {"enabled": True, "bypass_attention": False},
            "live-camera": {"enabled": True, "bypass_attention": False},
            # Master permission for every passive external background source.
            # Random ambient and physical telemetry remain independent adapter
            # switches below this boundary.
            "background": {"enabled": True, "bypass_attention": False},
        },
    },
    # Persistent desired adapter settings.  The live registry below is the
    # authoritative runtime state; this object only restores it next launch.
    "adapter_preferences": {},
    "conversation": {
        "show_environment_stimuli": False,
        "show_triggering_environment_stimuli": True,
        # Presentation only: background-driven passive output remains fully
        # recorded, but an ambient field should not flood the chat view by
        # default.
        "show_background_readouts": False,
    },
    "experiments": {
        "provider_id": "",
        "language": "follow-ui",
        "auto_run_default": False,
    },
}


def _merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively overlay user settings while preserving unknown fields."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def _default_ui_settings_document() -> dict[str, Any]:
    """Build the complete first-run/example document with explicit defaults."""
    result = copy.deepcopy(DEFAULT_UI_SETTINGS)
    result["adapter_preferences"] = _default_adapter_preferences()
    return result


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Replace a JSON document atomically after a complete UTF-8 write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _create_ui_settings_if_missing(payload: dict[str, Any]) -> bool:
    """Create the first-run file without ever replacing an existing file."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with SETTINGS_PATH.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        return False
    return True


def _load_ui_settings() -> dict[str, Any]:
    first_run = _default_ui_settings_document()
    if not SETTINGS_PATH.exists() and _create_ui_settings_if_missing(first_run):
        return first_run
    try:
        loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("UI settings must be a JSON object")
        # Existing files are never rewritten here.  Missing nested defaults
        # are resolved in memory and are persisted only after an explicit save.
        return _merge(copy.deepcopy(DEFAULT_UI_SETTINGS), loaded)
    except (OSError, ValueError, TypeError):
        # A malformed but existing user file is likewise left untouched.
        return copy.deepcopy(DEFAULT_UI_SETTINGS)


ui_settings = _load_ui_settings()


def _migrate_legacy_ambient_setting(settings: dict[str, Any]) -> bool | None:
    """Detach the old random-ambient switch from the new background master.

    Historically ``ambient_enabled`` selected the stochastic ambient source.
    Reinterpreting it as the outer permission would let an old decision to
    disable random noise silently disable physical telemetry as well.  Return
    the old value for the adapter bootstrap and establish an independent,
    default-on background permission.
    """
    stimuli = settings.setdefault("stimuli", {})
    legacy = stimuli.pop("ambient_enabled", None)
    stimuli.setdefault("background_enabled", True)
    return bool(legacy) if legacy is not None else None


_legacy_random_ambient_enabled = _migrate_legacy_ambient_setting(ui_settings)
adapter_registry = default_adapter_registry()
adapter_runtime_state: dict[str, dict[str, Any]] = {}


def _bootstrap_adapter_settings() -> None:
    """Build one live registry state from persisted preferences.

    Adapter preferences have one persisted source and
    ``adapter_runtime_state`` is the single live source.  Unpublished legacy
    host-load data is intentionally not translated into the new structured
    real-time telemetry format.
    """
    global adapter_runtime_state
    preferences = ui_settings.setdefault("adapter_preferences", {})
    legacy_adapters = ui_settings.get("adapters", {})
    body = dict(ui_settings.get("body", {}))
    energy = dict(body.get("energy_supply") or body.get("energy_modulator") or {})
    network = dict(ui_settings.get("network", {}))
    defaults = _default_adapter_preferences()
    # Preserve one-time compatibility with pre-registry local settings.  New
    # first-run documents already contain the explicit registry configuration.
    if body:
        defaults["body-background"]["enabled"] = bool(body.get("enabled", False))
        for key, fallback in defaults["body-background"]["config"].items():
            defaults["body-background"]["config"][key] = body.get(key, fallback)
    if energy:
        defaults["energy-budget"]["enabled"] = bool(energy.get("enabled", False))
        defaults["energy-budget"]["config"] = {
            "supply_per_tick": float(energy.get("supply_per_tick", energy.get("recovery", .004))),
            "total_supply_limit": float(energy.get("total_supply_limit", 0.0)),
        }
    if network:
        defaults["network-transport"]["enabled"] = bool(network.get("enabled", False))
        for key, fallback in defaults["network-transport"]["config"].items():
            defaults["network-transport"]["config"][key] = network.get(key, fallback)
    merged: dict[str, dict[str, Any]] = {}
    for adapter_id, default in defaults.items():
        saved = preferences.get(adapter_id, legacy_adapters.get(adapter_id, {}))
        saved = saved if isinstance(saved, dict) else {}
        # Before the pipeline existed, ``body.enabled`` defaulted to true and
        # silently changed the meaning of every environment frame.  Do not
        # carry that historical default into the new baseline.  Only an
        # explicit new-registry preference can re-enable the body filter.
        if adapter_id == "body-background" and adapter_id not in preferences:
            saved = {**saved, "enabled": False}
        saved_config = saved.get("config", {}) if isinstance(saved.get("config", {}), dict) else {}
        if adapter_id == "energy-budget":
            # One-time in-memory migration from the unpublished attention
            # modulator. Old ranking/cost fields are not carried forward.
            saved_config = {
                "supply_per_tick": saved_config.get("supply_per_tick", saved_config.get("recovery", default["config"]["supply_per_tick"])),
                "total_supply_limit": saved_config.get("total_supply_limit", default["config"]["total_supply_limit"]),
            }
        merged_config = copy.deepcopy(default["config"])
        AdapterRegistry._deep_merge(merged_config, saved_config)
        merged[adapter_id] = {
            "enabled": bool(saved.get("enabled", default["enabled"])),
            "config": merged_config,
        }
    # Physical telemetry is the new baseline background. Random ambient noise
    # remains available but is opt-in. An explicit persisted setting always
    # wins over these defaults.
    if "ambient-field" not in preferences:
        merged["ambient-field"]["enabled"] = (
            _legacy_random_ambient_enabled
            if _legacy_random_ambient_enabled is not None
            else False
        )
    if "host-telemetry-field" not in preferences:
        merged["host-telemetry-field"]["enabled"] = True
    preferences.clear(); preferences.update(json.loads(json.dumps(merged)))
    adapter_runtime_state = json.loads(json.dumps(merged))
    # Never persist two competing adapter configurations.
    ui_settings.pop("adapters", None); ui_settings.pop("body", None); ui_settings.pop("network", None)


def _adapter_enabled(adapter_id: str) -> bool:
    return bool(adapter_runtime_state.get(adapter_id, {}).get("enabled", False))


def _adapter_config(adapter_id: str) -> dict[str, Any]:
    return dict(adapter_runtime_state.get(adapter_id, {}).get("config", {}))


_MODEL_ADAPTER_DEFAULTS = {
    "ambient-field": False,
    "host-telemetry-field": True,
    "process-telemetry-field": False,
    "runtime-telemetry-field": False,
    "auditory-sensor": False,
    "visual-sensor": False,
    "acoustic-output-organ": False,
    "activation-image-projector": False,
}


def _model_adapter_route(adapter_id: str) -> str:
    return {
        "ambient-field": "environment.frame -> input.bus",
        "host-telemetry-field": "host.telemetry -> sensory.frame -> input.bus",
        "process-telemetry-field": "process.telemetry -> sensory.frame -> input.bus",
        "runtime-telemetry-field": "runtime.telemetry -> sensory.frame -> input.bus",
        "auditory-sensor": "audio.pcm -> sensory.frame -> input.bus",
        "visual-sensor": "image.pixels|video.pixels -> sensory.frame -> input.bus",
        "acoustic-output-organ": "output.bus -> audio.control",
        "activation-image-projector": "output.bus -> image.pixels",
    }.get(adapter_id, "adapter -> bus")


def _model_adapter_binding(item: ConsciousnessRuntime, adapter_id: str) -> dict[str, Any]:
    for binding in item.manifest.adapter_bindings:
        if str(binding.get("adapter_id")) == adapter_id:
            if adapter_id in _MODEL_ADAPTER_DEFAULTS and not isinstance(binding.get("config"), dict):
                binding["config"] = copy.deepcopy(_adapter_config(adapter_id))
            return binding
    binding = {
        "adapter_id": adapter_id,
        "enabled": bool(_MODEL_ADAPTER_DEFAULTS.get(adapter_id, False)),
        "route": _model_adapter_route(adapter_id),
    }
    if adapter_id in _MODEL_ADAPTER_DEFAULTS:
        binding["config"] = copy.deepcopy(_adapter_config(adapter_id))
    # Resolve an absent declaration into an explicit package declaration. The
    # next package save therefore never relies on a hidden host default.
    item.manifest.adapter_bindings.append(binding)
    return binding


def _model_adapter_enabled(item: ConsciousnessRuntime, adapter_id: str) -> bool:
    return bool(_model_adapter_binding(item, adapter_id).get("enabled", False))


def _model_adapter_config(item: ConsciousnessRuntime, adapter_id: str) -> dict[str, Any]:
    """Return the package-resolved adapter config used by this instance."""
    binding = _model_adapter_binding(item, adapter_id)
    declared = binding.get("config")
    resolved = copy.deepcopy(_adapter_config(adapter_id))
    if isinstance(declared, dict):
        AdapterRegistry._deep_merge(resolved, declared)
    binding["config"] = resolved
    return copy.deepcopy(resolved)


def _telemetry_delivery_enabled(item: ConsciousnessRuntime, adapter_id: str) -> bool:
    return (
        item.life_state != "dead"
        and not item._paused
        and bool(ui_settings.get("stimuli", {}).get("background_enabled", True))
        and item.source_status().get("ambient", True)
        and _source_policy("background")["enabled"]
        and _adapter_enabled(adapter_id)
        and _model_adapter_enabled(item, adapter_id)
    )


_EXPERIMENT_LIMIT_KEYS = ("max_steps", "max_stimuli", "max_text_length", "max_wait_ticks")


def _experiment_run_limits(overrides: dict[str, Any] | None) -> dict[str, int]:
    """Resolve one run's visible bridge limits without granting a bypass.

    A browser may choose a *smaller* per-run bound for a controlled protocol,
    but the only authority able to expand a bound is the registered
    ``ai-debug-duplex`` adapter configuration.  This keeps AI plan validation
    and the Adapter Manager's displayed values aligned.
    """
    base = _adapter_config("ai-debug-duplex")
    unknown = set((overrides or {})) - set(_EXPERIMENT_LIMIT_KEYS)
    if unknown:
        raise ExperimentError(f"unsupported experiment limit: {sorted(unknown)[0]}")
    result: dict[str, int] = {}
    for key in _EXPERIMENT_LIMIT_KEYS:
        try:
            maximum = int(base.get(key, 1))
            requested = int((overrides or {}).get(key, maximum))
        except (TypeError, ValueError) as error:
            raise ExperimentError(f"experiment limit {key} must be an integer") from error
        if maximum < 1 or requested < 1 or requested > maximum:
            raise ExperimentError(f"experiment limit {key} may only tighten the configured bridge bound")
        result[key] = requested
    return result


def _source_policy(source: str) -> dict[str, bool]:
    """Resolve an exact input-source policy with legacy-class fallback."""
    stimuli = ui_settings.get("stimuli", {})
    policies = stimuli.get("source_policies", {})
    raw = policies.get(source, {}) if isinstance(policies, dict) else {}
    kind = "ai" if source.startswith("ai") else "ambient" if source.startswith(("ambient", "body", "background", "interoceptive", "host-load")) else "manual"
    legacy_enabled = bool(stimuli.get(f"{kind}_enabled", True))
    legacy_bypass = kind in set(stimuli.get("bypass_filter_sources", []))
    return {
        "enabled": bool(raw.get("enabled", legacy_enabled)),
        "bypass_attention": bool(raw.get("bypass_attention", legacy_bypass)),
    }


def _sync_source_policy_legacy() -> None:
    """Expose exact policies through the legacy runtime source switches."""
    stimuli = ui_settings.setdefault("stimuli", {})
    policies = stimuli.setdefault("source_policies", {})
    defaults = DEFAULT_UI_SETTINGS["stimuli"]["source_policies"]
    for source, default in defaults.items():
        entry = policies.setdefault(source, {})
        entry.setdefault("enabled", default["enabled"])
        entry.setdefault("bypass_attention", default["bypass_attention"])
    # ``manual`` is the Core's legacy carrier class, not a synonym for text.
    # Keep it enabled while any explicitly controlled human-facing sensory
    # source is enabled. Exact policies still decide which adapter may submit
    # a frame, so disabling text cannot accidentally disable another sense.
    stimuli["manual_enabled"] = any(bool(policies[source]["enabled"]) for source in (
        "ui-text", "cli-text", "ui-audio", "ui-image", "ui-video",
        "live-microphone", "live-camera",
    ))
    stimuli["ai_enabled"] = bool(policies["ai-environment"]["enabled"] or policies["ai-debug"]["enabled"])
    stimuli["background_enabled"] = bool(policies["background"]["enabled"])
    stimuli.pop("ambient_enabled", None)


def _project_legacy_source_switches_into_policies(settings: dict[str, Any]) -> None:
    """Accept old grouped switches at the API boundary without dual state."""
    stimuli = settings.get("stimuli")
    if not isinstance(stimuli, dict):
        return
    policies = stimuli.setdefault("source_policies", {})
    if not isinstance(policies, dict):
        policies = {}
        stimuli["source_policies"] = policies
    mapping = {
        "manual_enabled": ("ui-text", "cli-text"),
        "ai_enabled": ("ai-environment", "ai-debug"),
        "background_enabled": ("background",),
    }
    for legacy_name, exact_sources in mapping.items():
        if legacy_name not in stimuli:
            continue
        # Current clients send exact policies. The legacy aggregate is then a
        # derived compatibility field and must not overwrite precise choices.
        # Project only genuinely old payloads with no corresponding entries.
        # ``background_enabled`` is a one-to-one legacy alias and remains an
        # authoritative public master switch when explicitly supplied.  The
        # manual/AI aggregates cover multiple exact sources, so a modern
        # payload's precise entries must win there (otherwise enabling a
        # camera could silently re-enable text input).
        if legacy_name != "background_enabled" and any(source in policies for source in exact_sources):
            continue
        enabled = bool(stimuli[legacy_name])
        for source in exact_sources:
            entry = policies.setdefault(source, {})
            if isinstance(entry, dict):
                entry["enabled"] = enabled


_sync_source_policy_legacy()


def _legacy_adapter_projection() -> dict[str, Any]:
    """Temporary UI projection; it is derived, never persisted as state."""
    body = {**_adapter_config("body-background"), "enabled": _adapter_enabled("body-background")}
    body["energy_supply"] = {**_adapter_config("energy-budget"), "enabled": _adapter_enabled("energy-budget")}
    network = {**_adapter_config("network-transport"), "enabled": _adapter_enabled("network-transport"), "token_configured": bool(_network_token)}
    return {"body": body, "network": network}


def _apply_legacy_adapter_patch(values: dict[str, Any]) -> None:
    """Translate the existing settings UI into the live adapter registry."""
    body = values.get("body")
    if isinstance(body, dict):
        state = adapter_runtime_state.setdefault("body-background", {"enabled": False, "config": {}})
        if "enabled" in body: state["enabled"] = bool(body["enabled"])
        state.setdefault("config", {}).update({key: body[key] for key in ("sampling_ticks", "threshold", "adaptation", "noise", "channel_count") if key in body})
        energy = body.get("energy_supply") or body.get("energy_modulator")
        if isinstance(energy, dict):
            energy_state = adapter_runtime_state.setdefault("energy-budget", {"enabled": False, "config": {}})
            if "enabled" in energy: energy_state["enabled"] = bool(energy["enabled"])
            energy_state.setdefault("config", {}).update({key: energy[key] for key in ("supply_per_tick", "total_supply_limit") if key in energy})
    network = values.get("network")
    if isinstance(network, dict):
        state = adapter_runtime_state.setdefault("network-transport", {"enabled": False, "config": {}})
        if "enabled" in network: state["enabled"] = bool(network["enabled"])
        state.setdefault("config", {}).update({key: network[key] for key in ("allow_remote_modulation", "modulation_timeout_ticks", "output_interval_ms") if key in network})


_bootstrap_adapter_settings()
persistence_store = SecretStore(DATA_DIR, data_name="persistence.enc")
try:
    _stored_persistence_rows = persistence_store.load()
except RuntimeError:
    _stored_persistence_rows = []
_stored_persistence = _stored_persistence_rows[0] if _stored_persistence_rows and isinstance(_stored_persistence_rows[0], dict) else {}
_persistence_environment_override = os.getenv("THREEMIND_PERSISTENCE")
_persistence_kind = str(_persistence_environment_override or _stored_persistence.get("kind") or "sqlite")
_persistence_config = dict(_stored_persistence.get("config", {})) if not _persistence_environment_override and isinstance(_stored_persistence.get("config", {}), dict) else {}
_persistence_startup_warning = ""
try:
    persistence = build_backend(_persistence_kind, DATA_DIR, _persistence_config)
except FileBackendTooLarge as error:
    # Do not let an old JSON history document make the whole Core look frozen
    # before Uvicorn can bind its port.  The legacy file is left untouched; a
    # later, explicit migration can inspect it without putting normal startup
    # at risk.  SQLite becomes the live host-history store from this point.
    _persistence_kind = "sqlite"
    _persistence_config = {}
    persistence = build_backend("sqlite", DATA_DIR)
    _stored_persistence = {"kind": _persistence_kind, "config": {}}
    _persistence_startup_warning = (
        f"Legacy file persistence was bypassed because {error.path.name} is "
        f"{error.size:,} bytes. The file was preserved unchanged; ThreeMind is "
        "using local SQLite for new history."
    )
    if not _persistence_environment_override:
        try:
            persistence_store.save([_stored_persistence])
        except OSError:
            # The current process remains safe even if a lock prevents the
            # preference from being written. It will repeat this safe fallback
            # next time instead of attempting the dangerous eager JSON load.
            pass
    print(f"ThreeMind persistence warning: {_persistence_startup_warning}", file=sys.stderr, flush=True)
except (RuntimeError, ValueError, OSError) as error:
    # A bad optional database configuration should fall back to the local
    # database, never back to an eager JSON document that may be too large.
    _persistence_kind = "sqlite"
    _persistence_config = {}
    persistence = build_backend("sqlite", DATA_DIR)
    _persistence_startup_warning = f"Requested persistence backend was unavailable ({type(error).__name__}: {error}); using local SQLite."
    print(f"ThreeMind persistence warning: {_persistence_startup_warning}", file=sys.stderr, flush=True)
# History is a host concern rather than a Core concern.  The writer receives
# immutable runtime copies and persists them through the selected backend on a
# separate thread, leaving graph evolution and its tick thread independent of
# database latency.
history_writer = HistoryCheckpointWriter(lambda: persistence)
# Archive metadata has a dedicated local SQLite index.  It is intentionally
# separate from the generic persistence backend: package payloads remain
# portable ``.tmind`` files, while management queries stay small and indexed.
archive_repository = ArchiveRepository(DATA_DIR / "archive-index.sqlite3")
archive_indexer = ArchiveIndexer(archive_repository, DATA_DIR)
archive_writer = ArchiveWriter(archive_repository)
runtime: ConsciousnessRuntime | None = None
providers: dict[str, Provider] = {}
provider_store = SecretStore(DATA_DIR)
network_store = SecretStore(DATA_DIR, data_name="network.enc")
notification_service = NotificationService(DATA_DIR)
try:
    _stored_providers = provider_store.load()
except RuntimeError:
    _stored_providers = []
for _item in _stored_providers:
    try:
        _provider = Provider(**_item)
        providers[_provider.id] = _provider
    except (TypeError, ValueError):
        continue
ai_client = ChatClient()
scheduler = EnvironmentScheduler(runtime, lambda provider_id: providers.get(provider_id), ai_client, stimulus_submit=lambda item, text, intensity: _submit_text(item, text, intensity=intensity, source="ai-environment", queued=True))
interpreter = InterpreterScheduler(
    runtime,
    lambda provider_id: providers.get(provider_id),
    ai_client,
    on_interpretation=lambda item, event: (
        _schedule_history_checkpoint(item),
        _maybe_auto_snapshot(item, "interpreter_important") if event.get("important") else None,
    ),
)
manager = RuntimeManager(runtime)


def _require_active_runtime() -> ConsciousnessRuntime:
    """Return the selected runtime without inventing one during startup."""
    try:
        return manager.active()
    except KeyError as error:
        raise HTTPException(status_code=409, detail="no active consciousness") from error
_saved_ai = ui_settings.get("ai", {})
if _saved_ai.get("environment"):
    scheduler.configure(_saved_ai["environment"])
if _saved_ai.get("interpreter"):
    interpreter.configure(_saved_ai["interpreter"])
_text_adapters: dict[str, TextSensorAdapter] = {}
_body_adapters: dict[str, BodyAdapter] = {}
_ambient_adapters: dict[str, AmbientSensorAdapter] = {}
_interoceptive_adapters: dict[str, InteroceptiveAdapter] = {}
_structural_readouts: dict[str, StructuralReadoutAdapter] = {}
_temporal_readouts: dict[str, TemporalConvergenceReadoutAdapter] = {}
_energy_adapters: dict[str, MetabolicEnergyAdapter] = {}
_host_telemetry_adapters: dict[str, HostTelemetryAdapter] = {}
_process_telemetry_adapters: dict[str, ProcessTelemetryAdapter] = {}
_runtime_telemetry_adapters: dict[str, RuntimeTelemetryAdapter] = {}
_auditory_adapters: dict[str, AuditorySensorAdapter] = {}
_visual_adapters: dict[str, VisualSensorAdapter] = {}
_media_output_subscriptions: dict[tuple[str, str], tuple[ConsciousnessRuntime, int, Any]] = {}
_TELEMETRY_ADAPTER_IDS = (
    "host-telemetry-field", "process-telemetry-field", "runtime-telemetry-field",
)
_MEDIA_ADAPTER_IDS = (
    "auditory-sensor", "visual-sensor",
    "acoustic-output-organ", "activation-image-projector",
)
telemetry_collector = HostTelemetryCollector()
telemetry_audit_store = TelemetryAuditStore(DATA_DIR / "telemetry-audit.sqlite3")
media_audit_store = MediaAuditStore(DATA_DIR / "media", DATA_DIR / "media-audit.sqlite3")
media_codec_service = MediaCodecService()
_media_background_tasks: set[asyncio.Task[Any]] = set()


@dataclass
class _ActiveMediaLiveSession:
    """One browser-owned live sensory reservation.

    The reservation is tied to the concrete runtime object, not merely to its
    persisted consciousness id. Restoring a snapshot deliberately creates a
    new runtime with the same id, so an id-only registry would otherwise leave
    the old microphone/camera session blocking its replacement.
    """

    token: str
    runtime: ConsciousnessRuntime
    session_id: str | None = None


_media_live_session_lock = RLock()
_active_media_live_sessions: dict[tuple[str, str], _ActiveMediaLiveSession] = {}


def _reserve_media_live_session(
    key: tuple[str, str], item: ConsciousnessRuntime,
) -> _ActiveMediaLiveSession | None:
    """Reserve a live input slot, replacing only a stale runtime owner."""

    with _media_live_session_lock:
        existing = _active_media_live_sessions.get(key)
        if existing is not None and existing.runtime is item:
            return None
        reservation = _ActiveMediaLiveSession(uuid.uuid4().hex, item)
        _active_media_live_sessions[key] = reservation
        return reservation


def _release_media_live_session(
    key: tuple[str, str], reservation: _ActiveMediaLiveSession,
) -> bool:
    """Release a slot only if it is still owned by this exact connection."""

    with _media_live_session_lock:
        if _active_media_live_sessions.get(key) is not reservation:
            return False
        _active_media_live_sessions.pop(key, None)
        return True


def _retire_media_live_sessions(item: ConsciousnessRuntime) -> None:
    """Detach live inputs owned by a runtime that has left the manager."""

    with _media_live_session_lock:
        for key, reservation in tuple(_active_media_live_sessions.items()):
            if reservation.runtime is item and _active_media_live_sessions.get(key) is reservation:
                _active_media_live_sessions.pop(key, None)


def _media_live_session_id(consciousness_id: str, adapter_id: str) -> str | None:
    with _media_live_session_lock:
        reservation = _active_media_live_sessions.get((consciousness_id, adapter_id))
        return reservation.session_id if reservation is not None else None


def _telemetry_adapter_cache(adapter_id: str) -> dict[str, Any]:
    if adapter_id == "host-telemetry-field":
        return _host_telemetry_adapters
    if adapter_id == "process-telemetry-field":
        return _process_telemetry_adapters
    if adapter_id == "runtime-telemetry-field":
        return _runtime_telemetry_adapters
    raise ValueError(f"unknown telemetry adapter: {adapter_id}")


def _telemetry_scope(adapter_id: str) -> str:
    if adapter_id == "host-telemetry-field": return "host"
    if adapter_id == "process-telemetry-field": return "process"
    if adapter_id == "runtime-telemetry-field": return "runtime"
    raise ValueError(f"unknown telemetry adapter: {adapter_id}")


def _reset_telemetry_baselines(item: ConsciousnessRuntime | None = None) -> None:
    """Forget only host-side derivative baselines, never Core state."""
    consciousness_id = item.consciousness_id if item is not None else None
    for adapters in (_host_telemetry_adapters, _process_telemetry_adapters, _runtime_telemetry_adapters):
        for current_id, current in adapters.items():
            if consciousness_id is None or current_id == consciousness_id:
                current.reset_baseline()
    candidates = [item] if item is not None else list(manager.instances.values())
    for candidate in candidates:
        if isinstance(candidate, _HostObservedRuntime):
            candidate.reset_runtime_telemetry_window()
_remote_sensory_adapters: dict[str, RemoteSensoryAdapter] = {}
_remote_modulators: dict[str, RemotePhysiologyModulator] = {}
_auto_snapshot_ticks: dict[str, int] = {}
_auto_snapshot_lock = RLock()
# A manual interpretation is requested only once the final causal frame of
# its envelope has reached the runtime.  This host-side bookkeeping is not a
# graph input and is intentionally discarded on process restart.
_pending_manual_interpretation_envelopes: dict[str, set[str]] = {}
# The passive reader must receive every published frame.  A polling observer
# only sees the most recent OutputBus frame and can miss a short-lived local
# associative cascade.  The subscription callback is deliberately tiny; the
# potentially blocking persistence/notification work occurs in this external
# dispatcher thread, never inside Core's tick thread.
_output_observer_queue: SimpleQueue[tuple[ConsciousnessRuntime, OutputFrame] | None] = SimpleQueue()
_output_observer_stop = Event()
_output_observer_thread: Thread | None = None
_output_observer_subscriptions: dict[str, tuple[ConsciousnessRuntime, int]] = {}
_output_observer_processing_locks: dict[str, RLock] = {}
_output_observer_lock = RLock()
try:
    _network_secret_rows = network_store.load()
except RuntimeError:
    _network_secret_rows = []
_network_token = str(_network_secret_rows[0].get("token") or "") if _network_secret_rows else ""
def _write_ui_settings() -> None:
    """Persist only public settings; credentials belong in encrypted stores."""
    ui_settings["adapter_preferences"] = json.loads(json.dumps(adapter_runtime_state))
    ui_settings.pop("body", None); ui_settings.pop("adapters", None); ui_settings.pop("network", None)
    clean = json.loads(json.dumps(ui_settings))
    notification = clean.setdefault("notifications", {})
    notification.pop("resend_api_key", None)
    notification.pop("clear_resend_api_key", None)
    notification.update(notification_service.public(ui_settings.get("notifications", {})))
    _write_json_atomic(SETTINGS_PATH, clean)


def _notification_public() -> dict[str, Any]:
    """Return notification configuration without exposing credentials."""
    return notification_service.public(ui_settings.get("notifications", {}))


def _save_notification_settings(values: dict[str, Any]) -> None:
    """Delegate notification credentials and public settings to the app service."""
    notification_service.update(ui_settings.setdefault("notifications", {}), values)


def _send_notification(event: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Deliver a notification through the external application service."""
    return notification_service.send(
        ui_settings.get("notifications", {}),
        event,
        force=force,
        ui_locale=str(ui_settings.get("ui", {}).get("locale", "zh-CN")),
    )


def _text_adapter(item: ConsciousnessRuntime) -> TextSensorAdapter:
    adapter = _text_adapters.get(item.consciousness_id)
    if adapter is None:
        configured_channels = item.manifest.parameters.get("sensory_channels")
        if configured_channels is None:
            # Pre-fix packages used the former 8192-channel projection but did
            # not persist that carrier setting.  Preserve their existing
            # receptor mapping rather than silently disconnecting learned
            # nodes when the corrected 192-channel default is introduced.
            configured_channels = 8192 if item.receptor_index and max(item.receptor_index) >= 192 else 192
            item.manifest.parameters["sensory_channels"] = configured_channels
        encoding = str(item.manifest.parameters.get("sensory_encoding") or ("legacy-labeled" if item.manifest.node_payload == "labeled" else "anonymous-distributed"))
        adapter = TextSensorAdapter(
            item.sensory_seed,
            labeled=item.manifest.node_payload == "labeled",
            channels=int(configured_channels),
            encoding=encoding,
        )
        # Stimulus logs are external records. Replaying them only rebuilds the
        # V1 observation dictionary; it never changes graph nodes or edges.
        for record in item.stimuli:
            if record.get("text"):
                adapter.encode(str(record["text"]), intensity=float(record.get("intensity", 1.0)), source=str(record.get("source", "manual")))
        item.register_channel_labels(adapter.channel_labels)
        _text_adapters[item.consciousness_id] = adapter
    return adapter


def _auditory_adapter(item: ConsciousnessRuntime) -> AuditorySensorAdapter:
    config = _model_adapter_config(item, "auditory-sensor")
    adapter = _auditory_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = AuditorySensorAdapter(item.sensory_seed, config)
        _auditory_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _visual_adapter(item: ConsciousnessRuntime) -> VisualSensorAdapter:
    config = _model_adapter_config(item, "visual-sensor")
    adapter = _visual_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = VisualSensorAdapter(item.sensory_seed, config)
        _visual_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _media_input_enabled(item: ConsciousnessRuntime, adapter_id: str, source: str) -> bool:
    return (
        item.life_state != "dead"
        and not item._paused
        and item.source_status().get("manual", True)
        and _source_policy(source)["enabled"]
        and _adapter_enabled(adapter_id)
        and _model_adapter_enabled(item, adapter_id)
    )


def _media_output_adapter(item: ConsciousnessRuntime, adapter_id: str) -> AcousticOutputOrgan | ActivationImageProjector:
    key = (item.consciousness_id, adapter_id)
    existing = _media_output_subscriptions.get(key)
    if existing is not None and existing[0] is item:
        return existing[2]
    if existing is not None:
        existing[0].output_bus.unsubscribe(existing[1])
    config = _model_adapter_config(item, adapter_id)
    if adapter_id == "acoustic-output-organ":
        device: AcousticOutputOrgan | ActivationImageProjector = AcousticOutputOrgan(
            maximum_voices=int(config.get("maximum_voices", 12)),
            minimum_activation=float(config.get("minimum_activation", .08)),
        )
    elif adapter_id == "activation-image-projector":
        device = ActivationImageProjector(
            width=int(config.get("width", 48)), height=int(config.get("height", 32)),
        )
    else:
        raise ValueError(f"unknown media output adapter: {adapter_id}")
    token = item.output_bus.subscribe(device.observe)
    _media_output_subscriptions[key] = (item, token, device)
    return device


def _release_media_runtime(item: ConsciousnessRuntime) -> None:
    """Release host media state associated with one detached runtime.

    Model replacement and deletion are application lifecycle operations.  This
    cleanup only drops adapter buffers/subscriptions; it never edits the model
    package or graph state.
    """
    consciousness_id = item.consciousness_id
    # A restored snapshot keeps the same consciousness id but owns a new
    # runtime object. Retire the old browser reservation immediately so the
    # replacement can attach its microphone/camera without waiting for an old
    # WebSocket coroutine to observe the disconnect.
    _retire_media_live_sessions(item)
    _auditory_adapters.pop(consciousness_id, None)
    _visual_adapters.pop(consciousness_id, None)
    for key, (runtime_item, token, _device) in tuple(_media_output_subscriptions.items()):
        if runtime_item is item:
            runtime_item.output_bus.unsubscribe(token)
            _media_output_subscriptions.pop(key, None)


def _media_adapter_runtime_status(adapter_id: str, active: ConsciousnessRuntime | None) -> dict[str, Any]:
    capabilities = media_codec_service.capabilities()
    active_id = active.consciousness_id if active is not None else None
    status: dict[str, Any] = {
        "protocol": "threemind-media/1",
        "audit": media_audit_store.status(),
        "semantic_models": [],
        "consciousness_id": active_id,
    }
    if adapter_id == "auditory-sensor":
        status.update({
            "dependency": "full" if capabilities["audio_codecs"] else "partial",
            "backend": capabilities["backend"],
            "available_inputs": [
                "live microphone PCM", "WAV upload",
                *(["compressed audio upload"] if capabilities["audio_codecs"] else []),
            ],
            "unavailable_inputs": {} if capabilities["audio_codecs"] else {
                "compressed audio upload": "install the optional media dependency",
            },
            "live_session_id": _media_live_session_id(active_id, adapter_id) if active_id else None,
            "raw_retention": "content-addressed uploads; live PCM is ephemeral",
        })
    elif adapter_id == "visual-sensor":
        unavailable: dict[str, str] = {}
        if not capabilities["images"]:
            unavailable["image upload"] = "install the optional media dependency"
        if not capabilities["video_codecs"]:
            unavailable["video upload"] = "install the optional media dependency"
        status.update({
            "dependency": "full" if not unavailable else "partial",
            "backend": capabilities["backend"],
            "available_inputs": [
                "live camera pixels",
                *(["image upload"] if capabilities["images"] else []),
                *(["video upload"] if capabilities["video_codecs"] else []),
            ],
            "unavailable_inputs": unavailable,
            "live_session_id": _media_live_session_id(active_id, adapter_id) if active_id else None,
            "raw_retention": "content-addressed uploads; live pixels are ephemeral",
        })
    else:
        status.update({
            "dependency": "full",
            "backend": "web-audio" if adapter_id == "acoustic-output-organ" else "browser-canvas",
            "subscribed": bool(active_id and (active_id, adapter_id) in _media_output_subscriptions),
            "raw_retention": "no raw output retention",
        })
    return status

def _body_adapter(item: ConsciousnessRuntime) -> BodyAdapter:
    config = _adapter_config("body-background")
    adapter = _body_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = BodyAdapter(item.sensory_seed, **{key: config[key] for key in ("sampling_ticks", "threshold", "adaptation", "noise", "channel_count") if key in config})
        _body_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _configure_attention_modulators(item: ConsciousnessRuntime) -> None:
    modulators: list[Any] = []
    network = _adapter_config("network-transport")
    if _adapter_enabled("network-transport") and network.get("allow_remote_modulation"):
        remote = _remote_modulators.get(item.consciousness_id)
        if remote is None:
            remote = RemotePhysiologyModulator(timeout_ticks=int(network.get("modulation_timeout_ticks", 300)))
            _remote_modulators[item.consciousness_id] = remote
        else:
            remote.timeout_ticks = max(1, int(network.get("modulation_timeout_ticks", 300)))
        modulators.append(remote)
    else:
        _remote_modulators.pop(item.consciousness_id, None)
    item.set_attention_modulators(modulators)


def _energy_adapter(item: ConsciousnessRuntime) -> MetabolicEnergyAdapter:
    config = _adapter_config("energy-budget")
    adapter = _energy_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = MetabolicEnergyAdapter(**{key: config[key] for key in ("supply_per_tick", "total_supply_limit") if key in config})
        # A model-package resume must not silently reset a configured total
        # supply cap.  Only supply accepted from this adapter counts; manual
        # API injections remain separately auditable experimental actions.
        adapter.supplied_total = sum(
            max(0.0, float(event.get("accepted", 0.0)))
            for event in item.package.logs.get("energy", [])
            if isinstance(event, dict) and event.get("source") == "energy-budget"
        )
        _energy_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _telemetry_adapter(item: ConsciousnessRuntime, adapter_id: str) -> HostTelemetryAdapter | ProcessTelemetryAdapter | RuntimeTelemetryAdapter:
    config = _model_adapter_config(item, adapter_id)
    if adapter_id == "host-telemetry-field":
        adapters: dict[str, Any] = _host_telemetry_adapters
        factory: Any = HostTelemetryAdapter
    elif adapter_id == "process-telemetry-field":
        adapters = _process_telemetry_adapters
        factory = ProcessTelemetryAdapter
    elif adapter_id == "runtime-telemetry-field":
        adapters = _runtime_telemetry_adapters
        factory = RuntimeTelemetryAdapter
    else:
        raise ValueError(f"unknown telemetry adapter: {adapter_id}")
    adapter = adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = factory(item.sensory_seed, config=config)
        adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _resolve_model_adapters(item: ConsciousnessRuntime) -> None:
    """Materialise defaults so every subsequently saved package is explicit."""
    for adapter_id in _MODEL_ADAPTER_DEFAULTS:
        binding = _model_adapter_binding(item, adapter_id)
        # A package is self-describing: adapter defaults used by this runtime
        # are copied into the declaration even when the host preference was
        # originally implicit. Explicit false always remains false.
        binding["enabled"] = bool(binding.get("enabled", _MODEL_ADAPTER_DEFAULTS[adapter_id]))
        binding["config"] = copy.deepcopy(_model_adapter_config(item, adapter_id))
    item.manifest.parameters.setdefault("homeostasis_enabled", bool(item.config.homeostasis_enabled))


def _resolve_package_adapters(package: ModelPackage) -> ModelPackage:
    """Resolve application adapter defaults without hydrating graph runtime.

    Package management operations such as rename and embedded-snapshot
    restore must not instantiate a second Core runtime merely to write
    application-owned adapter declarations.
    """
    by_id = {
        str(binding.get("adapter_id")): binding
        for binding in package.manifest.adapter_bindings
        if isinstance(binding, dict) and binding.get("adapter_id")
    }
    for adapter_id, default_enabled in _MODEL_ADAPTER_DEFAULTS.items():
        binding = by_id.get(adapter_id)
        if binding is None:
            binding = {
                "adapter_id": adapter_id,
                "enabled": default_enabled,
                "route": _model_adapter_route(adapter_id),
            }
            package.manifest.adapter_bindings.append(binding)
            by_id[adapter_id] = binding
        binding["enabled"] = bool(binding.get("enabled", default_enabled))
        declared = binding.get("config") if isinstance(binding.get("config"), dict) else {}
        resolved = copy.deepcopy(_adapter_config(adapter_id))
        AdapterRegistry._deep_merge(resolved, declared)
        binding["config"] = resolved
    package.manifest.parameters.setdefault("homeostasis_enabled", False)
    return package


def _remote_sensory_adapter(item: ConsciousnessRuntime) -> RemoteSensoryAdapter:
    return _remote_sensory_adapters.setdefault(item.consciousness_id, RemoteSensoryAdapter(item.sensory_seed))


def _ambient_adapter(item: ConsciousnessRuntime) -> AmbientSensorAdapter:
    config = _model_adapter_config(item, "ambient-field")
    adapter = _ambient_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = AmbientSensorAdapter(item.sensory_seed, **{key: config[key] for key in ("transient_rate", "transient_amplitude", "transient_lifetime_min", "transient_lifetime_max") if key in config})
        _ambient_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _interoceptive_adapter(item: ConsciousnessRuntime) -> InteroceptiveAdapter:
    config = _adapter_config("interoceptive-field")
    adapter = _interoceptive_adapters.get(item.consciousness_id)
    if adapter is None:
        adapter = InteroceptiveAdapter(item.sensory_seed, **{key: config[key] for key in ("channel_count", "amplitude") if key in config})
        _interoceptive_adapters[item.consciousness_id] = adapter
    else:
        adapter.configure(config)
    return adapter


def _network_public() -> dict[str, Any]:
    config = _adapter_config("network-transport")
    config["enabled"] = _adapter_enabled("network-transport")
    config.pop("token", None)
    config["token_configured"] = bool(_network_token)
    config["protocol"] = "threemind-network/1"
    return config


def _archive_catalog_items(consciousness_id: str | None = None) -> list[dict[str, Any]]:
    """Read the indexed archive catalogue; never deserialize package files."""
    return archive_repository.list_archives(consciousness_id)


def _record_artifact(path: Path | str, package: ModelPackage) -> dict[str, Any]:
    """Index a just-written package from memory, without rereading its graph."""
    try:
        return archive_repository.index_metadata(path, package.catalog_metadata())
    except (OSError, ValueError, sqlite3.Error):
        # A complete package file is still a valid archive if the operational
        # index is temporarily unavailable.  Repair it asynchronously rather
        # than turning an archival bookkeeping fault into a Core failure.
        archive_indexer.start()
        return {"path": str(Path(path).resolve()), "state": "pending_index"}


def _queue_snapshot_write(
    item: ConsciousnessRuntime,
    path: Path,
    *,
    portrait: bool,
    label: str | None,
    automatic: bool,
    reason: str,
    wait: bool,
) -> dict[str, Any]:
    """Capture under the runtime lock, then archive outside the Core tick."""
    _resolve_model_adapters(item)
    package = item.capture_snapshot_package(
        portrait=portrait,
        label=label,
        automatic=automatic,
        reason=reason,
    )
    ticket = archive_writer.submit(path, package)
    if not wait:
        return {"path": str(path.resolve()), "state": "queued", "archive": dict(package.archive)}
    try:
        return ticket.result(timeout=90.0)
    except TimeoutError:
        return {"path": str(path.resolve()), "state": "queued", "archive": dict(package.archive)}


def _snapshot_candidate(consciousness_id: str, path: str | None = None) -> dict[str, Any]:
    candidate = archive_repository.get_archive(consciousness_id, path)
    if candidate is None:
        raise KeyError("no restorable snapshot found; archive index may still be building")
    return candidate


def _latest_package_path(consciousness_id: str) -> Path:
    """Fallback for a deliberately saved model package with no snapshot yet."""
    path = archive_repository.latest_package_path(consciousness_id)
    if path is None:
        raise KeyError("no saved package found; archive index may still be building")
    return path


_HISTORY_KINDS = {"stimuli", "events", "interpretations", "observations", "trace"}


def _schedule_history_checkpoint(item: ConsciousnessRuntime) -> None:
    """Request host-side durable history without blocking Core or the API."""
    if history_writer.running():
        history_writer.schedule(item)


def _history_document_from_package(package: ModelPackage, *, origin: str) -> dict[str, Any]:
    """Normalize one explicitly selected package's history for management.

    This intentionally loads at most one archive artifact chosen through the
    SQLite metadata index.  It never scans or deserializes the full data
    directory merely to answer a detail-page request.
    """
    state = package.state if isinstance(package.state, dict) else {}
    state_logs = state.get("logs") if isinstance(state.get("logs"), dict) else package.logs
    logs = state_logs if isinstance(state_logs, dict) else {}

    def rows(value: Any) -> list[dict[str, Any]]:
        return [dict(row) for row in value] if isinstance(value, list) else []

    return {
        "record_type": "history_checkpoint",
        "consciousness_id": package.consciousness_id,
        "consciousness_name": package.consciousness_name,
        "tick": int(state.get("tick", 0)),
        "life_state": str(state.get("life_state", "stored")),
        "history_revision": int(state.get("history_revision", 0)),
        "origin": origin,
        "events": rows(state.get("events")),
        "stimuli": rows(state.get("stimuli")),
        "interpretations": rows(state.get("interpretations")),
        "observations": rows(logs.get("observations")),
        "trace_entries": rows(state.get("trace_entries")),
        "logs": {str(kind): rows(value) for kind, value in logs.items() if isinstance(value, list)},
    }


def _history_document(consciousness_id: str) -> tuple[dict[str, Any], str]:
    """Resolve one consciousness history from live, durable, then archive state."""
    try:
        return manager.get(consciousness_id).history_snapshot(), "live"
    except KeyError:
        pass

    # The configured persistence backend is the authoritative durable history
    # store for future runs.  A database outage should not hide the older
    # portable snapshot history that is still available through the archive
    # index, so fall through to that one-artifact recovery path.
    try:
        stored = persistence.get(HistoryCheckpointWriter.key(consciousness_id))
    except Exception:
        stored = None
    candidate = archive_repository.get_archive(consciousness_id)
    path = Path(str(candidate["path"])) if candidate is not None else archive_repository.latest_package_path(consciousness_id)
    persisted = dict(stored) if isinstance(stored, dict) and stored.get("record_type") == "history_checkpoint" else None
    archive_document: dict[str, Any] | None = None
    if path is not None:
        try:
            archive_document = _history_document_from_package(ModelPackage.load(path), origin="archive")
        except (OSError, ValueError):
            # A stale archive-index row should not prevent a valid durable
            # checkpoint from being read.  The indexer can later repair it.
            archive_document = None
    if persisted is not None:
        persisted["origin"] = "persistence"
        if archive_document is None:
            return persisted, "persistence"
        # Snapshots and durable checkpoints may be created in either order.
        # Prefer whichever contains the later observable history, instead of
        # assuming a database checkpoint is automatically newer.
        def rank(document: dict[str, Any]) -> tuple[int, int, int, float]:
            count = sum(len(_history_rows(document, kind)) for kind in _HISTORY_KINDS)
            return (
                int(document.get("history_revision", 0)),
                int(document.get("tick", 0)),
                count,
                float(document.get("captured_at", 0.0)),
            )
        return (archive_document, "archive") if rank(archive_document) > rank(persisted) else (persisted, "persistence")
    if archive_document is None:
        raise KeyError(f"no persisted history found for consciousness: {consciousness_id}")
    return archive_document, "archive"


def _history_rows(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    if kind not in _HISTORY_KINDS:
        raise ValueError("unknown log kind")
    key = "trace_entries" if kind == "trace" else kind
    value = document.get(key, [])
    return [dict(row) for row in value] if isinstance(value, list) else []


def _archive_path(item: ConsciousnessRuntime, suffix: str) -> Path:
    """Allocate a distinct artifact path even when the runtime is paused."""
    return DATA_DIR / f"{item.consciousness_id}-{item.tick}-{suffix}-{uuid.uuid4().hex[:10]}{MODEL_PACKAGE_SUFFIX}"


def _restore_package_path(path: str | Path, *, reason: str) -> ConsciousnessRuntime:
    """Hydrate a package artifact and replace only the matching live identity."""
    global runtime
    package = ModelPackage.load(path)
    restored = _new_runtime(package)
    _resolve_model_adapters(restored)
    restored.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(restored)
    previous = manager.instances.get(restored.consciousness_id)
    manager.replace(restored, activate=True, reason=reason)
    if previous is not None and previous is not restored:
        _release_media_runtime(previous)
        _schedule_history_checkpoint(previous)
    _ensure_output_observer(restored)
    runtime = restored
    scheduler.runtime = restored
    interpreter.runtime = restored
    restored.start()
    _schedule_history_checkpoint(restored)
    return restored


def _restore_snapshot_candidate(candidate: dict[str, Any]) -> ConsciousnessRuntime:
    """Hydrate the exact archive selected by the user and make it active."""
    return _restore_package_path(str(candidate["path"]), reason="replaced by restored snapshot")


def _maybe_auto_snapshot(item: ConsciousnessRuntime, reason: str) -> None:
    """Create a labeled package only for explicitly enabled automatic rules."""
    # Ambient and output-observer loops may reach this function concurrently.
    # One lock prevents two automatic rules from both saving the same tick.
    with _auto_snapshot_lock:
        config = dict(ui_settings.get("ai", {}).get("auto_snapshot", {}))
        if not config.get("enabled", False) or item.life_state == "dead":
            return
        if reason == "repeatable_structure" and not config.get("on_repeatable_structure", True):
            return
        if reason == "interpreter_important" and not config.get("on_interpreter_important", True):
            return
        previous = _auto_snapshot_ticks.get(item.consciousness_id, -1)
        frequency = max(0, int(config.get("frequency_ticks", 0)))
        if reason == "periodic":
            if frequency <= 0 or item.tick - previous < frequency:
                return
        elif item.tick == previous:
            return
        suffix = "auto" if reason == "periodic" else f"auto-{reason}"
        path = _archive_path(item, suffix)
        _queue_snapshot_write(
            item,
            path,
            portrait=False,
            label=f"{item.consciousness_name}-{suffix}",
            automatic=True,
            reason=reason,
            wait=False,
        )
        _auto_snapshot_ticks[item.consciousness_id] = item.tick


def _structural_readout(item: ConsciousnessRuntime) -> StructuralReadoutAdapter:
    adapter = _structural_readouts.get(item.consciousness_id)
    if adapter is None:
        adapter = StructuralReadoutAdapter()
        # Restore only durable external observations.  This preserves
        # recurrence continuity across host restarts without replaying any
        # event into the consciousness network.
        adapter.restore([
            dict(row) for row in item.package.logs.get("observations", [])
            if isinstance(row, dict)
        ])
        _structural_readouts[item.consciousness_id] = adapter
    return adapter


def _temporal_readout(item: ConsciousnessRuntime) -> TemporalConvergenceReadoutAdapter:
    return _temporal_readouts.setdefault(item.consciousness_id, TemporalConvergenceReadoutAdapter())


def _process_output_frame(item: ConsciousnessRuntime, frame: OutputFrame) -> dict[str, Any]:
    """Consume one exact OutputBus frame at the external readout boundary.

    This function is intentionally host-side.  It receives an immutable
    projection that Core already published and can record, notify, or schedule
    an optional AI interpretation, but cannot send a signal back to the graph.
    """
    with _output_observer_lock:
        processing_lock = _output_observer_processing_locks.setdefault(item.consciousness_id, RLock())
    with processing_lock:
        return _process_output_frame_locked(item, frame)


def _process_output_frame_locked(item: ConsciousnessRuntime, frame: OutputFrame) -> dict[str, Any]:
    """Implementation of :func:`_process_output_frame` under one reader lock."""
    driver = _character_driver(item)
    readout_settings = _readout_settings()
    structural_enabled = _adapter_enabled("structural-readout") and bool(readout_settings.get("snapshot_enabled", True))
    if structural_enabled:
        view = _structural_readout(item).consume(
            frame,
            readout_settings,
            render=driver.render if driver else None,
            describe=driver.describe if driver else None,
        )
    else:
        view = {
            "current": {"tick": frame.tick, "text": "(structural readout adapter disabled)", "occurrences": 0, "internal_edges": 0, "repeatable": False},
            "events": item.package.logs.get("observations", [])[-100:],
            "config": readout_settings,
        }
    # Old ThreeMind recorded each eligible passive readout by default because a
    # sustained sequence can itself be experimental evidence.  The strict
    # deduplication toggle gates only this external observation stream; it
    # never changes Core activity.
    if structural_enabled and view.get("new_passive_event"):
        _record_output_observation(item, view["new_passive_event"])
    if structural_enabled and view.get("new_event"):
        event = dict(view["new_event"])
        event["consciousness_id"] = item.consciousness_id
        # Notifications are an external side effect of the output observer.
        # They receive a copy of the readout event and can never feed a signal
        # back into the runtime.
        event["delivery"] = _send_notification(event)
        _record_output_observation(item, event)
        # This setting controls only the optional external AI interpretation.
        # The passive structural observation above is always an observation;
        # it does not require an AI provider.
        if bool(ui_settings.get("ai", {}).get("interpreter", {}).get("on_repeatable_structure", False)):
            interpreter.request("repeatable_structure", item)
        _maybe_auto_snapshot(item, "repeatable_structure")
    # A background listener is a passive output adapter, not an AI request.
    # It is evaluated after the background frame has actually changed the
    # graph, and its causal provenance is carried in OutputFrame.delta.
    if structural_enabled and bool(ui_settings.get("ai", {}).get("interpreter", {}).get("listen_background_active_nodes", False)):
        background = _structural_readout(item).consume_background_activity(
            frame,
            readout_settings,
            render=driver.render if driver else None,
            describe=driver.describe if driver else None,
        )
        if background.get("current") is not None:
            view["background_current"] = background["current"]
            view["current"] = background["current"]
        if background.get("new_event"):
            _record_output_observation(item, background["new_event"])

    temporal_config = dict(readout_settings.get("temporal", {}))
    if _adapter_enabled("temporal-convergence-readout"):
        temporal_view = _temporal_readout(item).consume(
            frame,
            temporal_config,
            render=driver.render if driver else None,
            describe=driver.describe if driver else None,
        )
        for event in temporal_view.get("new_events", []):
            _record_output_observation(item, dict(event))
        view["temporal"] = {
            "current": temporal_view.get("current"),
            "active_windows": temporal_view.get("active_windows", []),
        }
    else:
        view["temporal"] = {"current": None, "active_windows": []}
    view["events"] = item.package.logs.get("observations", [])[-100:]
    view["config"] = readout_settings
    view.pop("new_event", None)
    view.pop("new_passive_event", None)
    return view


def _prune_output_observer_subscriptions() -> None:
    """Unsubscribe stopped/replaced runtimes without retaining old graphs."""
    live = dict(manager.instances)
    with _output_observer_lock:
        for consciousness_id, (registered, token) in list(_output_observer_subscriptions.items()):
            if live.get(consciousness_id) is registered:
                continue
            registered.output_bus.unsubscribe(token)
            _output_observer_subscriptions.pop(consciousness_id, None)
            _output_observer_processing_locks.pop(consciousness_id, None)
            _structural_readouts.pop(consciousness_id, None)
            _temporal_readouts.pop(consciousness_id, None)
    live_ids = set(live)
    # Per-consciousness application adapters must not retain a stopped or
    # replaced graph.  Dropping them also guarantees a fresh change baseline
    # if that consciousness ID is later restored into a new runtime object.
    for cache in (
        _text_adapters, _body_adapters, _ambient_adapters,
        _interoceptive_adapters, _energy_adapters,
        _host_telemetry_adapters, _process_telemetry_adapters, _runtime_telemetry_adapters,
        _remote_sensory_adapters, _remote_modulators,
    ):
        for consciousness_id in tuple(cache):
            if consciousness_id not in live_ids:
                cache.pop(consciousness_id, None)


def _ensure_output_observer(item: ConsciousnessRuntime) -> None:
    """Attach a lightweight, lossless-for-process-lifetime frame callback."""
    _prune_output_observer_subscriptions()
    with _output_observer_lock:
        existing = _output_observer_subscriptions.get(item.consciousness_id)
        if existing is not None and existing[0] is item:
            return
        if existing is not None:
            existing[0].output_bus.unsubscribe(existing[1])

        def enqueue(frame: OutputFrame, *, observed: ConsciousnessRuntime = item) -> None:
            _output_observer_queue.put((observed, frame))

        token = item.output_bus.subscribe(enqueue)
        _output_observer_subscriptions[item.consciousness_id] = (item, token)


def _output_observer_worker() -> None:
    """Persist external observations in frame order outside the Core thread."""
    while True:
        queued = _output_observer_queue.get()
        if queued is None:
            return
        item, frame = queued
        if _output_observer_stop.is_set() or item.life_state == "dead":
            continue
        try:
            _process_output_frame(item, frame)
            _flush_post_delivery_interpretations(item)
        except Exception:
            # A readout, email transport, or presentation fault is external
            # observability failure.  It must never terminate the Core tick
            # thread or prevent later frames from being inspected.
            continue
        finally:
            # This is a full, coalesced host checkpoint.  It is deliberately
            # after all output-adapter effects for the frame, so a restarted
            # management page can recover the same readout records it showed
            # while this process was alive.
            _schedule_history_checkpoint(item)


def _start_output_observer_dispatcher() -> None:
    global _output_observer_thread
    with _output_observer_lock:
        _output_observer_stop.clear()
        if _output_observer_thread is None or not _output_observer_thread.is_alive():
            _output_observer_thread = Thread(target=_output_observer_worker, name="threemind-output-observer", daemon=True)
            _output_observer_thread.start()
    for item in list(manager.instances.values()):
        _ensure_output_observer(item)


def _stop_output_observer_dispatcher() -> None:
    global _output_observer_thread
    _output_observer_stop.set()
    _output_observer_queue.put(None)
    thread = _output_observer_thread
    if thread is not None:
        thread.join(timeout=3.0)
    with _output_observer_lock:
        for item, token in _output_observer_subscriptions.values():
            item.output_bus.unsubscribe(token)
        _output_observer_subscriptions.clear()
        _output_observer_processing_locks.clear()
        _output_observer_thread = None


def _character_driver(item: ConsciousnessRuntime) -> CharacterDriver | None:
    encoding = str(item.manifest.parameters.get("sensory_encoding") or ("legacy-labeled" if item.manifest.node_payload == "labeled" else "anonymous-distributed"))
    if encoding == "anonymous-distributed":
        return None
    return CharacterDriver(item.node_label)


def _readout_settings() -> dict[str, Any]:
    """Combine observer thresholds with passive-observation preferences.

    The structural thresholds remain in the observer section.  The five
    controls under AI/interpretation deliberately live with the observer
    trigger preferences, while only actual language-model interpretation
    requires an AI provider.
    """
    observer = {**DEFAULT_UI_SETTINGS["observer"], **dict(ui_settings.get("observer", {}))}
    observer["temporal"] = {
        **DEFAULT_TEMPORAL_CONFIG,
        **dict(observer.get("temporal", {}) if isinstance(observer.get("temporal"), dict) else {}),
    }
    interpretation = dict(ui_settings.get("ai", {}).get("interpreter", {}))
    observer["activation_min"] = interpretation.get("activation_min", .08)
    observer["activation_max"] = interpretation.get("activation_max", 1.0)
    observer["strict_deduplicate"] = bool(interpretation.get("deduplicate_readouts", False))
    return observer


def _record_output_observation(item: ConsciousnessRuntime, event: dict[str, Any]) -> dict[str, Any]:
    """Persist an output-bus event with auditable preceding carrier context."""
    stored = dict(event)
    stored["consciousness_id"] = item.consciousness_id
    stored["preceding_stimuli"] = [dict(row) for row in item.stimuli[-6:]]
    return item.record_observation(stored)


def _flush_post_delivery_interpretations(item: ConsciousnessRuntime) -> None:
    """Schedule manual interpretation after, never before, carrier delivery."""
    pending = _pending_manual_interpretation_envelopes.get(item.consciousness_id)
    if not pending:
        return
    completed: set[str] = set()
    # The final frame is naturally near the end of the event history.  Walk
    # backward so a long streamed carrier does not require a separate polling
    # queue or alter the InputBus's causal ordering.
    for event in reversed(list(item.events)):
        if event.get("kind") != "stimulus_frame_delivered":
            continue
        envelope_id = str(event.get("envelope_id") or "")
        if envelope_id not in pending:
            continue
        if int(event.get("frame_index", -1)) + 1 >= int(event.get("frame_count", 0)):
            completed.add(envelope_id)
        if completed == pending:
            break
    for envelope_id in completed:
        pending.discard(envelope_id)
        interpreter.request("manual_stimulus", item)
    if not pending:
        _pending_manual_interpretation_envelopes.pop(item.consciousness_id, None)

def _submit_text(item: ConsciousnessRuntime, text: str, *, intensity: float, source: str, queued: bool) -> dict[str, Any]:
    if not _adapter_enabled("text-sensor"):
        raise RuntimeError("text sensor adapter is disabled")
    policy = _source_policy(source)
    if not policy["enabled"]:
        raise RuntimeError(f"stimulus source is disabled: {source}")
    adapter = _text_adapter(item)
    transport = _adapter_config("text-sensor")
    frames = adapter.encode_stream(
        text,
        intensity=intensity,
        source=source,
        bypass_filter=policy["bypass_attention"],
        frame_characters=int(transport.get("frame_characters", 24)),
    )
    item.register_channel_labels(adapter.channel_labels)
    metadata = {"text": str(text), "carrier": "text", "carrier_length": len(str(text))}
    # All production text takes the same causal transport path.  ``queued``
    # remains an API compatibility argument but no longer changes a text
    # carrier into an unsafe synchronous graph-wide co-activation.
    result = item.enqueue_frames(
        frames,
        metadata=metadata,
        adapter_id="text-sensor",
        inter_frame_epochs=int(transport.get("inter_frame_epochs", 1)),
    )
    # Persist the carrier record as soon as it enters the InputBus.  A later
    # frame checkpoint will include delivery/readout results too; this early
    # request protects an accepted long carrier if the process ends before its
    # final frame is delivered.
    _schedule_history_checkpoint(item)
    if source in {"ui", "manual", "cli", "ui-text", "cli-text"}:
        # Do not request the observer here: at this point a queued carrier has
        # not reached any receptors.  The output observer notices the final
        # delivery frame and schedules the external interpreter afterwards.
        _pending_manual_interpretation_envelopes.setdefault(item.consciousness_id, set()).add(str(result["envelope_id"]))
    return {**result, "metrics": item.metrics()}

def _graph_view(item: ConsciousnessRuntime, limit: int | None = None) -> dict[str, Any]:
    payload = item.graph(limit)
    for node in payload["nodes"]:
        node["feature"] = item.node_label(int(node["id"])) or ""
    return payload


def _prepare_experiment_runtime(item: ConsciousnessRuntime) -> None:
    """Attach host-side services to an experimental clone without changing Core."""
    item.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(item)
    _ensure_output_observer(item)


def _experiment_snapshot(item: ConsciousnessRuntime, label: str, reason: str) -> dict[str, Any]:
    return _queue_snapshot_write(
        item,
        _archive_path(item, "snapshot"),
        portrait=False,
        label=label,
        automatic=False,
        reason=reason,
        wait=False,
    )


experiment_store = ExperimentStore(lambda: persistence)
intervention_store = InterventionStore(lambda: persistence)
experiment_controller = ExperimentController(
    manager=manager,
    store=experiment_store,
    provider_lookup=lambda provider_id: providers.get(provider_id),
    ai_client=ai_client,
    submit_stimulus=lambda item, text, intensity, source: _submit_text(item, text, intensity=intensity, source=source, queued=True),
    graph_view=_graph_view,
    prepare_runtime=_prepare_experiment_runtime,
    snapshot_capture=_experiment_snapshot,
    checkpoint_history=_schedule_history_checkpoint,
    lab_directory=_project_root / "lab",
    runtime_factory=_new_runtime,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    history_writer.start()
    _start_output_observer_dispatcher()
    for item in manager.instances.values():
        _ensure_output_observer(item)
        item.start()
        _schedule_history_checkpoint(item)
    # Legacy package discovery is deliberately background work.  A large
    # archive must never block the initial graph, stimulus, or control APIs.
    archive_writer.start()
    archive_indexer.start()
    ambient_task = asyncio.create_task(_ambient_source_loop())
    telemetry_task = asyncio.create_task(_telemetry_source_loop())
    yield
    ambient_task.cancel()
    telemetry_task.cancel()
    for task in tuple(_media_background_tasks):
        task.cancel()
    scheduler.stop()
    interpreter.stop()
    experiment_controller.shutdown()
    manager.stop_all()
    for item in list(manager.instances.values()):
        _schedule_history_checkpoint(item)
    # A graceful shutdown waits for complete host-side history checkpoints;
    # forced process termination can only guarantee records already committed
    # by the selected backend, just like any local database process.
    history_writer.stop(flush=True, timeout=10.0)
    _stop_output_observer_dispatcher()
    archive_indexer.stop()
    archive_writer.stop()
    archive_repository.close()
    # The process owns this connection for its entire lifetime.  Keeping it
    # open also permits multiple in-process FastAPI lifespan cycles in tests.


async def _telemetry_source_loop() -> None:
    """Sample shared and instance physics on monotonic wall time.

    Host/process counters are collected once and shared. Runtime counters are
    closed independently for each consciousness, then encoded for a future
    input epoch. No sample can synchronously affect the work it measures.
    """
    expected_wakeup = time.perf_counter()
    last_delivery: dict[tuple[str, str], float] = {}
    last_continuity: dict[tuple[str, str], int] = {}
    active_before: set[tuple[str, str]] = set()
    while True:
        eligible = [
            (item, adapter_id)
            for item in manager.instances.values()
            for adapter_id in _TELEMETRY_ADAPTER_IDS
            if _telemetry_delivery_enabled(item, adapter_id)
        ]
        eligible_by_key = {(item.consciousness_id, adapter_id): item for item, adapter_id in eligible}
        for key in set(eligible_by_key) - active_before:
            item = eligible_by_key[key]
            adapter_id = key[1]
            cached = _telemetry_adapter_cache(adapter_id).get(item.consciousness_id)
            if cached is not None:
                cached.reset_baseline()
            if adapter_id == "runtime-telemetry-field" and isinstance(item, _HostObservedRuntime):
                item.reset_runtime_telemetry_window(monotonic_seconds=time.perf_counter())
        intervals = [int(_model_adapter_config(item, adapter_id).get("sample_interval_ms", 1000)) for item, adapter_id in eligible]
        if not intervals:
            telemetry_collector.clear_process_observations()
            telemetry_collector.deactivate()
            await asyncio.sleep(.25)
            expected_wakeup = time.perf_counter()
            for key in active_before:
                consciousness_id, adapter_id = key
                adapters = _telemetry_adapter_cache(adapter_id)
                if consciousness_id in adapters: adapters[consciousness_id].reset_baseline()
                item = manager.instances.get(consciousness_id)
                if adapter_id == "runtime-telemetry-field" and isinstance(item, _HostObservedRuntime):
                    item.reset_runtime_telemetry_window()
            active_before.clear()
            last_delivery.clear()
            last_continuity.clear()
            continue
        interval_ms = max(250, min(intervals, default=1000))
        expected_wakeup += interval_ms / 1000.0
        await asyncio.sleep(max(.001, expected_wakeup - time.perf_counter()))
        woke_at = time.perf_counter()
        process_scope_requested = any(
            adapter_id == "process-telemetry-field"
            for _item, adapter_id in eligible
        )
        # Process telemetry describes this whole ThreeMind service.  Once any
        # model deliberately opts into it, scheduler timing must cover every
        # running runtime in the process rather than only the requesting
        # consciousness.  This remains read-only host instrumentation.
        service_runtimes = [
            item
            for item in manager.instances.values()
            if process_scope_requested
            and isinstance(item, _HostObservedRuntime)
            and item.life_state != "dead"
            and not item._paused
        ]
        process_scheduler_measurements = [
            measured
            for item in service_runtimes
            for measured in [item.host_tick_scheduler_latency_ms()]
            if measured is not None
        ]
        telemetry_collector.set_scheduler_latency(
            max(process_scheduler_measurements) if process_scheduler_measurements else None
        )
        process_epoch_measurements = [
            measured
            for item in service_runtimes
            for measured in [item.host_epoch_execution_ms()]
            if measured is not None
        ]
        telemetry_collector.set_tick_execution_time(
            max(process_epoch_measurements) if process_epoch_measurements else None
        )
        expected_wakeup = woke_at
        scopes = {
            _telemetry_scope(adapter_id)
            for _item, adapter_id in eligible
            if adapter_id != "runtime-telemetry-field"
        }
        shared_sample = await asyncio.to_thread(telemetry_collector.sample, scopes) if scopes else None
        sample_batches: dict[str, tuple[TelemetrySample, list[dict[str, Any]]]] = {}
        if shared_sample is not None:
            sample_batches[shared_sample.sample_id] = (shared_sample, [])
        active_now: set[tuple[str, str]] = set()
        for item in list(manager.instances.values()):
            for adapter_id in _TELEMETRY_ADAPTER_IDS:
                key = (item.consciousness_id, adapter_id)
                if not _telemetry_delivery_enabled(item, adapter_id):
                    if key in active_before:
                        adapters = _telemetry_adapter_cache(adapter_id)
                        if item.consciousness_id in adapters:
                            adapters[item.consciousness_id].reset_baseline()
                        if adapter_id == "runtime-telemetry-field" and isinstance(item, _HostObservedRuntime):
                            item.reset_runtime_telemetry_window(monotonic_seconds=woke_at)
                    continue
                adapter = _telemetry_adapter(item, adapter_id)
                active_now.add(key)
                continuity = item.host_continuity_revision() if isinstance(item, _HostObservedRuntime) else 0
                if last_continuity.get(key) != continuity:
                    adapter.reset_baseline()
                    last_continuity[key] = continuity
                configured_interval = max(250, int(_model_adapter_config(item, adapter_id).get("sample_interval_ms", 1000))) / 1000.0
                if woke_at - last_delivery.get(key, -configured_interval) + 1e-9 < configured_interval:
                    continue
                last_delivery[key] = woke_at
                if adapter_id == "runtime-telemetry-field":
                    if not isinstance(item, _HostObservedRuntime):
                        continue
                    sample = await asyncio.to_thread(item.consume_runtime_telemetry, woke_at)
                    sample_batches[sample.sample_id] = (sample, [])
                else:
                    if shared_sample is None:
                        continue
                    sample = shared_sample
                encoded = adapter.encode(sample, intensity=1.0, bypass_filter=_source_policy("background")["bypass_attention"])
                if encoded.frame is None:
                    continue
                try:
                    receipt = item.enqueue_frame(
                        encoded.frame,
                        adapter_id=adapter_id,
                        metadata={
                            "carrier": "instance runtime physical telemetry" if adapter_id == "runtime-telemetry-field" else "shared physical telemetry",
                            "adapter_id": adapter_id,
                            "telemetry_sample_id": sample.sample_id,
                            "telemetry_scope": adapter.scope,
                        },
                    )
                except (RuntimeError, ValueError):
                    adapter.reset_baseline()
                    continue
                audit = copy.deepcopy(encoded.audit)
                audit["delivery_envelope_id"] = str(receipt.get("envelope_id") or "") or None
                sample_batches[sample.sample_id][1].append({
                    "consciousness_id": item.consciousness_id,
                    "adapter_id": adapter_id,
                    "envelope_id": str(receipt.get("envelope_id") or "") or None,
                    "audit": audit,
                })
                _schedule_history_checkpoint(item)
        for sample, delivery_rows in sample_batches.values():
            try:
                # SQLite I/O remains outside every Core runtime thread. Shared
                # samples are stored once; runtime samples belong to one mind.
                await asyncio.to_thread(telemetry_audit_store.record_batch, sample, delivery_rows)
            except Exception:
                # Audit failure must remain visible through /api/adapters, but
                # an external recorder can never stop sensation or Core.
                pass
        for key in tuple(last_delivery):
            if key not in active_now:
                last_delivery.pop(key, None)
                last_continuity.pop(key, None)
        active_before = active_now


async def _ambient_source_loop() -> None:
    while True:
        # Body sampling is expressed in Core ticks.  Polling once per second
        # while the Core ticks at 0.1s weakened the continuous background by
        # roughly an order of magnitude compared with the former runtime.
        active_ticks = [item.config.tick_seconds for item in manager.instances.values() if item.life_state != "dead"]
        await asyncio.sleep(max(.002, min(active_ticks, default=.10)))
        intensity = max(.01, min(.4, float(ui_settings.get("ambient_intensity", .08))))
        for item in list(manager.instances.values()):
            if item.life_state == "dead":
                continue
            # The environment exists independently of a body.  Enabled body
            # adapters filter its raw frame; disabling a body therefore
            # exposes the unfiltered environmental field instead of killing
            # the world.
            try:
                if _adapter_enabled("energy-budget") and item.config.energy_simulation_enabled:
                    energy_adapter = _energy_adapter(item)
                    supplied = energy_adapter.supply_for_tick(item.tick)
                    if supplied > 0.0:
                        event = item.supply_energy(supplied, source="energy-budget")
                        energy_adapter.record_accepted(float(event["accepted"]))
                background_enabled = (
                    bool(ui_settings.get("stimuli", {}).get("background_enabled", True))
                    and item.source_status().get("ambient", True)
                    and _source_policy("background")["enabled"]
                )
                if background_enabled and _adapter_enabled("ambient-field") and _model_adapter_enabled(item, "ambient-field"):
                    raw_frames = _ambient_adapter(item).frames(item.tick, intensity=intensity, bypass_filter=_source_policy("background")["bypass_attention"])
                    for raw in raw_frames:
                        if _adapter_enabled("body-background"):
                            body = _body_adapter(item)
                            frame = body.filter_frame(raw, item.tick, bypass_filter=_source_policy("background")["bypass_attention"])
                            if frame:
                                item.enqueue_frame(frame, adapter_id="body-background", metadata={"carrier": "body-filtered environmental field", "adapter_id": "body-background", "body": {"sampling_ticks": body.sampling_ticks, "threshold": body.threshold, "adaptation": body.adaptation, "channel_count": body.channel_count}})
                        else:
                            item.enqueue_frame(raw, adapter_id="ambient-field", metadata={"carrier": "unfiltered environmental field", "adapter_id": "ambient-field"})
                if background_enabled and _adapter_enabled("interoceptive-field"):
                    frame = _interoceptive_adapter(item).frame(item.tick, intensity=intensity, bypass_filter=_source_policy("background")["bypass_attention"])
                    item.enqueue_frame(frame, adapter_id="interoceptive-field", metadata={"carrier": "interoceptive body signal", "adapter_id": "interoceptive-field"})
                _maybe_auto_snapshot(item, "periodic")
                _schedule_history_checkpoint(item)
            except (RuntimeError, ValueError): pass


app = FastAPI(title="ThreeMind Core", version="0.1.0", lifespan=lifespan)
_cors_origins = [item.strip() for item in os.getenv("THREEMIND_CORS_ORIGINS", "http://127.0.0.1:3001,http://localhost:3001").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class StimulusRequest(BaseModel):
    text: str
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    source: str = "cli-text"


class StepRequest(BaseModel):
    ticks: int = Field(default=1, ge=1, le=10_000)


class EnergySupplyRequest(BaseModel):
    amount: float = Field(gt=0.0, le=1_000_000_000.0)
    source: str = Field(default="api-energy-supply", max_length=200)


class NewRequest(BaseModel):
    name: str = "Unnamed consciousness"
    manifest: dict[str, Any] = Field(default_factory=dict)


class ContinueRequest(BaseModel):
    """Optional explicit archive choice for a consciousness continuation."""
    path: str | None = None


class PersistenceRequest(BaseModel):
    kind: str
    config: dict[str, Any] = Field(default_factory=dict)
    migrate: bool = False


class StorageCleanupRequest(BaseModel):
    """Explicit, bounded request for host-storage cleanup.

    ``DELETE`` is intentionally a fixed confirmation phrase.  The endpoint
    only accepts identifiers produced by a current storage scan, never a raw
    filesystem path supplied by the browser.
    """

    item_ids: list[str] = Field(min_length=1, max_length=500)
    confirmation: str = Field(min_length=1, max_length=64)


class ModelParametersRequest(BaseModel):
    spatial_dimensions: int | None = Field(default=None, ge=2, le=32)
    parameters: dict[str, Any] = Field(default_factory=dict)


class PackageRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PackageBatchRequest(BaseModel):
    names: list[str] = Field(min_length=1, max_length=100)


class CommandRequest(BaseModel):
    command: str
    args: dict[str, Any] = Field(default_factory=dict)


class NetworkSettingsRequest(BaseModel):
    enabled: bool = False
    allow_remote_modulation: bool = False
    modulation_timeout_ticks: int = Field(default=300, ge=1, le=1_000_000)
    output_interval_ms: int = Field(default=150, ge=20, le=10_000)
    token: str | None = Field(default=None, min_length=16, max_length=512)


class AdapterUpdateRequest(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class AdapterBindingUpdateRequest(BaseModel):
    enabled: bool
    config: dict[str, Any] | None = None


class BackgroundInputUpdateRequest(BaseModel):
    enabled: bool


class ExperimentCreateRequest(BaseModel):
    target_id: str | None = None
    title: str = Field(default="", max_length=200)
    mode: str | None = Field(default=None)
    provider_id: str = Field(default="", max_length=200)
    goal: str = Field(default="", max_length=8000)
    template_id: str = Field(default="free-form")
    sandbox: bool = True
    background_mode: str = Field(default="paused")
    limits: dict[str, Any] = Field(default_factory=dict)


class ExperimentPlanRequest(BaseModel):
    steps: list[dict[str, Any]] = Field(default_factory=list)
    origin: str = Field(default="manual", max_length=64)


class ExperimentAiPlanRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=200)
    goal: str = Field(default="", max_length=8000)
    language: str = Field(default="zh-CN", max_length=20)


class ExperimentAnalyzeRequest(BaseModel):
    provider_id: str = Field(default="", max_length=200)
    language: str = Field(default="zh-CN", max_length=20)
    prompt: str = Field(default="", max_length=8000)


class ExperimentRunRequest(BaseModel):
    approved: bool = False


class ExperimentReportRequest(BaseModel):
    language: str = Field(default="zh-CN", max_length=20)


class InterventionPairRequest(BaseModel):
    target_id: str | None = None
    title: str = Field(default="Paired ablation experiment", max_length=200)
    mode: str = Field(default="silence", pattern="^(silence|remove)$")
    node_ids: list[int] = Field(default_factory=list, max_length=10_000)
    edge_pairs: list[list[int]] = Field(default_factory=list, max_length=20_000)
    background_mode: str = Field(default="paused", pattern="^(paused|preserve)$")


class InterventionControlRequest(BaseModel):
    action: str = Field(pattern="^(pause|resume|step|clear-intervention)$")
    ticks: int = Field(default=1, ge=1, le=10_000)


class InterventionStimulusRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)


def _binding_status(item: ConsciousnessRuntime) -> list[dict[str, Any]]:
    """Resolve declarative package wiring against currently registered devices.

    A package may describe a device that is not installed by this host.  That
    is a visible warning, not a reason to make the Core fail or invent one.
    """
    rows: list[dict[str, Any]] = []
    for adapter_id in _MODEL_ADAPTER_DEFAULTS:
        _model_adapter_binding(item, adapter_id)
    for binding in item.manifest.adapter_bindings:
        adapter_id = str(binding.get("adapter_id", ""))
        installed = adapter_id in adapter_registry.ids()
        runtime_enabled = _adapter_enabled(adapter_id) if installed else False
        declared_enabled = bool(binding.get("enabled", False))
        rows.append({**binding, "installed": installed, "runtime_enabled": runtime_enabled,
                     "effective_enabled": installed and runtime_enabled and declared_enabled,
                     "status": "attached" if installed and runtime_enabled and declared_enabled else "package-disabled" if installed and not declared_enabled else "host-disabled" if installed else "missing"})
    return rows


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "threemind-core"}


@app.get("/api/adapters")
def adapters() -> dict[str, Any]:
    active = manager.instances.get(manager.active_id) if manager.active_id is not None else None
    items = adapter_registry.list(adapter_runtime_state)
    telemetry_status = telemetry_collector.status()
    for row in items:
        if row["id"] in _TELEMETRY_ADAPTER_IDS:
            scope = _telemetry_scope(row["id"])
            if scope == "runtime":
                status = active.runtime_telemetry_status() if isinstance(active, _HostObservedRuntime) else {
                    "backend": "python-thread-time+monotonic", "dependency": "full",
                    "last_sample_time": None, "available_metrics": [],
                    "unavailable_metrics": {}, "recent_error": None,
                }
                row["runtime"] = {**status, "audit": telemetry_audit_store.status(), "scope": scope, "whole_process": False, "per_consciousness": True, "consciousness_id": active.consciousness_id if active is not None else None}
            else:
                row["runtime"] = {
                    **telemetry_status,
                    "audit": telemetry_audit_store.status(),
                    "available_metrics": telemetry_status["available_metrics"][scope],
                    "unavailable_metrics": telemetry_status["unavailable_metrics"][scope],
                    "scope": scope,
                    "whole_process": scope == "process",
                    "per_consciousness": False,
                }
        elif row["id"] in _MEDIA_ADAPTER_IDS:
            row["runtime"] = _media_adapter_runtime_status(row["id"], active)
    return {
        "items": items,
        "protocol": "threemind-adapter/1",
        "runtime_state": "registered",
        "active_consciousness_id": active.consciousness_id if active is not None else None,
        "bindings": _binding_status(active) if active is not None else [],
        "background_input": {"enabled": bool(ui_settings.get("stimuli", {}).get("background_enabled", True))},
    }


@app.get("/api/adapters/{adapter_id}")
def adapter(adapter_id: str) -> dict[str, Any]:
    try:
        result = adapter_registry.describe(adapter_id, adapter_runtime_state)
        if adapter_id in _TELEMETRY_ADAPTER_IDS:
            scope = _telemetry_scope(adapter_id)
            active = manager.instances.get(manager.active_id) if manager.active_id is not None else None
            if scope == "runtime":
                status = active.runtime_telemetry_status() if isinstance(active, _HostObservedRuntime) else {"backend": "python-thread-time+monotonic", "dependency": "full", "last_sample_time": None, "available_metrics": [], "unavailable_metrics": {}, "recent_error": None}
                result["runtime"] = {**status, "audit": telemetry_audit_store.status(), "scope": scope, "whole_process": False, "per_consciousness": True, "consciousness_id": active.consciousness_id if active is not None else None}
            else:
                status = telemetry_collector.status()
                result["runtime"] = {**status, "audit": telemetry_audit_store.status(), "available_metrics": status["available_metrics"][scope], "unavailable_metrics": status["unavailable_metrics"][scope], "scope": scope, "whole_process": scope == "process", "per_consciousness": False}
        elif adapter_id in _MEDIA_ADAPTER_IDS:
            active = manager.instances.get(manager.active_id) if manager.active_id is not None else None
            result["runtime"] = _media_adapter_runtime_status(adapter_id, active)
        return result
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.patch("/api/adapters/{adapter_id}")
def update_adapter(adapter_id: str, request: AdapterUpdateRequest) -> dict[str, Any]:
    try:
        result = adapter_registry.update(adapter_runtime_state, adapter_id, enabled=request.enabled, config=request.config)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    _write_ui_settings()
    if adapter_id == "structural-readout":
        _structural_readouts.clear()
    elif adapter_id == "temporal-convergence-readout":
        _temporal_readouts.clear()
    elif adapter_id in _TELEMETRY_ADAPTER_IDS:
        _reset_telemetry_baselines()
        if adapter_id == "runtime-telemetry-field":
            for item in manager.instances.values():
                if isinstance(item, _HostObservedRuntime):
                    item.reset_runtime_telemetry_window()
    elif adapter_id == "auditory-sensor":
        for device in _auditory_adapters.values(): device.reset_baseline()
    elif adapter_id == "visual-sensor":
        for device in _visual_adapters.values(): device.reset_baseline()
    elif adapter_id in {"acoustic-output-organ", "activation-image-projector"}:
        for key, (runtime_item, token, _device) in tuple(_media_output_subscriptions.items()):
            if key[1] == adapter_id:
                runtime_item.output_bus.unsubscribe(token)
                _media_output_subscriptions.pop(key, None)
    for item in manager.instances.values():
        _body_adapter(item)
        _configure_attention_modulators(item)
    return result


@app.patch("/api/background-input")
def update_background_input(request: BackgroundInputUpdateRequest) -> dict[str, Any]:
    policies = ui_settings.setdefault("stimuli", {}).setdefault("source_policies", {})
    entry = policies.setdefault("background", {"enabled": True, "bypass_attention": False})
    entry["enabled"] = bool(request.enabled)
    _sync_source_policy_legacy()
    # The background master is also exposed through the legacy runtime source
    # switch.  Keep the two views atomic so a user cannot end up with a UI
    # master that says "enabled" while an instance silently retains an old
    # disabled ambient source.  Reset telemetry baselines on either transition:
    # time spent disconnected is not accumulated into a synthetic rise/fall.
    for item in manager.instances.values():
        item.set_source("ambient", bool(request.enabled), confirm_last=True)
    _reset_telemetry_baselines()
    _write_ui_settings()
    return {
        "enabled": bool(ui_settings["stimuli"]["background_enabled"]),
        "instances_updated": len(manager.instances),
    }


@app.get("/api/consciousnesses/{consciousness_id}/adapters")
def consciousness_adapter_bindings(consciousness_id: str) -> dict[str, Any]:
    try:
        item = manager.get(consciousness_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"consciousness_id": consciousness_id, "items": _binding_status(item)}


@app.patch("/api/consciousnesses/{consciousness_id}/adapters/{adapter_id}")
def update_consciousness_adapter_binding(consciousness_id: str, adapter_id: str, request: AdapterBindingUpdateRequest) -> dict[str, Any]:
    if adapter_id not in adapter_registry.ids():
        raise HTTPException(status_code=404, detail=f"unknown adapter: {adapter_id}")
    try:
        item = manager.get(consciousness_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    binding = _model_adapter_binding(item, adapter_id)
    binding["enabled"] = bool(request.enabled)
    if request.config is not None:
        try:
            # Reuse the recursive public adapter schema as validation without
            # mutating the host-wide registry state.
            temporary = {adapter_id: {"enabled": True, "config": _model_adapter_config(item, adapter_id)}}
            validated = adapter_registry.update(
                temporary,
                adapter_id,
                enabled=None,
                config=request.config,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        binding["config"] = validated["config"]
    if adapter_id in _TELEMETRY_ADAPTER_IDS:
        adapters = _telemetry_adapter_cache(adapter_id)
        if item.consciousness_id in adapters:
            adapters[item.consciousness_id].configure(_model_adapter_config(item, adapter_id))
            adapters[item.consciousness_id].reset_baseline()
        if adapter_id == "runtime-telemetry-field" and isinstance(item, _HostObservedRuntime):
            item.reset_runtime_telemetry_window()
    elif adapter_id == "auditory-sensor":
        device = _auditory_adapters.get(item.consciousness_id)
        if device is not None:
            device.configure(_model_adapter_config(item, adapter_id)); device.reset_baseline()
    elif adapter_id == "visual-sensor":
        device = _visual_adapters.get(item.consciousness_id)
        if device is not None:
            device.configure(_model_adapter_config(item, adapter_id)); device.reset_baseline()
    elif adapter_id in {"acoustic-output-organ", "activation-image-projector"}:
        existing = _media_output_subscriptions.pop((item.consciousness_id, adapter_id), None)
        if existing is not None: existing[0].output_bus.unsubscribe(existing[1])
    # Write the resolved declaration into the canonical package location. It
    # does not alter graph state; the runtime state snapshot is current at the
    # exact moment of the explicit binding change.
    path = DATA_DIR / f"{item.consciousness_id}{MODEL_PACKAGE_SUFFIX}"
    _resolve_model_adapters(item)
    item.save_package(str(path))
    _record_artifact(path, item.package)
    _schedule_history_checkpoint(item)
    return {"consciousness_id": consciousness_id, "binding": next(row for row in _binding_status(item) if row.get("adapter_id") == adapter_id), "package_path": str(path)}


def _media_source_for(content_type: str, filename: str) -> tuple[str, str]:
    normalized = str(content_type or "").casefold()
    suffix = Path(filename or "").suffix.casefold()
    if normalized.startswith("audio/") or suffix in {".wav", ".wave", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}:
        return "auditory-sensor", "ui-audio"
    if normalized.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
        return "visual-sensor", "ui-image"
    if normalized.startswith("video/") or suffix in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
        return "visual-sensor", "ui-video"
    raise ValueError("unsupported media type; upload an audio, image, or video carrier")


async def _enqueue_media_frames(
    item: ConsciousnessRuntime,
    *,
    session_id: str,
    adapter_id: str,
    source: str,
    frames: tuple[Any, ...],
    inter_frame_epochs: int,
    frame_start: int,
    initial_delay_epochs: int = 0,
    captured_at_ms: float | None = None,
    audit: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not frames:
        return None
    if manager.instances.get(item.consciousness_id) is not item:
        raise RuntimeError("the target consciousness instance was replaced or removed")
    if not _media_input_enabled(item, adapter_id, source):
        raise RuntimeError("media sensory input was paused or disabled before delivery")
    receipt = await asyncio.to_thread(
        item.enqueue_frames,
        frames,
        metadata={
            "carrier": "audio" if adapter_id == "auditory-sensor" else "visual",
            "media_session_id": session_id,
            "captured_at_ms": captured_at_ms,
            # Reserved observation metadata for future receptor-topology tools.
            # Core does not inspect or act on this field.
            "receptor_topology": "auditory-bank" if adapter_id == "auditory-sensor" else "retinal-grid",
        },
        adapter_id=adapter_id,
        inter_frame_epochs=max(1, int(inter_frame_epochs)),
        initial_delay_epochs=max(0, int(initial_delay_epochs)),
    )
    await asyncio.to_thread(
        media_audit_store.record_delivery,
        session_id=session_id,
        consciousness_id=item.consciousness_id,
        adapter_id=adapter_id,
        envelope_id=str(receipt.get("envelope_id") or "") or None,
        frame_start=frame_start,
        frame_count=len(frames),
        captured_at_ms=captured_at_ms,
        audit={
            "source": source,
            "intensity": float(frames[0].intensity),
            "anonymous_channel_count": sum(len(frame.channels) for frame in frames),
            **dict(audit or {}),
        },
    )
    _schedule_history_checkpoint(item)
    return receipt


def _next_video_frame(iterator: Any) -> Any | None:
    try:
        return next(iterator)
    except StopIteration:
        return None


async def _process_media_upload(
    session_id: str,
    consciousness_id: str,
    adapter_id: str,
    source: str,
    asset_path: str,
    content_type: str,
    intensity: float,
) -> None:
    try:
        item = manager.get(consciousness_id)
        if not _media_input_enabled(item, adapter_id, source):
            raise RuntimeError("media sensory adapter or its consciousness binding is disabled")
        await asyncio.to_thread(media_audit_store.update_session, session_id, state="decoding", progress=.02)
        total_encoded = 0
        if adapter_id == "auditory-sensor":
            decoded = await asyncio.to_thread(media_codec_service.decode_audio, asset_path)
            device = _auditory_adapter(item); device.reset_baseline()
            frames = await asyncio.to_thread(
                device.encode_samples, decoded.samples, decoded.sample_rate,
                intensity=intensity, source=source,
                bypass_filter=_source_policy(source)["bypass_attention"],
            )
            await asyncio.to_thread(media_audit_store.update_session, session_id, state="encoding", progress=.55)
            await _enqueue_media_frames(
                item, session_id=session_id, adapter_id=adapter_id, source=source,
                frames=frames, inter_frame_epochs=device.inter_frame_epochs,
                frame_start=0,
                audit={"sample_rate": decoded.sample_rate, "duration_seconds": decoded.duration_seconds},
            )
            total_encoded = len(frames)
        else:
            device = _visual_adapter(item); device.reset_baseline()
            suffix = Path(asset_path).suffix.casefold()
            is_image = content_type.casefold().startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            if is_image:
                decoded = await asyncio.to_thread(media_codec_service.decode_image, asset_path)
                frames = await asyncio.to_thread(
                    device.encode_pixels, decoded.pixels, decoded.width, decoded.height,
                    components=decoded.components, intensity=intensity, source=source,
                    bypass_filter=_source_policy(source)["bypass_attention"],
                )
                await _enqueue_media_frames(
                    item, session_id=session_id, adapter_id=adapter_id, source=source,
                    frames=frames, inter_frame_epochs=device.inter_patch_epochs,
                    frame_start=0,
                    audit={"media_frame": 0, "source_width": decoded.width, "source_height": decoded.height},
                )
                total_encoded = len(frames)
            else:
                iterator = media_codec_service.iter_video(
                    asset_path,
                    maximum_frame_rate=float(device.config.get("sensory_frame_rate", 6.0)),
                )
                media_frame = 0
                while True:
                    decoded = await asyncio.to_thread(_next_video_frame, iterator)
                    if decoded is None: break
                    frames = await asyncio.to_thread(
                        device.encode_pixels, decoded.pixels, decoded.width, decoded.height,
                        components=decoded.components, intensity=intensity, source=source,
                        bypass_filter=_source_policy(source)["bypass_attention"],
                    )
                    await _enqueue_media_frames(
                        item, session_id=session_id, adapter_id=adapter_id, source=source,
                        frames=frames, inter_frame_epochs=device.inter_patch_epochs,
                        initial_delay_epochs=total_encoded * device.inter_patch_epochs,
                        frame_start=total_encoded, captured_at_ms=decoded.timestamp_seconds * 1000.0,
                        audit={"media_frame": media_frame, "source_width": decoded.width, "source_height": decoded.height},
                    )
                    total_encoded += len(frames); media_frame += 1
                    await asyncio.to_thread(
                        media_audit_store.update_session, session_id,
                        state="encoding", progress=min(.95, .05 + media_frame / (media_frame + 30.0)),
                        frames_encoded=total_encoded,
                    )
        await asyncio.to_thread(media_audit_store.update_session, session_id, state="queued", progress=1.0, frames_encoded=total_encoded)
    except asyncio.CancelledError:
        await asyncio.to_thread(media_audit_store.update_session, session_id, state="cancelled", error="service shutdown")
        raise
    except Exception as error:
        await asyncio.to_thread(media_audit_store.update_session, session_id, state="failed", error=str(error))


@app.get("/api/media/capabilities")
def media_capabilities() -> dict[str, Any]:
    return {
        **media_codec_service.capabilities(),
        "protocol": "threemind-media/1",
        "upload_retention": "content-addressed",
        "live_raw_retention": "ephemeral",
        "semantic_models": [],
    }


@app.post("/api/media/uploads")
async def upload_media(
    consciousness_id: str,
    intensity: float = 1.0,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    try:
        item = manager.get(consciousness_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        adapter_id, source = _media_source_for(str(file.content_type or ""), str(file.filename or "media.bin"))
    except ValueError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    if not _media_input_enabled(item, adapter_id, source):
        raise HTTPException(status_code=409, detail="enable the media adapter and this consciousness binding before submitting a carrier")
    config = _model_adapter_config(item, adapter_id)
    byte_limit = int(config.get("upload_limit_mb", 32 if adapter_id == "auditory-sensor" else 128)) * 1024 * 1024
    try:
        asset = await asyncio.to_thread(
            media_audit_store.save_stream, file.file,
            filename=str(file.filename or "media.bin"),
            content_type=str(file.content_type or "application/octet-stream"),
            byte_limit=byte_limit,
        )
    except MediaSizeLimitError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    session = await asyncio.to_thread(
        media_audit_store.create_session,
        consciousness_id=consciousness_id, adapter_id=adapter_id, mode="upload",
        asset_id=asset.asset_id, config={"intensity": max(0.0, min(2.0, float(intensity))), **config},
    )
    task = asyncio.create_task(_process_media_upload(
        str(session["session_id"]), consciousness_id, adapter_id, source,
        asset.path, asset.content_type, max(0.0, min(2.0, float(intensity))),
    ))
    _media_background_tasks.add(task)
    task.add_done_callback(_media_background_tasks.discard)
    return {"accepted": True, "asset": asdict(asset), "session": session}


@app.get("/api/media/sessions")
def media_sessions(consciousness_id: str | None = None, adapter_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    return media_audit_store.list_sessions(consciousness_id=consciousness_id, adapter_id=adapter_id, limit=limit, offset=offset)


@app.get("/api/media/sessions/{session_id}")
def media_session(session_id: str) -> dict[str, Any]:
    result = media_audit_store.session(session_id)
    if result is None: raise HTTPException(status_code=404, detail="media session not found")
    return result


@app.get("/api/media/deliveries")
def media_deliveries(consciousness_id: str | None = None, session_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    return media_audit_store.list_deliveries(consciousness_id=consciousness_id, session_id=session_id, limit=limit, offset=offset)


@app.get("/api/media/export")
def export_media_history(format: str = "jsonl", consciousness_id: str | None = None, session_id: str | None = None):
    normalized = format.casefold()
    if normalized == "jsonl":
        def json_lines():
            for row in media_audit_store.iter_deliveries(consciousness_id=consciousness_id, session_id=session_id):
                yield json.dumps(row, ensure_ascii=False) + "\n"
        return StreamingResponse(json_lines(), media_type="application/x-ndjson", headers={"Content-Disposition": "attachment; filename=threemind-media-history.jsonl"})
    if normalized == "csv":
        fields = ["delivery_id", "session_id", "consciousness_id", "adapter_id", "envelope_id", "frame_start", "frame_count", "captured_at_ms", "created_at_utc", "audit_json"]
        def csv_lines():
            stream = io.StringIO(newline=""); writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); yield "\ufeff" + stream.getvalue(); stream.seek(0); stream.truncate(0)
            for row in media_audit_store.iter_deliveries(consciousness_id=consciousness_id, session_id=session_id):
                writer.writerow({**{field: row.get(field) for field in fields}, "audit_json": json.dumps(row.get("audit", {}), ensure_ascii=False)})
                yield stream.getvalue(); stream.seek(0); stream.truncate(0)
        return StreamingResponse(csv_lines(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=threemind-media-history.csv"})
    raise HTTPException(status_code=400, detail="format must be jsonl or csv")


@app.websocket("/api/media/input/{consciousness_id}/{adapter_id}")
async def live_media_input(websocket: WebSocket, consciousness_id: str, adapter_id: str) -> None:
    await websocket.accept()
    if adapter_id not in {"auditory-sensor", "visual-sensor"}:
        await websocket.send_json({"type": "error", "detail": "unsupported live media adapter"}); await websocket.close(code=4404); return
    try:
        item = manager.get(consciousness_id)
    except KeyError:
        await websocket.send_json({"type": "error", "detail": "consciousness not found"}); await websocket.close(code=4404); return
    source = "live-microphone" if adapter_id == "auditory-sensor" else "live-camera"
    if not _media_input_enabled(item, adapter_id, source):
        await websocket.send_json({"type": "error", "detail": "media adapter or consciousness binding is disabled"}); await websocket.close(code=4409); return
    config = _model_adapter_config(item, adapter_id)
    if not bool(config.get("live_enabled", False)):
        await websocket.send_json({"type": "error", "detail": "live capture is disabled in adapter settings"}); await websocket.close(code=4403); return
    key = (consciousness_id, adapter_id)
    reservation = _reserve_media_live_session(key, item)
    if reservation is None:
        await websocket.send_json({"type": "error", "detail": "another live session is already active"}); await websocket.close(code=4409); return
    session: dict[str, Any] | None = None
    device: Any | None = None
    try:
        # A client that opens a socket but never sends the protocol hello must
        # not monopolize the microphone/camera slot indefinitely.
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        except TimeoutError as error:
            raise MediaProtocolError("live media hello timed out") from error
        if hello.get("protocol") != "threemind-media/1" or hello.get("type") != "hello":
            raise MediaProtocolError("expected a threemind-media/1 hello message")
        intensity = max(0.0, min(2.0, float(hello.get("intensity", 1.0))))
        session = await asyncio.to_thread(
            media_audit_store.create_session,
            consciousness_id=consciousness_id, adapter_id=adapter_id, mode="live",
            asset_id=None, config={"intensity": intensity, "raw_retention": "ephemeral", **config},
        )
        session_id = str(session["session_id"])
        with _media_live_session_lock:
            reservation.session_id = session_id
        await asyncio.to_thread(media_audit_store.update_session, session_id, state="running")
        device = _auditory_adapter(item) if adapter_id == "auditory-sensor" else _visual_adapter(item)
        device.reset_baseline(); last_sequence = -1; total_encoded = 0; last_video_timestamp = float("-inf")
        await websocket.send_json({
            "type": "ready", "protocol": "threemind-media/1",
            "session_id": session_id, "raw_retention": "ephemeral",
            # This is the resolved sensory-device configuration, not Core
            # state.  The browser uses it to honor the selected camera
            # resolution/frame rate before sending physical samples.
            "config": config,
        })
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect": break
            if message.get("text") is not None:
                control = json.loads(str(message["text"]))
                if control.get("type") == "stop": break
                if control.get("type") == "ping": await websocket.send_json({"type": "pong"})
                continue
            raw = message.get("bytes")
            if raw is None: continue
            if manager.instances.get(consciousness_id) is not item:
                raise RuntimeError("the target consciousness instance was replaced or removed")
            if not _media_input_enabled(item, adapter_id, source):
                raise RuntimeError("media sensory input was paused or disabled")
            packet = decode_live_packet(raw)
            if packet.sequence <= last_sequence:
                raise MediaProtocolError("live media sequence must increase monotonically")
            last_sequence = packet.sequence
            if adapter_id == "auditory-sensor" and isinstance(packet, LiveAudioPacket):
                mono = [sum(packet.samples[index:index + packet.channels]) / packet.channels for index in range(0, len(packet.samples), packet.channels)]
                frames = await asyncio.to_thread(
                    device.encode_live_samples, mono, packet.sample_rate,
                    intensity=intensity, source=source,
                    bypass_filter=_source_policy(source)["bypass_attention"],
                )
                spacing = device.inter_frame_epochs
            elif adapter_id == "visual-sensor" and isinstance(packet, LiveVideoPacket):
                minimum_delta = 1000.0 / max(.2, float(device.config.get("sensory_frame_rate", 6.0)))
                if packet.timestamp_ms - last_video_timestamp + 1e-6 < minimum_delta:
                    await websocket.send_json({"type": "ack", "sequence": packet.sequence, "sampled": False, "reason": "frame-rate filter"}); continue
                last_video_timestamp = packet.timestamp_ms
                frames = await asyncio.to_thread(
                    device.encode_pixels, packet.pixels, packet.width, packet.height,
                    components=packet.components, intensity=intensity, source=source,
                    bypass_filter=_source_policy(source)["bypass_attention"],
                )
                spacing = device.inter_patch_epochs
            else:
                raise MediaProtocolError("packet kind does not match the selected adapter")
            receipt = await _enqueue_media_frames(
                item, session_id=session_id, adapter_id=adapter_id, source=source,
                frames=frames, inter_frame_epochs=spacing, frame_start=total_encoded,
                captured_at_ms=packet.timestamp_ms, audit={"live_sequence": packet.sequence, "raw_retained": False},
            )
            total_encoded += len(frames)
            await asyncio.to_thread(media_audit_store.update_session, session_id, state="running", frames_encoded=total_encoded)
            sampled = bool(frames)
            await websocket.send_json({
                "type": "ack", "sequence": packet.sequence,
                "sampled": sampled,
                "reason": None if sampled else ("buffering" if adapter_id == "auditory-sensor" else "no-positive-drive"),
                "frame_count": len(frames),
                "envelope_id": receipt.get("envelope_id") if receipt else None,
            })
    except WebSocketDisconnect:
        pass
    except Exception as error:
        if session is not None: await asyncio.to_thread(media_audit_store.update_session, str(session["session_id"]), state="failed", error=str(error))
        try: await websocket.send_json({"type": "error", "detail": str(error)})
        except Exception: pass
    finally:
        if session is not None:
            current = media_audit_store.session(str(session["session_id"]))
            if current and current.get("state") not in {"failed", "cancelled"}:
                await asyncio.to_thread(media_audit_store.update_session, str(session["session_id"]), state="completed", progress=1.0)
        # An older connection can finish after a restored runtime has already
        # accepted a new browser session. Never let the old finally block
        # remove the replacement's reservation.
        _release_media_live_session(key, reservation)
        if device is not None: device.reset_baseline()
        try: await websocket.close()
        except Exception: pass


@app.websocket("/api/media/output/{consciousness_id}/{adapter_id}")
async def live_media_output(websocket: WebSocket, consciousness_id: str, adapter_id: str) -> None:
    await websocket.accept()
    if adapter_id not in {"acoustic-output-organ", "activation-image-projector"}:
        await websocket.send_json({"type": "error", "detail": "unsupported media output adapter"}); await websocket.close(code=4404); return
    try:
        item = manager.get(consciousness_id)
    except KeyError:
        await websocket.send_json({"type": "error", "detail": "consciousness not found"}); await websocket.close(code=4404); return
    if not (_adapter_enabled(adapter_id) and _model_adapter_enabled(item, adapter_id)):
        await websocket.send_json({"type": "error", "detail": "media output adapter or consciousness binding is disabled"}); await websocket.close(code=4409); return
    device = _media_output_adapter(item, adapter_id); config = _model_adapter_config(item, adapter_id)
    interval = max(.02, min(10.0, float(config.get("output_interval_ms", 100)) / 1000.0))
    try:
        await websocket.send_json({"type": "ready", "protocol": "threemind-media/1", "adapter_id": adapter_id})
        while True:
            await asyncio.sleep(interval)
            if manager.instances.get(consciousness_id) is not item:
                break
            if not (_adapter_enabled(adapter_id) and _model_adapter_enabled(item, adapter_id)):
                break
            frame = device.latest()
            if frame is None: continue
            if adapter_id == "acoustic-output-organ":
                await websocket.send_json({"type": "audio-control", "tick": frame.tick, "voices": [{"frequency": frequency, "amplitude": amplitude} for frequency, amplitude in frame.voices]})
            else:
                await websocket.send_json({"type": "image-frame", "tick": frame.tick, "width": frame.width, "height": frame.height, "format": "gray8", "pixels": base64.b64encode(frame.pixels).decode("ascii")})
    except WebSocketDisconnect:
        pass
    except Exception:
        try: await websocket.close()
        except Exception: pass


@app.get("/api/telemetry/samples")
def telemetry_samples(consciousness_id: str | None = None, adapter_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    if adapter_id and adapter_id not in _TELEMETRY_ADAPTER_IDS:
        raise HTTPException(status_code=400, detail="adapter_id must identify a physical telemetry adapter")
    if consciousness_id and adapter_id in {"host-telemetry-field", "process-telemetry-field"}:
        raise HTTPException(status_code=400, detail="shared raw telemetry cannot be filtered by consciousness_id")
    sample_scope = "runtime" if consciousness_id or adapter_id == "runtime-telemetry-field" else "shared" if adapter_id else None
    return telemetry_audit_store.list_samples(scope=sample_scope, consciousness_id=consciousness_id, limit=limit, offset=offset)


@app.get("/api/telemetry/history")
def telemetry_history(consciousness_id: str | None = None, adapter_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    if adapter_id and adapter_id not in _TELEMETRY_ADAPTER_IDS:
        raise HTTPException(status_code=400, detail="adapter_id must identify a physical telemetry adapter")
    return telemetry_audit_store.list_deliveries(consciousness_id=consciousness_id, adapter_id=adapter_id, limit=limit, offset=offset)


def _telemetry_export_rows(consciousness_id: str | None, adapter_id: str | None) -> list[dict[str, Any]]:
    # Explicit user export may be large; pagination remains the normal browser
    # path. The store itself has no hidden truncation.
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = telemetry_audit_store.list_deliveries(consciousness_id=consciousness_id, adapter_id=adapter_id, limit=10_000, offset=offset)
        batch = list(result["items"])
        rows.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(result["total"]):
            break
    return list(reversed(rows))


def _telemetry_export_samples(*, scope: str | None = None, consciousness_id: str | None = None) -> list[dict[str, Any]]:
    """Read every de-duplicated raw sample in chronological order."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = telemetry_audit_store.list_samples(scope=scope, consciousness_id=consciousness_id, limit=10_000, offset=offset)
        batch = list(result["items"])
        rows.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(result["total"]):
            break
    return list(reversed(rows))


@app.get("/api/telemetry/export")
def export_telemetry(format: str = "jsonl", records: str = "deliveries", consciousness_id: str | None = None, adapter_id: str | None = None):
    if adapter_id and adapter_id not in _TELEMETRY_ADAPTER_IDS:
        raise HTTPException(status_code=400, detail="adapter_id must identify a physical telemetry adapter")
    normalized_format = format.casefold()
    normalized_records = records.casefold()
    if normalized_records not in {"deliveries", "samples"}:
        raise HTTPException(status_code=400, detail="records must be deliveries or samples")
    if normalized_records == "samples" and consciousness_id and adapter_id in {"host-telemetry-field", "process-telemetry-field"}:
        raise HTTPException(status_code=400, detail="shared raw telemetry cannot be filtered by consciousness_id")
    scope = _telemetry_scope(adapter_id) if adapter_id else None
    sample_scope = "runtime" if consciousness_id or scope == "runtime" else "shared" if scope in {"host", "process"} else None
    rows = _telemetry_export_samples(scope=sample_scope, consciousness_id=consciousness_id) if normalized_records == "samples" else _telemetry_export_rows(consciousness_id, adapter_id)
    if normalized_format == "jsonl":
        if normalized_records == "samples" and scope is not None:
            rows = [
                {
                    "record_type": "raw_telemetry_sample", "scope": scope,
                    "owner_consciousness_id": row.get("owner_consciousness_id"),
                    "sample_id": row.get("sample_id"), "captured_at_utc": row.get("captured_at_utc"),
                    "monotonic_seconds": row.get("monotonic_seconds"), "backend": row.get("backend"),
                    "duration_ms": row.get("duration_ms"), "recent_error": row.get("recent_error"),
                    "metrics": row.get(scope, {}), "context": row.get("context", {}),
                }
                for row in rows
            ]
        elif normalized_records == "samples":
            rows = [{"record_type": "raw_telemetry_sample", **row} for row in rows]
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        filename = "threemind-telemetry-raw.jsonl" if normalized_records == "samples" else "threemind-telemetry-deliveries.jsonl"
        return StreamingResponse(iter((content,)), media_type="application/x-ndjson", headers={"Content-Disposition": f"attachment; filename={filename}"})
    if normalized_format == "csv":
        import csv
        import io
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        if normalized_records == "samples":
            writer.writerow([
                "sample_id", "captured_at_utc", "monotonic_seconds", "backend",
                "duration_ms", "scope", "owner_consciousness_id", "metric", "available", "raw_value",
                "unit", "normalized_level", "reference", "reference_unit",
                "reference_source", "unavailable_reason", "recent_error", "context_json",
            ])
            for row in rows:
                requested_scopes = (scope,) if scope is not None else (("runtime",) if row.get("scope") == "runtime" else ("host", "process"))
                for current_scope in requested_scopes:
                    for metric, value in dict(row.get(current_scope, {})).items():
                        writer.writerow([
                            row.get("sample_id"), row.get("captured_at_utc"),
                            row.get("monotonic_seconds"), row.get("backend"),
                            row.get("duration_ms"), current_scope, row.get("owner_consciousness_id"), metric,
                            value.get("available"), value.get("raw_value"),
                            value.get("unit"), value.get("normalized_level"),
                            value.get("reference"), value.get("reference_unit"),
                            value.get("reference_source"), value.get("unavailable_reason"),
                            row.get("recent_error"),
                            json.dumps(row.get("context", {}), ensure_ascii=False, sort_keys=True),
                        ])
            return StreamingResponse(iter((stream.getvalue(),)), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=threemind-telemetry-raw.csv"})
        writer.writerow([
            "delivery_id", "sample_id", "consciousness_id", "adapter_id",
            "envelope_id", "created_at_utc", "captured_at_utc",
            "monotonic_seconds", "backend", "sample_scope", "sample_owner_consciousness_id",
            "sample_context_json", "metric", "raw_value", "unit",
            "normalized_level", "smoothed_level", "rise", "fall", "gain",
            "smoothing", "reference", "reference_source",
            "reference_override", "available", "unavailable_reason", "channels",
            "input_frame",
        ])
        for row in rows:
            measurements = row.get("audit", {}).get("measurements", {})
            for metric, value in measurements.items():
                sample = row.get("sample", {})
                writer.writerow([
                    row.get("delivery_id"), row.get("sample_id"),
                    row.get("consciousness_id"), row.get("adapter_id"),
                    row.get("envelope_id"), row.get("created_at_utc"),
                    sample.get("captured_at_utc"), sample.get("monotonic_seconds"),
                    sample.get("backend"), sample.get("scope"), sample.get("owner_consciousness_id"),
                    json.dumps(sample.get("context", {}), ensure_ascii=False, sort_keys=True),
                    metric, value.get("raw_value"),
                    value.get("unit"), value.get("normalized_level"),
                    value.get("smoothed_level"), value.get("rise"),
                    value.get("fall"), value.get("gain"), value.get("smoothing"),
                    value.get("reference"), value.get("reference_source"),
                    value.get("reference_override"), value.get("available"),
                    value.get("unavailable_reason"),
                    json.dumps(value.get("channels", {}), ensure_ascii=False, sort_keys=True),
                    json.dumps(row.get("audit", {}).get("input_frame"), ensure_ascii=False, sort_keys=True),
                ])
        return StreamingResponse(iter((stream.getvalue(),)), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=threemind-telemetry-deliveries.csv"})
    raise HTTPException(status_code=400, detail="format must be csv or jsonl")


@app.get("/api/network/settings")
def network_settings() -> dict[str, Any]:
    return _network_public()


@app.post("/api/network/settings")
def save_network_settings(request: NetworkSettingsRequest) -> dict[str, Any]:
    global _network_token
    if request.enabled and not (request.token or _network_token):
        raise HTTPException(status_code=400, detail="a network token is required before enabling network transport")
    if request.token:
        _network_token = request.token
        network_store.save([{"token": _network_token}])
    adapter_registry.update(adapter_runtime_state, "network-transport", enabled=request.enabled, config={
        "allow_remote_modulation": request.allow_remote_modulation,
        "modulation_timeout_ticks": request.modulation_timeout_ticks,
        "output_interval_ms": request.output_interval_ms,
    })
    _write_ui_settings()
    for item in manager.instances.values():
        _configure_attention_modulators(item)
    return _network_public()


def _storage_inventory() -> dict[str, Any]:
    """Build a metadata-only, host-side cleanup catalogue.

    The graph runtime is intentionally absent from this traversal.  In
    particular, it never opens ``records.json`` or a ``.tmind`` package merely
    to render a storage page.
    """

    inventory = scan_data_directory(DATA_DIR, active_persistence=persistence.name)
    items = list(inventory["items"])
    # This represents logical records in the selected backend rather than an
    # arbitrary local file.  Clearing it is a separate, explicitly labelled
    # action; it cannot be confused with deleting a .tmind model package.
    items.insert(0, {
        "id": "persistence:records",
        "name": "current durable history records",
        "category": "durable_records",
        "bytes": 0,
        "modified_at": 0.0,
        "selectable": True,
        "action": "clear_records",
        "note": f"active_{persistence.name}_backend",
    })
    inventory["items"] = items
    inventory["archive_writer"] = archive_writer.status()
    inventory["confirmation_phrase"] = "DELETE"
    return inventory


@app.get("/api/persistence")
def persistence_status() -> dict[str, Any]:
    public_config: dict[str, Any] = {}
    if persistence.name == "sqlite":
        public_config["path"] = str(_persistence_config.get("path") or DATA_DIR / "threemind.sqlite3")
    elif persistence.name == "mysql":
        public_config["url_configured"] = bool(_persistence_config.get("url"))
    elif persistence.name == "d1":
        public_config["endpoint"] = str(_persistence_config.get("endpoint") or "")
        public_config["token_configured"] = bool(_persistence_config.get("token") or os.getenv("THREEMIND_D1_TOKEN"))
    legacy_file = DATA_DIR / "records.json"
    legacy_file_bytes = legacy_file.stat().st_size if legacy_file.exists() else 0
    return {
        "kind": persistence.name,
        "available": True,
        "supported": ["file", "sqlite", "mysql", "d1"],
        "config": public_config,
        "configured_from": "environment" if _persistence_environment_override else "encrypted-local" if _stored_persistence else "default",
        "startup_warning": _persistence_startup_warning or None,
        "legacy_file": {
            "path": str(legacy_file),
            "bytes": legacy_file_bytes,
            # A selected database backend deliberately leaves a legacy JSON
            # document alone.  It may be migrated explicitly later, but the
            # normal server must never delete or eagerly reopen it.
            "preserved": bool(legacy_file.exists()),
        } if legacy_file.exists() else None,
        "history_checkpoint": history_writer.status(),
        "archive_index": {**archive_repository.status(), **archive_indexer.status(), "writer": archive_writer.status()},
    }


@app.post("/api/persistence/switch")
def switch_persistence(request: PersistenceRequest) -> dict[str, Any]:
    global persistence, _persistence_kind, _persistence_config, _stored_persistence
    target: Any | None = None
    try:
        target = build_backend(request.kind, DATA_DIR, request.config)
        # Complete writes started against the old backend before copying or
        # closing it.  The history writer is coalesced but never intentionally
        # truncates records: every checkpoint is a full per-consciousness log.
        if not history_writer.flush(timeout=15.0):
            raise RuntimeError("history checkpoint writer did not flush before persistence switch")
        if request.migrate:
            for record in persistence.all():
                key = str(record.get("key") or record.get("id") or record.get("consciousness_id") or "")
                if key: target.put(key, record)
        # The selected backend may contain credentials (for example a MySQL
        # URL).  Keep it in the existing encrypted local credential store,
        # never in ui-settings.json or the public status endpoint.
        next_config = dict(request.config)
        persistence_store.save([{"kind": request.kind, "config": next_config}])
        old = persistence
        persistence = target; _persistence_kind = request.kind; _persistence_config = next_config
        _stored_persistence = {"kind": _persistence_kind, "config": dict(_persistence_config)}
        target = None
        old.close()
        for item in list(manager.instances.values()):
            _schedule_history_checkpoint(item)
    except (RuntimeError, ValueError, OSError) as error:
        if target is not None:
            try: target.close()
            except Exception: pass
        raise HTTPException(status_code=400, detail=str(error)) from error
    return persistence_status()


@app.get("/api/storage/scan")
def storage_scan() -> dict[str, Any]:
    """Scan local storage without opening model or legacy-history payloads."""

    return _storage_inventory()


@app.post("/api/storage/cleanup")
def storage_cleanup(request: StorageCleanupRequest) -> dict[str, Any]:
    """Delete only current-scan, user-selected removable artifacts.

    Configuration, encrypted credentials, database sidecars and unclassified
    files never enter the removable set.  Snapshot writes in progress make
    package deletion temporarily unavailable, rather than racing a writer.
    """

    if request.confirmation.strip() != "DELETE":
        raise HTTPException(status_code=400, detail="type DELETE to confirm the selected storage cleanup")
    inventory = _storage_inventory()
    current = {str(item["id"]): item for item in inventory["items"]}
    requested_ids = list(dict.fromkeys(str(item_id) for item_id in request.item_ids))
    deleted: list[str] = []
    cleared: list[str] = []
    skipped: list[dict[str, str]] = []
    writer_status = archive_writer.status()

    for item_id in requested_ids:
        item = current.get(item_id)
        if item is None:
            skipped.append({"id": item_id, "reason": "item is no longer present in the current storage scan"})
            continue
        if not bool(item.get("selectable")):
            skipped.append({"id": item_id, "reason": "this item is protected and cannot be removed from the cleanup screen"})
            continue
        action = str(item.get("action") or "")
        if action == "clear_records":
            try:
                # Finish already-requested durable writes before the explicit
                # purge. A live runtime can later make a new checkpoint; it is
                # never stopped or otherwise altered by storage cleanup.
                if not history_writer.flush(timeout=15.0):
                    raise RuntimeError("history writer did not settle before cleanup")
                persistence.clear()
                cleared.append(item_id)
            except Exception as error:
                skipped.append({"id": item_id, "reason": str(error)})
            continue
        if action != "delete_file" or not item_id.startswith("file:"):
            skipped.append({"id": item_id, "reason": "unsupported cleanup action"})
            continue
        name = item_id.removeprefix("file:")
        path = direct_child(DATA_DIR, name)
        if path is None or not path.exists() or not path.is_file():
            skipped.append({"id": item_id, "reason": "file is no longer available"})
            continue
        if is_model_package_path(path) and (int(writer_status.get("queued", 0)) > 0 or int(writer_status.get("pending", 0)) > 0):
            skipped.append({"id": item_id, "reason": "archive writes are still pending; retry after they finish"})
            continue
        try:
            path.unlink()
            if is_model_package_path(path):
                archive_repository.remove_path(path)
            deleted.append(path.name)
        except OSError as error:
            skipped.append({"id": item_id, "reason": str(error)})

    return {
        "deleted": deleted,
        "cleared": cleared,
        "skipped": skipped,
        "scan": _storage_inventory(),
    }


@app.get("/api/archive-index")
def archive_index_status() -> dict[str, Any]:
    """Return the non-blocking SQLite archive-index status."""
    return {**archive_repository.status(), **archive_indexer.status(), "writer": archive_writer.status()}


@app.post("/api/archive-index/reindex")
def reindex_archives(force: bool = False) -> dict[str, Any]:
    """Schedule a background scan for externally copied legacy packages."""
    return archive_indexer.start(force=force)


@app.get("/api/status")
def status() -> dict[str, Any]:
    active = manager.instances.get(manager.active_id) if manager.active_id is not None else None
    if active is None:
        return {
            "has_active": False,
            "active_id": None,
            "metrics": None,
            "manifest": None,
            "running": False,
            "paused": False,
        }
    return {
        "has_active": True,
        "active_id": active.consciousness_id,
        "metrics": active.metrics(),
        "manifest": active.manifest.to_dict(),
        "running": active.running(),
        "paused": active._paused,
    }


@app.get("/api/input-queue")
def input_queue() -> dict[str, Any]:
    """Audit-facing status for the active InputBus queue."""
    return _require_active_runtime().input_queue_status()


@app.get("/api/consciousnesses")
def consciousnesses() -> dict[str, Any]:
    # This endpoint is a hot UI path.  It must query the metadata index only;
    # loading every historic graph here can starve stimulation and live output.
    archive_counts = archive_repository.archive_counts()
    live = [dict(item) for item in manager.list()]
    for item in live:
        counts = archive_counts.get(str(item["id"]), {})
        item["snapshots"] = int(counts.get("snapshot", 0))
        item["portraits"] = int(counts.get("portrait", 0))
    live_ids = {str(item["id"]) for item in live}
    stored = [item for item in archive_repository.list_consciousnesses() if str(item["id"]) not in live_ids]
    return {
        "active_id": manager.active_id,
        "items": live + stored,
        "archive_index": {**archive_repository.status(), **archive_indexer.status(), "writer": archive_writer.status()},
    }


@app.post("/api/consciousnesses")
def create_consciousness(request: NewRequest) -> dict[str, Any]:
    global runtime
    manifest = ModelManifest.from_dict(request.manifest or {})
    item = _new_runtime(ModelPackage.empty(manifest, name=request.name))
    _resolve_model_adapters(item)
    item.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(item)
    manager.add(item)
    _ensure_output_observer(item)
    runtime = item
    scheduler.runtime = item
    interpreter.runtime = item
    item.start()
    _schedule_history_checkpoint(item)
    return {"metrics": item.metrics(), "manifest": manifest.to_dict()}


@app.delete("/api/consciousnesses/{consciousness_id}")
def delete_consciousness(consciousness_id: str) -> dict[str, Any]:
    global runtime
    try:
        item = manager.get(consciousness_id)
        manager.remove(consciousness_id)
        _release_media_runtime(item)
        _schedule_history_checkpoint(item)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    _prune_output_observer_subscriptions()
    runtime = manager.instances.get(manager.active_id) if manager.active_id is not None else None
    scheduler.runtime = runtime
    interpreter.runtime = runtime
    return {"deleted": consciousness_id, "active_id": manager.active_id}


@app.post("/api/consciousnesses/batch-control")
def batch_control_consciousnesses(action: str, ids: list[str]) -> dict[str, Any]:
    if action not in {"start", "pause", "resume", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported action")
    changed = []
    for consciousness_id in ids:
        try:
            item = manager.get(consciousness_id)
            getattr(item, action)("batch control") if action == "stop" else getattr(item, action)()
            if action == "stop":
                _schedule_history_checkpoint(item)
            changed.append(consciousness_id)
        except (KeyError, RuntimeError):
            continue
    return {"changed": changed}


@app.post("/api/consciousnesses/{consciousness_id}/activate")
def activate_consciousness(consciousness_id: str) -> dict[str, Any]:
    global runtime
    try:
        item = manager.activate(consciousness_id)
    except KeyError as error:
        # A saved consciousness is not a running instance yet. Hydrate its
        # newest package on demand so the management list can reopen it.
        try:
            item = _restore_snapshot_candidate(_snapshot_candidate(consciousness_id))
        except (KeyError, OSError, ValueError):
            try:
                item = _restore_package_path(_latest_package_path(consciousness_id), reason="replaced by restored model package")
            except (KeyError, OSError, ValueError) as restore_error:
                raise HTTPException(status_code=404, detail=str(error)) from restore_error
    runtime = item
    scheduler.runtime = item
    interpreter.runtime = item
    return {"active_id": item.consciousness_id, "metrics": item.metrics()}


@app.post("/api/consciousnesses/{consciousness_id}/continue")
def continue_consciousness(consciousness_id: str, request: ContinueRequest | None = None) -> dict[str, Any]:
    """Continue a stored consciousness from its latest, or selected, archive.

    This differs deliberately from ``runtime/resume``: the latter only
    unpauses a currently hydrated instance.  This endpoint reconstructs an
    instance from a persisted snapshot, which is what the management page's
    continuation control needs after restart or deletion from memory.
    """
    try:
        candidate = _snapshot_candidate(consciousness_id, request.path if request else None)
        item = _restore_snapshot_candidate(candidate)
    except (KeyError, OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "active_id": item.consciousness_id,
        "metrics": item.metrics(),
        "snapshot": candidate,
    }


@app.post("/api/consciousnesses/{consciousness_id}/stimulate")
def stimulate_consciousness(consciousness_id: str, request: StimulusRequest) -> dict[str, Any]:
    try:
        item = manager.get(consciousness_id)
        event = _submit_text(item, request.text, intensity=request.intensity, source=request.source, queued=True)
    except (KeyError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"queued": event, "metrics": item.metrics(), "conversation_append": _conversation_items(item=item)[-1:]}


@app.get("/api/consciousnesses/{consciousness_id}/input-queue")
def consciousness_input_queue(consciousness_id: str) -> dict[str, Any]:
    try:
        return manager.get(consciousness_id).input_queue_status()
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/consciousnesses/{consciousness_id}/energy")
def supply_consciousness_energy(consciousness_id: str, request: EnergySupplyRequest) -> dict[str, Any]:
    """External resource port for explicitly energy-enabled experiments."""
    try:
        item = manager.get(consciousness_id)
        event = item.supply_energy(request.amount, source=request.source)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"event": event, "metrics": item.metrics()}


@app.get("/api/consciousnesses/{consciousness_id}/graph")
def consciousness_graph(consciousness_id: str, limit: int | None = None) -> dict[str, Any]:
    """Instance-scoped graph projection for management and experiment UIs."""
    try:
        return _graph_view(manager.get(consciousness_id), limit)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/consciousnesses/{consciousness_id}/runtime/{action}")
def control_consciousness(consciousness_id: str, action: str) -> dict[str, Any]:
    try:
        item = manager.get(consciousness_id)
        if action == "start":
            _ensure_output_observer(item)
            item.start()
        elif action == "pause": item.pause()
        elif action == "resume": item.resume()
        elif action == "stop":
            item.stop("stopped by API")
            _schedule_history_checkpoint(item)
        else: raise ValueError("unknown runtime action")
    except KeyError as error:
        if action == "resume":
            try:
                candidate = _snapshot_candidate(consciousness_id)
                item = _restore_snapshot_candidate(candidate)
                return {"metrics": item.metrics(), "running": item.running(), "snapshot": candidate}
            except (KeyError, OSError, ValueError) as restore_error:
                raise HTTPException(status_code=404, detail=str(restore_error)) from restore_error
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"metrics": item.metrics(), "running": item.running()}


@app.get("/api/consciousnesses/{consciousness_id}/snapshots")
def consciousness_snapshots(consciousness_id: str) -> dict[str, Any]:
    """List only the snapshot artifacts belonging to one consciousness."""
    return {"items": _archive_catalog_items(consciousness_id)}


@app.get("/api/consciousnesses/{consciousness_id}/history")
def consciousness_history(consciousness_id: str, kind: str = "events", limit: int = 200, page: int = 1, page_size: int | None = None, query: str = "") -> dict[str, Any]:
    try:
        document, origin = _history_document(consciousness_id)
        data = _history_rows(document, kind)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {**_page(data, page=page, page_size=page_size or limit, query=query), "origin": origin, "checkpoint": {
        "tick": document.get("tick", 0),
        "history_revision": document.get("history_revision", 0),
    }}


@app.get("/api/model")
def model() -> dict[str, Any]:
    item = _require_active_runtime()
    return {"manifest": item.manifest.to_dict(), "runtime_config": asdict(item.config)}


@app.patch("/api/model/parameters")
def update_model_parameters(request: ModelParametersRequest) -> dict[str, Any]:
    item = _require_active_runtime()
    allowed = {
        "spatial_radius", "spatial_competition", "neighborhood_enabled",
        "activation_decay", "propagation_gain", "propagation_activation_min",
        "node_activation_floor", "direct_gain", "learning_rate", "edge_decay",
        "edge_birth_weight", "stability_gain", "stability_decay", "prune_threshold",
        "consolidation_first_gain", "consolidation_intensity_gain", "consolidation_cap",
        "consolidation_repeat_gain", "consolidation_associative_gain",
        "node_support_gain", "node_support_decay", "node_support_prune_threshold",
        "node_prune_after", "association_window", "attention_budget", "attention_competition_enabled",
        "edge_adaptation_limit", "propagation_limit", "edge_birth_activation_product_min",
        "edge_birth_policy",
        "local_novelty_gain", "novelty_touch_reference", "sensory_channels", "sensory_encoding",
        "homeostasis_enabled", "target_total_activation",
        "topology_inhibition_enabled", "inhibition_generation_gain",
        "inhibition_decay", "inhibition_diffusion", "inhibition_response_gain",
        "inhibition_saturation", "inhibition_propagation_min",
        "energy_simulation_enabled", "energy_initial_reserve", "energy_capacity",
        "energy_direct_cost", "energy_associative_cost", "energy_inhibition_cost",
        "irreversible_energy_death_enabled", "energy_maintenance_cost_per_node",
        "energy_maintenance_cost_per_edge", "energy_starvation_structural_decay",
        "energy_starvation_death_ticks",
        "response_epsilon", "unresponsive_window",
        "max_nodes", "max_edges", "tick_seconds", "random_seed",
    }
    unknown = set(request.parameters) - allowed
    if unknown:
        raise HTTPException(status_code=400, detail=f"unsupported model parameters: {', '.join(sorted(unknown))}")
    if "edge_birth_policy" in request.parameters and request.parameters["edge_birth_policy"] not in {"local-coactivation", "temporal-association"}:
        raise HTTPException(status_code=400, detail="edge_birth_policy must be local-coactivation or temporal-association")
    if request.spatial_dimensions is not None and not item.manifest.spatial_embedding:
        raise HTTPException(status_code=400, detail="the active model has no spatial embedding")
    if "sensory_channels" in request.parameters and item.nodes:
        current_channels = int(item.manifest.parameters.get("sensory_channels") or (8192 if item.receptor_index and max(item.receptor_index) >= 192 else 192))
        requested_channels = int(request.parameters["sensory_channels"])
        if requested_channels != current_channels:
            raise HTTPException(status_code=400, detail="sensory channel count cannot be changed on a populated consciousness; create a new consciousness to use a different sensory body")
    item.configure_model(parameters=request.parameters, spatial_dimensions=request.spatial_dimensions)
    # A sensory-channel-count change belongs to the external adapter rather
    # than the graph. Recreate that adapter before the next carrier arrives so
    # the setting takes effect deterministically.
    if "sensory_channels" in request.parameters:
        _text_adapters.pop(item.consciousness_id, None)
    return {"manifest": item.manifest.to_dict(), "runtime_config": asdict(item.config), "metrics": item.metrics()}


def _observer_view(item: ConsciousnessRuntime | None = None) -> dict[str, Any]:
    item = item or runtime
    if item is None:
        return {
            "current": {
                "tick": 0,
                "text": "—",
                "occurrences": 0,
                "internal_edges": 0,
                "repeatable": False,
            },
            "events": [],
            "temporal": {"current": None, "active_windows": []},
            "config": _readout_settings(),
        }
    # The live dispatcher normally consumes this frame first.  Re-consuming
    # the same tick is a no-op inside StructuralReadoutAdapter, which keeps the
    # synchronous REST view useful in tests and before the service lifespan
    # has started without ever duplicating a persisted observation.
    return _process_output_frame(item, item.latest_output())


def _conversation_items(limit: int | None = None, *, item: ConsciousnessRuntime | None = None) -> list[dict[str, Any]]:
    """Return the observatory's chronological *external* dialogue view.

    This is intentionally a presentation projection.  It combines the
    stimulus log, output-adapter observations, and optional AI interpretation
    records, but never sends any of those messages back into Core.
    """
    item = item or runtime
    if item is None:
        return []
    manual_sources = {"ui", "ui-text", "manual", "cli", "cli-text"}

    def is_background_source(source: str) -> bool:
        return source.startswith((
            "ambient",
            "body",
            "interoceptive",
            "host-load",
        ))

    def readout_provenance(row: dict[str, Any]) -> tuple[bool, list[str]]:
        """Return presentation provenance without changing historical data.

        New output records carry a precise source list from the Runtime.  A
        few already-saved records predate that field; their final preceding
        stimulus is the best available audit trail, so old ambient rows do
        not continue to flood the chat after the presentation setting exists.
        """
        sources = [str(source) for source in row.get("source_provenance", []) if str(source)]
        if not sources:
            preceding = row.get("preceding_stimuli", [])
            if isinstance(preceding, list) and preceding:
                latest = preceding[-1]
                if isinstance(latest, dict) and latest.get("source"):
                    sources = [str(latest["source"])]
        background = (
            bool(row.get("background"))
            or str(row.get("kind", "")) == "background_active_nodes"
            or (bool(sources) and all(is_background_source(source) for source in sources))
        )
        return background, sources

    items: list[dict[str, Any]] = []
    for index, row in enumerate(item.stimuli):
        items.append({
            "kind": "stimulus",
            "role": "user" if row.get("source") in manual_sources else "environment",
            **row,
            "order": index,
            "conversation_key": f"stimulus:{index}:{int(row.get('tick', 0))}",
        })
    for index, row in enumerate(item.package.logs.get("observations", [])):
        if str(row.get("kind", "")) not in {"repeatable_output_structure", "repeatable_structure", "repeatable_anonymous_structure", "passive_readout", "structural_readout", "activated_node_readout", "background_active_nodes", "temporal_convergence_readout"}:
            continue
        anonymous_readout = str(row.get("anonymous_readout") or row.get("readout") or "")
        display_readout = str(row.get("display_readout") or anonymous_readout)
        if not anonymous_readout:
            continue
        background, source_provenance = readout_provenance(row)
        items.append({
            "kind": "readout", "role": "interpreter", "order": index,
            "conversation_key": f"readout:{index}:{int(row.get('tick', 0))}:{str(row.get('id', row.get('signature', '')))}",
            "tick": int(row.get("tick", 0)), "text": display_readout,
            "anonymous_text": anonymous_readout,
            "node_ids": list(row.get("node_ids", [])),
            "label_entries": list(row.get("label_entries", [])),
            "readable_labels": list(row.get("readable_labels", [])),
            "background": background,
            "source_provenance": source_provenance,
            "trigger": "background_active_nodes" if background else "",
            "source": str(row.get("kind", "structural_readout")),
            "readout_kind": str(row.get("readout_kind", "structural")),
            "start_tick": row.get("start_tick"),
            "end_tick": row.get("end_tick"),
            "classification": row.get("classification"),
            "rankings": list(row.get("rankings", [])),
            "convergence": dict(row.get("convergence", {})) if isinstance(row.get("convergence"), dict) else {},
            "window": dict(row.get("window", {})) if isinstance(row.get("window"), dict) else {},
            "occurrences": int(row.get("occurrences", 1)),
            "internal_edges": int(row.get("internal_edges", 0)),
            "repeatable": bool(row.get("repeatable", False)),
        })
    for index, row in enumerate(item.interpretations):
        items.append({"kind": "interpretation", "role": "interpreter", **row, "order": index, "conversation_key": f"interpretation:{index}:{int(row.get('tick', 0))}"})
    order = {"stimulus": 0, "readout": 1, "interpretation": 2}
    ordered = sorted(items, key=lambda row: (int(row.get("tick", 0)), order.get(str(row.get("kind")), 3), int(row.get("order", 0))))
    return ordered if limit is None else ordered[-max(1, int(limit)):]


@app.get("/api/observer")
def observer() -> dict[str, Any]: return _observer_view()


@app.get("/api/conversation")
def conversation(limit: int | None = None) -> dict[str, Any]: return {"items": _conversation_items(limit, item=runtime)}


@app.get("/api/settings")
def settings() -> dict[str, Any]:
    result = json.loads(json.dumps(ui_settings))
    result["observer"] = {**DEFAULT_UI_SETTINGS["observer"], **dict(result.get("observer", {}))}
    result["observer"]["temporal"] = {
        **DEFAULT_TEMPORAL_CONFIG,
        **dict(result["observer"].get("temporal", {}) if isinstance(result["observer"].get("temporal"), dict) else {}),
    }
    result["notifications"] = _notification_public()
    result["network"] = _network_public()
    result.update(_legacy_adapter_projection())
    result["adapters"] = adapter_registry.list(adapter_runtime_state)
    saved_ai = result.get("ai", {})
    result["ai"] = {
        "providers": [{"id": item.id, "name": item.name, "kind": item.kind, "base_url": item.base_url, "model": item.model, "api_key_configured": bool(item.api_key)} for item in providers.values()],
        "environment": {**saved_ai.get("environment", {}), **scheduler.public()},
        "interpreter": {**saved_ai.get("interpreter", {}), **interpreter.public()},
        "auto_snapshot": saved_ai.get("auto_snapshot", {"enabled": False, "frequency_ticks": 0, "on_repeatable_structure": True, "on_interpreter_important": True}),
    }
    return result


async def _network_handshake(socket: WebSocket) -> tuple[NetworkTransportAdapter, str] | None:
    await socket.accept()
    if not _adapter_enabled("network-transport"):
        await socket.send_json({"type": "error", "detail": "network transport is disabled"})
        await socket.close(code=1008)
        return None
    try:
        hello = await asyncio.wait_for(socket.receive_json(), timeout=10)
        transport = NetworkTransportAdapter(_network_token)
        peer_id = transport.authorize_hello(hello)
        await socket.send_json({"protocol": "threemind-network/1", "type": "hello_ack", "peer_id": peer_id})
        return transport, peer_id
    except (asyncio.TimeoutError, NetworkProtocolError, ValueError) as error:
        await socket.send_json({"type": "error", "detail": str(error)})
        await socket.close(code=1008)
        return None


@app.websocket("/api/network/input")
async def network_input(socket: WebSocket) -> None:
    session = await _network_handshake(socket)
    if session is None:
        return
    transport, peer_id = session
    try:
        while True:
            envelope = await socket.receive_json()
            message_type = transport.validate_message(envelope)
            consciousness_id = str(envelope.get("consciousness_id") or manager.active_id or "")
            if not consciousness_id:
                raise NetworkProtocolError("no active consciousness")
            item = manager.get(consciousness_id)
            if message_type == "sensory_frame":
                frame = _remote_sensory_adapter(item).decode(envelope, peer_id=peer_id)
                item.enqueue_frame(frame, adapter_id="network-transport", metadata={"carrier": "network", "peer_id": peer_id, "protocol": "threemind-network/1"})
                await socket.send_json({"protocol": "threemind-network/1", "type": "accepted", "tick": item.tick, "kind": "sensory_frame"})
            else:
                if not ui_settings.get("network", {}).get("allow_remote_modulation", False):
                    raise NetworkProtocolError("remote modulation is disabled")
                _configure_attention_modulators(item)
                modulator = _remote_modulators.get(item.consciousness_id)
                if modulator is None:
                    raise NetworkProtocolError("remote modulation plugin is unavailable")
                modulator.update(envelope, tick=item.tick)
                await socket.send_json({"protocol": "threemind-network/1", "type": "accepted", "tick": item.tick, "kind": "modulation_frame"})
    except (WebSocketDisconnect, RuntimeError, KeyError):
        return
    except (NetworkProtocolError, ValueError) as error:
        await socket.send_json({"protocol": "threemind-network/1", "type": "error", "detail": str(error)})
        await socket.close(code=1008)


@app.websocket("/api/network/output")
async def network_output(socket: WebSocket) -> None:
    session = await _network_handshake(socket)
    if session is None:
        return
    transport, _peer_id = session
    consciousness_id = socket.query_params.get("consciousness_id") or manager.active_id
    if consciousness_id is None:
        await socket.send_json({"protocol": "threemind-network/1", "type": "error", "detail": "no active consciousness"})
        await socket.close(code=1008)
        return
    try:
        item = manager.get(consciousness_id)
    except KeyError:
        await socket.send_json({"protocol": "threemind-network/1", "type": "error", "detail": "unknown consciousness_id"})
        await socket.close(code=1008)
        return
    last_tick = -1
    try:
        while True:
            frame = item.latest_output()
            if frame.tick != last_tick:
                await socket.send_json(transport.output_envelope(frame))
                last_tick = frame.tick
            await asyncio.sleep(max(.02, int(_adapter_config("network-transport").get("output_interval_ms", 150)) / 1000))
    except (WebSocketDisconnect, RuntimeError):
        return


_LIVE_SNAPSHOT_CHUNK_ITEMS = 600


async def _send_live_snapshot(socket: WebSocket, item: ConsciousnessRuntime, *, sequence_start: int = 0) -> int:
    """Send a complete graph projection as acknowledged transport chunks.

    Chunking is a wire-level concern only: no node or edge is omitted.  The
    browser acknowledges each chunk after storing it, which avoids a slow UI
    being flooded by one huge JSON message while Core continues independently.
    Older clients that do not yet acknowledge receive a timeout fallback rather
    than causing the runtime to block.
    """
    graph = _graph_view(item)
    nodes = list(graph.pop("nodes", []))
    edges = list(graph.pop("edges", []))
    chunks: list[dict[str, Any]] = []
    for offset in range(0, len(nodes), _LIVE_SNAPSHOT_CHUNK_ITEMS):
        chunks.append({"part": "nodes", "items": nodes[offset:offset + _LIVE_SNAPSHOT_CHUNK_ITEMS]})
    for offset in range(0, len(edges), _LIVE_SNAPSHOT_CHUNK_ITEMS):
        chunks.append({"part": "edges", "items": edges[offset:offset + _LIVE_SNAPSHOT_CHUNK_ITEMS]})
    if not chunks:
        chunks.append({"part": "nodes", "items": []})
    sequence = sequence_start + 1
    await socket.send_json({
        "type": "snapshot_begin", "sequence": sequence,
        "graph": graph, "chunk_count": len(chunks),
        "observer": _observer_view(item),
        "conversation": _conversation_items(item=item),
    })
    try:
        await asyncio.wait_for(socket.receive_json(), timeout=4.0)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        pass
    for index, chunk in enumerate(chunks):
        sequence += 1
        await socket.send_json({
            "type": "snapshot_chunk", "sequence": sequence,
            "index": index, "chunk_count": len(chunks), **chunk,
        })
        try:
            await asyncio.wait_for(socket.receive_json(), timeout=4.0)
        except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
            # Compatibility fallback: a client that predates acknowledgements
            # must not freeze an otherwise independent Core runtime.
            pass
    sequence += 1
    await socket.send_json({"type": "snapshot_end", "sequence": sequence, "tick": item.tick})
    return sequence


async def _live_stream(socket: WebSocket, item: ConsciousnessRuntime, *, follow_active: bool) -> None:
    """Publish one runtime's graph through the acknowledged live protocol.

    ``follow_active`` preserves the legacy observatory behavior.  A named
    instance stream, used by the experiment workbench, remains attached to its
    sandbox even when the user switches the main observatory to another
    consciousness.  The transport is deliberately separate from Core: slow
    clients may lose visual deltas and request a resync, but never block a
    runtime tick or alter its topology.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
    # A live delta normally contains only nodes that changed.  Retain the
    # previous touch set for one extra frame so the browser also receives the
    # zeroed direct/associative values after a touch expires.
    last_touch_nodes: set[int] = set()
    seen_conversation_keys: set[str] = set()
    last_history_revision: list[int] = [-1]

    def publish(frame: Any) -> None:
        delta = frame.delta
        current_touch_nodes = (
            set(delta.get("created_nodes", []))
            | set(delta.get("direct_nodes", []))
            | set(delta.get("associated_nodes", []))
        )
        node_ids = current_touch_nodes | last_touch_nodes
        edge_keys = set(tuple(value) for value in delta.get("created_edges", [])) | set(tuple(value) for value in delta.get("strengthened_edges", [])) | set(tuple(value) for value in delta.get("weakened_edges", []))

        def node_view(node_id: int) -> dict[str, Any]:
            node = dict(item.nodes[node_id])
            # The graph endpoint already exposes these UI-facing aliases;
            # publish the same shape over WebSocket rather than leaking the
            # internal *_touch field names.
            node["direct"] = float(node.get("direct_touch", 0.0))
            node["associative"] = float(node.get("associative_touch", 0.0))
            node["feature"] = item.node_label(node_id) or ""
            node["source"] = "anonymous"
            return node

        payload = {
            "type": "delta", "metrics": frame.metrics, "delta": delta,
            "nodes": [node_view(node_id) for node_id in node_ids if node_id in item.nodes],
            "edges": [{**dict(item.edges[key]), "touched": key in set(tuple(value) for value in delta.get("strengthened_edges", []))} for key in edge_keys if key in item.edges],
        }
        # Conversation is an event stream, unlike graph state.  Include it
        # only when a bounded chronological projection changed; this keeps the
        # canvas delta stream compact while making sent stimuli and later
        # passive-readout events appear immediately in the sidebar.
        history_revision = int(frame.metrics.get("history_revision", -1))
        if history_revision != last_history_revision[0]:
            conversation_items = _conversation_items(item=item)
            additions = [row for row in conversation_items if str(row.get("conversation_key", "")) not in seen_conversation_keys]
            if additions:
                payload["conversation_append"] = additions
                seen_conversation_keys.update(str(row.get("conversation_key", "")) for row in additions)
            last_history_revision[0] = history_revision
        last_touch_nodes.clear()
        last_touch_nodes.update(current_touch_nodes)
        def put_latest() -> None:
            if queue.full():
                try: queue.get_nowait()
                except asyncio.QueueEmpty: pass
                # A dropped visual delta must never make the browser retain a
                # partial topology.  Ask it to fetch a complete chunked
                # projection instead of pretending the missing delta arrived.
                queue.put_nowait({"type": "resync_required"})
                return
            queue.put_nowait(payload)
        loop.call_soon_threadsafe(put_latest)

    token = item.output_bus.subscribe(publish)
    try:
        sequence = 0
        initial_conversation = _conversation_items(item=item)
        seen_conversation_keys.update(str(row.get("conversation_key", "")) for row in initial_conversation)
        last_history_revision[0] = int(item.metrics().get("history_revision", -1))
        sequence = await _send_live_snapshot(socket, item, sequence_start=sequence)
        while True:
            # The main observatory follows whichever instance the user has
            # selected.  Named experiment streams intentionally do not: an
            # isolated sandbox needs a stable observation target.
            if follow_active:
                try:
                    active = manager.active()
                except KeyError:
                    item.output_bus.unsubscribe(token)
                    await socket.send_json({"type": "empty", "has_active": False})
                    # Deleting the final live instance returns the *host* to
                    # its empty state; it does not represent a transport
                    # failure. Keep this observatory connection alive so a
                    # later create/open operation can attach without showing a
                    # false "Core disconnected" error in the UI.
                    while True:
                        await asyncio.sleep(.5)
                        try:
                            active = manager.active()
                            break
                        except KeyError:
                            await socket.send_json({"type": "empty", "has_active": False})
                    item = active
                    last_touch_nodes.clear()
                    seen_conversation_keys.clear()
                    last_history_revision[0] = -1
                    token = item.output_bus.subscribe(publish)
                    initial_conversation = _conversation_items(item=item)
                    seen_conversation_keys.update(str(row.get("conversation_key", "")) for row in initial_conversation)
                    last_history_revision[0] = int(item.metrics().get("history_revision", -1))
                    sequence = await _send_live_snapshot(socket, item, sequence_start=sequence)
                    continue
                if active is not item:
                    item.output_bus.unsubscribe(token)
                    item = active
                    last_touch_nodes.clear()
                    seen_conversation_keys.clear()
                    last_history_revision[0] = -1
                    token = item.output_bus.subscribe(publish)
                    initial_conversation = _conversation_items(item=item)
                    seen_conversation_keys.update(str(row.get("conversation_key", "")) for row in initial_conversation)
                    last_history_revision[0] = int(item.metrics().get("history_revision", -1))
                    sequence = await _send_live_snapshot(socket, item, sequence_start=sequence)
                    continue
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=.20)
            except asyncio.TimeoutError:
                continue
            if payload.get("type") == "resync_required":
                sequence = await _send_live_snapshot(socket, item, sequence_start=sequence)
                continue
            sequence += 1
            payload["sequence"] = sequence
            await socket.send_json(payload)
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        item.output_bus.unsubscribe(token)


@app.websocket("/api/ws/live")
async def live_stream(socket: WebSocket) -> None:
    await socket.accept()
    # Keep one transport alive while the startup screen has no consciousness.
    # Once the user creates or opens one, the same connection starts streaming
    # its exact OutputBus projection.
    while manager.active_id is None:
        try:
            await socket.send_json({"type": "empty", "has_active": False})
            await asyncio.sleep(.5)
        except (WebSocketDisconnect, RuntimeError):
            return
    try:
        item = manager.active()
    except KeyError:
        return
    await _live_stream(socket, item, follow_active=True)


@app.websocket("/api/ws/consciousnesses/{consciousness_id}")
async def consciousness_live_stream(socket: WebSocket, consciousness_id: str) -> None:
    """Live projection for one explicit runtime, including an experiment sandbox."""
    await socket.accept()
    try:
        item = manager.get(consciousness_id)
    except KeyError:
        await socket.send_json({"type": "error", "detail": "consciousness not found"})
        await socket.close(code=1008)
        return
    await _live_stream(socket, item, follow_active=False)


@app.get("/api/packages")
def packages() -> dict[str, Any]:
    return {"items": archive_repository.list_packages(), "archive_index": {**archive_repository.status(), **archive_indexer.status(), "writer": archive_writer.status()}}


@app.get("/api/snapshots")
def snapshot_catalog() -> dict[str, Any]:
    return {"items": _archive_catalog_items()}


@app.get("/api/logs/{kind}/{consciousness_id}")
def instance_logs(kind: str, consciousness_id: str, limit: int = 5000) -> dict[str, Any]:
    try:
        document, origin = _history_document(consciousness_id)
        rows = _history_rows(document, kind)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    requested = max(0, int(limit))
    # ``0`` explicitly asks for the complete audit history.  Otherwise this
    # legacy convenience route returns the requested tail without a hidden
    # server-side ceiling; paged ``/history`` remains better for very large UI
    # tables.
    items = rows if requested == 0 else rows[-requested:]
    return {"items": items, "origin": origin, "checkpoint": {
        "tick": document.get("tick", 0),
        "history_revision": document.get("history_revision", 0),
    }}


@app.get("/api/archive")
def download_archive(path: str):
    target = Path(path).resolve()
    if target.parent != DATA_DIR.resolve() or not is_model_package_path(target) or not target.exists(): raise HTTPException(status_code=404, detail="archive not found")
    return FileResponse(target, filename=target.name, media_type="application/zip")


@app.get("/api/packages/{package_name}")
def package_details(package_name: str) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    if path.parent != DATA_DIR.resolve() or not is_model_package_path(path) or not path.exists():
        raise HTTPException(status_code=404, detail="package not found")
    try:
        package = ModelPackage.load(path)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"path": str(path), "payload": package.to_payload()}


@app.get("/api/packages/{package_name}/signature")
def package_signature(package_name: str) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    if path.parent != DATA_DIR.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="package not found")
    return {"algorithm": "sha256", "digest": hashlib.sha256(path.read_bytes()).hexdigest()}


@app.post("/api/packages/{package_name}/restore")
def restore_package_snapshot(package_name: str, index: int = 0, portrait: bool = False) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    if path.parent != DATA_DIR.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="package not found")
    try:
        package = ModelPackage.load(path)
        records = package.portraits if portrait else package.snapshots
        record = records[index]
        state = record.get("state")
        if not isinstance(state, dict): raise ValueError("snapshot does not contain a restorable state")
        package.state = state
        # The package may contain a deliberately partial adapter declaration.
        # Resolve the new schema before writing the restored artifact.
        package = _resolve_package_adapters(package)
        package.save(path)
        _record_artifact(path, package)
        if package.consciousness_id in manager.instances:
            running = manager.instances[package.consciousness_id]
            was_running = running.running()
            was_active = manager.active_id == package.consciousness_id
            replacement = _new_runtime(package)
            _resolve_model_adapters(replacement)
            replacement.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
            _configure_attention_modulators(replacement)
            manager.replace(
                replacement,
                activate=was_active,
                reason="replaced by restored package snapshot",
            )
            _release_media_runtime(running)
            _schedule_history_checkpoint(running)
            _ensure_output_observer(replacement)
            if was_running:
                replacement.start()
            if was_active:
                global runtime
                runtime = replacement
                scheduler.runtime = replacement
                interpreter.runtime = replacement
    except (IndexError, OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"restored": True, "index": index, "portrait": portrait}


@app.get("/api/packages/{package_name}/compare")
def compare_package_snapshots(package_name: str, left: int = 0, right: int = 1, portrait: bool = False) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    try:
        package = ModelPackage.load(path); records = package.portraits if portrait else package.snapshots
        a, b = records[left], records[right]
        am, bm = a.get("metrics", {}), b.get("metrics", {})
        return {"left": a, "right": b, "delta": {key: bm.get(key, 0) - am.get(key, 0) for key in set(am) | set(bm) if isinstance(am.get(key, bm.get(key, 0)), (int, float))}}
    except (IndexError, OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/packages/{package_name}")
def delete_package(package_name: str) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    if path.parent != DATA_DIR.resolve() or not is_model_package_path(path) or not path.exists():
        raise HTTPException(status_code=404, detail="package not found")
    path.unlink()
    archive_repository.remove_path(path)
    return {"deleted": package_name}


@app.post("/api/packages/batch-delete")
def batch_delete_packages(request: PackageBatchRequest) -> dict[str, Any]:
    deleted = []
    for package_name in request.names:
        path = (DATA_DIR / Path(package_name).name).resolve()
        if path.parent == DATA_DIR.resolve() and is_model_package_path(path) and path.exists():
            path.unlink()
            archive_repository.remove_path(path)
            deleted.append(path.name)
    return {"deleted": deleted}


@app.patch("/api/packages/{package_name}")
def rename_package(package_name: str, request: PackageRenameRequest) -> dict[str, Any]:
    path = (DATA_DIR / package_name).resolve()
    if path.parent != DATA_DIR.resolve() or not is_model_package_path(path) or not path.exists():
        raise HTTPException(status_code=404, detail="package not found")
    try:
        package = ModelPackage.load(path)
        package.consciousness_name = request.name.strip()
        package = _resolve_package_adapters(package)
        package.save(path)
        _record_artifact(path, package)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"name": package.consciousness_name, "path": str(path)}


@app.post("/api/packages/import")
async def import_package(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or f"import{MODEL_PACKAGE_SUFFIX}").name
    source_suffix = Path(filename).suffix.casefold()
    if source_suffix not in READABLE_MODEL_PACKAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"only {MODEL_PACKAGE_SUFFIX} model packages are accepted")
    # A legacy package is normalized to the ThreeMind extension on import.
    target = DATA_DIR / f"{Path(filename).stem}{MODEL_PACKAGE_SUFFIX}"
    if target.exists():
        target = DATA_DIR / f"{target.stem}-import-{uuid.uuid4().hex[:8]}{MODEL_PACKAGE_SUFFIX}"
    content = await file.read()
    temporary = target.with_suffix(".upload.tmp")
    temporary.write_bytes(content)
    try:
        package = ModelPackage.load(temporary)
        package = _resolve_package_adapters(package)
        # Re-emit the accepted package rather than moving opaque uploaded
        # bytes. This validates and persists the resolved adapter declaration.
        package.save(target)
        temporary.unlink(missing_ok=True)
        _record_artifact(target, package)
    except (OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"path": str(target), "name": package.consciousness_name, "consciousness_id": package.consciousness_id}


@app.get("/api/ai/providers")
def ai_providers() -> dict[str, Any]:
    return {"items": [{"id": item.id, "name": item.name, "kind": item.kind, "base_url": item.base_url, "model": item.model, "api_key_configured": bool(item.api_key)} for item in providers.values()]}


@app.get("/api/ai/environment/settings")
def environment_settings() -> dict[str, Any]:
    return scheduler.public()


class EnvironmentSettingsRequest(BaseModel):
    enabled: bool = False
    provider_id: str = ""
    frequency_ticks: int = Field(default=120, ge=10, le=1_000_000)
    random_frequency: bool = True
    intensity: float = Field(default=0.7, ge=0.0, le=2.0)
    irregularity: float = Field(default=0.65, ge=0.0, le=1.0)


@app.post("/api/ai/environment/settings")
def save_environment_settings(request: EnvironmentSettingsRequest) -> dict[str, Any]:
    if request.enabled and request.provider_id not in providers:
        raise HTTPException(status_code=400, detail="AI provider not found")
    values = request.model_dump()
    ui_settings.setdefault("ai", {}).setdefault("environment", {}).update(values)
    _write_ui_settings()
    return scheduler.configure(values)


@app.get("/api/ai/interpreter/settings")
def interpreter_settings() -> dict[str, Any]:
    return interpreter.public()


class InterpreterSettingsRequest(BaseModel):
    enabled: bool = False
    provider_id: str = ""
    frequency_ticks: int = Field(default=300, ge=20, le=1_000_000)
    language: str = "auto"
    periodic_enabled: bool = True
    on_repeatable_structure: bool = False
    active_nodes_enabled: bool = True
    on_manual_stimulus: bool = False
    listen_background_active_nodes: bool = False
    deduplicate_readouts: bool = False
    activation_min: float = Field(default=.08, ge=0.0, le=1.0)
    activation_max: float = Field(default=1.0, ge=0.0, le=1.0)


@app.post("/api/ai/interpreter/settings")
def save_interpreter_settings(request: InterpreterSettingsRequest) -> dict[str, Any]:
    if request.enabled and request.provider_id not in providers:
        raise HTTPException(status_code=400, detail="AI provider not found")
    interpreter.runtime = runtime
    values = request.model_dump()
    ui_settings.setdefault("ai", {}).setdefault("interpreter", {}).update(values)
    _write_ui_settings()
    return interpreter.configure(values)


class InterpreterRunRequest(BaseModel):
    provider_id: str
    language: str = "auto"


@app.post("/api/ai/interpreter/run")
def run_interpreter(request: InterpreterRunRequest) -> dict[str, Any]:
    item = _require_active_runtime()
    provider = providers.get(request.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI provider not found")
    try:
        snapshot = item.observation_snapshot()
        text = ai_client.complete(provider, system="You are an external observer of a ThreeMind consciousness experiment. Interpret the supplied snapshot cautiously. Do not claim sentience or certainty. Respond in the requested language.", user=json.dumps({"language": request.language, "snapshot": snapshot}, ensure_ascii=False), temperature=0.25, max_tokens=260)
        important = any(token in text.lower() for token in ("important", "significant", "重要", "关键", "异常"))
        event = item.record_interpretation(text, provider_id=provider.id, trigger="manual", important=important)
    except (RuntimeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"item": event}


class ProviderRequest(BaseModel):
    id: str
    name: str = "AI provider"
    base_url: str
    model: str = ""
    api_key: str
    kind: str = "openai-compatible"


class ProviderTestRequest(BaseModel):
    """A non-persisting provider draft used by the settings form.

    Testing a card must not require saving the entire settings form first.  In
    particular, a newly added card has no runtime-registry entry yet.  A saved
    provider may deliberately leave its key field blank in the browser; in
    that case ``use_stored_key`` permits the Core to use the already protected
    local secret while still testing the other draft fields from the form.
    """

    id: str = ""
    name: str = "AI provider"
    base_url: str
    model: str = ""
    api_key: str = ""
    kind: str = "openai-compatible"
    use_stored_key: bool = False


@app.post("/api/ai/providers")
def save_provider(request: ProviderRequest) -> dict[str, Any]:
    providers[request.id] = Provider(**request.model_dump())
    provider_store.save([asdict(item) for item in providers.values()])
    return {"id": request.id, "saved": True}


def _run_provider_test(provider: Provider) -> dict[str, Any]:
    try:
        text = ai_client.complete(
            provider,
            system="Reply with exactly: ThreeMind provider test OK",
            user="test",
            temperature=0.0,
            max_tokens=20,
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"ok": True, "text": text}


@app.post("/api/ai/providers/test")
def test_provider_draft(request: ProviderTestRequest) -> dict[str, Any]:
    """Test the configuration currently visible in the Settings form.

    This endpoint intentionally does not write the provider registry or the
    secret store.  It only reads an existing protected key when the caller
    explicitly requests that behaviour for an already saved provider.
    """

    api_key = request.api_key.strip()
    if not api_key and request.use_stored_key:
        stored = providers.get(request.id)
        if stored is not None:
            api_key = stored.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="AI provider requires an API key")
    provider = Provider(
        id=request.id.strip() or "provider-draft",
        name=request.name.strip() or "AI provider",
        base_url=request.base_url.strip(),
        model=request.model.strip(),
        api_key=api_key,
        kind=request.kind,
    )
    return _run_provider_test(provider)


@app.post("/api/ai/providers/{provider_id}/test")
def test_provider(provider_id: str) -> dict[str, Any]:
    provider = providers.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI provider not found")
    return _run_provider_test(provider)


@app.delete("/api/ai/providers/{provider_id}")
def delete_provider(provider_id: str) -> dict[str, Any]:
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail="AI provider not found")
    providers.pop(provider_id)
    provider_store.save([asdict(item) for item in providers.values()])
    return {"deleted": provider_id}


class EnvironmentRequest(BaseModel):
    provider_id: str
    intensity: float = Field(default=0.7, ge=0.0, le=2.0)
    irregularity: float = Field(default=0.65, ge=0.0, le=1.0)


@app.post("/api/ai/environment")
def generate_environment(request: EnvironmentRequest) -> dict[str, Any]:
    provider = providers.get(request.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI provider not found")
    item = _require_active_runtime()
    try:
        text = ai_client.complete(provider, system=ENVIRONMENT_SYSTEM, user=environment_prompt(irregularity=request.irregularity, intensity=request.intensity))
        queued = _submit_text(item, text, source="ai-environment", intensity=request.intensity, queued=True)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"text": text, "queued": queued}


@app.get("/api/experiments/commands")
def experiment_commands() -> dict[str, Any]:
    """The complete, finite command vocabulary available to manual and AI runs."""
    return {
        "protocol": "threemind-experiment/1",
        "commands": experiment_controller.command_specs(),
        "templates": [{"id": key, **dict(value)} for key, value in TEMPLATE_DEFINITIONS.items()],
        "bridge": {
            "enabled": _adapter_enabled("ai-debug-duplex"),
            "limits": _experiment_run_limits(None),
            "auto_run_default": bool(_adapter_config("ai-debug-duplex").get("auto_run_default", False)),
        },
    }


@app.get("/api/experiments")
def experiments(query: str = "", limit: int = 100) -> dict[str, Any]:
    return {"items": experiment_controller.list_runs(query=query, limit=limit)}


def _experiment_create_kwargs(request: ExperimentCreateRequest) -> dict[str, Any]:
    if not _adapter_enabled("ai-debug-duplex"):
        raise ExperimentError("AI experiment/debug bridge adapter is disabled")
    mode = request.mode or ("auto" if bool(_adapter_config("ai-debug-duplex").get("auto_run_default", False)) else "manual")
    target_id = request.target_id or manager.active_id
    if not target_id:
        raise ExperimentError("an experiment requires a target consciousness")
    return {
        "target_id": target_id,
        "title": request.title,
        "mode": mode,
        "provider_id": request.provider_id,
        "goal": request.goal,
        "template_id": request.template_id,
        "sandbox": request.sandbox,
        "background_mode": request.background_mode,
        "limits": _experiment_run_limits(request.limits),
    }


def _experiment_event_stream(events: Any) -> StreamingResponse:
    """Expose host-side experiment lifecycle events over a one-way SSE stream."""

    def emit() -> Any:
        for item in events:
            payload = dict(item) if isinstance(item, dict) else {"detail": str(item)}
            event_type = str(payload.get("type") or "message")
            yield f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        emit(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/experiments")
def create_experiment(request: ExperimentCreateRequest) -> dict[str, Any]:
    try:
        return experiment_controller.create_run(**_experiment_create_kwargs(request))
    except (ExperimentError, KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/stream")
def create_experiment_stream(request: ExperimentCreateRequest) -> StreamingResponse:
    try:
        return _experiment_event_stream(experiment_controller.create_run_events(**_experiment_create_kwargs(request)))
    except (ExperimentError, KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/experiments/{run_id}")
def experiment_detail(run_id: str) -> dict[str, Any]:
    try:
        return experiment_controller.get_run(run_id)
    except ExperimentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/plan")
def save_experiment_plan(run_id: str, request: ExperimentPlanRequest) -> dict[str, Any]:
    try:
        return experiment_controller.set_plan(run_id, request.steps, origin=request.origin)
    except ExperimentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/template-plan")
def create_template_experiment_plan(run_id: str, carrier_a: str = "A", carrier_b: str = "B", intensity: float = 1.0) -> dict[str, Any]:
    try:
        run = experiment_controller.get_run(run_id)
        plan = experiment_controller.template_plan(str(run.get("template_id") or "free-form"), carrier_a=carrier_a, carrier_b=carrier_b, intensity=float(intensity))
        return experiment_controller.set_plan(run_id, plan, origin="template")
    except ExperimentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/ai-plan")
def create_ai_experiment_plan(run_id: str, request: ExperimentAiPlanRequest) -> dict[str, Any]:
    try:
        return experiment_controller.plan_with_ai(run_id, provider_id=request.provider_id, goal=request.goal, language=request.language)
    except ExperimentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/ai-plan/stream")
def stream_ai_experiment_plan(run_id: str, request: ExperimentAiPlanRequest) -> StreamingResponse:
    return _experiment_event_stream(
        experiment_controller.plan_with_ai_events(
            run_id,
            provider_id=request.provider_id,
            goal=request.goal,
            language=request.language,
        )
    )


@app.post("/api/experiments/{run_id}/steps/{step_id}/execute")
def execute_experiment_step(run_id: str, step_id: str) -> dict[str, Any]:
    try:
        return experiment_controller.execute_step(run_id, step_id)
    except (ExperimentError, KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/run")
def run_experiment_plan(run_id: str, request: ExperimentRunRequest) -> dict[str, Any]:
    try:
        return experiment_controller.run_plan_async(run_id, approved=request.approved)
    except ExperimentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/cancel")
def cancel_experiment(run_id: str) -> dict[str, Any]:
    try:
        return experiment_controller.cancel(run_id)
    except ExperimentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/analyze")
def analyze_experiment(run_id: str, request: ExperimentAnalyzeRequest) -> dict[str, Any]:
    try:
        return experiment_controller.analyze(run_id, provider_id=request.provider_id, language=request.language, prompt=request.prompt)
    except (ExperimentError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/report")
def export_experiment_report(run_id: str, request: ExperimentReportRequest) -> dict[str, Any]:
    try:
        return experiment_controller.export_report(run_id, language=request.language)
    except ExperimentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _analytics_service(consciousness_id: str) -> AnalyticsService:
    try:
        document, origin = _history_document(consciousness_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        graph_view = _graph_view(manager.get(consciousness_id))
    except KeyError:
        graph_view = None
    return AnalyticsService(document, graph_view, origin=origin)


@app.get("/api/analytics/consciousnesses/{consciousness_id}/overview")
def analytics_overview(consciousness_id: str) -> dict[str, Any]:
    return _analytics_service(consciousness_id).overview()


@app.get("/api/analytics/consciousnesses/{consciousness_id}/dynamics")
def analytics_dynamics(
    consciousness_id: str,
    from_tick: int | None = None,
    to_tick: int | None = None,
    max_points: int = 1500,
    node_ids: str = "",
) -> dict[str, Any]:
    try:
        selected_node_ids = [int(value.strip()) for value in node_ids.split(",") if value.strip()]
    except ValueError as error:
        raise HTTPException(status_code=400, detail="node_ids must be a comma-separated list of integers") from error
    return _analytics_service(consciousness_id).dynamics(
        from_tick=from_tick,
        to_tick=to_tick,
        max_points=max_points,
        node_ids=selected_node_ids,
    )


@app.get("/api/analytics/consciousnesses/{consciousness_id}/structures")
def analytics_structures(
    consciousness_id: str,
    page: int = 1,
    page_size: int = 50,
    query: str = "",
) -> dict[str, Any]:
    rows = _analytics_service(consciousness_id).structure_catalog()
    return _page(rows, page=page, page_size=page_size, query=query)


@app.get("/api/analytics/consciousnesses/{consciousness_id}/structures/{structure_id}")
def analytics_structure_detail(consciousness_id: str, structure_id: str) -> dict[str, Any]:
    try:
        return _analytics_service(consciousness_id).structure_detail(structure_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/analytics/consciousnesses/{consciousness_id}/convergence")
def analytics_convergence(consciousness_id: str) -> dict[str, Any]:
    return _analytics_service(consciousness_id).temporal_summary()


@app.get("/api/analytics/consciousnesses/{consciousness_id}/export")
def analytics_export(consciousness_id: str) -> FileResponse:
    service = _analytics_service(consciousness_id)
    destination = DATA_DIR / "exports" / f"{consciousness_id}-{int(time.time())}-evidence.zip"
    EvidenceExporter(service).write(destination)
    return FileResponse(
        destination,
        media_type="application/zip",
        filename=destination.name,
    )


def _paired_clone(
    source: ConsciousnessRuntime,
    source_state: dict[str, Any],
    *,
    name: str,
    background_mode: str,
) -> ConsciousnessRuntime:
    package = copy.deepcopy(source.package)
    package.state = copy.deepcopy(source_state)
    package = package.clone(name=name)
    package.state["parent_id"] = source.consciousness_id
    package.state["life_state"] = "active"
    package.state["death_reason"] = None
    item = _new_runtime(package)
    _resolve_model_adapters(item)
    item.set_filter_bypass_sources(source.filter_bypass_sources)
    item.set_source("manual", True)
    if background_mode == "paused":
        item.set_source("ambient", False)
    _prepare_experiment_runtime(item)
    manager.add(item, activate=False)
    # Both members remain paused until an explicit paired resume.  This keeps
    # their baseline identical while the researcher reviews the intervention.
    item.start(paused=True)
    _schedule_history_checkpoint(item)
    return item


@app.get("/api/interventions/pairs")
def intervention_pairs() -> dict[str, Any]:
    return {"items": intervention_store.list()}


@app.get("/api/interventions/pairs/{pair_id}")
def intervention_pair_detail(pair_id: str) -> dict[str, Any]:
    record = intervention_store.get(pair_id)
    if record is None:
        raise HTTPException(status_code=404, detail="intervention pair not found")
    for key in ("control_runtime_id", "intervention_runtime_id"):
        runtime_id = str(record.get(key) or "")
        try:
            record[f"{key}_metrics"] = manager.get(runtime_id).metrics()
        except KeyError:
            record[f"{key}_metrics"] = None
    return record


@app.post("/api/interventions/pairs")
def create_intervention_pair(request: InterventionPairRequest) -> dict[str, Any]:
    target_id = request.target_id or manager.active_id
    if not target_id:
        raise HTTPException(status_code=409, detail="an intervention requires a source consciousness")
    try:
        source = manager.get(target_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    edge_pairs: set[tuple[int, int]] = set()
    for raw in request.edge_pairs:
        if len(raw) != 2:
            raise HTTPException(status_code=400, detail="every edge pair must contain source and target")
        edge_pairs.add((int(raw[0]), int(raw[1])))
    node_ids = {int(value) for value in request.node_ids}
    if not node_ids and not edge_pairs:
        raise HTTPException(status_code=400, detail="select at least one node or edge")
    source_state = source.state_dict()
    baseline_hash = hashlib.sha256(
        json.dumps(source_state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    pair_id = str(uuid.uuid4())
    control = _paired_clone(
        source,
        source_state,
        name=f"{source.consciousness_name} · control",
        background_mode=request.background_mode,
    )
    intervention = _paired_clone(
        source,
        source_state,
        name=f"{source.consciousness_name} · intervention",
        background_mode=request.background_mode,
    )
    policy = InterventionPolicy(
        intervention_id=pair_id,
        mode=request.mode,
        node_ids=frozenset(node_ids),
        edge_pairs=frozenset(edge_pairs),
        label=request.title,
    )
    intervention_event = None
    if request.mode == "silence":
        intervention.set_intervention_policy(policy)
    else:
        intervention_event = intervention.apply_structural_lesion(
            node_ids=node_ids,
            edge_pairs=edge_pairs,
            intervention_id=pair_id,
            label=request.title,
        )
    created_at = time.time()
    record = {
        "id": pair_id,
        "title": request.title,
        "status": "paused",
        "mode": request.mode,
        "created_at": created_at,
        "source_consciousness_id": source.consciousness_id,
        "source_tick": int(source_state.get("tick", source.tick)),
        "baseline_state_sha256": baseline_hash,
        "background_mode": request.background_mode,
        "control_runtime_id": control.consciousness_id,
        "intervention_runtime_id": intervention.consciousness_id,
        "intervention": policy.describe(),
        "intervention_event": intervention_event,
        "audit_note": "Both runtimes were cloned from the same captured state and paused before protocol execution.",
    }
    _schedule_history_checkpoint(intervention)
    return intervention_store.save(record)


@app.post("/api/interventions/pairs/{pair_id}/control")
def control_intervention_pair(pair_id: str, request: InterventionControlRequest) -> dict[str, Any]:
    record = intervention_store.get(pair_id)
    if record is None:
        raise HTTPException(status_code=404, detail="intervention pair not found")
    try:
        control = manager.get(str(record["control_runtime_id"]))
        intervention = manager.get(str(record["intervention_runtime_id"]))
    except KeyError as error:
        raise HTTPException(status_code=409, detail="one or both paired runtimes are no longer loaded") from error
    if request.action == "pause":
        control.pause(); intervention.pause(); record["status"] = "paused"
    elif request.action == "resume":
        control.resume(); intervention.resume(); record["status"] = "running"
    elif request.action == "step":
        # Deterministic paired advancement is preferable to comparing two
        # independently scheduled wall-clock threads. Both are paused before
        # exactly the same number of local transitions are executed.
        control.pause(); intervention.pause()
        control.step(ticks=request.ticks); intervention.step(ticks=request.ticks)
        record["status"] = "paused"
    else:
        intervention.set_intervention_policy(None); record["status"] = "intervention_cleared"
    record.setdefault("control_events", []).append({"at": time.time(), "action": request.action, "ticks": request.ticks if request.action == "step" else None})
    return intervention_store.save(record)


@app.post("/api/interventions/pairs/{pair_id}/stimulus")
def stimulate_intervention_pair(pair_id: str, request: InterventionStimulusRequest) -> dict[str, Any]:
    record = intervention_store.get(pair_id)
    if record is None:
        raise HTTPException(status_code=404, detail="intervention pair not found")
    try:
        control = manager.get(str(record["control_runtime_id"]))
        intervention = manager.get(str(record["intervention_runtime_id"]))
        control_result = _submit_text(control, request.text, intensity=request.intensity, source="ai-debug", queued=True)
        intervention_result = _submit_text(intervention, request.text, intensity=request.intensity, source="ai-debug", queued=True)
    except (KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    audit = {
        "at": time.time(),
        "text_sha256": hashlib.sha256(request.text.encode("utf-8")).hexdigest(),
        "text": request.text,
        "intensity": request.intensity,
        "control_envelope": control_result,
        "intervention_envelope": intervention_result,
    }
    record.setdefault("paired_stimuli", []).append(audit)
    intervention_store.save(record)
    return audit


@app.get("/api/graph")
def graph(limit: int | None = None) -> dict[str, Any]:
    return _graph_view(_require_active_runtime(), limit)


def _page(items: list[dict[str, Any]], *, page: int, page_size: int, query: str = "", source: str = "", field: str = "source") -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    filtered = items
    if query:
        needle = query.casefold()
        filtered = [item for item in filtered if needle in json.dumps(item, ensure_ascii=False).casefold()]
    if source:
        filtered = [item for item in filtered if item.get(field) == source]
    total = len(filtered)
    start = (page - 1) * page_size
    return {"items": filtered[start:start + page_size], "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@app.get("/api/events")
def events(limit: int = 200, page: int = 1, page_size: int | None = None, query: str = "", source: str = "") -> dict[str, Any]:
    item = _require_active_runtime()
    return _page(item.events, page=page, page_size=page_size or limit, query=query, source=source)


@app.get("/api/stimuli")
def stimuli(limit: int = 200, page: int = 1, page_size: int | None = None, query: str = "", source: str = "") -> dict[str, Any]:
    item = _require_active_runtime()
    return _page(item.stimuli, page=page, page_size=page_size or limit, query=query, source=source)


@app.get("/api/interpretations")
def interpretations(limit: int = 200, page: int = 1, page_size: int | None = None, query: str = "", trigger: str = "") -> dict[str, Any]:
    item = _require_active_runtime()
    return _page(item.interpretations, page=page, page_size=page_size or limit, query=query, source=trigger, field="trigger")


@app.get("/api/sources")
def sources() -> dict[str, bool]:
    return _require_active_runtime().source_status()


@app.post("/api/sources/{source}")
def set_source(source: str, enabled: bool, confirm_last: bool = False) -> dict[str, bool]:
    item = _require_active_runtime()
    try:
        if not enabled and not confirm_last and sum(bool(value) for value in item.sources.values()) <= 1:
            raise ValueError("disabling the last stimulus source requires confirmation")
        previous = item.source_status().get(source)
        result = item.set_source(source, enabled, confirm_last=confirm_last)
        if source == "ambient" and previous != bool(enabled):
            _reset_telemetry_baselines(item)
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/stimulate")
def stimulate(request: StimulusRequest) -> dict[str, Any]:
    item = _require_active_runtime()
    try:
        event = _submit_text(item, request.text, intensity=request.intensity, source=request.source, queued=False)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"event": event, "metrics": item.metrics(), "conversation_append": _conversation_items(item=item)[-1:]}


@app.post("/api/stimuli/queue")
def queue_stimulus(request: StimulusRequest) -> dict[str, Any]:
    item = _require_active_runtime()
    try:
        envelope = _submit_text(item, request.text, intensity=request.intensity, source=request.source, queued=True)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"queued": envelope, "queue_size": item.queue_size()}


@app.post("/api/step")
def step(request: StepRequest) -> dict[str, Any]:
    return {"metrics": _require_active_runtime().step(ticks=request.ticks)}


@app.post("/api/runtime/start")
def start_runtime() -> dict[str, Any]:
    item = _require_active_runtime()
    _ensure_output_observer(item)
    item.start()
    return {"running": item.running(), "metrics": item.metrics()}


@app.post("/api/runtime/pause")
def pause_runtime() -> dict[str, Any]:
    item = _require_active_runtime()
    item.pause()
    return {"running": item.running(), "paused": True, "metrics": item.metrics()}


@app.post("/api/runtime/resume")
def resume_runtime() -> dict[str, Any]:
    item = _require_active_runtime()
    try:
        item.resume()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"running": item.running(), "paused": False, "metrics": item.metrics()}


@app.post("/api/new")
def new_consciousness(request: NewRequest) -> dict[str, Any]:
    global runtime
    manifest = ModelManifest.from_dict(request.manifest or {})
    previous = runtime
    replacement = _new_runtime(ModelPackage.empty(manifest, name=request.name))
    _resolve_model_adapters(replacement)
    replacement.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(replacement)
    manager.replace_active(replacement, reason="replaced by new consciousness")
    if previous is not None:
        _release_media_runtime(previous)
        _schedule_history_checkpoint(previous)
    runtime = replacement
    _ensure_output_observer(runtime)
    scheduler.runtime = runtime
    interpreter.runtime = runtime
    runtime.start()
    _schedule_history_checkpoint(runtime)
    return {"metrics": runtime.metrics(), "manifest": manifest.to_dict(), "graph": _graph_view(runtime)}


@app.post("/api/package/load")
def load_package(path: str) -> dict[str, Any]:
    global runtime
    try:
        package = ModelPackage.load(path)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    previous = runtime
    replacement = _new_runtime(package)
    _resolve_model_adapters(replacement)
    replacement.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(replacement)
    manager.replace_active(replacement, reason="replaced by loaded package")
    if previous is not None:
        _release_media_runtime(previous)
        _schedule_history_checkpoint(previous)
    runtime = replacement
    _ensure_output_observer(runtime)
    scheduler.runtime = runtime
    interpreter.runtime = runtime
    runtime.start()
    _schedule_history_checkpoint(runtime)
    return {"metrics": runtime.metrics(), "manifest": runtime.manifest.to_dict()}


@app.post("/api/package/clone")
def clone_package(name: str | None = None) -> dict[str, Any]:
    global runtime
    current = _require_active_runtime()
    package = current.package.clone(name=name)
    previous = runtime
    replacement = _new_runtime(package)
    _resolve_model_adapters(replacement)
    replacement.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(replacement)
    manager.replace_active(replacement, reason="replaced by cloned package")
    if previous is not None:
        _release_media_runtime(previous)
        _schedule_history_checkpoint(previous)
    runtime = replacement
    _ensure_output_observer(runtime)
    scheduler.runtime = runtime
    interpreter.runtime = runtime
    runtime.start()
    _schedule_history_checkpoint(runtime)
    return {"metrics": runtime.metrics(), "manifest": runtime.manifest.to_dict()}


@app.post("/api/package/clone-from")
def clone_package_from(path: str, name: str | None = None) -> dict[str, Any]:
    try:
        package = ModelPackage.load(path)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    clone = _new_runtime(package.clone(name=name))
    _resolve_model_adapters(clone)
    clone.set_filter_bypass_sources(ui_settings.get("stimuli", {}).get("bypass_filter_sources", []))
    _configure_attention_modulators(clone)
    manager.add(clone)
    _ensure_output_observer(clone)
    clone.start()
    _schedule_history_checkpoint(clone)
    return {"metrics": clone.metrics(), "manifest": clone.manifest.to_dict()}


@app.post("/api/death")
def death(reason: str = "stopped") -> dict[str, Any]:
    item = _require_active_runtime()
    item.die(reason)
    _schedule_history_checkpoint(item)
    return {"metrics": item.metrics()}


@app.post("/api/package/save")
def save_package(label: str | None = None) -> dict[str, Any]:
    item = _require_active_runtime()
    path = DATA_DIR / f"{item.consciousness_id}{MODEL_PACKAGE_SUFFIX}"
    _resolve_model_adapters(item)
    item.save_package(str(path))
    _schedule_history_checkpoint(item)
    artifact = _record_artifact(path, item.package)
    return {"path": str(path), "label": label, "metrics": item.metrics(), "artifact": artifact}


@app.post("/api/snapshot")
def snapshot(portrait: bool = False, label: str | None = None, reason: str = "manual") -> dict[str, Any]:
    item = _require_active_runtime()
    suffix = "portrait" if portrait else "snapshot"
    path = _archive_path(item, suffix)
    archive = _queue_snapshot_write(
        item,
        path,
        portrait=portrait,
        label=label,
        automatic=False,
        reason=reason,
        wait=True,
    )
    _schedule_history_checkpoint(item)
    return {"path": str(path), "metrics": item.metrics(), "archive": archive}


@app.post("/api/command")
def compatibility_command(request: CommandRequest) -> dict[str, Any]:
    global runtime, ui_settings
    name, args = request.command, request.args
    try:
        if name == "stimulate": return stimulate(StimulusRequest(text=str(args.get("text", "")), intensity=float(args.get("intensity", 1)), source=str(args.get("source", "ui-text"))))
        if name in {"trace_start", "trace_stop"}:
            item = _require_active_runtime()
            enabled = item.set_trace(name == "trace_start")
            _schedule_history_checkpoint(item)
            return {"enabled": enabled, "entries": len(item.trace_entries)}
        if name == "stop":
            item = _require_active_runtime()
            result = snapshot(portrait=True, label="portrait", reason="manual_stop"); item.die("stopped by user"); return result
        if name == "new":
            supplied_manifest = args.get("manifest")
            if isinstance(supplied_manifest, dict):
                manifest = supplied_manifest
            else:
                kernel = str(args.get("kernel", "anonymous-spatial-v3")); spatial = kernel in {"v3", "anonymous-spatial-v3"}
                manifest = {"kernel_id": kernel, "node_payload": "labeled" if kernel == "labeled-feature-v1" else "anonymous", "spatial_embedding": spatial, "spatial_dimensions": 3 if spatial else 0, "parameters": {"neighborhood_enabled": True, "spatial_radius": 2.5, "spatial_competition": 0.0} if spatial else {}}
            return new_consciousness(NewRequest(name=str(args.get("name") or "Unnamed consciousness"), manifest=manifest))
        if name == "snapshot": return snapshot(label=str(args.get("label")) if args.get("label") else None)
        if name == "portrait": return snapshot(portrait=True, label="portrait", reason="manual_portrait")
        if name == "resume": return load_package(str(args.get("path", "")))
        if name == "clone": return clone_package_from(str(args.get("path", "")))
        if name == "archive_delete":
            target = Path(str(args.get("path", ""))).resolve()
            if target.parent != DATA_DIR.resolve() or not is_model_package_path(target): raise ValueError("invalid archive path")
            target.unlink(missing_ok=True); archive_repository.remove_path(target); return {"deleted": str(target)}
        if name == "rename":
            item = _require_active_runtime()
            item.package.consciousness_name = str(args.get("name") or item.consciousness_name)
            return {"metrics": item.metrics()}
        if name == "ambient":
            ui_settings["ambient_intensity"] = float(args.get("intensity", .08))
            _write_ui_settings()
            return {"intensity": ui_settings["ambient_intensity"]}
        if name == "speed":
            item = _require_active_runtime()
            item.config.tick_seconds = max(.002, .1 / max(.1, float(args.get("value", 1))))
            return {"value": args.get("value", 1)}
        if name == "settings_update":
            incoming_settings = dict(args.get("settings", {}))
            incoming_notifications = incoming_settings.pop("notifications", None)
            if isinstance(incoming_notifications, dict):
                _save_notification_settings(incoming_notifications)
            _apply_legacy_adapter_patch(incoming_settings)
            # Legacy projections are accepted at the boundary but never
            # become a second persisted authority for adapters.
            incoming_settings.pop("body", None)
            incoming_settings.pop("network", None)
            incoming_settings.pop("adapters", None)
            _project_legacy_source_switches_into_policies(incoming_settings)
            ui_settings = _merge(ui_settings, incoming_settings)
            _sync_source_policy_legacy()
            _write_ui_settings()
            stimuli_cfg = ui_settings.get("stimuli", {})
            runtime_source_switches = {
                "manual": "manual_enabled",
                "ai": "ai_enabled",
                # ``ambient`` is the Core's generic external-background class;
                # the public setting was renamed so random ambient and
                # physical telemetry can retain independent adapter switches.
                "ambient": "background_enabled",
            }
            for item in manager.instances.values():
                for source, setting_name in runtime_source_switches.items():
                    if setting_name in stimuli_cfg:
                        enabled = bool(stimuli_cfg[setting_name])
                        previous = item.source_status().get(source)
                        item.set_source(source, enabled, confirm_last=True)
                        if source == "ambient" and previous != enabled:
                            _reset_telemetry_baselines(item)
            if "bypass_filter_sources" in stimuli_cfg:
                # This is an explicitly configured sensory gate, not a hidden
                # shortcut around the attention mechanism.
                for item in manager.instances.values():
                    item.set_filter_bypass_sources(stimuli_cfg["bypass_filter_sources"])
            for item in manager.instances.values():
                _body_adapter(item)
                _configure_attention_modulators(item)
            ai_cfg = ui_settings.get("ai", {})
            for raw in ai_cfg.get("providers", []):
                provider_id = str(raw.get("id", "")); existing = providers.get(provider_id)
                if not provider_id: continue
                providers[provider_id] = Provider(id=provider_id, name=str(raw.get("name") or provider_id), kind=str(raw.get("kind") or "openai-compatible"), base_url=str(raw.get("base_url") or ""), model=str(raw.get("model") or ""), api_key=str(raw.get("api_key") or (existing.api_key if existing else "")))
            provider_store.save([asdict(item) for item in providers.values()])
            environment_cfg = ai_cfg.get("environment", {})
            if environment_cfg: scheduler.configure(environment_cfg)
            interpreter_cfg = ai_cfg.get("interpreter", {})
            if interpreter_cfg: interpreter.configure(interpreter_cfg)
            return {"settings": settings()}
        if name == "ai_provider_test": return test_provider(str(args.get("provider_id", "")))
        if name == "notification_test":
            active = manager.instances.get(manager.active_id) if manager.active_id is not None else None
            event = {
                "id": f"notification-test-{active.consciousness_id if active else 'host'}-{active.tick if active else 0}",
                "consciousness_id": active.consciousness_id if active else "host",
                "tick": active.tick if active else 0,
                "readout": "Manual notification transport test",
                "signature": "notification-test",
                "occurrences": 0,
                "internal_edges": 0,
            }
            return {"delivery": _send_notification(event, force=True)}
        raise ValueError(f"unknown command: {name}")
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
