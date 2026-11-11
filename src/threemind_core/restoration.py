"""causal/9 local operators, restored from Git 97d8592's V3 runtime.

Accepted departures: timestamp transport, independent physical pulse cadence,
sender-local accounting, traversal consolidation, and quiescence death.
The host owns labels, storage, semantic interpretations and wall-clock pacing.
"""

from __future__ import annotations

import heapq
import math


class RestoredDynamics:
    def _birth_novelty(self, source, target, connected):
        c = self.config
        reentry = max(self.nodes[source].associative, self.nodes[target].associative)
        return (
            c.local_novelty_gain * max(0.0, 1.0 - min(1.0, reentry / c.novelty_touch_reference))
            if reentry > 0 and (source in connected or target in connected)
            else 0.0
        )

    def _next_local_deadline(self):
        return None

    def _settle_local_arrivals(self):
        pass

    def _edge_consolidation_enabled(self):
        """Research variants may gate positive edge updates, never forgetting."""
        return True

    def _adaptive_retention_active(self):
        return False

    def _automatic_node_retention(self):
        return False

    def _prepare_edge(self, key):
        pass

    def _edge_changed(self, key):
        pass

    def _before_emit_node(self, node):
        pass

    def _legacy_edge_decayed(self, key):
        pass

    def _local_retention_enabled(self):
        return False

    def _node_became_quiet(self, node_id):
        pass

    def _support_changed(self, node_id):
        pass

    def _edge_capacity_used(self, key=None):
        return len(self.edges)

    def _saturate_inhibition(self, value):
        cap = self.config.inhibition_saturation
        return cap * math.tanh(max(0.0, value) / cap)

    def _inhibitory_response(self, node):
        if not self.config.inhibition:
            return 1.0
        return 1.0 / (1.0 + self.config.inhibition_response_gain * self._saturate_inhibition(node.inhibition))

    def _relax(self, when):
        dt = (when - self.state_time_us) / 1e6
        if dt <= 0:
            return
        c = self.config
        a = math.exp(-dt / c.activation_tau) if c.activation_decay_enabled else 1.0
        tr = math.exp(-dt / c.trace_tau) if c.trace_decay_enabled else 1.0
        inh = math.exp(-dt / c.inhibition_tau) if c.inhibition_decay_enabled else 1.0
        for n in self.nodes.values():
            was_active = n.activation > 0
            n.activation *= a
            n.trace *= tr
            n.inhibition *= inh
            if n.activation < c.activation_floor:
                n.activation = 0.0
            if was_active and n.activation == 0:
                self._node_became_quiet(n.id)
            if c.plasticity and c.support_decay_enabled and not self._automatic_node_retention():
                n.support = max(0.0, n.support - dt / c.support_tau * (1.0 - n.stability))
        self._maintain_energy(when, when - self.state_time_us)
        self.state_time_us = when

    def _touch(self, node_id, value, *, direct):
        if node_id not in self.nodes or node_id in self.silenced_nodes or value <= 0:
            return 0.0
        n, c = self.nodes[node_id], self.config
        arrived = value
        if direct and c.energy_simulation_enabled:
            arrived = self.energy.afford(value, c.energy_direct_cost, "direct")
        self.transport["received"] += arrived
        touch = arrived * self._inhibitory_response(n)
        delta = min(1.0 - n.activation, touch)
        n.activation += delta
        self.transport["activated"] += delta
        n.trace = min(1.0, n.trace + touch)
        if direct:
            n.direct = max(n.direct, touch)
        else:
            n.associative += touch
        if touch > 0:
            n.last_touch_us = str(self.time_us)
        return touch

    def _update_touched(self, touched):
        c = self.config
        for node_id, amount in touched:
            n = self.nodes[node_id]
            n.touches += 1
            n.last_touch_us = str(self.time_us)
            if c.plasticity:
                n.stability = min(1.0, n.stability + 0.5 * c.stability_gain * n.activation)
                if not self._automatic_node_retention():
                    n.support = min(1.0, n.support + c.support_gain * amount)
                n.local_plasticity = max(0.12, 1.0 - 0.72 * n.stability)
        if any(n.activation > 0 for n in self.nodes.values()):
            self.life = "active"
            self.quiet_since_us = None

    def _stimulate(self, stimulus):
        from .engine import Node

        c = self.config
        touched = []
        for channel, value in sorted(stimulus.channels):
            effective_drive = value * stimulus.intensity
            request = min(1.0, effective_drive * c.direct_gain)
            if request <= 0:
                continue
            node_id = self.receptors.get(channel)
            if node_id is None:
                if c.max_nodes is not None and len(self.nodes) >= c.max_nodes:
                    self.resources.increment("node_capacity_rejections")
                    continue
                node_id = self.next_node
                self.next_node += 1
                self.nodes[node_id] = Node(
                    node_id, channel, birth_us=str(self.time_us), last_touch_us=str(self.time_us)
                )
                self.receptors[channel] = node_id
            n = self.nodes[node_id]
            initial = n.touches == 0
            response = self._inhibitory_response(n)
            amount = self._touch(node_id, request, direct=True)
            fraction = amount / (request * response) if request * response > 0 else 0.0
            if amount > 0:
                impulse = min(
                    c.consolidation_cap,
                    effective_drive
                    * fraction
                    * n.local_plasticity
                    * (c.first_gain * initial + c.repeat_gain + c.intensity_gain * max(0.0, stimulus.intensity - 1.0)),
                )
                touched.append((node_id, amount, impulse))
        self._associate(touched)
        self._update_touched([(n, amount) for n, amount, _ in touched])

    def _associate(self, touched):
        from .engine import Edge

        c = self.config
        if not c.plasticity or not touched:
            return
        self.spatial.sync(c, self.nodes)
        sources = touched
        if c.edge_birth_policy == "temporal-association":
            impulses = {n: i for n, _, i in touched}
            sources = [
                (n.id, 0.0, impulses.get(n.id, 0.0))
                for n in sorted(self.nodes.values(), key=lambda n: n.id)
                if n.activation > 0
                and n.id not in self.silenced_nodes
                and (n.touches > 0 or n.id in impulses)
                and self.time_us - int(n.last_touch_us) <= c.association_window_us
            ]
        connected = {n for n, neighbours in self.incident.items() if neighbours}

        def candidates():
            for source, _, si in sources:
                for target, _, ti in touched:
                    if (
                        source == target
                        or (source, target) in self.silenced_edges
                        or not self.spatial.allowed(c, source, target)
                    ):
                        continue
                    score = self.nodes[source].activation * self.nodes[target].activation
                    if score > 0 and ((source, target) in self.edges or score >= c.edge_birth_activation_product_min):
                        yield score, source, target, si, ti

        choices = candidates()
        if c.edge_adaptation_limit is not None:
            available = self.resources.available_adaptations(
                self.time_us, c.propagation_interval_us, c.edge_adaptation_limit
            )
            selected, count = [], 0
            for score, source, target, si, ti in choices:
                count += 1
                item = (score, -source, -target, si, ti)
                if available:
                    if len(selected) < available:
                        heapq.heappush(selected, item)
                    elif item > selected[0]:
                        heapq.heapreplace(selected, item)
            self.resources.increment("adaptation_budget_skips", count - len(selected))
            choices = ((s, -a, -b, si, ti) for s, a, b, si, ti in sorted(selected, reverse=True))
        for score, source, target, si, ti in choices:
            if c.edge_adaptation_limit is not None:
                self.resources.use_adaptation(self.time_us, c.propagation_interval_us)
            key = source, target
            impulse = min(c.consolidation_cap, si + ti)
            if key not in self.edges:
                if c.max_edges is not None and self._edge_capacity_used(key) >= c.max_edges:
                    self.resources.increment("edge_capacity_rejections")
                    continue
                novelty = self._birth_novelty(source, target, connected)
                self.edges[key] = Edge(
                    source,
                    target,
                    min(1.0, c.birth_weight * (0.5 + score) + 0.18 * impulse + novelty),
                    stability=min(1.0, impulse + novelty),
                    eligibility=impulse,
                    birth_us=str(self.time_us),
                    last_touch_us=str(self.time_us),
                )
                self.outgoing.setdefault(source, set()).add(target)
                self.incident.setdefault(source, set()).add(target)
                self.incident.setdefault(target, set()).add(source)
                self._edge_changed(key)
                continue
            self._prepare_edge(key)
            e = self.edges[key]
            internal = 1.0 if key in self.traversed else 0.45
            if self._edge_consolidation_enabled():
                e.weight = min(1.0, e.weight + c.learning_rate * score * internal * (1.0 - e.weight) + 0.08 * impulse)
            e.eligibility = min(1.0, e.eligibility + 0.3 * score + 0.25 * impulse)
            # Traversal has its own accepted impulse below. Do not count it a second time here.
            if self._edge_consolidation_enabled():
                e.stability = min(1.0, e.stability + c.stability_gain * score * (1.0 + math.log1p(e.touches)) + impulse)
            e.touches += 1
            e.last_touch_us = str(self.time_us)
            self._edge_changed(key)

    def _generate_inhibition(self, baseline):
        if self.config.inhibition:
            for n in self.nodes.values():
                n.generated_inhibition += max(0.0, n.activation - baseline.get(n.id, 0.0)) * self.config.inhibition_gain

    def _spatial_competition(self):
        c = self.config
        dt = c.step_us / 1e6
        # Optional causal-space competition keeps its existing explicit boundary.
        if c.spatial_embedding and c.spatial_competition_rate > 0:
            self.spatial.sync(c, self.nodes)
            weak = {}
            for source, target in sorted(self.edges):
                if (
                    source in self.silenced_nodes
                    or target in self.silenced_nodes
                    or (source, target) in self.silenced_edges
                ):
                    continue
                if (
                    self.spatial.distance(source, target) <= c.spatial_radius
                    and self.nodes[source].activation > self.nodes[target].activation
                ):
                    weak[target] = weak.get(target, 0) + 1
            for node_id, count in weak.items():
                n = self.nodes[node_id]
                scale = math.exp(-c.spatial_competition_rate * dt * count)
                n.activation *= scale
                n.direct *= scale
                n.associative *= scale

    def _emit(self):
        c = self.config
        dt = c.propagation_interval_us / 1e6
        gain, diffusion = c.propagation_rate * dt, min(1.0, c.inhibition_diffusion_rate * dt)
        for n in self.nodes.values():
            if c.inhibition:
                n.inhibition = self._saturate_inhibition(n.inhibition + n.pending_inhibition)
                n.pending_inhibition = 0.0
            else:
                n.inhibition = n.pending_inhibition = n.generated_inhibition = 0.0
        signals, inhibitors, traversed = {}, {}, set()
        ordered = sorted(self.nodes.values(), key=lambda n: n.id)
        if c.propagation_limit is not None:
            ordered.sort(key=lambda n: (-n.activation, n.id))
        emissions = 0
        for n in ordered:
            if n.id in self.silenced_nodes:
                continue
            targets = sorted(self.outgoing.get(n.id, ()))
            if c.propagation_limit is not None:
                targets.sort(key=lambda target: (-self.edges[n.id, target].weight, target))
            for target in targets if n.activation > 0 and n.activation >= c.propagation_activation_min else ():
                key = n.id, target
                if key in self.silenced_edges:
                    continue
                e = self.edges[key]
                amount = n.activation * self._inhibitory_response(n) * e.weight * gain
                if c.spatial_embedding and c.neighborhood_enabled:
                    amount *= self.spatial.attenuation(c, n.id, target)
                if amount <= 0 or amount < c.activation_floor:
                    continue
                if c.propagation_limit is not None and emissions >= c.propagation_limit:
                    self.resources.increment("propagation_budget_skips")
                    continue
                if c.energy_simulation_enabled:
                    amount = self.energy.afford(amount, c.energy_associative_cost, "associative")
                self.transport["sent"] += amount
                if amount <= 0 or amount < c.activation_floor:
                    self.transport["discarded"] += amount
                    continue
                emissions += 1
                signals[target] = signals.get(target, 0.0) + amount
                traversed.add(key)
                if c.plasticity:
                    if c.edge_adaptation_limit is not None:
                        if not self.resources.available_adaptations(
                            self.time_us, c.propagation_interval_us, c.edge_adaptation_limit
                        ):
                            self.resources.increment("adaptation_budget_skips")
                            continue
                        self.resources.use_adaptation(self.time_us, c.propagation_interval_us)
                    e.eligibility = min(1.0, 0.7 * e.eligibility + amount)
                    if self._edge_consolidation_enabled():
                        e.weight = min(1.0, e.weight + c.associative_gain * amount)
                        e.stability = min(1.0, e.stability + c.stability_gain * amount)
                    e.touches += 1
                    e.last_touch_us = str(self.time_us)
            if c.inhibition and n.generated_inhibition > 0:
                n.inhibition = self._saturate_inhibition(n.inhibition + n.generated_inhibition)
            n.generated_inhibition = 0.0
            if c.inhibition and n.inhibition >= c.inhibition_propagation_min:
                conductances = []
                for target in sorted(self.incident.get(n.id, ())):
                    weights = [
                        self.edges[k].weight
                        for k in ((n.id, target), (target, n.id))
                        if k in self.edges and k not in self.silenced_edges
                    ]
                    if weights and max(weights) > 0:
                        conductances.append((target, max(weights)))
                total = sum(w for _, w in conductances)
                transfer = n.inhibition * diffusion
                if total > 0 and transfer >= c.inhibition_propagation_min:
                    if c.energy_simulation_enabled:
                        transfer = self.energy.afford(transfer, c.energy_inhibition_cost, "inhibition")
                    if transfer >= c.inhibition_propagation_min:
                        n.inhibition -= transfer
                        for target, w in conductances:
                            inhibitors[target] = inhibitors.get(target, 0.0) + transfer * w / total
        for kind, values in (("signal", signals), ("inhibition", inhibitors)):
            if values:
                self._event(
                    self.time_us + c.delay_us,
                    kind,
                    {
                        "values": [
                            [n, self._saturate_inhibition(v) if kind == "inhibition" else v]
                            for n, v in sorted(values.items())
                        ]
                    },
                )
        if c.plasticity:
            retention = math.exp(-dt / c.eligibility_tau) if c.eligibility_decay_enabled else 1.0
            for key, e in self.edges.items():
                e.eligibility *= retention
                if c.stability_decay_enabled:
                    e.stability = max(0.0, e.stability - dt / c.stability_tau * (1.0 - e.eligibility))
                if key not in traversed and not self._adaptive_retention_active():
                    e.weight *= max(0.0, 1.0 - 0.1 * c.forgetting_rate * (1.0 - (0.08 + 0.92 * e.stability))) ** (
                        dt / 0.1
                    )
        self.traversed = traversed
        for n in self.nodes.values():
            n.direct = n.associative = 0.0

    def _prune(self):
        c = self.config
        if not c.plasticity:
            return
        for key in [k for k, e in self.edges.items() if e.weight < c.prune_weight]:
            self._remove_edge(key)
        for node_id in list(self.nodes):
            n = self.nodes[node_id]
            if (
                n.activation == 0
                and n.support < c.prune_support
                and not self.incident.get(node_id)
                and self.time_us - int(n.last_touch_us) > c.node_prune_after_us
            ):
                del self.nodes[node_id]
                self.receptors.pop(n.channel, None)
        self.traversed.intersection_update(self.edges)

    def _lifecycle(self):
        self._record_energy_shortage()
        if self.life == "dead":
            return
        if any(n.activation > 0 for n in self.nodes.values()):
            self.life = "active"
            self.quiet_since_us = None
        elif self.life != "waiting":
            if self.quiet_since_us is None:
                self.quiet_since_us = self.time_us
            if self.time_us - self.quiet_since_us >= self.config.quiescence_death_us:
                self.life = "dead"
                self.energy.death_us = str(self.time_us)

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        if action and lesion:
            raise ValueError("use either action or legacy lesion, not both")
        action = action or ("delete_nodes" if lesion and nodes else "disconnect_edges" if lesion else "silence")
        if action not in ("silence", "unsilence", "disconnect_edges", "delete_nodes"):
            raise ValueError("unknown intervention action")
        if action == "disconnect_edges" and nodes:
            raise ValueError("disconnect_edges accepts edges only")
        keys = {tuple(e) for e in edges}
        if any(n not in self.nodes for n in nodes) or any(e not in self.edges for e in keys):
            raise ValueError("intervention target does not exist")
        self._relax(self.time_us)
        if action in ("disconnect_edges", "delete_nodes"):
            removed = set(nodes) if action == "delete_nodes" else set()
            keys.update(k for k in self.edges if k[0] in removed or k[1] in removed)
            for k in keys:
                self._remove_edge(k)
                self.silenced_edges.discard(k)
                self.traversed.discard(k)
            for node_id in removed:
                n = self.nodes.pop(node_id)
                self.receptors.pop(n.channel, None)
                self.silenced_nodes.discard(node_id)
                self.outgoing.pop(node_id, None)
                self.incident.pop(node_id, None)
        elif action == "unsilence":
            self.silenced_nodes.difference_update(nodes)
            self.silenced_edges.difference_update(keys)
        else:
            self.silenced_nodes.update(nodes)
            self.silenced_edges.update(keys)
            for node_id in nodes:
                n = self.nodes[node_id]
                n.activation = n.direct = n.associative = 0.0
        self.sequence += 1
        self._lifecycle()
