"""Isolated /5.2 candidate: selectable persistent decay, inherited /5.1 signaling.

This development copy is not registered in the production kernel catalogue.
Node support and connection weight keep contribution ages for non-exponential
laws. Existing local learning assignments add new contributions or scale old
ones; decay projections advance ages explicitly. Fast states remain unchanged.
"""
from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from types import SimpleNamespace

from threemind_core import Stimulus
from threemind_core.energy import supply_payload
from threemind_core.spec import MAX_TIME, timestamp
from threemind_kernels.local5 import Local5Node, Local5Edge
from threemind_kernels.local51 import Local51Config, Local51Engine, MECHANISMS as OLD_MECHANISMS
from threemind_kernels.local_deadlines import LocalDeadlines
from threemind_kernels.mechanisms import FastTrace, ShortTermState, number
from threemind_kernels.retention import decay, crossing
from decay_reference import Contribution, Trace, CURVES, advance_age, seconds_for_age

KERNEL_ID='threemind.continuous-memory/5.2'
STATE_SCHEMA='threemind.continuous-memory-state/5.2'
HYPOTHESIS_ID='threemind.hypotheses/continuous-memory52'
MECHANISMS=tuple(x for x in OLD_MECHANISMS if x[0]!='threemind.adaptive-half-life/2')+(
    ('threemind.experience-dependent-decay/1','local-touch-emission-expiry'),)

@dataclass(frozen=True,slots=True)
class Local52Config(Local51Config):
    decay_curve:str='exponential'
    retention_relaxation_enabled:bool=True

    def __post_init__(self):
        Local51Config.__post_init__(self)
        if self.decay_curve not in CURVES:raise ValueError('unknown persistent decay curve')
        if type(self.retention_relaxation_enabled) is not bool:raise ValueError('retention relaxation switch must be boolean')
        if self.decay_curve!='exponential' and (self.consolidation_mode!='adaptive-half-life' or self.node_retention_mode!='automatic'):
            raise ValueError('non-exponential decay requires adaptive connection and automatic node retention')

def _trace(row):
    return Trace(row.decay_curve,tuple(Contribution(*x) for x in row.decay_contributions))

def _put_trace(row,trace):
    object.__setattr__(row,'decay_contributions',tuple((c.amount,c.age) for c in trace.components))

def _initialize_trace(row):
    field='support' if isinstance(row,Local5Node) else 'weight'
    if row.decay_contributions is None:
        value=getattr(row,field)
        parts=((value,0.),) if value>0 and row.decay_curve!='exponential' else ()
        object.__setattr__(row,'decay_contributions',parts)
    else:
        object.__setattr__(row,'decay_contributions',tuple(tuple(c) for c in row.decay_contributions))

def _assign_local_value(row,name,value):
    # Decay itself bypasses this hook. Each ordinary learning or damage write
    # is recorded before a later operation can cancel it in a net difference.
    if name in ('support','weight') and getattr(row,'decay_curve','exponential')!='exponential' and getattr(row,'decay_contributions',None) is not None:
        previous=getattr(row,name,None)
        if previous is not None and value>previous:_put_trace(row,_trace(row).reinforce(value-previous))
        elif previous is not None and value<previous:_put_trace(row,_trace(row).scale(value/previous if previous else 0.))
    object.__setattr__(row,name,value)

@dataclass(slots=True)
class Local52Node(Local5Node):
    decay_curve:str='exponential'
    decay_contributions:tuple|None=None
    __setattr__=_assign_local_value
    def __post_init__(self):_initialize_trace(self)

@dataclass(slots=True)
class Local52Edge(Local5Edge):
    decay_curve:str='exponential'
    decay_contributions:tuple|None=None
    __setattr__=_assign_local_value
    def __post_init__(self):_initialize_trace(self)

def definition(config):
    return dict(schema='threemind.kernel-definition/1',kernel_id=KERNEL_ID,state_schema=STATE_SCHEMA,
        hypothesis_id=HYPOTHESIS_ID,operators=[dict(id=k,phase=p) for k,p in MECHANISMS],config=config.to_dict())

class Local52Engine(Local51Engine):
    dynamics=KERNEL_ID
    state_schema=STATE_SCHEMA
    config_type=Local52Config
    definition=staticmethod(definition)

    def node_type(self,*args,**kwargs):
        kwargs.setdefault('decay_curve',self.config.decay_curve)
        return Local52Node(*args,**kwargs)

    def edge_type(self,*args,**kwargs):
        kwargs.setdefault('decay_curve',self.config.decay_curve)
        return Local52Edge(*args,**kwargs)

    def _decay_parameters(self):
        c=self.config
        return c if c.retention_relaxation_enabled else SimpleNamespace(
            memory_half_life_min_s=c.memory_half_life_min_s,memory_half_life_decay_rate=0.)

    def _decay_value(self,row,field,seconds):
        c=self._decay_parameters()
        if row.decay_curve=='exponential':
            value,h=decay(getattr(row,field),row.half_life,seconds,c)
        else:
            age,h=advance_age(row.half_life,seconds,c.memory_half_life_min_s,c.memory_half_life_decay_rate)
            history=_trace(row).elapse(age)
            value=history.value();_put_trace(row,history)
        object.__setattr__(row,field,value)
        row.half_life=h

    def _crossing(self,row,field,floor):
        if floor<=0:return None
        c=self._decay_parameters()
        if row.decay_curve=='exponential':return crossing(getattr(row,field),row.half_life,floor,c)
        horizon=(MAX_TIME-int(row.state_us))/1e6
        age,_=advance_age(row.half_life,horizon,c.memory_half_life_min_s,c.memory_half_life_decay_rate)
        need=_trace(row).crossing_age(floor,age)
        if need is None:return None
        seconds=seconds_for_age(row.half_life,need,c.memory_half_life_min_s,c.memory_half_life_decay_rate)
        if int(row.state_us)+max(1,math.ceil(seconds*1e6)+1)>MAX_TIME:return None
        return seconds

    def reconfigure(self,config):
        if type(config) is not self.config_type or config.decay_curve!=self.config.decay_curve:
            raise ValueError('decay curve is fixed at birth; conversion is not restoration')
        super().reconfigure(config)

    def _restore(self,doc):
        for group in ('nodes','edges'):
            for row in doc.get(group,[]):
                if 'decay_curve' not in row or not isinstance(row.get('decay_contributions'),(list,tuple)):
                    raise ValueError('missing version 5.2 contribution history')
        super()._restore(doc)

    def _project_node(self, node, when):
        n, c = copy.copy(node), self.config
        dt = (when - int(n.state_us)) / 1e6
        if self.restored_learning and dt == 0:
            return n
        for key, tau, enabled in (
            ("activation", c.activation_tau, c.activation_decay_enabled),
            ("trace", c.trace_tau, c.trace_decay_enabled),
            ("inhibition", c.inhibition_tau, c.inhibition_decay_enabled),
        ):
            if enabled:
                setattr(n, key, getattr(n, key) * math.exp(-dt / tau))
        if n.activation < c.activation_floor:
            n.activation = 0.0
        if c.plasticity and c.support_decay_enabled:
            if c.node_retention_mode == "automatic":
                self._decay_value(n, "support", dt)
            else:
                n.support = max(0.0, n.support - dt / c.support_tau * (1 - n.stability))
        if self.restored_learning:
            if n.fatigue != 0 or n.salience != 0:
                recovery = math.exp(-dt / c.strong_fatigue_tau_s)
                n.fatigue *= recovery
                n.salience *= recovery
        else:
            n.fatigue *= math.exp(-dt / c.strong_fatigue_tau_s)
            n.salience *= math.exp(-dt / c.strong_fatigue_tau_s)
        n.state_us = str(when)
        return n

    def _project_edge(self, edge, when):
        # Same operation order as /5; only exp(-period / tau) is cached.
        # Identity comparison also invalidates it after explicit reconfigure
        # and restoration. The cache is derived and is never serialized.
        e, c = copy.copy(edge), self.config
        dt = (when - int(e.state_us)) / 1e6
        if c.consolidation_mode == "adaptive-half-life":
            if dt and c.plasticity:
                self._decay_value(e, "weight", dt)
            period = c.propagation_interval_us
            before = self._before_emission and when == self.time_us
            complete = max(0, (when - int(before)) // period * period)
            count = (complete - int(e.completed_period_us)) // period
            if count > 0 and c.plasticity:
                seconds = period / 1e6
                if self._eligibility_config is not c:
                    self._eligibility_period_retention = (
                        math.exp(-seconds / c.eligibility_tau) if c.eligibility_decay_enabled else 1.0
                    )
                    self._eligibility_config = c
                ratio = self._eligibility_period_retention
                retained = ratio**count
                total = e.eligibility * (count if ratio == 1.0 else ratio * (1 - retained) / (1 - ratio))
                if c.stability_decay_enabled:
                    e.stability = max(0.0, e.stability - seconds / c.stability_tau * (count - total))
                if c.eligibility_decay_enabled:
                    e.eligibility *= retained
            e.completed_period_us = str(complete)
        elif not c.plasticity:
            period = c.propagation_interval_us
            before = self._before_emission and when == self.time_us
            e.completed_period_us = str(max(0, (when - int(before)) // period * period))
        e.state_us = str(when)
        return e

    def _node_timers(self, n):
        c, id = self.config, n.id
        if n.activation > c.activation_floor and c.activation_decay_enabled and c.activation_floor > 0:
            self.timers.set((1, id, 0), self._delay(c.activation_tau * math.log(n.activation / c.activation_floor)))
        else:
            self.timers.discard((1, id, 0))
        connected = any(not self.edges[k].sleeping for k in self.incident.get(id, ()))
        if c.retain_nodes or not c.plasticity or connected:
            self.timers.discard((3, id, 0))
            return
        inactive = (
            c.activation_tau * math.log(n.activation / c.activation_floor)
            if n.activation > c.activation_floor and c.activation_decay_enabled and c.activation_floor > 0
            else 0.0
        )
        if n.activation > 0 and (not c.activation_decay_enabled or c.activation_floor == 0):
            return
        if c.node_retention_mode == "automatic":
            seconds = (
                self._crossing(n, "support", 0.006)
                if c.support_decay_enabled
                else (0.0 if n.support < 0.006 else None)
            )
        elif c.prune_support == 0:
            seconds = max(
                0.0, (max(int(n.isolated_us), int(n.last_touch_us)) + c.dead_node_retention_us - self.time_us) / 1e6
            )
        else:
            rate = (1 - n.stability) / c.support_tau if c.support_decay_enabled else 0
            seconds = (
                max(0.0, (n.support - c.prune_support) / rate)
                if rate
                else (0.0 if n.support < c.prune_support else None)
            )
            if seconds is not None:
                seconds = max(seconds, (int(n.last_touch_us) + c.node_prune_after_us - self.time_us) / 1e6)
        self.timers.set((3, id, 0), None if seconds is None else self._delay(max(inactive, seconds)))

    def _edge_timer(self, e):
        c, key = self.config, (e.source, e.target)
        if not c.plasticity:
            self.timers.discard((2, *key))
        elif c.consolidation_mode == "adaptive-half-life":
            seconds = self._crossing(e, "weight", c.dormant_prune_weight if e.sleeping else c.prune_weight)
            self.timers.set((2, *key), None if seconds is None else self._delay(seconds))
        else:
            period = c.propagation_interval_us
            current_due = (
                self.restored_learning
                and self._before_emission
                and self.time_us > 0
                and (self.time_us % period == 0 and int(e.completed_period_us) < self.time_us)
            )
            self.timers.set((2, *key), self.time_us if current_due else (self.time_us // period + 1) * period)
        if e.novelty_deadline_us is not None:
            self.timers.set((4, *key), int(e.novelty_deadline_us))

    def _validate(self):
        c = self.config
        if set(self.audit) != {
            "node_visits",
            "edge_visits",
            "scan_visits",
            "expiry_checks",
            "nodes_deleted",
            "edges_deleted",
            "nodes_awakened",
            "edges_awakened",
        } or set(self.transport) != {"sent", "received", "activated", "discarded"}:
            raise ValueError("invalid local audit or transport fields")
        if any(type(v) is not int or not 0 <= v < 2**64 for v in self.audit.values()):
            raise ValueError("invalid local audit counter")
        for v in self.transport.values():
            number(v, "transport counter", high=1.7976931348623157e308)
        if self.life not in ("waiting", "active", "dead") or (
            self.quiet_since_us is not None and self.quiet_since_us > self.time_us
        ):
            raise ValueError("invalid lifecycle")
        for key in ("sequence", "next_event", "next_node", "energy_serial", "energy_rng"):
            if type(getattr(self, key)) is not int or not 0 <= getattr(self, key) < 2**64:
                raise ValueError("invalid local counter")
        if type(self.sources_open) is not bool or set(self.pools) != set(range(c.energy_region_count)):
            raise ValueError("invalid local identities or pools")
        for v in self.pools.values():
            number(v, "local energy pool", high=c.energy_capacity)
        for n in self.nodes.values():
            for t in (n.state_us, n.birth_us, n.last_touch_us, n.isolated_us, n.energy_us):
                if timestamp(t) > self.time_us:
                    raise ValueError("invalid node clock")
            if (
                type(n.id) is not int
                or type(n.channel) is not int
                or not 0 <= n.channel < 2**32
                or type(n.touches) is not int
                or n.touches < 0
                or type(n.sleeping) is not bool
            ):
                raise ValueError("invalid local node identity")
            for k, v in asdict(n).items():
                if isinstance(v, (int, float)) and k not in ("id", "channel", "touches", "region", "sleeping"):
                    number(v, "local node value", high=1.7976931348623157e308)
            if (
                any(getattr(n, k) > 1 for k in ("activation", "trace", "support", "stability", "local_plasticity"))
                or n.reserve > c.energy_node_capacity
                or not c.memory_half_life_min_s <= n.half_life <= c.memory_half_life_max_s
            ):
                raise ValueError("invalid local node bounds")
            if (
                c.energy_simulation_enabled
                and c.energy_starvation_damage_enabled
                and (5, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node energy deadline")
            if (
                not n.sleeping
                and n.id not in self.silenced_nodes
                and (n.activation > 0 or n.inhibition >= c.inhibition_propagation_min or n.pending_inhibition > 0)
                and (0, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node emission deadline")
            if (
                c.plasticity
                and not c.retain_nodes
                and not any(not self.edges[k].sleeping for k in self.incident.get(n.id, ()))
                and (n.activation == 0 or (c.activation_decay_enabled and c.activation_floor > 0))
            ):
                floor = 0.006 if c.node_retention_mode == "automatic" else c.prune_support
                deletable = (
                    n.support < floor
                    or (c.node_retention_mode == "manual" and floor == 0)
                    or (c.support_decay_enabled and (c.node_retention_mode == "automatic" or n.stability < 1))
                )
                if n.decay_curve != "exponential" and c.support_decay_enabled and self._crossing(n, "support", floor) is None:
                    deletable = False
                if deletable and (3, n.id, 0) not in self.timers.positions:
                    raise ValueError("missing node reclamation deadline")
        for key, e in self.edges.items():
            for t in (e.state_us, e.birth_us, e.last_touch_us, e.last_pass_us):
                if timestamp(t) > self.time_us:
                    raise ValueError("invalid edge clock")
            for k in ("weight", "stability", "eligibility", "novelty_source", "novelty_target"):
                number(getattr(e, k), "local edge value", high=1.7976931348623157e308)
            if (
                key[0] == key[1]
                or any(getattr(e, k) > 1 for k in ("weight", "stability", "eligibility"))
                or not c.memory_half_life_min_s <= e.half_life <= c.memory_half_life_max_s
            ):
                raise ValueError("invalid local edge bounds")
            if e.short_term:
                ShortTermState(**(e.short_term | {"time_us": timestamp(e.short_term["time_us"])})).recovered(
                    self.time_us, c.short_term()
                )
            if e.fast:
                FastTrace(**(e.fast | {"time_us": timestamp(e.fast["time_us"])})).projected(
                    self.time_us, c.fast_trace()
                )
            expiring = (
                c.consolidation_mode == "legacy-stability"
                or self._crossing(e, "weight", c.dormant_prune_weight if e.sleeping else c.prune_weight)
                is not None
            )
            if c.plasticity and expiring and (2, *key) not in self.timers.positions:
                raise ValueError("missing connection expiry deadline")
            if e.novelty_deadline_us is not None and (4, *key) not in self.timers.positions:
                raise ValueError("missing novelty deadline")
        seen = set()
        for t, id, kind, payload in self.queue:
            if id in seen:
                raise ValueError("duplicate queued event")
            seen.add(id)
            if kind == "stimulus":
                s = Stimulus.from_dict(payload)
                if s.time_us != t:
                    raise ValueError("queued stimulus clock mismatch")
            elif kind == "energy":
                supply_payload(**payload)
            elif kind == "signal":
                for source, target, value, features in payload["messages"]:
                    if (
                        type(source) is not int
                        or not -1 <= source < 2**63
                        or type(target) is not int
                        or not 0 <= target < 2**64
                    ):
                        raise ValueError("invalid queued signal identities")
                    number(value, "queued signal", high=1e12)
                    if len(features) != 4 or any(not math.isfinite(v) or not -1 <= v <= 1 for v in features):
                        raise ValueError("invalid queued features")
            elif kind == "inhibition":
                for id, value in payload["values"]:
                    if type(id) is not int or not 0 <= id < 2**64:
                        raise ValueError("invalid queued inhibition identity")
                    number(value, "queued inhibition", high=1e12)
            elif kind == "wake":
                if (
                    len(payload["edge"]) != 2
                    or any(type(id) is not int or not 0 <= id < 2**64 for id in payload["edge"])
                    or payload["sender"] not in payload["edge"]
                ):
                    raise ValueError("invalid wake sender")
                number(payload["value"], "queued wake", high=1e12)

        period=c.propagation_interval_us
        if self.completed_emission_us!=self.time_us//period*period:raise ValueError('invalid 5.2 completed emission phase')
        for n in self.nodes.values():
            if timestamp(n.last_emit_us)>self.time_us:raise ValueError('invalid source emission clock')
        for e in self.edges.values():
            if timestamp(e.completed_period_us)>self.time_us or int(e.completed_period_us)%period:
                raise ValueError('invalid completed-period anchor')
        for field,rows in [('support',self.nodes.values()),('weight',self.edges.values())]:
            for row in rows:
                if row.decay_curve!=c.decay_curve:raise ValueError('object decay curve disagrees with kernel definition')
                if row.decay_curve=='exponential':
                    if row.decay_contributions:raise ValueError('exponential objects must use the original scalar representation')
                else:
                    history=_trace(row)
                    if not math.isclose(history.value(),getattr(row,field),rel_tol=2e-12,abs_tol=1e-15):
                        raise ValueError('persistent value disagrees with contribution history')
                    if any(x.age>(int(row.state_us)-int(row.birth_us))*1.000001 for x in history.components):
                        raise ValueError('contribution age exceeds elapsed time at the minimum allowed scale')
        if c.decay_curve!='exponential':
            expected=copy.copy(self)
            expected.timers=LocalDeadlines()
            for n in self.nodes.values():expected._node_timers(expected._project_node(n,self.time_us))
            for e in self.edges.values():expected._edge_timer(expected._project_edge(e,self.time_us))
            actual={tuple(r[:3]):int(r[3]) for r in self.timers.rows() if r[0] in (2,3)}
            desired={tuple(r[:3]):int(r[3]) for r in expected.timers.rows() if r[0] in (2,3)}
            if actual.keys()!=desired.keys():raise ValueError('persistent expiry set disagrees with decay history')
            for key,when in desired.items():
                if abs(actual[key]-when)>max(8,math.ulp(float(when))*8):
                    raise ValueError('persistent expiry time disagrees with decay history')
