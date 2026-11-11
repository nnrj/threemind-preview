"""Versioned developmental geometry; never creates edges from proximity alone."""

import hashlib
import math

from .spec import SPATIAL_DEFAULTS, Config

COORDINATE_RULE = "threemind.sha256-id-axis/1"


def position(seed: int, node_id: int, dimensions: int) -> list[float]:
    return [
        int.from_bytes(hashlib.sha256(f"{COORDINATE_RULE}:{seed}:{node_id}:{axis}".encode("ascii")).digest()[:4], "big")
        / 2**31
        - 1.0
        for axis in range(dimensions)
    ]


class Spatial:
    def __init__(self):
        self.identity = None
        self.positions = {}

    def sync(self, config: Config, nodes):
        identity = (config.spatial_embedding, config.seed, config.spatial_dimensions)
        if identity != self.identity:
            self.positions = {}
            self.identity = identity
        if config.spatial_embedding:
            for node in nodes:
                if node not in self.positions:
                    self.positions[node] = position(config.seed, node, config.spatial_dimensions)
            if len(self.positions) > len(nodes):
                self.positions = {k: v for k, v in self.positions.items() if k in nodes}

    def distance(self, source, target):
        return math.sqrt(
            sum((a - b) * (a - b) for a, b in zip(self.positions[source], self.positions[target], strict=True))
        )

    def allowed(self, config, source, target):
        return (
            not (config.spatial_embedding and config.neighborhood_enabled)
            or self.distance(source, target) <= config.spatial_radius
        )

    def attenuation(self, config, source, target):
        if not (config.spatial_embedding and config.neighborhood_enabled):
            return 1.0
        return max(0.0, 1.0 - self.distance(source, target) / config.spatial_radius)

    def summary(self, config, nodes, edges):
        result = {
            "schema": "threemind.spatial-observation/1",
            "coordinate_rule": COORDINATE_RULE,
            "parameters": {key: getattr(config, key) for key in SPATIAL_DEFAULTS},
            "seed": config.seed,
            "neighbor_edges": None,
            "clusters": None,
            "isolated_nodes": None,
        }
        if not config.spatial_embedding:
            return result
        self.sync(config, nodes)
        labels, count, connected = self.components(config, nodes, edges)
        result.update(
            neighbor_edges=count, clusters=len(set(labels.values())), isolated_nodes=len(nodes) - len(connected)
        )
        return result

    def components(self, config, nodes, edges):
        parents = {node: node for node in nodes}

        def find(node):
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        connected, count = set(), 0
        for source, target in edges:
            if self.distance(source, target) <= config.spatial_radius:
                count += 1
                connected.update((source, target))
                a, b = find(source), find(target)
                parents[max(a, b)] = min(a, b)
        return {n: find(n) for n in nodes}, count, connected

    def geometry(self, config, nodes, edges):
        result = self.summary(config, nodes, edges)
        result.update(nodes=[], edges=[])
        if not config.spatial_embedding:
            return result
        labels, _, _ = self.components(config, nodes, edges)
        result["nodes"] = [{"id": n, "position": list(self.positions[n]), "cluster": labels[n]} for n in sorted(nodes)]
        result["edges"] = [
            {
                "source": a,
                "target": b,
                "distance": self.distance(a, b),
                "within_radius": self.distance(a, b) <= config.spatial_radius,
            }
            for a, b in sorted(edges)
        ]
        return result
