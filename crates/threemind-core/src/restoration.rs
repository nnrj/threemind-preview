//! V3 local operators. Reference: Git 97d8592; accepted changes: causal/9.
use super::*;

pub(super) fn soft(c: &Config, value: f64) -> f64 {
    c.inhibition_saturation * (value.max(0.0) / c.inhibition_saturation).tanh()
}
pub(super) fn response(c: &Config, n: &Node) -> f64 {
    if c.inhibition {
        1.0 / (1.0 + c.inhibition_response_gain * soft(c, n.inhibition))
    } else {
        1.0
    }
}

impl Engine {
    pub(super) fn relax(&mut self, when: u128) {
        let elapsed = when - self.state_time;
        if elapsed == 0 {
            return;
        }
        let dt = elapsed as f64 / 1e6;
        let automatic = self.automatic_node_retention();
        let c = &self.config;
        let a = if c.activation_decay_enabled {
            (-dt / c.activation_tau).exp()
        } else {
            1.0
        };
        let tr = if c.trace_decay_enabled {
            (-dt / c.trace_tau).exp()
        } else {
            1.0
        };
        let inh = if c.inhibition_decay_enabled {
            (-dt / c.inhibition_tau).exp()
        } else {
            1.0
        };
        for n in &mut self.nodes {
            let was_active = n.activation > 0.0;
            n.activation *= a;
            n.trace *= tr;
            n.inhibition *= inh;
            if n.activation < c.activation_floor {
                n.activation = 0.0;
            }
            if was_active && n.activation == 0.0 {
                if let Some(op) = self.retention.as_mut() {
                    op.node_quiet(n.id, self.incident.get(&n.id).is_none_or(|s| s.is_empty()));
                }
            }
            if c.plasticity && c.support_decay_enabled && !automatic {
                n.support = (n.support - dt / c.support_tau * (1.0 - n.stability)).max(0.0);
            }
        }
        self.maintain_energy(when, elapsed);
        self.state_time = when;
    }
    pub(super) fn touch(&mut self, id: u64, value: f64, direct: bool) -> f64 {
        if self.silenced_nodes.contains(&id) || value <= 0.0 {
            return 0.0;
        }
        let Some(&i) = self.node_index.get(&id) else {
            return 0.0;
        };
        if self.retention.as_mut().is_some_and(|op| op.gate(id, value)) {
            return 0.0;
        }
        let c = &self.config;
        let arrived = if direct && c.energy_simulation_enabled {
            self.energy
                .afford(value, c.energy_direct_cost, Cost::Direct)
        } else {
            value
        };
        *self.transport.get_mut("received").unwrap() += arrived;
        let touch = arrived * response(c, &self.nodes[i]) * self.fatigue_response(id);
        let n = &mut self.nodes[i];
        let delta = (1.0 - n.activation).min(touch);
        n.activation += delta;
        *self.transport.get_mut("activated").unwrap() += delta;
        n.trace = (n.trace + touch).min(1.0);
        if direct {
            n.direct = n.direct.max(touch);
        } else {
            n.associative += touch;
        }
        if touch > 0.0 {
            n.last_touch_us = self.time.to_string();
        }
        if !direct {
            if let Some(novelty) = self.novelty.as_mut() {
                novelty.touch(id, touch);
            }
        }
        if let Some(mut op) = self.retention.take() {
            op.touch(id, touch, direct, self);
            self.retention = Some(op);
        }
        touch
    }
    pub(super) fn update_touched(&mut self, touched: &[(u64, f64)]) {
        let automatic = self.automatic_node_retention();
        let c = &self.config;
        for &(id, amount) in touched {
            let n = &mut self.nodes[self.node_index[&id]];
            n.touches += 1;
            n.last_touch_us = self.time.to_string();
            if c.plasticity {
                n.stability = (n.stability + 0.5 * c.stability_gain * n.activation).min(1.0);
                if !automatic {
                    n.support = (n.support + c.support_gain * amount).min(1.0);
                }
                n.local_plasticity = (1.0 - 0.72 * n.stability).max(0.12);
            }
        }
        for &(id, _) in touched {
            self.retention_node_changed(id);
        }
        if self.nodes.iter().any(|n| n.activation > 0.0) {
            self.life = "active".into();
            self.quiet_since = None;
        }
    }
    pub(super) fn stimulate(&mut self, mut stimulus: Stimulus) {
        if let Some(op) = self.retention.as_mut() {
            op.strong_intensity = stimulus.intensity;
        }
        stimulus.channels.sort_by_key(|c| c.0);
        let c = self.config.clone();
        let (mut touched, mut contacts) = (vec![], vec![]);
        for (channel, value) in stimulus.channels {
            let drive = value * stimulus.intensity;
            let request = (drive * c.direct_gain).min(1.0);
            if request <= 0.0 {
                continue;
            }
            let id = if let Some(&id) = self.receptors.get(&channel) {
                id
            } else {
                if c.max_nodes
                    .is_some_and(|limit| self.nodes.len() as u64 >= limit)
                {
                    self.resources.increment(Counter::Node, 1);
                    continue;
                }
                let id = self.next_node;
                self.next_node += 1;
                self.node_index.insert(id, self.nodes.len());
                self.receptors.insert(channel, id);
                self.nodes.push(Node {
                    id,
                    channel,
                    activation: 0.0,
                    inhibition: 0.0,
                    trace: 0.0,
                    support: 0.0,
                    stability: 0.0,
                    direct: 0.0,
                    associative: 0.0,
                    touches: 0,
                    last_touch_us: self.time.to_string(),
                    birth_us: self.time.to_string(),
                    local_plasticity: 1.0,
                    pending_inhibition: 0.0,
                    generated_inhibition: 0.0,
                });
                if c.spatial_embedding {
                    self.spatial_points.insert(id, spatial::position(&c, id));
                }
                id
            };
            let n = &self.nodes[self.node_index[&id]];
            let first = n.touches == 0;
            let p = n.local_plasticity;
            let expected = request * response(&c, n) * self.fatigue_response(id);
            let amount = self.touch(id, request, true);
            let fraction = if expected > 0.0 {
                amount / expected
            } else {
                0.0
            };
            if amount > 0.0 {
                let impulse = (drive
                    * fraction
                    * p
                    * (c.first_gain * if first { 1.0 } else { 0.0 }
                        + c.repeat_gain
                        + c.intensity_gain * (stimulus.intensity - 1.0).max(0.0)))
                .min(c.consolidation_cap);
                touched.push((id, impulse));
                contacts.push((id, amount));
            }
        }
        self.associate(touched);
        self.update_touched(&contacts);
        if let Some(op) = self.retention.as_mut() {
            op.strong_intensity = 1.0;
        }
    }
    pub(super) fn adapt_candidate(&mut self, candidate: Candidate, connected: &BTreeSet<u64>) {
        self.retention_prepare_edge((candidate.source, candidate.target));
        let c = &self.config;
        if c.edge_adaptation_limit.is_some() {
            self.resources
                .use_adaptation(self.time, c.propagation_interval_us);
        }
        let Candidate {
            score,
            source,
            target,
            si,
            ti,
        } = candidate;
        let key = (source, target);
        let impulse = (si + ti).min(c.consolidation_cap);
        if let Some(&i) = self.edge_index.get(&key) {
            let e = &mut self.edges[i];
            let internal = if self.traversed.contains(&key) {
                1.0
            } else {
                0.45
            };
            if self.edge_consolidation_enabled {
                e.weight = (e.weight
                    + c.learning_rate * score * internal * (1.0 - e.weight)
                    + 0.08 * impulse)
                    .min(1.0);
            }
            e.eligibility = (e.eligibility + 0.3 * score + 0.25 * impulse).min(1.0);
            if self.edge_consolidation_enabled {
                e.stability = (e.stability
                    + c.stability_gain * score * (1.0 + (e.touches as f64).ln_1p())
                    + impulse)
                    .min(1.0);
            }
            e.touches += 1;
            e.last_touch_us = self.time.to_string();
            self.retention_edge_changed(key);
            return;
        }
        if c.max_edges.is_some_and(|limit| {
            (self.edges.len()
                + self.retention.as_ref().map_or(0, |op| {
                    op.dormant.len() - usize::from(op.dormant.contains_key(&key))
                })) as u64
                >= limit
        }) {
            self.resources.increment(Counter::Edge, 1);
            return;
        }
        let reentry = self.nodes[self.node_index[&source]]
            .associative
            .max(self.nodes[self.node_index[&target]].associative);
        let novelty = if let Some(operator) = self.novelty.as_mut() {
            operator.birth(
                key,
                connected.contains(&source) || connected.contains(&target),
                (
                    self.nodes[self.node_index[&source]].associative,
                    self.nodes[self.node_index[&target]].associative,
                ),
                self.time,
                self.next_propagation + c.delay_us as u128,
                c,
            )
        } else if reentry > 0.0 && (connected.contains(&source) || connected.contains(&target)) {
            c.local_novelty_gain * (1.0 - (reentry / c.novelty_touch_reference).min(1.0)).max(0.0)
        } else {
            0.0
        };
        self.edge_index.insert(key, self.edges.len());
        self.edges.push(Edge {
            source,
            target,
            weight: (c.birth_weight * (0.5 + score) + 0.18 * impulse + novelty).min(1.0),
            stability: (impulse + novelty).min(1.0),
            eligibility: impulse,
            touches: 0,
            birth_us: self.time.to_string(),
            last_touch_us: self.time.to_string(),
        });
        self.outgoing.entry(source).or_default().insert(target);
        self.incident.entry(source).or_default().insert(target);
        self.incident.entry(target).or_default().insert(source);
        self.retention_edge_changed(key);
    }
    pub(super) fn generate_inhibition(&mut self, baseline: &HashMap<u64, f64>) {
        if self.config.inhibition {
            for n in &mut self.nodes {
                n.generated_inhibition +=
                    (n.activation - baseline.get(&n.id).copied().unwrap_or(0.0)).max(0.0)
                        * self.config.inhibition_gain;
            }
        }
    }
    pub(super) fn spatial_competition(&mut self) {
        let c = &self.config;
        let dt = c.step_us as f64 / 1e6;
        if c.spatial_embedding && c.spatial_competition_rate > 0.0 {
            let mut weak: BTreeMap<u64, u32> = BTreeMap::new();
            for e in &self.edges {
                if self.silenced_nodes.contains(&e.source)
                    || self.silenced_nodes.contains(&e.target)
                    || self.silenced_edges.contains(&(e.source, e.target))
                {
                    continue;
                }
                if spatial::distance(&self.spatial_points, e.source, e.target) <= c.spatial_radius
                    && self.nodes[self.node_index[&e.source]].activation
                        > self.nodes[self.node_index[&e.target]].activation
                {
                    *weak.entry(e.target).or_default() += 1;
                }
            }
            for (id, count) in weak {
                let n = &mut self.nodes[self.node_index[&id]];
                let scale = (-c.spatial_competition_rate * dt * count as f64).exp();
                n.activation *= scale;
                n.direct *= scale;
                n.associative *= scale;
            }
        }
    }
    pub(super) fn emit(&mut self) {
        let c = self.config.clone();
        let dt = c.propagation_interval_us as f64 / 1e6;
        let gain = c.propagation_rate * dt;
        let diffusion = (c.inhibition_diffusion_rate * dt).min(1.0);
        for n in &mut self.nodes {
            if c.inhibition {
                n.inhibition = soft(&c, n.inhibition + n.pending_inhibition);
                n.pending_inhibition = 0.0;
            } else {
                n.inhibition = 0.0;
                n.pending_inhibition = 0.0;
            }
        }
        let (mut signals, mut inhibitors): (BTreeMap<u64, f64>, BTreeMap<u64, f64>) =
            (BTreeMap::new(), BTreeMap::new());
        let mut traversed = BTreeSet::new();
        let mut emissions = 0;
        let mut order: Vec<_> = self.nodes.iter().map(|n| n.id).collect();
        order.sort();
        if c.propagation_limit.is_some() {
            order.sort_by(|a, b| {
                self.nodes[self.node_index[b]]
                    .activation
                    .total_cmp(&self.nodes[self.node_index[a]].activation)
                    .then_with(|| a.cmp(b))
            });
        }
        for id in order {
            if self.silenced_nodes.contains(&id) {
                continue;
            }
            let index = self.node_index[&id];
            let n = self.nodes[index].clone();
            let mut targets: Vec<_> = self
                .outgoing
                .get(&id)
                .map(|s| s.iter().copied().collect())
                .unwrap_or_default();
            if c.propagation_limit.is_some() {
                targets.sort_by(|a, b| {
                    self.edges[self.edge_index[&(id, *b)]]
                        .weight
                        .total_cmp(&self.edges[self.edge_index[&(id, *a)]].weight)
                        .then_with(|| a.cmp(b))
                });
            }
            if n.activation > 0.0 && n.activation >= c.propagation_activation_min {
                for target in targets {
                    let key = (id, target);
                    if self.silenced_edges.contains(&key) {
                        continue;
                    }
                    let i = self.edge_index[&key];
                    let mut amount = n.activation
                        * response(&c, &n)
                        * self.fatigue_response(id)
                        * self.edges[i].weight
                        * gain;
                    if c.spatial_embedding && c.neighborhood_enabled {
                        amount *= (1.0
                            - spatial::distance(&self.spatial_points, id, target)
                                / c.spatial_radius)
                            .max(0.0);
                    }
                    if amount <= 0.0 || amount < c.activation_floor {
                        continue;
                    }
                    if c.propagation_limit.is_some_and(|limit| emissions >= limit) {
                        self.resources.increment(Counter::Propagation, 1);
                        continue;
                    }
                    if c.energy_simulation_enabled {
                        amount = self.energy.afford(
                            amount,
                            c.energy_associative_cost,
                            Cost::Associative,
                        );
                    }
                    *self.transport.get_mut("sent").unwrap() += amount;
                    if amount <= 0.0 || amount < c.activation_floor {
                        *self.transport.get_mut("discarded").unwrap() += amount;
                        continue;
                    }
                    emissions += 1;
                    *signals.entry(target).or_default() += amount;
                    traversed.insert(key);
                    if c.plasticity {
                        if let Some(limit) = c.edge_adaptation_limit {
                            if self.resources.available_adaptations(
                                self.time,
                                c.propagation_interval_us,
                                limit,
                            ) == 0
                            {
                                self.resources.increment(Counter::Adaptation, 1);
                                continue;
                            }
                            self.resources
                                .use_adaptation(self.time, c.propagation_interval_us);
                        }
                        let e = &mut self.edges[i];
                        e.eligibility = (0.7 * e.eligibility + amount).min(1.0);
                        if self.edge_consolidation_enabled
                            && self.retention.as_ref().is_none_or(|op| !op.p.adaptive())
                        {
                            e.weight = (e.weight + c.associative_gain * amount).min(1.0);
                            e.stability = (e.stability + c.stability_gain * amount).min(1.0);
                        }
                        e.touches += 1;
                        e.last_touch_us = self.time.to_string();
                    }
                }
            }
            if c.inhibition && n.generated_inhibition > 0.0 {
                self.nodes[index].inhibition =
                    soft(&c, self.nodes[index].inhibition + n.generated_inhibition);
            }
            self.nodes[index].generated_inhibition = 0.0;
            let field = self.nodes[index].inhibition;
            if c.inhibition && field >= c.inhibition_propagation_min {
                let neighbours = self.incident.get(&id).cloned().unwrap_or_default();
                let mut conductances = vec![];
                for target in neighbours {
                    let mut weight: f64 = 0.0;
                    for key in [(id, target), (target, id)] {
                        if !self.silenced_edges.contains(&key) {
                            if let Some(&i) = self.edge_index.get(&key) {
                                weight = weight.max(self.edges[i].weight);
                            }
                        }
                    }
                    if weight > 0.0 {
                        conductances.push((target, weight));
                    }
                }
                let total: f64 = conductances.iter().map(|(_, w)| w).sum();
                let mut transfer = field * diffusion;
                if total > 0.0 && transfer >= c.inhibition_propagation_min {
                    if c.energy_simulation_enabled {
                        transfer = self.energy.afford(
                            transfer,
                            c.energy_inhibition_cost,
                            Cost::Inhibition,
                        );
                    }
                    if transfer >= c.inhibition_propagation_min {
                        self.nodes[index].inhibition -= transfer;
                        for (target, w) in conductances {
                            *inhibitors.entry(target).or_default() += transfer * w / total;
                        }
                    }
                }
            }
        }
        for (kind, values) in [("signal", signals), ("inhibition", inhibitors)] {
            if !values.is_empty() {
                let data: Vec<_> = values
                    .into_iter()
                    .map(|(id, v)| (id, if kind == "inhibition" { soft(&c, v) } else { v }))
                    .collect();
                self.event(self.time + c.delay_us as u128, kind, json!({"values":data}));
            }
        }
        if c.plasticity {
            let retention = if c.eligibility_decay_enabled {
                (-dt / c.eligibility_tau).exp()
            } else {
                1.0
            };
            for e in &mut self.edges {
                e.eligibility *= retention;
                if c.stability_decay_enabled {
                    e.stability =
                        (e.stability - dt / c.stability_tau * (1.0 - e.eligibility)).max(0.0);
                }
                if !traversed.contains(&(e.source, e.target))
                    && self.retention.as_ref().is_none_or(|op| !op.p.adaptive())
                {
                    e.weight *= (1.0
                        - 0.1 * c.forgetting_rate * (1.0 - (0.08 + 0.92 * e.stability)))
                        .max(0.0)
                        .powf(dt / 0.1);
                }
            }
        }
        self.traversed = traversed;
        for n in &mut self.nodes {
            n.direct = 0.0;
            n.associative = 0.0;
        }
    }
    pub(super) fn prune(&mut self) {
        if let Some(mut op) = self.retention.take() {
            op.prune(self);
            self.retention = Some(op);
            return;
        }
        if !self.config.plasticity {
            return;
        }
        let edge_count = self.edges.len();
        self.edges.retain(|e| e.weight >= self.config.prune_weight);
        if self.edges.len() != edge_count {
            self.reindex();
        }
        let node_count = self.nodes.len();
        self.nodes.retain(|n| {
            !(n.activation == 0.0
                && n.support < self.config.prune_support
                && self.incident.get(&n.id).is_none_or(|x| x.is_empty())
                && self.time - parse_time(&n.last_touch_us).unwrap()
                    > self.config.node_prune_after_us as u128)
        });
        if self.nodes.len() != node_count {
            self.reindex();
        }
        self.traversed
            .retain(|key| self.edge_index.contains_key(key));
    }
    pub(super) fn lifecycle(&mut self) {
        self.record_energy_shortage();
        if self.life == "dead" {
            return;
        }
        if self.nodes.iter().any(|n| n.activation > 0.0) {
            self.life = "active".into();
            self.quiet_since = None;
        } else if self.life != "waiting" {
            let since = *self.quiet_since.get_or_insert(self.time);
            if self.time - since >= self.config.quiescence_death_us as u128 {
                self.life = "dead".into();
                self.energy.death_us = Some(self.time.to_string());
            }
        }
    }
    pub fn intervene_action(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        action: &str,
    ) -> Result<()> {
        if !["silence", "unsilence", "disconnect_edges", "delete_nodes"].contains(&action) {
            return Err("unknown intervention action".into());
        }
        if action == "disconnect_edges" && !nodes.is_empty() {
            return Err("disconnect_edges accepts edges only".into());
        }
        if nodes.iter().any(|n| !self.node_index.contains_key(n))
            || edges.iter().any(|e| !self.edge_index.contains_key(e))
        {
            return Err("intervention target absent".into());
        }
        self.relax(self.time);
        if self.retention.is_some() {
            self.intervene_retention(&nodes, &edges, action);
            return Ok(());
        }
        let retention_nodes = nodes.clone();
        let retention_edges = edges.clone();
        let ids: BTreeSet<_> = nodes.into_iter().collect();
        let mut keys: BTreeSet<_> = edges.into_iter().collect();
        match action {
            "disconnect_edges" | "delete_nodes" => {
                if action == "delete_nodes" {
                    keys.extend(
                        self.edges
                            .iter()
                            .filter(|e| ids.contains(&e.source) || ids.contains(&e.target))
                            .map(|e| (e.source, e.target)),
                    );
                }
                self.edges.retain(|e| !keys.contains(&(e.source, e.target)));
                for key in &keys {
                    self.silenced_edges.remove(key);
                    self.traversed.remove(key);
                }
                if action == "delete_nodes" {
                    self.nodes.retain(|n| !ids.contains(&n.id));
                    for id in &ids {
                        self.silenced_nodes.remove(id);
                    }
                }
                self.reindex();
            }
            "unsilence" => {
                for id in ids {
                    self.silenced_nodes.remove(&id);
                }
                for key in keys {
                    self.silenced_edges.remove(&key);
                }
            }
            _ => {
                for id in ids {
                    self.silenced_nodes.insert(id);
                    let n = &mut self.nodes[self.node_index[&id]];
                    n.activation = 0.0;
                    n.direct = 0.0;
                    n.associative = 0.0;
                }
                self.silenced_edges.extend(keys);
            }
        }
        if let Some(mut op) = self.retention.take() {
            op.intervene(self, &retention_nodes, &retention_edges, action);
            self.retention = Some(op);
        }
        self.sequence += 1;
        self.lifecycle();
        Ok(())
    }
    pub fn intervene(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        lesion: bool,
    ) -> Result<()> {
        let action = if lesion {
            if nodes.is_empty() {
                "disconnect_edges"
            } else {
                "delete_nodes"
            }
        } else {
            "silence"
        };
        self.intervene_action(nodes, edges, action)
    }
}
