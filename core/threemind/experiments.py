from __future__ import annotations

"""Host-side, auditable experiment orchestration for ThreeMind.

This module is intentionally *outside* the associative runtime.  It may read an
OutputBus projection and may submit an external sensory carrier through the
normal InputBus, but it never changes node, edge, propagation, forgetting, or
adapter rules directly.  The same command registry is used by a human-facing
workbench and by an optional AI planner.

The implementation is deliberately conservative about authority: a language
model can propose a JSON plan, but only this host validates and executes a
small, explicit command set.  It has no path to arbitrary HTTP calls,
filesystem access, credential settings, deletion, or persistence switching.
"""

import copy
import json
import queue
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

from .ai import ChatClient, Provider
from .manager import RuntimeManager
from .persistence import PersistenceBackend
from .runtime import ConsciousnessRuntime


EXPERIMENT_RECORD_TYPE = "threemind_experiment_run/v1"
EXPERIMENT_INDEX_KEY = "threemind:experiment-runs:index:v1"


COMMAND_SPECS: tuple[dict[str, Any], ...] = (
    {
        "op": "observe.summary",
        "mutating": False,
        "description": "Read the target runtime metrics and its latest OutputBus summary.",
        "args": {},
    },
    {
        "op": "observe.output",
        "mutating": False,
        "description": "Read the latest anonymous output frame without altering the runtime.",
        "args": {},
    },
    {
        "op": "observe.graph",
        "mutating": False,
        "description": "Read a bounded visualization projection of the graph.",
        "args": {"limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500}},
    },
    {
        "op": "history.tail",
        "mutating": False,
        "description": "Read recent stimuli, events, observations, interpretations, or trace entries.",
        "args": {
            "kind": {"enum": ["stimuli", "events", "observations", "interpretations", "trace"], "default": "events"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 40},
        },
    },
    {
        "op": "stimulus.send",
        "mutating": True,
        "description": "Submit one external text carrier through the normal text sensor as source ai-debug.",
        "args": {
            "text": {"type": "string", "minLength": 1},
            "intensity": {"type": "number", "minimum": 0.0, "maximum": 2.0, "default": 1.0},
        },
    },
    {
        "op": "runtime.wait",
        "mutating": False,
        "description": "Wait for a stated number of actual Core ticks; does not synthesize a graph transition.",
        "args": {"ticks": {"type": "integer", "minimum": 1}},
    },
    {
        "op": "snapshot.capture",
        "mutating": True,
        "description": "Capture an immutable, named experimental snapshot through the archive writer.",
        "args": {"label": {"type": "string", "maxLength": 160, "default": "experiment snapshot"}},
    },
    {
        "op": "runtime.pause",
        "mutating": True,
        "description": "Pause the selected experimental runtime.",
        "args": {},
    },
    {
        "op": "runtime.resume",
        "mutating": True,
        "description": "Resume the selected experimental runtime.",
        "args": {},
    },
    {
        "op": "experiment.note",
        "mutating": False,
        "description": "Attach a researcher note to the audit trail; it never enters the consciousness as a stimulus.",
        "args": {"text": {"type": "string", "minLength": 1, "maxLength": 4000}},
    },
)
COMMAND_SPEC_BY_OP = {str(spec["op"]): spec for spec in COMMAND_SPECS}

TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "repeatability": {
        "title": "Repeated carrier / structure response",
        "description": "Send the same carrier several times with explicit temporal spacing, then compare output signatures.",
    },
    "association": {
        "title": "Association and transfer",
        "description": "Present two carriers in a controlled order, then probe each carrier separately.",
    },
    "forgetting": {
        "title": "Forgetting and consolidation",
        "description": "Compare an early response, a deliberate delay, and a repeated response without asserting memory in advance.",
    },
    "sequence-order": {
        "title": "Input-order comparison",
        "description": "Compare two ordered carrier sequences in separately cloned sandbox instances.",
    },
    "free-form": {
        "title": "Open research protocol",
        "description": "A researcher-defined protocol. AI may propose only the registered experiment commands.",
    },
}


class ExperimentError(ValueError):
    """A safe, user-facing rejection of an experiment request or plan."""


def _now() -> float:
    return time.time()


def _public_command_specs() -> list[dict[str, Any]]:
    return copy.deepcopy(list(COMMAND_SPECS))


def _json_from_completion(text: str) -> dict[str, Any]:
    """Extract one JSON object from an LLM response without executing its text."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    decoder = json.JSONDecoder()
    for offset, char in enumerate(candidate):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(candidate[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ExperimentError("AI planner did not return a JSON object")


def _compact_snapshot(runtime: ConsciousnessRuntime) -> dict[str, Any]:
    snapshot = runtime.observation_snapshot()
    frame = dict(snapshot.get("output_frame", {}))
    nodes = list(frame.get("nodes", []))
    nodes.sort(key=lambda node: float(node.get("activation", 0.0)), reverse=True)
    frame["nodes"] = nodes[:32]
    frame["edges"] = list(frame.get("edges", []))[:96]
    return {
        "metrics": snapshot.get("metrics", {}),
        "output_frame": frame,
        "recent_stimuli": list(snapshot.get("recent_stimuli", []))[-8:],
        "recent_events": list(snapshot.get("recent_events", []))[-8:],
    }


class ExperimentStore:
    """Portable records over ThreeMind's selected generic persistence backend."""

    def __init__(self, backend_getter: Callable[[], PersistenceBackend]) -> None:
        self._backend_getter = backend_getter
        self._lock = threading.RLock()

    @staticmethod
    def _record_key(run_id: str) -> str:
        return f"threemind:experiment-run:{run_id}"

    def _index(self) -> dict[str, Any]:
        value = self._backend_getter().get(EXPERIMENT_INDEX_KEY)
        if not isinstance(value, dict):
            return {"key": EXPERIMENT_INDEX_KEY, "record_type": "threemind_experiment_index/v1", "items": []}
        value.setdefault("key", EXPERIMENT_INDEX_KEY)
        value.setdefault("record_type", "threemind_experiment_index/v1")
        value.setdefault("items", [])
        return value

    def save(self, run: dict[str, Any]) -> dict[str, Any]:
        if not str(run.get("id") or ""):
            raise ExperimentError("experiment run requires an id")
        with self._lock:
            stored = copy.deepcopy(run)
            stored["key"] = self._record_key(str(stored["id"]))
            stored["record_type"] = EXPERIMENT_RECORD_TYPE
            stored["updated_at"] = _now()
            backend = self._backend_getter()
            backend.put(str(stored["key"]), stored)
            index = self._index()
            compact = {
                "id": stored["id"],
                "key": stored["key"],
                "title": str(stored.get("title") or "Untitled experiment"),
                "status": str(stored.get("status") or "draft"),
                "mode": str(stored.get("mode") or "manual"),
                "created_at": stored.get("created_at"),
                "updated_at": stored.get("updated_at"),
                "target": copy.deepcopy(stored.get("target", {})),
            }
            rows = [row for row in index.get("items", []) if isinstance(row, dict) and row.get("id") != stored["id"]]
            rows.append(compact)
            rows.sort(key=lambda row: float(row.get("updated_at") or 0), reverse=True)
            index["items"] = rows
            backend.put(EXPERIMENT_INDEX_KEY, index)
            return stored

    def get(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._backend_getter().get(self._record_key(run_id))
            if not isinstance(value, dict):
                raise ExperimentError("experiment run not found")
            return copy.deepcopy(value)

    def list(self, *, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            needle = query.casefold().strip()
            rows = []
            for row in self._index().get("items", []):
                if not isinstance(row, dict):
                    continue
                if needle and needle not in json.dumps(row, ensure_ascii=False).casefold():
                    continue
                rows.append(copy.deepcopy(row))
            return rows[:max(1, min(int(limit), 500))]


class ExperimentController:
    """Application service shared by manual and AI-assisted experiment flows."""

    def __init__(
        self,
        *,
        manager: RuntimeManager,
        store: ExperimentStore,
        provider_lookup: Callable[[str], Provider | None],
        ai_client: ChatClient,
        submit_stimulus: Callable[[ConsciousnessRuntime, str, float, str], dict[str, Any]],
        graph_view: Callable[[ConsciousnessRuntime, int | None], dict[str, Any]],
        prepare_runtime: Callable[[ConsciousnessRuntime], None],
        snapshot_capture: Callable[[ConsciousnessRuntime, str, str], dict[str, Any]],
        checkpoint_history: Callable[[ConsciousnessRuntime], None],
        lab_directory: Path,
        runtime_factory: Callable[[Any], ConsciousnessRuntime] = ConsciousnessRuntime,
    ) -> None:
        self.manager = manager
        self.store = store
        self.provider_lookup = provider_lookup
        self.ai_client = ai_client
        self.submit_stimulus = submit_stimulus
        self.graph_view = graph_view
        self.prepare_runtime = prepare_runtime
        self.snapshot_capture = snapshot_capture
        self.checkpoint_history = checkpoint_history
        self.lab_directory = lab_directory
        self.runtime_factory = runtime_factory
        self._lock = threading.RLock()
        self._controls: dict[str, threading.Event] = {}

    def command_specs(self) -> list[dict[str, Any]]:
        return _public_command_specs()

    def create_run(
        self,
        *,
        target_id: str,
        title: str,
        mode: str = "manual",
        provider_id: str = "",
        goal: str = "",
        template_id: str = "free-form",
        sandbox: bool = True,
        background_mode: str = "paused",
        limits: dict[str, Any] | None = None,
        progress: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        def emit(stage: str, message: str) -> None:
            if progress is not None:
                progress(stage, message)

        emit("validating", "Validating experiment request and target runtime.")
        if mode not in {"manual", "approval", "auto"}:
            raise ExperimentError("experiment mode must be manual, approval, or auto")
        if template_id not in TEMPLATE_DEFINITIONS:
            raise ExperimentError("unknown experiment template")
        if background_mode not in {"paused", "preserve"}:
            raise ExperimentError("background mode must be paused or preserve")
        source = self.manager.get(target_id)
        emit("target_ready", "Target consciousness is ready for the experiment.")
        runtime = source
        parent_id: str | None = None
        if sandbox:
            emit("cloning", "Cloning consciousness state into an isolated sandbox.")
            package = copy.deepcopy(source.package)
            package.state = source.state_dict()
            package = package.clone(name=f"{source.consciousness_name} · experiment")
            package.state["parent_id"] = source.consciousness_id
            package.state["life_state"] = "active"
            package.state["death_reason"] = None
            runtime = self.runtime_factory(package)
            runtime.set_filter_bypass_sources(source.filter_bypass_sources)
            if background_mode == "paused":
                # A sandbox that pauses its ambient field must still retain an
                # explicit externally driven path.  The research protocol can
                # then submit only the declared experiment carriers; this is
                # not an artificial internal stimulus.
                runtime.set_source("manual", True)
                runtime.set_source("ambient", False)
            emit("initializing", "Initializing isolated sandbox adapters and runtime.")
            self.prepare_runtime(runtime)
            self.manager.add(runtime, activate=False)
            runtime.start()
            parent_id = source.consciousness_id
            emit("sandbox_ready", "Isolated sandbox is running.")
        if mode == "auto" and not sandbox:
            raise ExperimentError("automatic AI execution is available only for a cloned sandbox instance")
        run_id = str(uuid.uuid4())
        # The host receives these bounds from the registered bridge adapter.
        # Do not silently add an unrelated second set of caps here: a run
        # records exactly the visible values that its adapter configuration
        # authorized.  The API only permits a run to tighten those bounds.
        raw_limits = limits or {}
        max_steps = int(raw_limits.get("max_steps", 24))
        max_stimuli = int(raw_limits.get("max_stimuli", 12))
        max_text_length = int(raw_limits.get("max_text_length", 2000))
        max_wait_ticks = int(raw_limits.get("max_wait_ticks", 5000))
        if min(max_steps, max_stimuli, max_text_length, max_wait_ticks) < 1:
            raise ExperimentError("experiment limits must be positive")
        emit("recording", "Recording the initial experiment state.")
        record = {
            "id": run_id,
            "title": (title or TEMPLATE_DEFINITIONS[template_id]["title"])[:200],
            "mode": mode,
            "provider_id": provider_id,
            "goal": goal[:8000],
            "template_id": template_id,
            "template": copy.deepcopy(TEMPLATE_DEFINITIONS[template_id]),
            "status": "draft",
            "created_at": _now(),
            "target": {
                "runtime_id": runtime.consciousness_id,
                "runtime_name": runtime.consciousness_name,
                "source_consciousness_id": parent_id or source.consciousness_id,
                "sandbox": bool(sandbox),
                "background_mode": background_mode,
            },
            "limits": {
                "max_steps": max_steps,
                "max_stimuli": max_stimuli,
                "max_text_length": max_text_length,
                "max_wait_ticks": max_wait_ticks,
            },
            "initial_observation": _compact_snapshot(runtime),
            "plan": [],
            "steps": [],
            "analysis": [],
            "report": None,
            "artifacts": [],
            "errors": [],
        }
        emit("checkpointing", "Checkpointing experiment history.")
        self.checkpoint_history(runtime)
        stored = self.store.save(record)
        emit("ready", "Experiment run is ready.")
        return stored

    def create_run_events(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Create one run while exposing only host lifecycle stages.

        The isolated runtime is still constructed by the same ``create_run``
        implementation used by the non-streaming API.  Progress events are
        observable host-side work, never synthetic Core events or topology
        changes.  A dedicated worker keeps a potentially large package clone
        from blocking the HTTP stream itself.
        """

        events: queue.Queue[dict[str, Any]] = queue.Queue()
        completed = threading.Event()

        def report(stage: str, message: str) -> None:
            events.put({"type": "progress", "stage": stage, "message": message})

        def worker() -> None:
            try:
                record = self.create_run(**kwargs, progress=report)
                events.put({"type": "result", "run": record})
            except Exception as error:
                events.put({"type": "error", "detail": str(error)})
            finally:
                completed.set()

        threading.Thread(target=worker, name="threemind-experiment-create", daemon=True).start()
        while not completed.is_set() or not events.empty():
            try:
                yield events.get(timeout=.25)
            except queue.Empty:
                continue

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get(run_id)

    def list_runs(self, *, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list(query=query, limit=limit)

    def _limits(self, run: dict[str, Any]) -> dict[str, int]:
        raw = dict(run.get("limits", {}))
        return {
            "max_steps": int(raw.get("max_steps", 24)),
            "max_stimuli": int(raw.get("max_stimuli", 12)),
            "max_text_length": int(raw.get("max_text_length", 2000)),
            "max_wait_ticks": int(raw.get("max_wait_ticks", 5000)),
        }

    def _validate_step(self, raw: dict[str, Any], *, limits: dict[str, int], index: int) -> dict[str, Any]:
        op = str(raw.get("op") or "").strip()
        if op not in COMMAND_SPEC_BY_OP:
            raise ExperimentError(f"experiment command is not permitted: {op or '<empty>'}")
        args = dict(raw.get("args") or {})
        if op == "stimulus.send":
            text = str(args.get("text") or "")
            if not text.strip():
                raise ExperimentError("stimulus.send requires text")
            if len(text) > limits["max_text_length"]:
                raise ExperimentError("stimulus text exceeds this run's explicit max_text_length")
            intensity = float(args.get("intensity", 1.0))
            if not 0.0 <= intensity <= 2.0:
                raise ExperimentError("stimulus intensity must be between 0 and 2")
            args = {"text": text, "intensity": intensity}
        elif op == "runtime.wait":
            ticks = int(args.get("ticks", 1))
            if not 1 <= ticks <= limits["max_wait_ticks"]:
                raise ExperimentError("runtime.wait ticks exceed this run's explicit max_wait_ticks")
            args = {"ticks": ticks}
        elif op == "observe.graph":
            args = {"limit": max(1, min(int(args.get("limit", 500)), 5000))}
        elif op == "history.tail":
            kind = str(args.get("kind", "events"))
            if kind not in {"stimuli", "events", "observations", "interpretations", "trace"}:
                raise ExperimentError("history.tail kind is unsupported")
            args = {"kind": kind, "limit": max(1, min(int(args.get("limit", 40)), 500))}
        elif op == "snapshot.capture":
            args = {"label": str(args.get("label") or "experiment snapshot")[:160]}
        elif op == "experiment.note":
            text = str(args.get("text") or "")
            if not text.strip():
                raise ExperimentError("experiment.note requires text")
            args = {"text": text[:4000]}
        else:
            args = {}
        return {
            "id": str(raw.get("id") or f"step-{index + 1}-{uuid.uuid4().hex[:8]}"),
            "op": op,
            "args": args,
            "rationale": str(raw.get("rationale") or "")[:2000],
            "mutating": bool(COMMAND_SPEC_BY_OP[op]["mutating"]),
            "status": "pending",
        }

    def set_plan(self, run_id: str, plan: list[dict[str, Any]], *, origin: str = "manual") -> dict[str, Any]:
        run = self.store.get(run_id)
        limits = self._limits(run)
        if len(plan) > limits["max_steps"]:
            raise ExperimentError("plan exceeds this run's explicit max_steps")
        normalized = [self._validate_step(row, limits=limits, index=index) for index, row in enumerate(plan)]
        stimulus_count = sum(1 for step in normalized if step["op"] == "stimulus.send")
        if stimulus_count > limits["max_stimuli"]:
            raise ExperimentError("plan exceeds this run's explicit max_stimuli")
        run["plan"] = normalized
        run["plan_origin"] = origin
        run["status"] = "awaiting_approval" if run.get("mode") in {"approval", "auto"} else "planned"
        return self.store.save(run)

    def template_plan(self, template_id: str, *, carrier_a: str = "A", carrier_b: str = "B", intensity: float = 1.0) -> list[dict[str, Any]]:
        if template_id not in TEMPLATE_DEFINITIONS:
            raise ExperimentError("unknown experiment template")
        if template_id == "repeatability":
            return [
                {"op": "observe.summary", "rationale": "baseline"},
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "first presentation"},
                {"op": "runtime.wait", "args": {"ticks": 24}, "rationale": "allow frame delivery and local propagation"},
                {"op": "observe.output", "rationale": "capture first response"},
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "second presentation"},
                {"op": "runtime.wait", "args": {"ticks": 24}, "rationale": "allow second response"},
                {"op": "observe.output", "rationale": "compare response signature"},
                {"op": "snapshot.capture", "args": {"label": "repeatability protocol"}, "rationale": "preserve experimental endpoint"},
            ]
        if template_id == "association":
            return [
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "carrier A"},
                {"op": "runtime.wait", "args": {"ticks": 8}, "rationale": "explicit temporal interval"},
                {"op": "stimulus.send", "args": {"text": carrier_b, "intensity": intensity}, "rationale": "carrier B"},
                {"op": "runtime.wait", "args": {"ticks": 30}, "rationale": "allow local propagation"},
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "probe carrier A"},
                {"op": "runtime.wait", "args": {"ticks": 20}, "rationale": "observe probe result"},
                {"op": "observe.output", "rationale": "record response"},
            ]
        if template_id == "forgetting":
            return [
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "initial presentation"},
                {"op": "runtime.wait", "args": {"ticks": 20}, "rationale": "initial response"},
                {"op": "observe.output", "rationale": "baseline response"},
                {"op": "runtime.wait", "args": {"ticks": 120}, "rationale": "unreinforced interval"},
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "retention probe"},
                {"op": "runtime.wait", "args": {"ticks": 20}, "rationale": "probe response"},
                {"op": "observe.output", "rationale": "compare response"},
            ]
        if template_id == "sequence-order":
            return [
                {"op": "stimulus.send", "args": {"text": carrier_a, "intensity": intensity}, "rationale": "first carrier"},
                {"op": "runtime.wait", "args": {"ticks": 10}, "rationale": "explicit order interval"},
                {"op": "stimulus.send", "args": {"text": carrier_b, "intensity": intensity}, "rationale": "second carrier"},
                {"op": "runtime.wait", "args": {"ticks": 30}, "rationale": "observe ordered response"},
                {"op": "observe.output", "rationale": "endpoint signature"},
            ]
        return [{"op": "observe.summary", "rationale": "researcher-defined baseline"}]

    def _prepare_ai_plan_request(self, run_id: str, *, provider_id: str, goal: str, language: str) -> tuple[dict[str, Any], Provider, str, str]:
        run = self.store.get(run_id)
        provider = self.provider_lookup(provider_id)
        if provider is None:
            raise ExperimentError("AI provider not found")
        target = self.manager.get(str(run["target"]["runtime_id"]))
        system = (
            "You are an external ThreeMind experiment planner. You do not control the consciousness directly. "
            "Return exactly one JSON object with keys title (string), hypothesis (string), and steps (array). "
            "Every step must use only one registered op and its documented args. Do not use HTTP, filesystem, "
            "settings, deletion, provider management, package management, arbitrary code, or any unregistered command. "
            "State uncertainty and avoid claims of sentience or proof. Keep the plan within the stated limits.\n"
            + json.dumps({"command_specs": _public_command_specs(), "limits": self._limits(run)}, ensure_ascii=False)
        )
        user = json.dumps(
            {
                "language": language,
                "research_goal": goal or run.get("goal") or "Describe an observable, falsifiable protocol.",
                "template": run.get("template"),
                "target_snapshot": _compact_snapshot(target),
            },
            ensure_ascii=False,
        )
        return run, provider, system, user

    def _save_ai_plan(self, run_id: str, *, provider: Provider, raw: str) -> dict[str, Any]:
        parsed = _json_from_completion(raw)
        steps = parsed.get("steps")
        if not isinstance(steps, list):
            raise ExperimentError("AI plan must contain a steps array")
        saved = self.set_plan(run_id, [dict(row) for row in steps if isinstance(row, dict)], origin="ai")
        saved["ai_plan"] = {
            "provider_id": provider.id,
            "model": provider.model,
            "hypothesis": str(parsed.get("hypothesis") or "")[:4000],
            "raw": raw[:20_000],
            "created_at": _now(),
        }
        saved = self.store.save(saved)
        # Automatic mode is an explicit, sandbox-only permission selected by
        # the researcher (or by the visible bridge default).  The AI still
        # cannot skip validation: only the normalized plan above reaches this
        # branch, and the worker uses the same command executor as manual
        # steps.
        if saved.get("mode") == "auto":
            return self.run_plan_async(run_id, approved=True)
        return saved

    def plan_with_ai(self, run_id: str, *, provider_id: str, goal: str, language: str = "zh-CN") -> dict[str, Any]:
        _run, provider, system, user = self._prepare_ai_plan_request(run_id, provider_id=provider_id, goal=goal, language=language)
        raw = self.ai_client.complete(provider, system=system, user=user, temperature=0.1, max_tokens=2200)
        return self._save_ai_plan(run_id, provider=provider, raw=raw)

    def plan_with_ai_events(self, run_id: str, *, provider_id: str, goal: str, language: str = "zh-CN") -> Iterator[dict[str, Any]]:
        """Yield planner text and lifecycle events without delegating authority.

        Every delta is merely the external model's untrusted proposal.  Only
        after the full response is parsed and passed through ``set_plan`` does
        a validated command plan become part of an experiment run.
        """

        yield {"type": "status", "stage": "preparing", "message": "Preparing a bounded AI planning request."}
        try:
            _run, provider, system, user = self._prepare_ai_plan_request(run_id, provider_id=provider_id, goal=goal, language=language)
        except (ExperimentError, KeyError, RuntimeError, ValueError) as error:
            yield {"type": "error", "detail": str(error)}
            return
        yield {"type": "status", "stage": "requesting", "message": "Requesting an external AI planning proposal.", "provider_id": provider.id, "model": provider.model}
        fragments: list[str] = []
        try:
            for delta in self.ai_client.stream_complete(provider, system=system, user=user, temperature=0.1, max_tokens=2200):
                fragments.append(delta)
                yield {"type": "delta", "text": delta}
        except (RuntimeError, ValueError) as error:
            yield {"type": "error", "detail": str(error)}
            return
        raw = "".join(fragments)
        yield {"type": "status", "stage": "validating", "message": "Extracting and validating the proposed command plan."}
        try:
            saved = self._save_ai_plan(run_id, provider=provider, raw=raw)
        except (ExperimentError, KeyError, RuntimeError, ValueError, TypeError) as error:
            yield {"type": "error", "detail": str(error), "raw": raw[:20_000]}
            return
        yield {"type": "result", "run": saved, "message": "AI plan generated and validated."}

    def _target_runtime(self, run: dict[str, Any]) -> ConsciousnessRuntime:
        return self.manager.get(str(run.get("target", {}).get("runtime_id") or ""))

    def _append_step(self, run: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        run.setdefault("steps", []).append(entry)
        # A manually executed step must not make the whole plan look like an
        # asynchronous worker is already running.  That would prevent the
        # researcher from continuing the remaining, validated steps.  The
        # worker has already set ``running`` before it calls this method.
        if run.get("status") != "running":
            pending = any(str(candidate.get("status")) != "completed" for candidate in run.get("plan", []))
            run["status"] = "partial" if pending else "completed"
        return self.store.save(run)

    def execute_step(self, run_id: str, step_id: str, *, _worker: bool = False) -> dict[str, Any]:
        with self._lock:
            run = self.store.get(run_id)
            if not _worker and run.get("status") in {"running", "cancelling"}:
                raise ExperimentError("whole-plan execution is already running")
            plan = list(run.get("plan", []))
            step = next((row for row in plan if str(row.get("id")) == step_id), None)
            if not isinstance(step, dict):
                raise ExperimentError("experiment step not found")
            if step.get("status") == "completed":
                return run
            runtime = self._target_runtime(run)
            started = _now()
            before = runtime.metrics()
            result: dict[str, Any]
            op = str(step["op"])
            args = dict(step.get("args", {}))
            if op == "observe.summary":
                result = _compact_snapshot(runtime)
            elif op == "observe.output":
                result = _compact_snapshot(runtime).get("output_frame", {})
            elif op == "observe.graph":
                result = self.graph_view(runtime, int(args.get("limit", 500)))
            elif op == "history.tail":
                kind = str(args["kind"])
                if kind == "stimuli": rows = runtime.stimuli
                elif kind == "events": rows = runtime.events
                elif kind == "interpretations": rows = runtime.interpretations
                elif kind == "observations": rows = list(runtime.package.logs.get("observations", []))
                else: rows = runtime.trace_entries
                result = {"kind": kind, "items": copy.deepcopy(list(rows)[-int(args["limit"]):])}
            elif op == "stimulus.send":
                result = self.submit_stimulus(runtime, str(args["text"]), float(args["intensity"]), "ai-debug")
            elif op == "runtime.wait":
                result = self._wait_for_ticks(runtime, int(args["ticks"]), run_id)
            elif op == "snapshot.capture":
                result = self.snapshot_capture(runtime, str(args["label"]), f"experiment:{run_id}")
                run.setdefault("artifacts", []).append({"kind": "snapshot", "created_at": _now(), "value": copy.deepcopy(result)})
            elif op == "runtime.pause":
                runtime.pause(); result = {"paused": True, "metrics": runtime.metrics()}
            elif op == "runtime.resume":
                runtime.resume(); result = {"paused": False, "metrics": runtime.metrics()}
            elif op == "experiment.note":
                result = {"note": str(args["text"])}
            else:  # Defensive: validation should already make this unreachable.
                raise ExperimentError(f"unsupported experiment command: {op}")
            step["status"] = "completed"
            step["executed_at"] = _now()
            step["result"] = result
            step["before_metrics"] = before
            step["after_metrics"] = runtime.metrics()
            step["duration_ms"] = round((_now() - started) * 1000, 2)
            for index, candidate in enumerate(plan):
                if str(candidate.get("id")) == step_id:
                    plan[index] = step
                    break
            run["plan"] = plan
            run = self._append_step(run, copy.deepcopy(step))
            self.checkpoint_history(runtime)
            return run

    def _wait_for_ticks(self, runtime: ConsciousnessRuntime, ticks: int, run_id: str) -> dict[str, Any]:
        start_tick = int(runtime.tick)
        target_tick = start_tick + ticks
        control = self._controls.get(run_id)
        # The timeout is an explicit audit field rather than a hidden semantic
        # cutoff. It only prevents an indefinitely paused/stopped host request.
        timeout_seconds = max(10.0, ticks * max(float(runtime.config.tick_seconds), 0.002) * 8.0)
        deadline = time.monotonic() + timeout_seconds
        while runtime.tick < target_tick:
            if control is not None and control.is_set():
                return {"start_tick": start_tick, "target_tick": target_tick, "reached_tick": runtime.tick, "cancelled": True, "timeout_seconds": timeout_seconds}
            if runtime.life_state == "dead":
                return {"start_tick": start_tick, "target_tick": target_tick, "reached_tick": runtime.tick, "stopped": "dead", "timeout_seconds": timeout_seconds}
            if time.monotonic() >= deadline:
                return {"start_tick": start_tick, "target_tick": target_tick, "reached_tick": runtime.tick, "timed_out": True, "timeout_seconds": timeout_seconds}
            time.sleep(min(0.05, max(0.002, float(runtime.config.tick_seconds))))
        return {"start_tick": start_tick, "target_tick": target_tick, "reached_tick": runtime.tick, "timeout_seconds": timeout_seconds}

    def run_plan_async(self, run_id: str, *, approved: bool = False) -> dict[str, Any]:
        with self._lock:
            run = self.store.get(run_id)
            if run.get("mode") == "approval" and not approved:
                raise ExperimentError("approval mode requires explicit approval before execution")
            if run.get("mode") == "auto" and not bool(run.get("target", {}).get("sandbox")):
                raise ExperimentError("automatic AI execution requires a sandbox target")
            if not run.get("plan"):
                raise ExperimentError("experiment has no validated plan")
            if run.get("status") in {"running", "cancelling"}:
                raise ExperimentError("experiment is already running")
            cancel = threading.Event()
            self._controls[run_id] = cancel
            run["status"] = "running"
            self.store.save(run)
            thread = threading.Thread(target=self._run_plan_worker, args=(run_id, cancel), name=f"threemind-experiment-{run_id[:8]}", daemon=True)
            thread.start()
            return self.store.get(run_id)

    def _run_plan_worker(self, run_id: str, cancel: threading.Event) -> None:
        try:
            run = self.store.get(run_id)
            for step in list(run.get("plan", [])):
                if cancel.is_set():
                    break
                if step.get("status") == "completed":
                    continue
                self.execute_step(run_id, str(step["id"]), _worker=True)
            run = self.store.get(run_id)
            run["status"] = "cancelled" if cancel.is_set() else "completed"
            self.store.save(run)
        except Exception as error:  # Worker errors are experiment evidence, not Core failures.
            try:
                run = self.store.get(run_id)
                run.setdefault("errors", []).append({"at": _now(), "message": str(error)})
                run["status"] = "failed"
                self.store.save(run)
            except Exception:
                pass
        finally:
            with self._lock:
                self._controls.pop(run_id, None)

    def cancel(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            control = self._controls.get(run_id)
            if control is not None:
                control.set()
            run = self.store.get(run_id)
            if run.get("status") == "running":
                run["status"] = "cancelling"
                return self.store.save(run)
            return run

    def analyze(self, run_id: str, *, provider_id: str = "", language: str = "zh-CN", prompt: str = "") -> dict[str, Any]:
        run = self.store.get(run_id)
        runtime = self._target_runtime(run)
        evidence = {
            "run": {key: run.get(key) for key in ("id", "title", "goal", "template", "status", "target", "limits")},
            "initial_observation": run.get("initial_observation"),
            "steps": list(run.get("steps", []))[-100:],
            "current_observation": _compact_snapshot(runtime),
        }
        if provider_id:
            provider = self.provider_lookup(provider_id)
            if provider is None:
                raise ExperimentError("AI provider not found")
            system = (
                "You are an external research observer. Analyze only the supplied ThreeMind experiment evidence. "
                "Separate observation from inference, list plausible alternatives, do not claim consciousness or proof, "
                "and propose a falsifiable next test. Return concise JSON with summary, observations, interpretation, alternatives, conclusion, follow_up, confidence."
            )
            raw = self.ai_client.complete(provider, system=system, user=json.dumps({
                "language": language,
                "researcher_focus": prompt[:8000],
                "evidence": evidence,
            }, ensure_ascii=False), temperature=0.15, max_tokens=1800)
            try:
                analysis: dict[str, Any] = _json_from_completion(raw)
            except ExperimentError:
                analysis = {"summary": raw, "raw": raw}
            analysis["provider_id"] = provider.id
            analysis["model"] = provider.model
        else:
            analysis = {
                "summary": "Deterministic experiment summary; no external AI interpretation was requested.",
                "observations": [
                    f"{len(run.get('steps', []))} recorded command executions.",
                    f"Current tick: {runtime.tick}; nodes: {len(runtime.nodes)}; edges: {len(runtime.edges)}.",
                ],
                "interpretation": "No semantic or sentience claim is made by this host-side summary.",
                "alternatives": ["Observed signatures can arise from the implemented sensory encoding, local propagation, and prior state."],
                "conclusion": "Further controlled comparison is required.",
                "follow_up": "Repeat in independently cloned sandboxes and compare a stated null/control carrier.",
                "confidence": "not_applicable",
            }
        entry = {
            "id": str(uuid.uuid4()),
            "created_at": _now(),
            "language": language,
            "researcher_focus": prompt[:8000],
            "analysis": analysis,
        }
        run.setdefault("analysis", []).append(entry)
        return self.store.save(run)

    def export_report(self, run_id: str, *, language: str = "zh-CN") -> dict[str, Any]:
        run = self.store.get(run_id)
        output_dir = self.lab_directory / "ai-debug"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
        safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", str(run.get("title") or "experiment")).strip("-")[:48] or "experiment"
        path = output_dir / f"{stamp}_{run_id[:8]}_{safe_title}.md"
        is_zh = language != "en"
        heading = "# AI 调试实验报告（自动生成，未审核）" if is_zh else "# AI Debug Experiment Report (Generated, Unreviewed)"
        labels = {
            "title": "实验标题" if is_zh else "Title",
            "status": "状态" if is_zh else "Status",
            "target": "目标运行时" if is_zh else "Target runtime",
            "goal": "研究目标" if is_zh else "Research goal",
            "steps": "执行步骤" if is_zh else "Executed steps",
            "analysis": "分析" if is_zh else "Analysis",
            "note": "说明" if is_zh else "Note",
        }
        lines = [heading, "", f"- {labels['title']}: {run.get('title', '')}", f"- {labels['status']}: {run.get('status', '')}", f"- {labels['target']}: `{run.get('target', {}).get('runtime_id', '')}`", f"- {labels['goal']}: {run.get('goal', '') or '—'}", "", f"## {labels['steps']}", ""]
        for step in run.get("steps", []):
            lines.append(f"- `{step.get('op', '')}` — {json.dumps(step.get('args', {}), ensure_ascii=False)}")
            if step.get("result") is not None:
                rendered = json.dumps(step.get("result"), ensure_ascii=False, indent=2)[:12_000]
                lines.extend(["", "```json", rendered, "```", ""])
        lines.extend([f"## {labels['analysis']}", ""])
        if run.get("analysis"):
            lines.append(json.dumps(run["analysis"][-1], ensure_ascii=False, indent=2))
        else:
            lines.append("尚未生成外部分析。" if is_zh else "No external analysis has been generated.")
        lines.extend(["", f"> {labels['note']}: " + ("本报告由宿主实验层自动生成；它不是 Core 输出，也不构成关于意识的结论。" if is_zh else "This report was generated by the host experiment layer. It is not Core output and is not a conclusion about consciousness."), ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        artifact = {"kind": "lab_report", "path": str(path), "created_at": _now(), "language": language, "review_status": "generated_unreviewed"}
        run.setdefault("artifacts", []).append(artifact)
        run["report"] = artifact
        self.store.save(run)
        return artifact

    def shutdown(self) -> None:
        with self._lock:
            for control in self._controls.values():
                control.set()
