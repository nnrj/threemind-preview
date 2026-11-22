"""Declared teaching lives, diagnostic copies and continuous relearning courses."""
import gc
import retention_rig as g


def save(folder, name, rig):
    state = rig.save()
    receipt = g.m.original(folder/(name+'.json.gz'), state, compressed=True)
    return {'path': name+'.json.gz', 'time_us': rig.time,
            'whole_sha256': g.m.digest(state), 'file_receipt': receipt}


def calibration_case(folder, seed, mode, history):
    rig = g.Rig('threemind', seed, mode)
    birth = save(folder, 'birth', rig)
    g.teaching(rig, history, delay=30, trained=False)
    initial = save(folder, 'course-initial', rig)
    course = g.course(rig, history, always_complete=True)
    final = save(folder, 'course-final', rig)
    return {'seed': seed, 'mode': mode, 'history': history, 'birth': birth,
            'initial': initial, 'final': final, 'course': course,
            'values': [r['directed_process_mean'] for r in course['lessons']]}


def unit(folder, case, selections):
    seed, mode = case['seed'], case['mode']
    histories = []
    for history in (0, 1):
        parent = g.Rig('threemind', seed, mode)
        birth = save(folder, f'h{history}-birth', parent)
        teaching = g.teaching(parent, history, delay=case['delay'])
        g.m.original(folder/f'h{history}-teaching.json', teaching)
        parent_receipt = save(folder, f'h{history}-parent', parent)
        before = parent.save()
        graph = parent.model.graph()
        assert parent.save() == before
        nodes = {n['channel']: n['id'] for n in graph['nodes']}
        associated = 'A' if history == 0 else 'B'
        edges = [e for e in graph['edges'] if e['source'] in {nodes.get(parent.channels[s]) for s in 'XY'}
                 and e['target'] == nodes.get(parent.channels[associated])]
        stored = [e for e in before['model']['edges'] if e['source'] in {parent.channels[s] for s in 'XY'}
                  and e['target'] == parent.channels[associated]]
        tests = {}
        for name, cue, dose in (('none', '', 0.), ('weak', 'X', .4), ('strong', 'X', .8), ('joint', 'XY', .8)):
            child = parent.fork(name)
            initial = save(folder, f'h{history}-{name}-initial', child)
            result = g.probe(child, cue, dose)
            final = save(folder, f'h{history}-{name}-final', child)
            tests[name] = result | {'initial': initial, 'final': final}
            del child
        assert parent.save() == before
        naive = g.Rig('threemind', seed, mode)
        naive_birth = save(folder, f'h{history}-naive-birth', naive)
        g.teaching(naive, history, delay=case['delay'], trained=False)
        naive_initial = save(folder, f'h{history}-naive-initial', naive)
        relearning = untrained = None
        if selections[mode]['valid']:
            threshold = selections[mode]['threshold']
            learner = parent.fork('relearning')
            initial = save(folder, f'h{history}-relearning-initial', learner)
            relearning = g.course(learner, history, threshold)
            relearning.update(initial=initial, final=save(folder, f'h{history}-relearning-final', learner))
            untrained = g.course(naive, history, threshold)
            untrained.update(initial=naive_initial, final=save(folder, f'h{history}-naive-final', naive))
            del learner
        assert parent.save() == before
        histories.append({'history': history, 'birth': birth, 'parent': parent_receipt,
                          'target_edges': edges, 'stored_target_edges': stored,
                          'sleeping_target_edges': sum(e['sleeping'] for e in stored),
                          'tests': tests, 'naive_birth': naive_birth,
                          'naive_initial': naive_initial, 'relearning': relearning, 'untrained': untrained})
        del parent, naive
        gc.collect()
    return case | {'package': 'X2-63', 'valid': True, 'histories': histories}
