"""Explicit per-item review schedules; no inference about the model's memory."""

import random
from collections import Counter

PHASE_ENDS = (24, 48, 80, 144, 272, 528)


def schedule(sentences, seed, mode="spaced"):
    """Four intact sentences, 56 presentations each plus one common last review.

    Spacing is a research schedule, not a fitted human forgetting curve.
    The concentrated control matches dose, total elapsed time and final review.
    """
    if len(sentences) != 4 or len(set(sentences)) != 4 or mode not in ("spaced", "massed", "none"):
        raise ValueError("four distinct intact sentences and a supported schedule required")
    if mode == "none":
        return []
    order = list(range(4))
    random.Random(seed).shuffle(order)
    rows = []

    def add(at, index, phase):
        rows.append({"time_us": round(at * 1e6), "item": index, "text": sentences[index], "phase": phase})

    if mode == "spaced":
        for slot, index in enumerate(order):
            for repetition in range(12):
                add(slot * 6 + repetition * 0.5, index, 1)
        for phase, (start, count, per_item) in enumerate(
            ((24, 12, 2), (48, 8, 4), (80, 8, 8), (144, 8, 16), (272, 8, 32)), 2
        ):
            for repetition in range(count):
                for slot, index in enumerate(order):
                    add(start + repetition * per_item + slot * per_item / 4, index, phase)
    else:
        for slot, index in enumerate(order):
            for repetition in range(56):
                add((slot * 56 + repetition) * 0.5, index, "massed")
    for slot, index in enumerate(order):
        add(528 + slot * 0.5, index, "matched-final-review")
    rows.sort(key=lambda row: row["time_us"])
    counts = Counter()
    previous = {}
    for row in rows:
        item = row["item"]
        counts[item] += 1
        row["presentation"] = counts[item]
        row["since_same_item_us"] = row["time_us"] - previous[item] if item in previous else None
        previous[item] = row["time_us"]
    return rows
