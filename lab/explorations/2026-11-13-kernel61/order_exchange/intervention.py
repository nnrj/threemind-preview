"""Prepared E21-style /6.1 research intervention; no engine is created here.

Inputs must already be settled to the same current clock by the declared
preparation procedure. This module does not teach, advance time or edit Core.
It has not yet been registered for a formal batch.
"""
import copy
import math

from threemind_core import StateImage
from threemind_kernels.decay61 import crossing_seconds
from threemind_kernels.local61_config import Local61Config

GROUPS = ('W', 'S', 'N', 'D')
EDGE_HISTORY = ('stability', 'eligibility', 'decay_age', 'half_life', 'birth_us',
                'last_touch_us', 'last_pass_us', 'touches')
NODE_HISTORY = ('support', 'stability', 'local_plasticity', 'decay_age', 'half_life',
                'birth_us', 'last_touch_us', 'touches', 'isolated_us')
NODE_DYNAMIC = ('activation', 'inhibition', 'trace', 'direct', 'associative',
                'pending_inhibition', 'generated_inhibition', 'fatigue', 'salience', 'last_emit_us')
EDGE_DYNAMIC = ('short_term', 'fast', 'novelty_source', 'novelty_target', 'novelty_deadline_us')


def deadline(now, state_us, seconds, interval):
    if seconds is None:
        return None
    due = max(now + 1, int(state_us) + math.ceil(seconds * 1e6) + 1)
    return ((due + interval - 1) // interval) * interval


def exchange(recipient, donor, groups=()):
    groups = tuple(groups)
    if len(set(groups)) != len(groups) or set(groups) - set(GROUPS):
        raise ValueError('unknown or duplicate state group')
    original_a, original_b = recipient.to_dict(), donor.to_dict()
    a, b = copy.deepcopy(original_a), copy.deepcopy(original_b)
    if any(d['dynamics'] != 'threemind.continuous-memory/6.1' for d in (a, b)):
        raise ValueError('genuine /6.1 states required')
    same = ('schema', 'dynamics', 'config', 'definition', 'definition_hash', 'time_us',
            'life', 'sources_open', 'quiet_since_us', 'energy', 'pools', 'energy_rng',
            'energy_serial', 'completed_emission_us')
    if any(a[k] != b[k] for k in same):
        raise ValueError('configuration, common clock, lifecycle or energy differs')
    c, now = Local61Config(**a['config']), int(a['time_us'])
    if c.deletion_strategy != 'local' or c.energy_simulation_enabled or c.dormant_traces_enabled:
        raise ValueError('this apparatus supports current default local deletion without energy or dormancy')
    for d in (a, b):
        if d['queue'] or d['silenced_nodes'] or d['silenced_edges']:
            raise ValueError('settled, unsilenced states with empty event queues required')
        if any(int(row['state_us']) != now for row in d['nodes'] + d['edges']):
            raise ValueError('all stored values must refer to the common current clock')
        if any(e['novelty_deadline_us'] is not None for e in d['edges']):
            raise ValueError('pending novelty is not part of this exchange')
        for e in d['edges']:
            for name in ('short_term', 'fast'):
                if e[name] is not None and int(e[name]['time_us']) != now:
                    raise ValueError('fast state is not settled to the common clock')
        if any(n['id'] != n['channel'] for n in d['nodes']):
            raise ValueError('fixed-function addresses required')
    an, bn = ({n['channel']: n for n in d['nodes']} for d in (a, b))
    ae, be = ({(e['source'], e['target']): e for e in d['edges']} for d in (a, b))
    if an.keys() != bn.keys() or ae.keys() != be.keys():
        raise ValueError('anonymous channels or directed topology differ')
    changes = []

    def assign(target, source, fields, location):
        for name in fields:
            if target[name] != source[name]:
                changes.append({'location': location + [name], 'before': copy.deepcopy(target[name]),
                                'after': copy.deepcopy(source[name])})
                target[name] = copy.deepcopy(source[name])

    for channel, node in an.items():
        if 'N' in groups: assign(node, bn[channel], NODE_HISTORY, ['node', channel])
        if 'D' in groups: assign(node, bn[channel], NODE_DYNAMIC, ['node', channel])
    for pair, edge in ae.items():
        if 'W' in groups: assign(edge, be[pair], ('weight',), ['edge', *pair])
        if 'S' in groups: assign(edge, be[pair], EDGE_HISTORY, ['edge', *pair])
        if 'D' in groups: assign(edge, be[pair], EDGE_DYNAMIC, ['edge', *pair])

    timers = {(kind, source, target): when for kind, source, target, when in a['timers']}
    if 'D' in groups:
        timers = {key: when for key, when in timers.items() if key[0] not in (0, 1)}
        timers.update({(k, source, target): when for k, source, target, when in b['timers'] if k in (0, 1)})
        active = sorted(n['id'] for n in a['nodes'] if n['activation'] > 0)
        if active != a['active']:
            changes.append({'location': ['active'], 'before': a['active'], 'after': active})
            a['active'] = active
    original_edges = {(e['source'], e['target']): e for e in original_a['edges']}
    original_nodes = {n['id']: n for n in original_a['nodes']}
    if 'W' in groups or 'S' in groups:
        for pair, edge in ae.items():
            if all(edge[k] == original_edges[pair][k] for k in ('weight', 'decay_age', 'half_life')):
                continue
            seconds = crossing_seconds(edge['weight'], edge['decay_age'], edge['half_life'], c.prune_weight, c) if c.plasticity else None
            due = deadline(now, edge['state_us'], seconds, c.structure_check_interval_us)
            key = (2, *pair)
            if due is None: timers.pop(key, None)
            else: timers[key] = str(due)
    if 'N' in groups or 'D' in groups:
        incident = {id for pair in ae for id in pair}
        for node in a['nodes']:
            if all(node[k] == original_nodes[node['id']][k] for k in ('support', 'decay_age', 'half_life', 'activation')):
                continue
            key = (3, node['id'], 0)
            if c.plasticity and not c.retain_nodes and node['activation'] == 0 and node['id'] not in incident:
                seconds = (crossing_seconds(node['support'], node['decay_age'], node['half_life'], .006, c)
                           if c.support_decay_enabled else (0.0 if node['support'] < .006 else None))
                due = deadline(now, node['state_us'], seconds, c.structure_check_interval_us)
                if due is None: timers.pop(key, None)
                else: timers[key] = str(due)
            else:
                timers.pop(key, None)
    new_timers = [[k, source, target, when] for (k, source, target), when in timers.items()]
    new_timers.sort(key=lambda row: (int(row[3]), row[0], row[1], row[2]))
    if new_timers != a['timers']:
        changes.append({'location': ['timers'], 'before': a['timers'], 'after': new_timers})
        a['timers'] = new_timers
    output = StateImage.from_dict(a)
    if not groups and output.digest != recipient.digest:
        raise AssertionError('sham exchange changed the complete state')
    assert recipient.to_dict() == original_a and donor.to_dict() == original_b
    return output, {'schema': 'threemind.research-order-exchange61/1', 'groups': [g for g in GROUPS if g in groups],
                    'time_us': now, 'alignment': 'fixed anonymous channel and directed channel pair',
                    'recipient_sha256': recipient.digest, 'donor_sha256': donor.digest,
                    'after_sha256': output.digest, 'changes': changes,
                    'derived_changes': 'active-node index and schedules required by the declared state exchange',
                    'artificial_intervention': True, 'created_engines': 0}
