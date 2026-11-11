"""Read-only controls for choosing from raw stimuli versus Core activity.

Zero padding matches an existing four-field model's parameter count; it is not
a generated neural observation and is never submitted to Core or its bus.
"""
import numpy as np
from lab.tools.activity_controller import ActivityLayout


def incoming_frame(layout: ActivityLayout, stimulus):
    values = np.zeros((len(layout.channels), 4), dtype=np.float32)
    intensity = float(stimulus['intensity'])
    for channel, amount in stimulus['channels']:
        values[layout.index[int(channel)], 0] += float(amount) * intensity
    if not np.isfinite(values).all():
        raise ValueError('nonfinite incoming stimulus')
    return values.ravel()


def raw_window(layout, rows, *, kind='activity', count=8):
    if not rows or kind not in ('activity', 'incoming'):
        raise ValueError('nonempty process and explicit input source')
    indexes = range(len(rows)) if count is None else np.rint(np.linspace(0, len(rows)-1, count)).astype(int)
    return np.stack([layout.frame(rows[i]['activity']) if kind == 'activity'
                     else incoming_frame(layout, rows[i]['stimulus']) for i in indexes])


def paired_scores(predictions, targets):
    """History-major arrays: two histories x identical current situations."""
    p, y = np.asarray(predictions), np.asarray(targets)
    if p.shape != y.shape or p.ndim != 2 or p.shape[0] != 2 or np.any(y[0] == y[1]):
        raise ValueError('two paired histories with conflicting targets required')
    return {'n': int(y.size), 'correct': int((p == y).sum()),
            'paired_both_correct': int(np.all(p == y, axis=0).sum()),
            'choices_changed': int((p[0] != p[1]).sum()),
            'history_free_ceiling': int(y.shape[1])}
