"""Stable non-overlapping u32 receptor identities, independent of graph topology."""

import hashlib

from .adapters import channel_id


class ReceptorWiring:
    def __init__(self, seed: int):
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("sensory seed must be a u32 integer")
        self.seed = seed
        reserved = [
            channel_id(seed, ns, i)
            for ns, count in (("planar-physical-v1", 16), ("host-physical-v1", 4))
            for i in range(count)
        ]
        attempt = 0
        while True:
            digest = hashlib.sha256(f"receptor-u32/1:{seed}:{attempt}".encode()).digest()
            self.multiplier = int.from_bytes(digest[:4], "big") | 1
            self.offset = int.from_bytes(digest[4:8], "big")
            inverse = pow(self.multiplier, -1, 2**32)
            if all(((c - self.offset) * inverse) % 2**32 >= 2**27 for c in reserved):
                break
            attempt += 1

    def identity(self, receptor: int) -> int:
        return (self.multiplier * receptor + self.offset) % 2**32
