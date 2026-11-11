from __future__ import annotations

import json
import time

from threemind_core import Config, StateImage, Stimulus


class NativeEngine:
    def __init__(self, config: Config | None = None, state: StateImage | None = None):
        if state is not None:
            from threemind_core.spec import DYNAMICS

            if state.to_dict().get("dynamics") != DYNAMICS:
                raise ValueError("Older dynamics are read-only; create a new causal/9 consciousness")
        from _threemind_native import NativeEngine as Native

        self._engine = Native(json.dumps((config or Config()).to_dict()), state.payload.decode() if state else None)

    @property
    def time_us(self):
        return int(self._engine.time_us())

    @property
    def sequence(self):
        return self._engine.sequence()

    @property
    def life(self):
        return self._engine.life()

    @property
    def config(self):
        return Config(**json.loads(self._engine.config_json()))

    def inject(self, stimulus: Stimulus):
        return self._engine.inject(json.dumps(stimulus.to_dict()))

    def close_inputs(self):
        self._engine.close_inputs()

    def supply_energy(self, amount, *, time_us=None, source="external-energy"):
        from threemind_core.energy import supply_payload
        from threemind_core.spec import timestamp

        payload = supply_payload(amount, source)
        when = self.time_us if time_us is None else timestamp(time_us)
        return self._engine.supply_energy(str(when), payload["amount"], payload["source"])

    def reconfigure(self, config: Config):
        self._engine.reconfigure(json.dumps(config.to_dict()))

    def modulate_input(self, *, time_us=None, **adjustment):
        from threemind_core.attention import modulation_payload
        from threemind_core.spec import timestamp

        payload = modulation_payload(**adjustment)
        when = self.time_us if time_us is None else timestamp(time_us)
        return self._engine.modulate_input(str(when), json.dumps(payload, allow_nan=False))

    def capture_state(self):
        return StateImage(self._engine.state_json().encode())

    def metrics(self):
        return json.loads(self._engine.metrics_json())

    def spatial_geometry(self):
        return json.loads(self._engine.spatial_geometry_json())

    def graph(self, limit=None):
        return json.loads(self._engine.graph_json(limit))

    def activations(self):
        return self._engine.activations()

    def observation_nodes(self):
        return json.loads(self._engine.observation_nodes_json())

    def induced_edges(self, node_ids):
        return json.loads(self._engine.induced_edges_json(list(node_ids)))

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        self._engine.intervene(list(nodes), [tuple(e) for e in edges], lesion, action)

    def advance_to(self, target_us, observer=None, *, inputs_only=False):
        rows = self._engine.advance(str(target_us), observer is not None, inputs_only)
        if observer is not None:
            for row in json.loads(rows):
                observer(row)


def create_engine(
    config=None, state: StateImage | None = None, *, backend: str = "native", kernel_id: str | None = None
):
    from threemind_kernels.registry import creation_kernel, state_kernel

    descriptor = state_kernel(state) if state is not None and kernel_id is None else creation_kernel(kernel_id, config)
    return descriptor.create(config, state, backend=backend)


class Runtime:
    def __init__(self, engine, *, clock: str = "realtime", speed: float = 1.0):
        if clock not in ("realtime", "scaled", "unbounded") or not 0 < speed < float("inf"):
            raise ValueError("invalid clock policy")
        self.engine = engine
        self.clock = clock
        self.speed = 1.0 if clock == "realtime" else speed
        self.anchor_host = time.monotonic_ns()
        self.anchor_sim = engine.time_us

    def pace(self, target_us: int) -> None:
        if self.clock == "unbounded":
            return
        elapsed = (time.monotonic_ns() - self.anchor_host) / 1e9
        ahead = (target_us - self.anchor_sim) / 1e6 / self.speed - elapsed
        if ahead > 0:
            time.sleep(min(ahead, 0.05))

    def reset_clock(self) -> None:
        self.anchor_host, self.anchor_sim = time.monotonic_ns(), self.engine.time_us
