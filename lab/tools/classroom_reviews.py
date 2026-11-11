"""Whole-lesson, per-concept expanding reviews; explicitly timed and exportable."""
from collections import Counter
import random


def classroom_reviews(seed=37, mode='spaced'):
    if mode not in ('spaced', 'uniform'): raise ValueError('review schedule')
    rng = random.Random(seed)
    shapes, colors = list(range(4)), list(range(4,8))
    rng.shuffle(shapes); rng.shuffle(colors); order = shapes+colors
    rows = []
    for slot, item in enumerate(order):
        for rep in range(12):
            rows.append({'time_us': round((slot*18+rep*1.5)*1e6), 'item':item, 'phase':'initial'})
    middle = []
    start = 144.
    for gap in (12., 24., 48., 96.):
        for repeat in range(2):
            for slot, item in enumerate(order):
                middle.append({'time_us': round((start+repeat*gap+slot*1.5)*1e6),
                               'item':item, 'phase':f'review-{int(gap)}s'})
        start += 2*gap
    if mode == 'uniform':
        # Same item order, presentations, lesson duration and final review;
        # only the middle 64 start times change (44.8 s within each review cycle).
        for i,row in enumerate(middle): row['time_us'] = round((144+i*5.6)*1e6)
    rows += middle
    for slot,item in enumerate(order):
        rows.append({'time_us':round((start+slot*1.5)*1e6), 'item':item,'phase':'matched-final'})
    counts, previous = Counter(), {}
    for row in rows:
        item = row['item']; counts[item] += 1
        row['presentation'] = counts[item]
        row['since_same_item_us'] = row['time_us']-previous[item] if item in previous else None
        previous[item] = row['time_us']
    return rows
