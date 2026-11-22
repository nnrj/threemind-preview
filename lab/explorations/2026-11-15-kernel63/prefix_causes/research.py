"""R51t15 isolated 6.3 candidates; no production changes.

The ordinary emitter is copied from 6.3, with resource bypass and individually
declared inhibitory learning controls. A separate legacy-emitter witness copies
R51t11 verbatim onto the 6.3 base for comparison with archived successful states.
"""
from dataclasses import dataclass
from threemind_kernels import local63 as production

globals().update({k:v for k,v in vars(production).items() if not k.startswith('__')})
KERNEL_ID='threemind.research-prefix-causes63/1'
STATE_SCHEMA='threemind.research-prefix-causes63-state/1'

@dataclass(frozen=True,slots=True)
class ResearchConfig(Local63Config):
    research_bypass_inhibition_resources: bool=False
    research_legacy_emission: bool=False
    research_learning_component: str='full'

    def __post_init__(self):
        Local63Config.__post_init__(self)
        for k in ('research_bypass_inhibition_resources','research_legacy_emission'):
            if type(getattr(self,k)) is not bool:raise ValueError(k)
        if self.research_bypass_inhibition_resources and self.separate_inhibition_resources:
            raise ValueError('bypass and independent resources are distinct conditions')
        if self.research_learning_component not in ('full','none','weight','fast','eligibility','stability','retention','touch'):
            raise ValueError('unknown learning component')
        if self.research_legacy_emission and (self.separate_inhibition_resources or self.research_learning_component!='full'):
            raise ValueError('legacy witness must retain its own emitter')

    @property
    def research_inhibition_marks_usage(self):return self.inhibition_updates_usage

    @property
    def research_normalize_inhibition(self):return self.inhibition_distribution=='weight-proportional'

def definition(config):
    return {'schema':'threemind.kernel-definition/1','kernel_id':KERNEL_ID,'state_schema':STATE_SCHEMA,
        'hypothesis_id':'r51t15/prefix-causal-factors','operators':[{'id':'r51t15/emission-controls','phase':'emission'}],
        'config':config.to_dict()}

class ResearchEngine(Local63Engine):
    dynamics=KERNEL_ID
    state_schema=STATE_SCHEMA
    config_type=ResearchConfig
    definition=staticmethod(definition)

    def _emit(self, id):
        if self.config.research_legacy_emission:
            return self._legacy_emit(id)
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
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
        n.generated_inhibition = 0.0
        negative = (
            n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
            if c.inhibition
            else 0.0
        )
        if c.inhibition_sender_gate_enabled and negative < c.inhibition_propagation_min:
            negative = 0.0
        if n.inhibition < c.inhibition_send_threshold:
            negative = 0.0
        if getattr(self, "_operator_config", None) is not c:
            self._operator_config = c
            self._short_term_config, self._fast_config = c.short_term(), c.fast_trace()
        keys = sorted(k for k in self.outgoing.get(id, ()) if k not in self.silenced_edges)
        proportional = c.inhibition_distribution == "weight-proportional"
        total_weight = 0.0
        if proportional:
            for key in keys:
                edge = self._project_edge(self.edges[key], self.time_us)
                if edge.sleeping:
                    continue
                trace = FastTrace(**(edge.fast | {"time_us": int(edge.fast["time_us"])})) if edge.fast else FastTrace(time_us=int(edge.birth_us))
                gain = trace.projected(self.time_us, self._fast_config) if c.fast_enabled else 0.0
                total_weight += min(1.0, edge.weight + c.fast_gain * gain) if c.fast_enabled else edge.weight
            if total_weight <= 0:
                negative = 0.0
        inhibition_offers = negative if proportional else len(keys) * negative
        self.transport["offered_excitation"] += len(keys) * positive
        self.transport["offered_inhibition"] += inhibition_offers
        # The node pays for its offers, including sleeping/weak connections.
        p_cost = len(keys) * positive * c.energy_associative_cost
        i_cost = inhibition_offers * c.energy_inhibition_cost
        requested = p_cost + i_cost
        scale = 1.0
        if c.energy_simulation_enabled and requested > 0:
            available = self.energy.reserve if c.energy_model == "global-ledger" else n.reserve
            scale = min(1.0, available / requested)
            self._expense(n, len(keys) * positive * scale, c.energy_associative_cost, "associative")
            self._expense(n, inhibition_offers * scale, c.energy_inhibition_cost, "inhibition")
            self.energy._add("unserved_total", requested * (1.0 - scale))
        self.transport["blocked_energy"] += (len(keys) * positive + inhibition_offers) * (1.0 - scale)
        positive *= scale
        negative *= scale
        messages = []
        for key in keys:
            e = self._settle_edge(key)
            if positive <= 0 and negative <= 0:
                continue
            if e.sleeping:
                self.transport["blocked_dormancy"] += positive + (0.0 if proportional else negative)
                continue
            fast = (
                FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                if e.fast
                else FastTrace(time_us=int(e.birth_us))
            )
            fast_value = fast.projected(self.time_us, self._fast_config) if c.fast_enabled else 0.0
            weight = min(1.0, e.weight + c.fast_gain * fast_value) if c.fast_enabled else e.weight
            inhibition_weight = (weight / total_weight if total_weight > 0 else 0.0) if proportional else weight
            distance = 1.0
            if c.spatial_embedding and c.neighborhood_enabled:
                from threemind_core.spatial import position

                pa, pb = (
                    position(c.seed, e.source, c.spatial_dimensions),
                    position(c.seed, e.target, c.spatial_dimensions),
                )
                distance = math.exp(-math.sqrt(sum((a - b) ** 2 for a, b in zip(pa, pb))) / c.spatial_radius)
            p_offer, n_offer = positive, negative
            if c.resource_precheck_enabled and c.signal_threshold_enabled:
                if weight * p_offer * distance < c.signal_threshold_for(False):
                    p_offer = 0.0
                if inhibition_weight * n_offer * distance < c.signal_threshold_for(True):
                    n_offer = 0.0
                if p_offer <= 0 and n_offer <= 0:
                    continue
            if c.research_bypass_inhibition_resources:
                fraction = self._release_resource(e, "short_term") if p_offer > 0 else 1.0
                i_fraction = 1.0
            elif c.separate_inhibition_resources:
                fraction = self._release_resource(e, "short_term") if p_offer > 0 else 1.0
                i_fraction = self._release_resource(e, "inhibition_short_term") if n_offer > 0 else 1.0
            else:
                fraction = i_fraction = self._release_resource(e, "short_term")
            transmitted = []
            for inhibitory, signal in enumerate((p_offer, n_offer)):
                amount = (inhibition_weight if inhibitory else weight) * signal * (i_fraction if inhibitory else fraction) * distance
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
            if pos > 0 or (neg > 0 and c.inhibition_updates_usage):
                e.last_pass_us = str(self.time_us)
            if c.research_learning_component != "full":
                self._learn_component(e, fast_value, pos, neg)
            else:
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
        n.last_emit_us = str(self.time_us)
        n.direct = n.associative = 0.0
        self._node_timers(n)
        self._pulse(n, after=True)

    def _inhibitory_weight(self,key):
        c=self.config;e=self._settle_edge(key)
        fast=(FastTrace(**(e.fast|{'time_us':int(e.fast['time_us'])})) if e.fast
              else FastTrace(time_us=int(e.birth_us)))
        value=fast.projected(self.time_us,self._fast_config) if c.fast_enabled else 0.0
        weight=min(1.0,e.weight+c.fast_gain*value) if c.fast_enabled else e.weight
        if c.spatial_embedding and c.neighborhood_enabled:
            from threemind_core.spatial import position
            a=position(c.seed,e.source,c.spatial_dimensions);b=position(c.seed,e.target,c.spatial_dimensions)
            weight*=math.exp(-math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))/c.spatial_radius)
        return weight

    def _legacy_emit(self, id):
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
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
        n.generated_inhibition = 0.0
        negative = (
            n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
            if c.inhibition
            else 0.0
        )
        if c.inhibition_sender_gate_enabled and negative < c.inhibition_propagation_min:
            negative = 0.0
        if n.inhibition < c.inhibition_send_threshold:
            negative = 0.0
        if getattr(self, "_operator_config", None) is not c:
            self._operator_config = c
            self._short_term_config, self._fast_config = c.short_term(), c.fast_trace()
        keys = sorted(k for k in self.outgoing.get(id, ()) if k not in self.silenced_edges)
        self.transport["offered_excitation"] += len(keys) * positive
        inhibitory_offers = (1 if keys else 0) if c.research_normalize_inhibition else len(keys)
        self.transport["offered_inhibition"] += inhibitory_offers * negative
        # The node pays for its offers, including sleeping/weak connections.
        p_cost = len(keys) * positive * c.energy_associative_cost
        i_cost = inhibitory_offers * negative * c.energy_inhibition_cost
        requested = p_cost + i_cost
        scale = 1.0
        if c.energy_simulation_enabled and requested > 0:
            available = self.energy.reserve if c.energy_model == "global-ledger" else n.reserve
            scale = min(1.0, available / requested)
            self._expense(n, len(keys) * positive * scale, c.energy_associative_cost, "associative")
            self._expense(n, inhibitory_offers * negative * scale, c.energy_inhibition_cost, "inhibition")
            self.energy._add("unserved_total", requested * (1.0 - scale))
        self.transport["blocked_energy"] += (len(keys) * positive + inhibitory_offers * negative) * (1.0 - scale)
        positive *= scale
        negative *= scale
        inhibition_total = 1.0
        if c.research_normalize_inhibition:
            inhibition_total = sum(self._inhibitory_weight(k) for k in keys if not self.edges[k].sleeping)
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
            inhibitory_factor = weight * distance
            if c.research_normalize_inhibition:
                inhibitory_factor = inhibitory_factor / inhibition_total if inhibition_total > 0 else 0.0
            p_offer, n_offer = positive, negative
            if c.resource_precheck_enabled and c.signal_threshold_enabled:
                if weight * p_offer * distance < c.signal_threshold_for(False):
                    p_offer = 0.0
                inhibitory_offer = (inhibitory_factor * n_offer if c.research_normalize_inhibition
                                    else weight * n_offer * distance)
                if inhibitory_offer < c.signal_threshold_for(True):
                    n_offer = 0.0
                if p_offer <= 0 and n_offer <= 0:
                    continue
            fraction = 1.0
            if c.stp_enabled and (p_offer > 0 or (n_offer > 0 and not c.research_bypass_inhibition_resources)):
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
                signal_fraction = 1.0 if inhibitory and c.research_bypass_inhibition_resources else fraction
                amount = (inhibitory_factor * signal * signal_fraction
                          if inhibitory and c.research_normalize_inhibition
                          else weight * signal * signal_fraction * distance)
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
            if pos > 0 or (neg > 0 and c.research_inhibition_marks_usage):
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
        n.last_emit_us = str(self.time_us)
        n.direct = n.associative = 0.0
        self._node_timers(n)
        self._pulse(n, after=True)

    def _learn_component(self,e,fast_value,pos,neg):
        c=self.config
        if not c.plasticity:return
        mode=c.research_learning_component
        inhibitory=neg if c.inhibitory_learning_enabled else 0.0
        def amount(name):return pos+(inhibitory if mode==name else 0.0)
        changed=False
        learned=amount('fast')
        if learned>0 and c.fast_enabled:
            fast_value += -math.expm1(-c.fast_learning_rate*learned)*(1.0-fast_value)
            e.fast=asdict(FastTrace(fast_value,self.time_us))|{'time_us':str(self.time_us)}
            changed=True
        learned=amount('eligibility')
        if learned>0:
            e.eligibility=min(1.0,.7*e.eligibility+learned);changed=True
        if c.edge_consolidation_enabled:
            signal=(pos if c.activation_weight_reinforcement_enabled else 0.0)+(
                inhibitory if mode=='weight' and c.inhibition_weight_reinforcement_enabled else 0.0)
            if signal>0:
                e.weight=min(1.0,e.weight+c.associative_gain*signal);changed=True
            learned=amount('stability')
            if learned>0 and (c.consolidation_mode!='stability' or c.stability_growth_enabled):
                e.stability=min(1.0,e.stability+c.stability_gain*learned);changed=True
            learned=amount('retention')
            if learned>0 and c.retention_growth_enabled:
                e.half_life=grow(e.half_life,learned*.1,c);changed=True
        if amount('touch')>0:
            e.touches+=1;e.last_touch_us=str(self.time_us);changed=True
        if changed:self._edge_timer(e)
