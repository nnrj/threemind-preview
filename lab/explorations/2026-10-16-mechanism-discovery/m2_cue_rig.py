"""Declared M2 research copies for fixed-parent cue intervention; no Core edits."""
import closure_rig as g
from m2_relearning_cal_driver import save, lesson
from pilot_m1 import differences
import pilot_m2 as m

N = 8
SEEDS = tuple(range(1116100, 1116108))
APPARATUS_SEED = 1116002
TEST_SEED = 1116004
ARMS = ('intact', 'silenced', 'restored', 'untaught')
CUES = (('blank', '', 0.), ('weak', 'X', .4), ('strong', 'X', .8))


def cases():
    return [{'origin': i, 'seed': s, 'mode': 'S', 'lessons': 16,
             'lesson_dose': .4, 'cultivation_probe_dose': .4, 'diagnostic_doses': [0., .4, .8]}
            for i, s in enumerate(SEEDS)]


def arm(parent, name, label):
    child = parent.fork(label)
    reference = child.save()
    if name in ('intact', 'untaught'):
        return child, {'arm': name, 'changed_paths': [], 'parent_sha256': m.digest(parent.save())}
    edges = [[e['source'], e['target']] for e in child.model.graph()['edges']]
    assert edges
    child.model.intervene(edges=edges, action='silence')
    masked = child.save()
    paths = differences(reference, masked)
    assert paths and set(paths) <= {'model.silenced_edges'}
    assert {tuple(e) for e in masked['model']['silenced_edges']} == {
        tuple(e) for e in reference['model']['silenced_edges']} | {tuple(e) for e in edges}
    receipt = {'arm': name, 'edge_count': len(edges), 'edges': edges, 'changed_paths': paths,
               'parent_sha256': m.digest(parent.save()), 'before_sha256': m.digest(reference),
               'silenced_sha256': m.digest(masked)}
    if name == 'restored':
        child = g.Rig.restore(reference)
        receipt['restored_exact'] = child.save() == reference
        assert receipt['restored_exact']
    else:
        assert name == 'silenced'
    return child, receipt


def unit(folder, origin, seed=None):
    case = cases()[origin] if seed is None else cases()[0] | {'origin': origin, 'seed': seed}
    p = g.Rig('threemind', case['seed'], 'S')
    save(folder, 'birth', p)
    g.teaching(p, 0, delay=30, trained=False)
    save(folder, 'age47', p)
    baseline = g.probe(p, 'X', .4)
    save(folder, 'baseline', p)
    parents = {}; cultivation = {}
    for role in ('h0', 'h1', 'untaught'):
        child = p.fork(role)
        save(folder, role+'-initial', child)
        records = []
        for j in range(1, 17):
            if role != 'untaught':
                row = lesson(child, int(role[1]), .4)
            else:
                start = child.time
                child.tick(start)
                child.advance(start+2_000_000, {start+k*500_000: {'K': .2} for k in range(1, 5)})
                row = {'start_us': start, 'end_us': start+3_500_000, 'probe': g.probe(child, 'X', .4)}
            records.append({'lesson': j, **row, 'checkpoint': save(folder, f'{role}-lesson{j:02d}', child)})
        assert child.time == 104_500_000
        parents[role] = child
        cultivation[role] = records
    rows = []
    for history in (0, 1):
        for name in ARMS:
            parent = parents['untaught' if name == 'untaught' else 'h'+str(history)]
            before = m.digest(parent.save())
            for cue_name, cue, dose in CUES:
                label = f'h{history}-{name}-{cue_name}'
                child, receipt = arm(parent, name, label)
                initial = save(folder, label+'-initial', child)
                result = g.probe(child, cue, dose)
                final = save(folder, label+'-final', child)
                rows.append({'history': history, 'arm': name, 'cue': cue_name, 'dose': dose,
                             'initial': initial, 'checkpoint': final, 'intervention': receipt, 'probe': result})
                assert m.digest(parent.save()) == before
    return {'origin': origin, 'case': case, 'valid': True, 'baseline': baseline,
            'cultivation': cultivation, 'diagnostics': rows, 'scientific_origins': 1 if seed is None else 0}


def instrument(folder, seed=APPARATUS_SEED):
    p = g.Rig('threemind', seed, 'S')
    g.teaching(p, 0, delay=30, trained=False)
    g.probe(p, 'X', .4)
    for _ in range(16):
        lesson(p, 0, .4)
    save(folder, 'parent', p)
    hashes = {}
    for mode in ('plain', 'observed', 'restored', 'paused'):
        child = g.Rig.restore(p.save())
        g.probe(child, 'X', .8, frequent=mode == 'observed', restore_mid=mode == 'restored', pause_mid=mode == 'paused')
        hashes[mode] = m.digest(child.save())
        save(folder, mode, child)
    checks = {}
    for name in ARMS:
        child, receipt = arm(p, name, 'instrument-'+name)
        checks[name] = receipt
        save(folder, 'arm-'+name, child)
    return {'passed': len(set(hashes.values())) == 1 and checks['restored']['restored_exact'],
            'whole_hashes': hashes, 'interventions': checks, 'scientific_origins': 0, 'seed': seed}
