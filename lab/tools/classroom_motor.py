"""Grounded pointing curricula and observer windows, never Core dynamics.

Explicit teacher forces belong to demonstrations only. Scene identities and
target coordinates are not arguments of the motor inference interface.
"""
from collections import Counter
import random
import numpy as np

PAIRS=tuple((s,c) for s in range(4) for c in range(4) if s!=c)


def motor_reviews(seed=83):
    order=list(range(len(PAIRS)));random.Random(seed).shuffle(order)
    rows=[]
    for slot,item in enumerate(order):
        for repeat in range(12):
            rows.append({'time_us':(slot*36+repeat*3)*1000000,'item':item,'phase':'initial'})
    for start,gap in ((432,36),(504,72),(648,144)):
        for slot,item in enumerate(order):
            rows.append({'time_us':(start+3*slot)*1000000,'item':item,'phase':f'review-{gap}s'})
    counts,previous=Counter(),{}
    for row in rows:
        item=row['item'];counts[item]+=1
        row.update(pair=list(PAIRS[item]),presentation=counts[item],
            since_same_item_us=row['time_us']-previous[item] if item in previous else None)
        previous[item]=row['time_us']
    return rows


def choice_scene(shape,color,target_slot,layout=0):
    """Four objects requiring both features; no majority or sole-colour cue."""
    offset=1+(layout%3)
    other_s=(shape+offset)%4;other_c=(color+offset)%4
    distractors=[(shape,other_c),(other_s,color),(other_s,other_c)]
    rng=np.random.default_rng(3307+layout*17+shape*5+color)
    rng.shuffle(distractors)
    items=[]
    for slot in range(4):items.append((shape,color) if slot==target_slot else distractors.pop())
    return items


def raw_process_window(layout,history,scope):
    """Select actual frames without subtraction, labels, or amplitude scaling."""
    if scope=='recent':
        if len(history)<4:raise ValueError('four actual frames required')
        selected=history[-4:]
    elif scope=='episode':
        if len(history)<16:raise ValueError('sixteen actual frames required')
        selected=[history[i] for i in np.rint(np.linspace(0,len(history)-1,16)).astype(int)]
    else:raise ValueError('explicit process scope')
    return np.stack([layout.frame(row['activity']) for row in selected])
