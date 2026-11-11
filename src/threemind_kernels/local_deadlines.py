"""Indexed local timers: changing one owner never scans unrelated timers."""


class LocalDeadlines:
    def __init__(self):
        self.heap = []
        self.positions = {}

    def _swap(self, a, b):
        self.heap[a], self.heap[b] = self.heap[b], self.heap[a]
        self.positions[self.heap[a][1]] = a
        self.positions[self.heap[b][1]] = b

    def _fix(self, i):
        while i and self.heap[i] < self.heap[(i - 1) // 2]:
            j = (i - 1) // 2
            self._swap(i, j)
            i = j
        while 2 * i + 1 < len(self.heap):
            j = 2 * i + 1
            if j + 1 < len(self.heap) and self.heap[j + 1] < self.heap[j]:
                j += 1
            if self.heap[i] <= self.heap[j]:
                break
            self._swap(i, j)
            i = j

    def discard(self, key):
        i = self.positions.pop(key, None)
        if i is None:
            return
        last = self.heap.pop()
        if i < len(self.heap):
            self.heap[i] = last
            self.positions[last[1]] = i
            self._fix(i)

    def set(self, key, when):
        self.discard(key)
        if when is not None:
            self.positions[key] = len(self.heap)
            self.heap.append((when, key))
            self._fix(len(self.heap) - 1)

    def due(self, when):
        while self.heap and self.heap[0][0] <= when:
            _, key = self.heap[0]
            self.discard(key)
            yield key

    def rows(self):
        return [[kind, a, b, str(t)] for t, (kind, a, b) in sorted(self.heap)]
