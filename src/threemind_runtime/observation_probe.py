"""Bounded same-source probe copies, extracted from repeated study scripts.

Interventions are explicit research operations on a copy; observation never
changes the source, kernel parameters, stimulus mapping or scientific defaults.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, replace
from itertools import islice

from .host import create_engine
from .readout_config import ActivityReadoutConfig
from .readout_session import ReadoutSession


@dataclass(frozen=True)
class ProbeBudget:
    simulation_us: int = 60_000_000
    wall_seconds: float = 120
    evidence_bytes: int = 64 * 1024**2
    rss_bytes: int = 4 * 1024**3

    def __post_init__(self):
        if any(type(v) not in (int, float) or not 0 < v < float("inf") for v in asdict(self).values()):
            raise ValueError("probe budgets must be positive and finite")


class ProbeLimit(RuntimeError):
    pass


def probe_copy(
    source, *, duration_us, frames=(), interventions=(), backend="native", reader=None, budget=None, policies=None
):
    """Observe one restored copy. Frames are existing decoded frames, offsets relative to its start.

    Compare a cue, no cue, silence and unsilence using separate calls with the
    same source. Returned audit includes every intervention and exact hashes.
    Pending Core events remain pending; external adapter state is not replayed.
    """
    import psutil

    budget = budget or ProbeBudget()
    if type(duration_us) is not int or not 1000 <= duration_us <= budget.simulation_us:
        raise ValueError("probe duration exceeds budget or is below 1 ms")
    started = time.monotonic()
    process = psutil.Process()
    events, evidence_bytes, audit = [], 0, []

    def guard():
        if time.monotonic() - started > budget.wall_seconds:
            raise ProbeLimit("wall time budget reached")
        if process.memory_info().rss > budget.rss_bytes:
            raise ProbeLimit("process memory budget reached")

    def record(value):
        nonlocal evidence_bytes
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
        if evidence_bytes + size > budget.evidence_bytes:
            raise ProbeLimit("evidence budget reached")
        evidence_bytes += size
        events.append(value)

    guard()
    engine = create_engine(state=source, backend=backend)
    for intervention in interventions:
        before = engine.capture_state().digest
        engine.intervene(**intervention)
        audit.append(
            {"operation": intervention, "before_sha256": before, "after_sha256": engine.capture_state().digest}
        )
    cfg = reader or ActivityReadoutConfig(
        analysis_version=2,
        interval_us=min(20000, duration_us),
        settle_us=min(800000, duration_us),
        min_response_us=min(1200000, duration_us),
        max_response_us=duration_us,
        periodic_max_samples=60,
    )
    cfg = replace(cfg, trigger_manual=False)
    session = ReadoutSession(
        engine,
        record=record,
        policies=policies,
        config={
            "structural_readout": {"enabled": False},
            "temporal_readout": {"enabled": False},
            "activity_readout": asdict(cfg),
        },
    )
    session.begin_observation("probe")
    # One manual observer window covers the whole probe. Frames remain actual
    # input envelopes but do not need to open a second per-carrier window.
    frames = list(islice(frames, 4097))
    if len(frames) > 4096 or sum(len(f["stimulus"].channels) for f in frames) > 100000:
        raise ProbeLimit("input frame/channel budget reached")
    if frames:
        session.schedule(frames, source="manual-anonymous", adapter_id="anonymous-frames")
    start = engine.time_us
    session.advance_to(start + duration_us, guard=guard)
    session.host.close(engine.time_us, "run_ended")
    final = engine.capture_state()
    return {
        "schema": "threemind.observation-probe/1",
        "source_sha256": source.digest,
        "final_sha256": final.digest,
        "final_state": final,
        "records": events,
        "interventions": audit,
        "target_reached": engine.time_us == start + duration_us,
        "budget": asdict(budget),
        "evidence_bytes": evidence_bytes,
        "wall_seconds": time.monotonic() - started,
        "external_adapter_state": "not included; use world/ecology Runtime for coupled environment replay",
    }
