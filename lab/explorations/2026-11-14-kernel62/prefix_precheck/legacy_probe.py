"""R51t8 reverse intervention: frozen 5.1 emission minus its pre-STP amount test.

Only `or amount < c.activation_floor` is removed from the pre-release guard.
The nonpositive guard, source gate and post-release threshold remain unchanged.
Production local.py is read-only. This function uses its original module globals.
"""
from threemind_kernels import local as historical
globals().update({k:v for k,v in vars(historical).items() if not k.startswith('__')})

def old_emit_without_precheck(self, id):
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
        if n.activation < c.propagation_activation_min or amount <= 0:
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
                e.weight = min(1.0, e.weight + c.associative_gain * amount)
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
