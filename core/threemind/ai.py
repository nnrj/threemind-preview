from __future__ import annotations

import json
import queue
import random
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(slots=True)
class Provider:
    id: str
    name: str
    base_url: str
    model: str
    api_key: str
    kind: str = "openai-compatible"

    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


class ChatClient:
    def complete(self, provider: Provider, *, system: str, user: str, temperature: float = 0.8, max_tokens: int = 120, timeout: float = 30.0) -> str:
        if not provider.base_url or not provider.api_key:
            raise ValueError("AI provider requires base_url and api_key")
        payload = json.dumps({
            "model": provider.model or "gpt-4o-mini",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        request = urllib.request.Request(provider.endpoint(), data=payload, method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {provider.api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"AI provider HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"AI provider connection failed: {error.reason}") from error
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("AI provider returned an invalid chat completion") from error
        return str(content).strip()

    def stream_complete(
        self,
        provider: Provider,
        *,
        system: str,
        user: str,
        temperature: float = 0.8,
        max_tokens: int = 120,
        timeout: float = 90.0,
    ) -> Iterator[str]:
        """Yield OpenAI-compatible chat-completion deltas.

        The experiment layer uses this only to make an external planner's
        proposed text observable while it is generated.  It does not give the
        provider an execution channel: validation still happens after the
        entire response has been received.  Providers which return a normal
        JSON completion despite ``stream: true`` remain usable; their complete
        content is yielded as one final delta.
        """

        if not provider.base_url or not provider.api_key:
            raise ValueError("AI provider requires base_url and api_key")
        payload = json.dumps({
            "model": provider.model or "gpt-4o-mini",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }).encode("utf-8")
        request = urllib.request.Request(
            provider.endpoint(),
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json",
                "Authorization": f"Bearer {provider.api_key}",
            },
        )
        received = False
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = str(response.headers.get("Content-Type", "")).lower()
                if "text/event-stream" not in content_type:
                    body = json.loads(response.read().decode("utf-8"))
                    try:
                        content = str(body["choices"][0]["message"]["content"])
                    except (KeyError, IndexError, TypeError) as error:
                        raise RuntimeError("AI provider returned an invalid chat completion") from error
                    if content:
                        received = True
                        yield content
                    return

                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    except (json.JSONDecodeError, AttributeError, IndexError, TypeError):
                        # A malformed or provider-specific auxiliary SSE line
                        # must not turn into a Core-side command or stop the
                        # observable stream.  Only usable text deltas pass on.
                        continue
                    if isinstance(delta, str) and delta:
                        received = True
                        yield delta
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"AI provider HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"AI provider connection failed: {error.reason}") from error
        if not received:
            raise RuntimeError("AI provider returned an empty streaming response")


ENVIRONMENT_SYSTEM = """You are an external environment stimulus generator for ThreeMind. Return one stimulus only. It may be semantic, fragmentary, multilingual, or meaningless. Do not explain, label, interpret, or mention ThreeMind. The stimulus is input to an experimental consciousness model."""


def environment_prompt(*, irregularity: float = 0.65, intensity: float = 0.7) -> str:
    return f"Generate one external stimulus. Irregularity: {irregularity:.2f}. Intensity: {intensity:.2f}. It can be a sound, image-like fragment, event, object, sentence, or noise."


class EnvironmentScheduler:
    """Optional external AI stimulus producer.

    It hands generated carrier text to an external submission callback; it
    never accesses model state or propagation rules.
    """

    def __init__(self, runtime: Any, provider_lookup: Any, client: ChatClient | None = None, stimulus_submit: Any | None = None) -> None:
        self.runtime = runtime
        self.provider_lookup = provider_lookup
        self.client = client or ChatClient()
        if stimulus_submit is None:
            raise ValueError("EnvironmentScheduler requires an external sensory adapter callback")
        self.stimulus_submit = stimulus_submit
        self.enabled = False
        self.provider_id = ""
        self.frequency_ticks = 120
        self.random_frequency = True
        self.intensity = 0.7
        self.irregularity = 0.65
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rng = random.Random()
        self.last_error: str | None = None
        self.generated = 0

    def configure(self, values: dict[str, Any]) -> dict[str, Any]:
        self.enabled = bool(values.get("enabled", self.enabled))
        self.provider_id = str(values.get("provider_id", self.provider_id))
        self.frequency_ticks = max(10, int(values.get("frequency_ticks", self.frequency_ticks)))
        self.random_frequency = bool(values.get("random_frequency", self.random_frequency))
        self.intensity = max(0.0, min(2.0, float(values.get("intensity", self.intensity))))
        self.irregularity = max(0.0, min(1.0, float(values.get("irregularity", self.irregularity))))
        if self.enabled:
            self.start()
        else:
            self.stop()
        return self.public()

    def public(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "provider_id": self.provider_id, "frequency_ticks": self.frequency_ticks, "random_frequency": self.random_frequency, "intensity": self.intensity, "irregularity": self.irregularity, "running": bool(self._thread and self._thread.is_alive()), "generated": self.generated, "last_error": self.last_error}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            if not self._stop.is_set():
                return
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="threemind-ai-environment", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval_seconds()):
            if not self.enabled:
                continue
            item = self.runtime
            if item is None:
                # AI environment generation is a host service, but there is no
                # destination until the user creates or opens a consciousness.
                continue
            provider = self.provider_lookup(self.provider_id)
            if provider is None:
                self.last_error = "AI provider not found"
                continue
            try:
                text = self.client.complete(provider, system=ENVIRONMENT_SYSTEM, user=environment_prompt(irregularity=self.irregularity, intensity=self.intensity), temperature=min(1.4, 0.4 + self.irregularity), max_tokens=120)
                self.stimulus_submit(item, text, self.intensity)
                self.generated += 1
                self.last_error = None
            except (RuntimeError, ValueError) as error:
                self.last_error = str(error)

    def _interval_seconds(self) -> float:
        ticks = self.frequency_ticks
        if self.random_frequency:
            ticks = self._rng.randint(max(10, ticks // 2), max(10, int(ticks * 1.5)))
        return max(1.0, ticks * 0.1)


class InterpreterScheduler:
    """External observer that can interpret periodic and explicitly triggered snapshots."""

    def __init__(self, runtime: Any, provider_lookup: Any, client: ChatClient | None = None, on_interpretation: Any | None = None) -> None:
        self.runtime = runtime
        self.provider_lookup = provider_lookup
        self.client = client or ChatClient()
        self.on_interpretation = on_interpretation
        self.enabled = False
        self.provider_id = ""
        self.frequency_ticks = 300
        self.language = "auto"
        self.periodic_enabled = True
        self.on_repeatable_structure = False
        self.active_nodes_enabled = True
        self.on_manual_stimulus = False
        self.listen_background_active_nodes = False
        self.deduplicate_readouts = False
        self.activation_min = .08
        self.activation_max = 1.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._requests: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._last_snapshot_signature = ""
        self.last_error: str | None = None
        self.generated = 0

    def configure(self, values: dict[str, Any]) -> dict[str, Any]:
        self.enabled = bool(values.get("enabled", self.enabled))
        self.provider_id = str(values.get("provider_id", self.provider_id))
        self.frequency_ticks = max(20, int(values.get("frequency_ticks", self.frequency_ticks)))
        self.language = str(values.get("language", self.language))
        self.periodic_enabled = bool(values.get("periodic_enabled", self.periodic_enabled))
        self.on_repeatable_structure = bool(values.get("on_repeatable_structure", self.on_repeatable_structure))
        self.active_nodes_enabled = bool(values.get("active_nodes_enabled", self.active_nodes_enabled))
        self.on_manual_stimulus = bool(values.get("on_manual_stimulus", self.on_manual_stimulus))
        self.listen_background_active_nodes = bool(values.get("listen_background_active_nodes", self.listen_background_active_nodes))
        self.deduplicate_readouts = bool(values.get("deduplicate_readouts", self.deduplicate_readouts))
        self.activation_min = max(0.0, min(1.0, float(values.get("activation_min", self.activation_min))))
        self.activation_max = max(self.activation_min, min(1.0, float(values.get("activation_max", self.activation_max))))
        if self.enabled:
            self.start()
        else:
            self.stop()
        return self.public()

    def public(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "provider_id": self.provider_id, "frequency_ticks": self.frequency_ticks, "language": self.language, "periodic_enabled": self.periodic_enabled, "on_repeatable_structure": self.on_repeatable_structure, "active_nodes_enabled": self.active_nodes_enabled, "on_manual_stimulus": self.on_manual_stimulus, "listen_background_active_nodes": self.listen_background_active_nodes, "deduplicate_readouts": self.deduplicate_readouts, "activation_min": self.activation_min, "activation_max": self.activation_max, "running": bool(self._thread and self._thread.is_alive()), "generated": self.generated, "last_error": self.last_error}

    def request(self, trigger: str, runtime: Any | None = None) -> bool:
        """Queue an explicitly enabled external observation without touching Core."""
        if not self.enabled:
            return False
        allowed = {
            "repeatable_structure": self.on_repeatable_structure,
            "manual_stimulus": self.on_manual_stimulus,
            "background_active_nodes": self.listen_background_active_nodes,
        }
        if not allowed.get(trigger, False):
            return False
        item = runtime or self.runtime
        if item is None:
            return False
        self.start()
        self._requests.put((trigger, item))
        return True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            if not self._stop.is_set():
                return
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="threemind-interpreter", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            timeout = max(2.0, self.frequency_ticks * .1) if self.periodic_enabled else .5
            try:
                trigger, item = self._requests.get(timeout=timeout)
            except queue.Empty:
                if self.periodic_enabled and self.runtime is not None:
                    self._interpret("periodic", self.runtime)
                continue
            self._interpret(trigger, item)

    def _interpret(self, trigger: str, item: Any) -> None:
        if not self.enabled or item is None:
            return
        provider = self.provider_lookup(self.provider_id)
        if provider is None:
            self.last_error = "AI provider not found"
            return
        try:
            snapshot = item.observation_snapshot()
            signature = json.dumps(snapshot.get("output_frame", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if self.deduplicate_readouts and signature == self._last_snapshot_signature:
                return
            frame = snapshot.get("output_frame", {})
            # Preserve the old trigger semantics.  Periodic interpretation is
            # a general external summary; activated-node detail is appended
            # for an immediate manual response, or for a repeatable structure
            # only when the corresponding option is enabled.  The ordering is
            # explicitly by activation so the model sent to the provider is
            # auditable and independent of dictionary insertion order.
            include_active_nodes = (
                trigger == "manual_stimulus"
                or (trigger == "repeatable_structure" and self.active_nodes_enabled)
                or trigger == "background_active_nodes"
            )
            if not include_active_nodes:
                frame.pop("nodes", None)
                frame.pop("edges", None)
            else:
                nodes = [
                    node for node in frame.get("nodes", [])
                    if self.activation_min <= float(node.get("activation", 0.0)) <= self.activation_max
                ]
                nodes.sort(key=lambda node: float(node.get("activation", 0.0)), reverse=True)
                selected_ids = {int(node.get("id", -1)) for node in nodes}
                frame["nodes"] = nodes
                frame["edges"] = [
                    edge for edge in frame.get("edges", [])
                    if int(edge.get("source", -1)) in selected_ids and int(edge.get("target", -1)) in selected_ids
                ]
                frame["active_nodes_ranked"] = [
                    {
                        "id": int(node.get("id", -1)),
                        "activation": float(node.get("activation", 0.0)),
                        "stability": float(node.get("stability", 0.0)),
                        "direct_touch": float(node.get("direct_touch", 0.0)),
                        "associative_touch": float(node.get("associative_touch", 0.0)),
                    }
                    for node in nodes
                ]
            text = self.client.complete(provider, system="You are an external observer of a ThreeMind consciousness experiment. Interpret the supplied snapshot cautiously. Do not claim sentience or certainty. Respond in the requested language.", user=json.dumps({"language": self.language, "trigger": trigger, "snapshot": snapshot}, ensure_ascii=False), temperature=.25, max_tokens=260)
            important = any(token in text.lower() for token in ("important", "significant", "重要", "关键", "异常"))
            event = item.record_interpretation(text, provider_id=provider.id, trigger=trigger, important=important)
            self._last_snapshot_signature = signature
            if self.on_interpretation is not None:
                self.on_interpretation(item, event)
            self.generated += 1
            self.last_error = None
        except (RuntimeError, ValueError, TypeError) as error:
            self.last_error = str(error)
