"""Replay an immutable acquisition with original timestamps and input amounts."""

import json
from dataclasses import replace

from threemind_core import Stimulus


class RecordedBackground:
    def __init__(self, path):
        self.rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        times = [int(r["time_us"]) for r in self.rows]
        if not times or times != sorted(times):
            raise ValueError("nonempty chronological recording required")
        for row in self.rows:
            if row["stimulus"] and int(row["stimulus"]["time_us"]) != int(row["time_us"]):
                raise ValueError("recorded delivery time mismatch")

    def queue_before(self, reader, cursor, end_us):
        """Half-open interval: checkpoints precede inputs at exactly their time."""
        while cursor < len(self.rows) and int(self.rows[cursor]["time_us"]) < end_us:
            row = self.rows[cursor]
            when = int(row["time_us"])
            if when < reader.engine.time_us:
                raise ValueError("recorded input would be delivered late or twice")
            if row["stimulus"]:
                stimulus = replace(Stimulus.from_dict(row["stimulus"]), time_us=0)
                reader.schedule(
                    [{"stimulus": stimulus, "labels": {}}],
                    at=when,
                    source="recorded-physical-" + row["scope"],
                    adapter_id=row["scope"] + "-telemetry",
                )
            cursor += 1
        return cursor
