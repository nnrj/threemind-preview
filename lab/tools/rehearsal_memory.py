"""Bounded teacher-example retention; never an inference input or Core rule."""
import copy
import numpy as np


class RehearsalMemory:
    VERSION = 'threemind.teacher-rehearsal/1'
    MODES = ('recent', 'reservoir', 'representative')

    def __init__(self, mode, capacity, seed, *, anchors=0, seen=0):
        if mode not in self.MODES or not 16 <= capacity <= 2048:
            raise ValueError('declared bounded rehearsal policy')
        self.mode, self.capacity = mode, capacity
        self.anchors, self.seen = anchors, seen
        self.rng = np.random.default_rng(seed)

    def initialize(self, xs, ys, *, correct=None):
        if len(xs) != len(ys) or len(xs) > self.capacity:
            raise ValueError('aligned existing teacher cache')
        self.seen = len(xs)
        if self.mode != 'representative' or not xs:
            return list(xs), list(ys)
        # Preserve correctly translated examples first, then target coverage.
        # Targets are permitted training supervision, never supplied to intent().
        y = np.asarray(ys).reshape(len(ys), -1)
        pool = list(np.flatnonzero(correct)) if correct is not None else list(range(len(y)))
        selected = []
        for candidates in (pool, list(range(len(y)))):
            while len(selected) < min(self.capacity//2, len(y)):
                remaining = [i for i in candidates if i not in selected]
                if not remaining: break
                if not selected: pick = remaining[0]
                else:
                    distances = ((y[remaining, None]-y[selected])**2).sum(-1).min(-1)
                    pick = remaining[int(distances.argmax())]
                selected.append(pick)
        self.anchors = len(selected)
        order = selected+[i for i in range(len(y)) if i not in selected]
        return [xs[i] for i in order], [ys[i] for i in order]

    def append(self, xs, ys, x, y):
        self.seen += 1
        if len(xs) < self.capacity:
            xs.append(x.copy()); ys.append(y.copy()); return
        if self.mode == 'reservoir':
            i = int(self.rng.integers(self.seen))
            if i < self.capacity: xs[i], ys[i] = x.copy(), y.copy()
        else:
            i = self.anchors if self.mode == 'representative' else 0
            xs.pop(i); ys.pop(i); xs.append(x.copy()); ys.append(y.copy())

    def indices(self, length, batch, rng):
        if self.mode != 'representative' or not 0 < self.anchors < length:
            return rng.integers(length, size=batch)
        n = batch//2
        return np.r_[rng.integers(self.anchors, size=n),
                     rng.integers(self.anchors, length, size=batch-n)]

    def state(self):
        return dict(schema=self.VERSION, mode=self.mode, capacity=self.capacity,
                    anchors=self.anchors, seen=self.seen, rng=copy.deepcopy(self.rng.bit_generator.state))

    @classmethod
    def restore(cls, state):
        if state['schema'] != cls.VERSION: raise ValueError('rehearsal version')
        obj = cls(state['mode'], state['capacity'], 0, anchors=state['anchors'], seen=state['seen'])
        obj.rng.bit_generator.state = state['rng']
        return obj
