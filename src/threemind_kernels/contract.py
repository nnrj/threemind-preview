from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, runtime_checkable

from threemind_core import StateImage, Stimulus


@runtime_checkable
class Kernel(Protocol):
    """Execution contract; concrete state/observation quantities belong to each kernel.

    time_us is simulation time. Implementations must preserve in-flight messages,
    operator histories and clock phase in capture_state. Observation is read-only.
    Backend changes may require declared floating-point tolerances, never new laws.
    """

    @property
    def time_us(self) -> int: ...

    @property
    def sequence(self) -> int: ...

    @property
    def life(self) -> str: ...

    @property
    def config(self) -> Any: ...

    def inject(self, stimulus: Stimulus) -> int: ...

    def advance_to(
        self, target_us: int, observer: Callable[[dict], None] | None = None, *, inputs_only: bool = False
    ) -> None: ...

    def capture_state(self) -> StateImage: ...

    def reconfigure(self, config: Any) -> None: ...

    def metrics(self) -> dict: ...

    def graph(self, limit: int | None = None) -> dict: ...

    def activations(self) -> list: ...

    def observation_nodes(self) -> list[dict]: ...

    def induced_edges(self, node_ids: Iterable[int]) -> list[dict]: ...

    def close_inputs(self) -> None: ...

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None) -> None: ...
