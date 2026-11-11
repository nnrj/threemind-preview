"""Verified, immutable state references supplied by a persistence host.

The Core never reads a database. A host may release a dead engine once its state
is durable and provide an on-demand reader for that exact image. Observation is
still complete; this layer does not classify or remove nodes or connections.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from threemind_core import StateImage

from .host import create_engine


@dataclass(frozen=True, slots=True, eq=False)
class StateReference:
    digest: str
    reader: Callable[[], StateImage]

    def __post_init__(self):
        if not re.fullmatch("[0-9a-f]{64}", self.digest) or not callable(self.reader):
            raise ValueError("an immutable state reference requires a digest and reader")

    def materialize(self):
        image = self.reader()
        if not isinstance(image, StateImage) or image.digest != self.digest:
            raise ValueError("archived state checksum mismatch")
        return image

    @property
    def payload(self):
        return self.materialize().payload

    def to_dict(self):
        return self.materialize().to_dict()

    def __eq__(self, other):
        if isinstance(other, (StateReference, StateImage)):
            return self.digest == other.digest
        return NotImplemented

    __hash__ = None


class FrozenCore:
    """Only an actually dead Core can be replaced by this read-only view."""

    life = "dead"

    def __init__(self, engine, state: StateReference, *, backend="native"):
        if engine.life != "dead" or engine.capture_state().digest != state.digest:
            raise ValueError("only the exact, durably stored dead core can be archived")
        self.state, self.backend = state, backend
        self.time_us, self.sequence, self.config = engine.time_us, engine.sequence, engine.config
        self.dynamics = getattr(engine, "dynamics", state.to_dict()["dynamics"])
        self._metrics = deepcopy(engine.metrics())

    def capture_state(self):
        return self.state

    def metrics(self):
        return deepcopy(self._metrics)

    def _read(self, method, *args):
        engine = create_engine(state=self.state.materialize(), backend=self.backend)
        return getattr(engine, method)(*args)

    def observation_nodes(self):
        return self._read("observation_nodes")

    def induced_edges(self, node_ids):
        return self._read("induced_edges", node_ids)

    def graph(self, limit=None):
        return self._read("graph", limit)

    def spatial_geometry(self):
        return self._read("spatial_geometry")

    def activations(self):
        return self._read("activations")

    def _closed(self, *args, **kwargs):
        raise ValueError("an archived dead core cannot receive mutations or be resumed")

    inject = supply_energy = modulate_input = intervene = reconfigure = close_inputs = advance_to = _closed
