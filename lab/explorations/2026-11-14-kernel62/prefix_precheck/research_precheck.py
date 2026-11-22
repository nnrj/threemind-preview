"""Isolated R51t8 resource precheck candidates. Never a production kernel.

_emit is copied from frozen local62.py with marked mode branches. The old full
emission method is invoked read-only from local.py. Fixed-function addressing,
retention and all other methods remain 6.2. No original instance is converted.
"""
from dataclasses import dataclass
from threemind_kernels import local62 as production
from threemind_kernels.local import LocalEngine as HistoricalEngine
from legacy_probe import old_emit_without_precheck

globals().update({k:v for k,v in vars(production).items() if not k.startswith('__')})
KERNEL_ID='threemind.research-prefix-precheck62/1'
STATE_SCHEMA='threemind.research-prefix-precheck62-state/1'

@dataclass(frozen=True,slots=True)
class ResearchConfig(Local62Config):
    research_transport: str='reference'
    resource_precheck: bool=False

    def __post_init__(self):
        Local62Config.__post_init__(self)
        if self.research_transport not in ('reference','old-inhibition','old-emission','old-emission-no-precheck'):
            raise ValueError('unknown isolated transport candidate')


def definition(config):
    return {'schema':'threemind.kernel-definition/1','kernel_id':KERNEL_ID,
            'state_schema':STATE_SCHEMA,'hypothesis_id':'r51t8/transport',
            'operators':[{'id':'r51t8/isolated-emission-replacement','phase':'emission'}],
            'config':config.to_dict()}


class ResearchEngine(Local62Engine):
    dynamics=KERNEL_ID
    state_schema=STATE_SCHEMA
    config_type=ResearchConfig
    definition=staticmethod(definition)

    def _old_inhibition(self,n):
        c=self.config
        if c.inhibition:
            n.inhibition=self._soft(n.inhibition+n.generated_inhibition)
        n.generated_inhibition=0.0
        transfer=n.inhibition*min(1.0,c.inhibition_diffusion_rate*c.propagation_interval_us/1e6)
        weights={}
        if c.inhibition and transfer>=c.inhibition_propagation_min:
            for key in sorted(self.incident.get(n.id,())):
                if key not in self.silenced_edges and not self.edges[key].sleeping:
                    e=self._settle_edge(key)
                    target=e.target if e.source==n.id else e.source
                    weights[target]=max(weights.get(target,0.0),e.weight)
        total=sum(weights.values())
        if c.inhibition and total>0 and transfer>=c.inhibition_propagation_min:
            transfer=self._expense(n,transfer,c.energy_inhibition_cost,'inhibition')
            if transfer>=c.inhibition_propagation_min:
                n.inhibition-=transfer
                for target,w in sorted(weights.items()):
                    self._emission_inhibitors[target]=self._emission_inhibitors.get(target,0.0)+transfer*w/total

    def _emit(self, id):
        if self.config.research_transport == "old-emission":
            return HistoricalEngine._emit(self, id)
        if self.config.research_transport == "old-emission-no-precheck":
            return old_emit_without_precheck(self, id)
        old_inhibition = self.config.research_transport == "old-inhibition"
        if id not in self.nodes or id in self.silenced_nodes:
            return
        c, n = self.config, self._settle_node(id)
        self._maintenance(n)
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.pending_inhibition)
        n.pending_inhibition = 0.0
        features = self._features(n)
        positive = n.activation * self._response(n) * c.propagation_rate * c.propagation_interval_us / 1e6
        if n.activation < max(c.propagation_activation_min, c.activation_send_threshold):
            positive = 0.0
        if not old_inhibition:
            if c.inhibition:
                n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
            n.generated_inhibition = 0.0
        negative = (
            n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
            if c.inhibition
            else 0.0
        )
        if old_inhibition:
            negative = 0.0
        if c.inhibition_sender_gate_enabled and negative < c.inhibition_propagation_min:
            negative = 0.0
        if n.inhibition < c.inhibition_send_threshold:
            negative = 0.0
        if getattr(self, "_operator_config", None) is not c:
            self._operator_config = c
            self._short_term_config, self._fast_config = c.short_term(), c.fast_trace()
        keys = sorted(k for k in self.outgoing.get(id, ()) if k not in self.silenced_edges)
        self.transport["offered_excitation"] += len(keys) * positive
        self.transport["offered_inhibition"] += len(keys) * negative
        # The node pays for its offers, including sleeping/weak connections.
        p_cost = len(keys) * positive * c.energy_associative_cost
        i_cost = len(keys) * negative * c.energy_inhibition_cost
        requested = p_cost + i_cost
        scale = 1.0
        if c.energy_simulation_enabled and requested > 0:
            available = self.energy.reserve if c.energy_model == "global-ledger" else n.reserve
            scale = min(1.0, available / requested)
            self._expense(n, len(keys) * positive * scale, c.energy_associative_cost, "associative")
            self._expense(n, len(keys) * negative * scale, c.energy_inhibition_cost, "inhibition")
            self.energy._add("unserved_total", requested * (1.0 - scale))
        self.transport["blocked_energy"] += len(keys) * (positive + negative) * (1.0 - scale)
        positive *= scale
        negative *= scale
        messages = []
        for key in keys:
            e = self._settle_edge(key)
            if positive <= 0 and negative <= 0:
                continue
            if e.sleeping:
                self.transport["blocked_dormancy"] += positive + negative
                continue
            fast = (
                FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                if e.fast
                else FastTrace(time_us=int(e.birth_us))
            )
            fast_value = fast.projected(self.time_us, self._fast_config) if c.fast_enabled else 0.0
            weight = min(1.0, e.weight + c.fast_gain * fast_value) if c.fast_enabled else e.weight
            distance = 1.0
            if c.spatial_embedding and c.neighborhood_enabled:
                from threemind_core.spatial import position

                pa, pb = (
                    position(c.seed, e.source, c.spatial_dimensions),
                    position(c.seed, e.target, c.spatial_dimensions),
                )
                distance = math.exp(-math.sqrt(sum((a - b) ** 2 for a, b in zip(pa, pb))) / c.spatial_radius)
            # R51t8 intervention: use the SAME per-type connection threshold
            # before releasing shared STP resources. The post-release test stays.
            p_offer, n_offer = positive, negative
            if c.resource_precheck and c.signal_threshold_enabled:
                if weight * p_offer * distance < c.signal_threshold_for(False):
                    p_offer = 0.0
                if weight * n_offer * distance < c.signal_threshold_for(True):
                    n_offer = 0.0
                if p_offer <= 0 and n_offer <= 0:
                    continue
            fraction = 1.0
            if c.stp_enabled:
                sc = self._short_term_config
                st = (
                    ShortTermState(**(e.short_term | {"time_us": int(e.short_term["time_us"])}))
                    if e.short_term
                    else ShortTermState(time_us=int(e.birth_us))
                )
                if not c.depletion_enabled:
                    st = st.recovered(self.time_us, sc)
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                st, fraction = st.release(self.time_us, sc)
                if not c.depletion_enabled:
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                e.short_term = asdict(st) | {"time_us": str(st.time_us)}
            transmitted = []
            for inhibitory, signal in enumerate((p_offer, n_offer)):
                amount = weight * signal * fraction * distance
                self.transport["sent"] += amount
                reason = (
                    "blocked_weight"
                    if c.weight_gate_enabled and e.weight < c.weight_gate
                    else ("blocked_signal" if c.signal_threshold_enabled and amount < c.signal_threshold_for(bool(inhibitory)) else None)
                )
                if reason:
                    self.transport[reason] += amount
                    self.transport["discarded"] += amount
                    amount = 0.0
                transmitted.append(amount)
            pos, neg = transmitted
            self.transport["transmitted_excitation"] += pos
            self.transport["transmitted_inhibition"] += neg
            if pos > 0:
                messages.append([id, e.target, pos, features])
            if neg > 0:
                self._emission_inhibitors[e.target] = self._emission_inhibitors.get(e.target, 0.0) + neg
            if pos > 0 or neg > 0:
                e.last_pass_us = str(self.time_us)
            learned = pos + (neg if c.inhibitory_learning_enabled else 0.0)
            if c.plasticity and learned > 0:
                if c.fast_enabled:
                    fast_value += -math.expm1(-c.fast_learning_rate * learned) * (1.0 - fast_value)
                    e.fast = asdict(FastTrace(fast_value, self.time_us)) | {"time_us": str(self.time_us)}
                e.eligibility = min(1.0, 0.7 * e.eligibility + learned)
                if c.edge_consolidation_enabled:
                    weight_signal = (pos if c.activation_weight_reinforcement_enabled else 0.0) + (
                        neg if c.inhibitory_learning_enabled and c.inhibition_weight_reinforcement_enabled else 0.0
                    )
                    e.weight = min(1.0, e.weight + c.associative_gain * weight_signal)
                    if c.consolidation_mode != "stability" or c.stability_growth_enabled:
                        e.stability = min(1.0, e.stability + c.stability_gain * learned)
                    if c.retention_growth_enabled:
                        e.half_life = grow(e.half_life, learned * 0.1, c)
                e.touches += 1
                e.last_touch_us = str(self.time_us)
                self._edge_timer(e)
        if messages:
            self._event(self.time_us + c.delay_us, "signal", {"messages": messages})
        # Inhibition is a node emission budget; fan-out and failed delivery do
        # not feed back from the connection into the node's generation rule.
        if keys:
            n.inhibition = max(0.0, n.inhibition - negative)
        if c.revival_enabled and positive > 0:
            for key in sorted(self.incident.get(id, ())):
                if self.edges[key].sleeping and key not in self.silenced_edges:
                    self._event(self.time_us + c.delay_us, "wake", {"edge": list(key), "sender": id, "value": positive})
        if old_inhibition:
            self._old_inhibition(n)
        n.last_emit_us = str(self.time_us)
        n.direct = n.associative = 0.0
        self._node_timers(n)
        self._pulse(n, after=True)
