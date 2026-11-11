"""Bounded database checkpoint deltas and one ordered persistence worker.

This is a checkpoint representation inside PostgreSQL, not a second WAL or a
public model format. Every exported model is a self-contained .tmind or JSON.
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor

from threemind_core import StateImage
from threemind_runtime import ArtifactCodec

MAX_DEPTH = 8
MAX_EXPANDED = 512 * 1024 * 1024
MAGIC = b"TMDELTA1"
KEYS = {"nodes": ("id",), "edges": ("source", "target")}


def key(row, table):
    return tuple(row[k] for k in KEYS[table])


def same_row(a, b):
    # JSON numeric equality alone loses -0.0 and int/float distinctions in the
    # canonical state hash. No tolerance is appropriate for recovery data.
    return a == b and all(
        type(value) is type(b[k])
        and (not isinstance(value, float) or value != 0 or math.copysign(1, value) == math.copysign(1, b[k]))
        for k, value in a.items()
    )


def changes(before, after):
    result = {}
    for table in KEYS:
        old = {key(r, table): r for r in before[table]}
        updated = []
        ordered, last_key = True, ()
        for row in after[table]:
            row_key = key(row, table)
            ordered &= last_key < row_key
            last_key = row_key
            previous = old.pop(row_key, None)
            if previous is None or not same_row(row, previous):
                updated.append(row)
        result[table] = {
            "upsert": updated,
            "delete": sorted(old),
            "order": None if ordered else [key(r, table) for r in after[table]],
        }
    return result


def encode(state, state_hash, previous=None):
    if state.get("dynamics") == "unified-associative":
        # Its raw package owns the graph and queued frame metadata. Modern row
        # deltas would create two competing representations of the same state.
        return ArtifactCodec._encode_binary(state, state_hash), "tmind/2", 0, None
    # A small deterministic sample can choose the always-correct full path.
    # It never decides which rows to omit. Dense training should not pay for a
    # Python comparison of every row before writing the same full checkpoint.
    estimated_changes = 0
    size = max(1, sum(len(state[t]) for t in KEYS))
    if previous and size > 1024:
        for table in KEYS:
            before, after = previous[1][table], state[table]
            if len(before) == len(after) and after:
                indices = range(0, len(after), max(1, len(after) // 64))
                estimated_changes += len(after) * sum(not same_row(before[i], after[i]) for i in indices) / len(indices)
    patch = changes(previous[1], state) if previous and estimated_changes < size * 0.5 else None
    depth = previous[0].get("delta_depth", 0) if previous else MAX_DEPTH
    changed = sum(len(p["upsert"]) + len(p["delete"]) for p in patch.values()) if patch else 0
    if patch is not None and depth < MAX_DEPTH and changed <= size * 0.25:
        document = {
            "base_hash": previous[0]["state_hash"],
            "state_hash": state_hash,
            "state": {k: v for k, v in state.items() if k not in KEYS},
            "tables": patch,
        }
        payload = json.dumps(document, allow_nan=False, separators=(",", ":")).encode()
        if len(payload) <= MAX_EXPANDED:
            raw = MAGIC + struct.pack(">Q", len(payload)) + zlib.compress(payload, level=3)
            return raw, "row-delta/1", depth + 1, patch
    return ArtifactCodec._encode_binary(state, state_hash), "tmind/2", 0, patch


def apply_delta(raw, image):
    state = image.to_dict()
    if state.get("dynamics") == "unified-associative":
        raise ValueError("historical unified checkpoints require a full original package")
    if len(raw) < 16 or raw[:8] != MAGIC:
        raise ValueError("invalid checkpoint delta header")
    size = struct.unpack(">Q", raw[8:16])[0]
    if size > MAX_EXPANDED:
        raise ValueError("checkpoint delta exceeds expansion budget")
    decoder = zlib.decompressobj()
    payload = decoder.decompress(raw[16:], size + 1)
    if len(payload) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("incomplete or oversized checkpoint delta")
    delta = json.loads(payload)
    if delta["base_hash"] != image.digest:
        raise ValueError("checkpoint delta base checksum failed")
    for table in KEYS:
        rows = {key(row, table): row for row in state[table]}
        for deleted in delta["tables"][table]["delete"]:
            del rows[tuple(deleted)]
        for row in delta["tables"][table]["upsert"]:
            rows[key(row, table)] = row
        order = delta["tables"][table].get("order")
        state[table] = [rows[tuple(k)] for k in order] if order is not None else [rows[k] for k in sorted(rows)]
    state = {**delta["state"], **{t: state[t] for t in KEYS}}
    restored = StateImage.from_dict(state)
    if restored.digest != delta["state_hash"]:
        raise ValueError("checkpoint delta state checksum failed")
    return restored


class CheckpointWriter:
    """At most one submitted immutable snapshot. A full slot applies backpressure.

    Capture and the numerical engine remain on the simulation thread. This
    thread alone owns decoded previous state, encoding, and ordered commits.
    Terminal status and export barriers are acknowledged only after drain().
    """

    def __init__(self, db, project, run_id, revision, *, job=None, previous=None):
        self.db, self.project, self.run_id, self.job = db, project, run_id, job
        self.revision, self.previous = revision, previous
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="checkpoint")
        self.pending = None

    def drain(self):
        if self.pending is not None:
            self.pending.result()  # Failure is propagated; never acknowledge a lost batch.
            self.pending = None

    def submit(self, image, **kwargs):
        self.drain()
        self.pending = self.executor.submit(self._commit, image, kwargs)

    def _commit(self, image, kwargs):
        state = image.to_dict()
        events = list(kwargs.pop("events", ()))
        if self.previous is not None:
            old = {key(e, "edges") for e in self.previous[1]["edges"]}
            new = {key(e, "edges") for e in state["edges"]}
            if old != new:
                events.append(
                    {
                        "key": f"structure:{self.revision + 1}",
                        "time_us": state["time_us"],
                        "kind": "structure_interval",
                        "payload": {
                            "from_time_us": self.previous[1]["time_us"],
                            "created": [list(e) for e in sorted(new - old)],
                            "removed": [list(e) for e in sorted(old - new)],
                            "quality": "checkpoint interval; replay for exact event times",
                        },
                    }
                )
        cp = self.db.save_checkpoint(
            self.project,
            self.run_id,
            image,
            expected_revision=self.revision,
            job=self.job,
            events=events,
            previous=self.previous,
            captured=state,
            **kwargs,
        )
        self.revision, self.previous = cp["revision"], (cp, state)

    def close(self):
        try:
            self.drain()
        finally:
            self.executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
