"""External dose controls and physical-template activity observation.

No engine access or semantic routing. Callers must record these explicit input
interventions separately from their underlying sensory protocol.
"""

from dataclasses import dataclass, replace

import numpy as np

DOSE_VERSION = "threemind.language-dose-study/1"
READER_VERSION = "threemind.sensory-response-library/1"


def matched_frames(frames, amount, *, repetitions=None, collapse=False, reverse=False, interval_us=20000):
    """Normalize channel amounts; leave the explicit intensity unchanged."""
    frames = list(frames)
    if not frames or not np.isfinite(amount) or amount <= 0:
        raise ValueError("nonempty frames and positive finite amount required")
    if repetitions is not None:
        if len(frames) != 1 or type(repetitions) is not int or not 1 <= repetitions <= 2048:
            raise ValueError("repetition requires one frame and bounded positive count")
        frames = frames * repetitions
    if reverse:
        frames = frames[::-1]
    total = sum(v for row in frames for _, v in row["stimulus"].channels)
    if total <= 0 or interval_us <= 0:
        raise ValueError("positive channel amount and cadence required")
    result = [{"stimulus": replace(row["stimulus"], time_us=i * interval_us,
               channels=tuple((c, v * amount / total) for c, v in row["stimulus"].channels)),
               "labels": {}} for i, row in enumerate(frames)]
    if collapse:
        # Preserve individual legal amplitudes and intensity-dependent learning.
        # Same-time separate deliveries are NOT a merged, higher-intensity event.
        result = [{"stimulus":replace(row["stimulus"],time_us=0),"labels":{}} for row in result]
    return result


def paired_visual(frames, visual, total_amount):
    """Explicit common acquisition, distributing a fixed visual dose over frames."""
    total = sum(v for row in frames for _, v in row["stimulus"].channels)
    visual_total = sum(v for _, v in visual.channels)
    if total <= 0 or visual_total <= 0 or total_amount <= 0:
        raise ValueError("positive language and visual amounts required")
    result = []
    for row in frames:
        stimulus = row["stimulus"]
        channels = dict(stimulus.channels)
        if channels.keys() & dict(visual.channels).keys():
            raise ValueError("sensory channel collision")
        share = sum(channels.values()) / total
        channels.update((c, v / visual_total * total_amount * share) for c, v in visual.channels)
        result.append({"stimulus": replace(stimulus, channels=tuple(sorted(channels.items()))), "labels": {}})
    return result


def process_vector(process, channels, *, start_us=None, end_us=None):
    """Time-weighted trapezoid, including all samples; no stable-window gate."""
    index = {c: i for i, c in enumerate(channels)}
    frames = process["trajectory"]
    if not frames:
        return np.zeros(len(channels))
    start = int(process["start_us"]) if start_us is None else start_us
    end = int(process["end_us"]) if end_us is None else end_us
    if end <= start:
        raise ValueError("positive integration window")
    times, values = [], []
    for frame in frames:
        row = np.zeros(len(channels))
        for node in frame["nodes"]:
            offset = index.get(int(node["channel"]))
            if offset is not None:
                row[offset] += float(node["activation"])
        times.append(int(frame["time_us"]))
        values.append(row)
    times, values = np.asarray(times), np.asarray(values)
    if np.any(np.diff(times) < 0) or times[0] > start or times[-1] < end:
        raise ValueError("observation does not cover requested interval")
    points = np.unique(np.r_[start, times[(times > start) & (times < end)], end])
    sampled = np.column_stack([np.interp(points, times, values[:, i]) for i in range(len(channels))])
    return np.trapezoid(sampled, points, axis=0) / (end - start)


@dataclass
class SensoryResponseLibrary:
    channels: tuple[int, ...]
    prototypes: np.ndarray
    schema: str = READER_VERSION

    def __post_init__(self):
        self.channels = tuple(self.channels)
        self.prototypes = np.asarray(self.prototypes, dtype=float)
        if self.schema != READER_VERSION or self.prototypes.ndim != 2 or self.prototypes.shape[1] != len(self.channels):
            raise ValueError("invalid sensory response library")
        if len(set(self.channels)) != len(self.channels) or not np.isfinite(self.prototypes).all():
            raise ValueError("invalid channels or prototypes")

    def read(self, activity):
        activity = np.asarray(activity, dtype=float)
        if activity.shape != (len(self.channels),) or not np.isfinite(activity).all():
            raise ValueError("activity shape or values")
        contrast = self.prototypes - self.prototypes.mean(axis=0)
        contrast /= np.maximum(1e-12, np.linalg.norm(contrast, axis=1))[:, None]
        scores = contrast @ activity
        order = np.argsort(-scores)
        identifiable = scores[order[0]] > 1e-8 and scores[order[0]] - scores[order[1]] > 1e-8
        return {"scores": scores.tolist(), "prediction": int(order[0]) if identifiable else None,
                "activity_l1": float(np.abs(activity).sum()), "schema": self.schema,
                "interpretation": "external physical-sample comparison; no subjective-image claim"}

    def to_dict(self):
        return {"schema": self.schema, "channels": list(self.channels), "prototypes": self.prototypes.tolist()}


def main():
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--input", required=True, help="JSONL processes")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    library = SensoryResponseLibrary(**json.loads(Path(args.library).read_text(encoding="utf-8")))
    with Path(args.input).open(encoding="utf-8") as source, Path(args.output).open("x", encoding="utf-8") as out:
        for index, line in enumerate(source):
            if index >= 16384 or len(line) > 16 * 2**20:
                raise ValueError("split large observations into bounded batches")
            row = json.loads(line)
            out.write(json.dumps(library.read(process_vector(row, library.channels)), allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
