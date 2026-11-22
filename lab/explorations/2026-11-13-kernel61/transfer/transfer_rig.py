"""6.1 transfer apparatus: unchanged declared edge packages and body choice."""
import copy
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'criteria'))
import rig as base
Rig, m = base.Rig, base.m
matching, teaching, case_seed, probe = base.matching, base.teaching, base.case_seed, base.probe
differences = base.differences
FAST = ('eligibility', 'fast', 'short_term', 'novelty_source', 'novelty_target', 'novelty_deadline_us')

def settle(rig):
    if rig.kind != 'threemind':
        return
    before = rig.time
    rig.model.reconfigure(rig.model.config)
    if rig.model.time_us != before:
        raise RuntimeError('settlement advances time')


def transfer(recipient, donor, sources='XY', mode='bundle'):
    """Channel-aligned directed-edge exchange on already settled research copies."""
    a, b = recipient.save(), donor.save()
    if recipient.kind != 'threemind' or donor.kind != 'threemind' or a['time_us'] != b['time_us']:
        raise ValueError('compatible same-time /6.1 required')
    ca, cb = a['model'], b['model']
    if ca['config'] != cb['config'] or ca['queue'] or cb['queue']:
        raise ValueError('same configuration and empty queues required')
    ida = {n['channel']: n['id'] for n in ca['nodes']}
    idb = {n['channel']: n['id'] for n in cb['nodes']}
    symbolic_b = {idb[c]: s for s, c in donor.channels.items()}
    def selected(c, ids, channels):
        return [e for e in c['edges'] if e['source'] in {ids[channels[s]] for s in sources}
                and e['target'] in {ids[channels[s]] for s in 'AB'}]
    old, incoming = selected(ca, ida, recipient.channels), selected(cb, idb, donor.channels)
    if len(old) != 2 or len(incoming) != 2:
        raise ValueError('two complete routes required')
    if any(e['novelty_deadline_us'] is not None for e in old+incoming):
        raise ValueError('pending novelty not permitted for this exchange')
    if any(int(e['state_us']) != recipient.time for e in old+incoming):
        raise ValueError('edge clocks must be settled to common time')
    old_by_source = {e['source']: e for e in old}
    keys = {(e['source'], e['target']) for e in old}
    incoming_keys = {(e['source'], e['target']) for e in incoming}
    replacements, remap = [], {}
    for edge in incoming:
        src = ida[recipient.channels[symbolic_b[edge['source']]]]
        dest = ida[recipient.channels[symbolic_b[edge['target']]]]
        original = old_by_source[src]
        new = copy.deepcopy(edge if mode != 'fast' else original)
        new['source'], new['target'] = src, dest if mode != 'fast' else original['target']
        if mode == 'persistent':
            for field in FAST:
                new[field] = copy.deepcopy(original[field])
        elif mode == 'fast':
            for field in FAST:
                new[field] = copy.deepcopy(edge[field])
        elif mode != 'bundle':
            raise ValueError('unknown exchange package')
        replacements.append(new)
        remap[(edge['source'], edge['target'])] = (new['source'], new['target'])
    ca['edges'] = sorted([e for e in ca['edges'] if (e['source'], e['target']) not in keys]+replacements,
                         key=lambda e: (e['source'], e['target']))
    if mode != 'fast':
        ca['timers'] = [v for v in ca['timers'] if not (v[0] in (2, 4) and (v[1], v[2]) in keys)]
        for k, src, dst, t in cb['timers']:
            if k in (2, 4) and (src, dst) in incoming_keys:
                rs, rd = remap[(src, dst)]
                ca['timers'].append([k, rs, rd, t])
        ca['timers'].sort(key=lambda v: (int(v[3]), v[0], v[1], v[2]))
    child = Rig.restore(a)
    changes = differences(recipient.save(), child.save())
    if not set(changes) <= {'model.edges', 'model.timers'}:
        raise RuntimeError('exchange changed an undeclared field')
    if donor.save() != b:
        raise RuntimeError('donor mutation')
    return child, {'sources': sources, 'mode': mode, 'changed_paths': changes,
                   'removed': old, 'inserted': replacements, 'donor_whole_sha256': m.digest(b),
                   'recipient_whole_sha256': m.digest(recipient.save())}
