from collections import Counter
from itertools import pairwise

from lab.tools.spaced_reviews import schedule


def test_per_item_spacing_dose_and_matched_last_review():
    sentences = ["甲是松子。", "乙是铃铛。", "丁是陶杯。", "戊是柳叶。"]
    spaced, massed = [schedule(sentences, 17, mode) for mode in ("spaced", "massed")]
    assert Counter(r["text"] for r in spaced) == Counter({s: 57 for s in sentences})
    assert Counter(r["text"] for r in spaced) == Counter(r["text"] for r in massed)
    assert [(r["text"], r["time_us"]) for r in spaced[-4:]] == [(r["text"], r["time_us"]) for r in massed[-4:]]
    for phase, gap in enumerate((0.5, 2, 4, 8, 16, 32), 1):
        for item in range(4):
            times = [r["time_us"] for r in spaced if r["phase"] == phase and r["item"] == item]
            assert all(b - a == gap * 1e6 for a, b in pairwise(times))
    assert all(r["text"] in sentences for r in spaced)
    assert schedule(sentences, 17, "none") == []
