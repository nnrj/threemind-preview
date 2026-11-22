"""Isolated R51t6 operator dissection; never registered as a production kernel.

The three methods below are copied from the frozen local.py and differ only at
the explicitly marked R51t6 switches. The reference switches reproduce /5.1.
"""
from dataclasses import dataclass
from threemind_kernels import local as _historical
from threemind_kernels.local51 import Local51Config, Local51Engine

# Resolve the copied methods' historical imports without changing that module.
globals().update({k:v for k,v in vars(_historical).items() if not k.startswith('__')})
KERNEL_ID='threemind.research-prefix-components/1'
STATE_SCHEMA='threemind.research-prefix-components-state/1'

@dataclass(frozen=True, slots=True)
class ResearchConfig(Local51Config):
    consolidation_mode: str='legacy-stability'
    research_novelty_weight: bool=True
    research_novelty_stability: bool=True
    research_use_protection: bool=True
    research_stability_protection: bool=True
    research_eligibility_protection: bool=True
    research_pass_weight_gain: bool=True

    def __post_init__(self):
        Local51Config.__post_init__(self)
        if self.consolidation_mode!='legacy-stability':
            raise ValueError('this isolated study requires legacy-stability')
        for k in SWITCHES:
            if type(getattr(self,k)) is not bool: raise ValueError(k)

SWITCHES=tuple(k for k in ResearchConfig.__dataclass_fields__ if k.startswith('research_'))

def definition(config):
    return {'schema':'threemind.kernel-definition/1','kernel_id':KERNEL_ID,
            'state_schema':STATE_SCHEMA,'hypothesis_id':'r51t6/prefix-components',
            'operators':[{'id':'r51t6/local51-component-ablation','phase':'historical-order'}],
            'config':config.to_dict()}

class ResearchEngine(Local51Engine):
    dynamics=KERNEL_ID
    state_schema=STATE_SCHEMA
    config_type=ResearchConfig
    definition=staticmethod(definition)

    def _associate(self, contacts):
            c = self.config
            if not c.plasticity:
                return
            connected = (
                {id for id, _, _ in contacts if any(not self.edges[k].sleeping for k in self.incident.get(id, ()))}
                if self.restored_learning
                else None
            )
            for a, av, ai in contacts:
                for b, bv, bi in contacts:
                    key = a, b
                    if a == b or key in self.silenced_edges or a not in self.nodes or b not in self.nodes:
                        continue
                    score = self.nodes[a].activation * self.nodes[b].activation if self.restored_learning else av * bv
                    if score <= 0 or (key not in self.edges and score < c.edge_birth_activation_product_min):
                        continue
                    if c.spatial_embedding and c.neighborhood_enabled:
                        from threemind_core.spatial import position

                        pa, pb = position(c.seed, a, c.spatial_dimensions), position(c.seed, b, c.spatial_dimensions)
                        if math.sqrt(sum((x - y) ** 2 for x, y in zip(pa, pb))) > c.spatial_radius:
                            continue
                    impulse = min(c.consolidation_cap, ai + bi)
                    if key not in self.edges:
                        if c.max_edges is not None and len(self.edges) >= c.max_edges:
                            continue
                        e = self.edge_type(
                            a,
                            b,
                            min(1.0, c.birth_weight * (0.5 + score) + 0.18 * impulse),
                            stability=min(1.0, impulse),
                            eligibility=impulse,
                            birth_us=str(self.time_us),
                            last_touch_us=str(self.time_us),
                            state_us=str(self.time_us),
                            half_life=c.memory_half_life_min_s,
                        )
                        if self.restored_learning:
                            e.completed_period_us = str(
                                max(
                                    0,
                                    (self.time_us - int(self._before_emission))
                                    // c.propagation_interval_us
                                    * c.propagation_interval_us,
                                )
                            )
                        eligible = (
                            (a in connected or b in connected)
                            if self.restored_learning
                            else (self.incident.get(a) or self.incident.get(b))
                        )
                        if eligible:
                            if c.novelty_mode == "arrival-window" and (
                                not self.restored_learning or c.local_novelty_gain > 0
                            ):
                                if self.restored_learning:
                                    period = c.propagation_interval_us
                                    deadline = (
                                        max(
                                            period,
                                            self.completed_emission_us + period,
                                            ((self.time_us + period - 1) // period) * period,
                                        )
                                        + c.delay_us
                                    )
                                    e.novelty_deadline_us = str(deadline)
                                    e.novelty_source = self.nodes[a].associative
                                    e.novelty_target = self.nodes[b].associative
                                    for id in key:
                                        self.pending_novelty.setdefault(id, set()).add(key)
                                else:
                                    e.novelty_deadline_us = str(self.time_us + c.propagation_interval_us + c.delay_us)
                            else:
                                reentry = (
                                    max(av, bv)
                                    if c.reception_mode == "unified" and not self.restored_learning
                                    else max(self.nodes[a].associative, self.nodes[b].associative)
                                )
                                bonus = (
                                    c.local_novelty_gain * max(0.0, 1 - reentry / c.novelty_touch_reference)
                                    if reentry > 0
                                    else 0
                                )
                                e.weight = min(1.0, e.weight + (bonus if c.research_novelty_weight else 0.0))  # R51t6
                                e.stability = min(1.0, e.stability + (bonus if c.research_novelty_stability else 0.0))  # R51t6
                        self.edges[key] = e
                        self.outgoing.setdefault(a, set()).add(key)
                        self.incident.setdefault(a, set()).add(key)
                        self.incident.setdefault(b, set()).add(key)
                    else:
                        e = self._settle_edge(key)
                        if e.sleeping:
                            continue
                        if c.edge_consolidation_enabled:
                            if self.restored_learning:
                                previous = (
                                    (self.time_us - int(self._before_emission))
                                    // c.propagation_interval_us
                                    * c.propagation_interval_us
                                    if c.propagation_phase == "aligned"
                                    else int(self.nodes[a].last_emit_us)
                                )
                                internal = 1 if int(e.last_pass_us) > 0 and int(e.last_pass_us) == previous else 0.45
                            else:
                                internal = 1 if int(e.last_pass_us) == self.time_us else 0.45
                            e.weight = min(
                                1.0, e.weight + c.learning_rate * score * internal * (1 - e.weight) + 0.08 * impulse
                            )
                            e.stability = min(
                                1.0, e.stability + c.stability_gain * score * (1 + math.log1p(e.touches)) + impulse
                            )
                        e.eligibility = min(1.0, e.eligibility + 0.3 * score + 0.25 * impulse)
                        e.touches += 1
                        e.last_touch_us = str(self.time_us)
                    self._edge_timer(e)
                    for id in key:
                        self.timers.discard((3, id, 0))

    def _emit(self, id):
            if id not in self.nodes or id in self.silenced_nodes:
                return
            c, n = self.config, self._settle_node(id)
            self._maintenance(n)
            if c.inhibition:
                n.inhibition = self._soft(n.inhibition + n.pending_inhibition)
            n.pending_inhibition = 0.0
            messages, inhibitors = [], []
            features = self._features(n) if self.restored_learning else None
            fast_config = short_config = None
            flux = n.activation * self._response(n) * c.propagation_rate * c.propagation_interval_us / 1e6
            for key in sorted(self.outgoing.get(id, ())):
                if key in self.silenced_edges:
                    continue
                e = self._settle_edge(key)
                if e.sleeping:
                    continue
                weight = e.weight
                if c.fast_enabled:
                    f = (
                        FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                        if e.fast
                        else FastTrace(time_us=int(e.birth_us))
                    )
                    if self.restored_learning:
                        if fast_config is None:
                            fast_config = c.fast_trace()
                        fast_value = f.projected(self.time_us, fast_config)
                        weight = min(1.0, weight + fast_config.gain * fast_value)
                    else:
                        weight = f.efficacy(weight, self.time_us, c.fast_trace())
                amount = flux * weight
                if c.spatial_embedding and (not self.restored_learning or c.neighborhood_enabled):
                    from threemind_core.spatial import position

                    pa, pb = (
                        position(c.seed, e.source, c.spatial_dimensions),
                        position(c.seed, e.target, c.spatial_dimensions),
                    )
                    amount *= math.exp(-math.sqrt(sum((a - b) ** 2 for a, b in zip(pa, pb))) / c.spatial_radius)
                if n.activation < c.propagation_activation_min or amount < c.activation_floor or amount <= 0:
                    continue
                if c.stp_enabled:
                    if self.restored_learning and short_config is None:
                        short_config = c.short_term()
                    st = (
                        ShortTermState(**(e.short_term | {"time_us": int(e.short_term["time_us"])}))
                        if e.short_term
                        else ShortTermState(time_us=int(e.birth_us))
                    )
                    if not c.depletion_enabled:
                        st = st.recovered(self.time_us, short_config if self.restored_learning else c.short_term())
                        st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                    st, fraction = st.release(self.time_us, short_config if self.restored_learning else c.short_term())
                    if not c.depletion_enabled:
                        st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                    e.short_term = asdict(st)
                    e.short_term["time_us"] = str(st.time_us)
                    amount *= fraction
                amount = self._expense(n, amount, c.energy_associative_cost, "associative")
                self.transport["sent"] += amount
                if amount < c.activation_floor or amount <= 0:
                    self.transport["discarded"] += amount
                    continue
                messages.append([id, e.target, amount, features if self.restored_learning else self._features(n)])
                e.last_pass_us = str(self.time_us)
                if c.fast_enabled and c.plasticity:
                    if self.restored_learning:
                        fast_value += -math.expm1(-fast_config.learning_rate * amount) * (1.0 - fast_value)
                        e.fast = asdict(FastTrace(fast_value, self.time_us))
                    else:
                        f = (
                            FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                            if e.fast
                            else FastTrace(time_us=int(e.birth_us))
                        )
                        e.fast = asdict(f.transmit(amount, self.time_us, c.fast_trace()))
                    e.fast["time_us"] = str(self.time_us)
                if c.plasticity:
                    e.eligibility = min(1.0, 0.7 * e.eligibility + amount)
                    if c.edge_consolidation_enabled:
                        e.weight = min(1.0, e.weight + (c.associative_gain * amount if c.research_pass_weight_gain else 0.0))  # R51t6
                        e.stability = min(1.0, e.stability + c.stability_gain * amount)
                        if c.consolidation_mode == "adaptive-half-life":
                            e.half_life = grow(e.half_life, amount * 0.1, c)
                    e.touches += 1
                    e.last_touch_us = str(self.time_us)
                    self._edge_timer(e)
            if c.revival_enabled and flux > 0:
                for key in sorted(self.incident.get(id, ())):
                    if self.edges[key].sleeping and key not in self.silenced_edges:
                        self._event(self.time_us + c.delay_us, "wake", {"edge": list(key), "sender": id, "value": flux})
            if messages:
                self._event(self.time_us + c.delay_us, "signal", {"messages": messages})
            if c.inhibition:
                n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
            n.generated_inhibition = 0.0
            conductances = []
            transfer = n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
            incident = (
                self.incident.get(id, ())
                if (not self.restored_learning or (c.inhibition and transfer >= c.inhibition_propagation_min))
                else ()
            )
            for key in sorted(incident):
                if key not in self.silenced_edges and not self.edges[key].sleeping:
                    e = self._settle_edge(key)
                    conductances.append((e.target if e.source == id else e.source, e.weight))
            weights = {}
            for target, w in conductances:
                weights[target] = max(weights.get(target, 0.0), w)
            total = sum(weights.values())
            if c.inhibition and total > 0 and transfer >= c.inhibition_propagation_min:
                transfer = self._expense(n, transfer, c.energy_inhibition_cost, "inhibition")
                if not self.restored_learning or transfer >= c.inhibition_propagation_min:
                    n.inhibition -= transfer
                    inhibitors = [[t, transfer * w / total] for t, w in sorted(weights.items())]
            if inhibitors:
                if self.restored_learning:
                    for target, amount in inhibitors:
                        self._emission_inhibitors[target] = self._emission_inhibitors.get(target, 0.0) + amount
                else:
                    self._event(self.time_us + c.delay_us, "inhibition", {"values": inhibitors})
            if self.restored_learning:
                n.last_emit_us = str(self.time_us)
            n.direct = n.associative = 0.0
            self._node_timers(n)
            self._pulse(n, after=True)

    def _expiry(self, kind, a, b):
            self.audit["expiry_checks"] += 1
            c, key = self.config, (a, b)
            if kind == 5 and a in self.nodes:
                n = self._settle_node(a)
                self._maintenance(n)
                self._node_timers(n)
                if c.energy_simulation_enabled and c.energy_starvation_damage_enabled:
                    self.timers.set((5, a, 0), self.time_us + c.propagation_interval_us)
            elif kind in (1, 3) and a in self.nodes:
                n = self._settle_node(a)
                if kind == 3:
                    floor = 0.006 if c.node_retention_mode == "automatic" else c.prune_support
                    eligible = (
                        n.support < floor
                        if floor > 0
                        else self.time_us - max(int(n.isolated_us), int(n.last_touch_us)) >= c.dead_node_retention_us
                    )
                    if c.node_retention_mode == "manual" and floor > 0:
                        eligible = eligible and self.time_us - int(n.last_touch_us) > c.node_prune_after_us
                    if (
                        not c.retain_nodes
                        and n.activation == 0
                        and not any(not self.edges[k].sleeping for k in self.incident.get(a, ()))
                        and eligible
                    ):
                        self._delete_node(a)
                        return
                self._node_timers(n)
                self._pulse(n)
            elif kind in (2, 4) and key in self.edges:
                e = self._settle_edge(key)
                if kind == 4:
                    reentry = max(e.novelty_source, e.novelty_target)
                    if (
                        c.plasticity
                        and reentry > 0
                        and not e.sleeping
                        and key not in self.silenced_edges
                        and not any(id in self.silenced_nodes for id in key)
                    ):
                        bonus = c.local_novelty_gain * max(0.0, 1 - reentry / c.novelty_touch_reference)
                        e.weight = min(1.0, e.weight + (bonus if c.research_novelty_weight else 0.0))  # R51t6
                        e.stability = min(1.0, e.stability + (bonus if c.research_novelty_stability else 0.0))  # R51t6
                    e.novelty_deadline_us = None
                    if self.restored_learning:
                        self._drop_novelty_index(key)
                elif c.plasticity and c.consolidation_mode == "legacy-stability":
                    dt = c.propagation_interval_us / 1e6
                    if c.eligibility_decay_enabled:
                        e.eligibility *= math.exp(-dt / c.eligibility_tau)
                    if c.stability_decay_enabled:
                        e.stability = max(0.0, e.stability - dt / c.stability_tau * (1 - (e.eligibility if c.research_eligibility_protection else 0.0)))
                    if not c.research_use_protection or int(e.last_pass_us) != self.time_us:  # R51t6
                        e.weight *= max(0.0, 1 - 0.1 * c.forgetting_rate * (1 - (0.08 + 0.92 * (e.stability if c.research_stability_protection else 0.0)))) ** (dt / 0.1)
                    if self.restored_learning:
                        e.completed_period_us = str(self.time_us)
                if e.weight < (c.dormant_prune_weight if e.sleeping else c.prune_weight):
                    self._remove_edge(key)
                else:
                    self._edge_timer(e)

