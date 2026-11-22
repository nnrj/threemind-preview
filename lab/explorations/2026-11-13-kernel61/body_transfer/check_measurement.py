"""Offline check of input boundaries and complete-window process scoring."""
import json
import importlib.util
from pathlib import Path
import study
spec = importlib.util.spec_from_file_location('r51h_transfer_analysis', Path(__file__).with_name('analyze.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
process, direction, FIELDS = analysis.process, analysis.direction, analysis.FIELDS


def check():
    root = Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/body-memory61-v1')
    parents = [study.f.read(root / 'cases' / c['key'] / 'result.json') for c in study.f.read(root / 'cases.json')
               if c['stage'] == 'retention' and c['delay'] == 1]
    materials = study.ROOT / '.work/memory-transfer-20260930'
    rows = study.cases(materials, parents, .3)
    assert len(rows) == 280 and sum(c['domain'] == 'none' for c in rows) == 40
    for c in rows:
        frames = [r for r in c['inputs'] if r['kind'] in ('physical', 'probe')]
        assert len(frames) == (0 if c['domain'] == 'none' else 20)
        assert sum(r['kind'] == 'probe' for r in frames) == int(c['domain'] != 'none')
        if frames:
            assert [int(r['stimulus']['time_us']) - c['begin_us'] for r in frames] == list(range(20000, 400001, 20000))
            assert frames[-1]['kind'] == 'probe'
            assert all(float(r['stimulus']['intensity']) == .3 for r in frames)
    blank = {t: {f: [0., 0.] for f in FIELDS} for t in range(0, 5600001, 100000)}
    cue = {t: {f: ([.01, 0.] if f == 'activation' else [0., 0.]) for f in FIELDS} for t in blank}
    result, error = process(cue, blank, 600000, 5600000)
    assert abs(result['activation']['signed_integrals'][0] - .05) < 1e-12 and error < 1e-12
    assert direction(result['activation'], 0) == 'correct' and direction(result['activation'], 1) == 'opposite'
    incomplete = dict(blank); incomplete.pop(5600000)
    try: process(cue, incomplete, 600000, 5600000)
    except AssertionError: pass
    else: raise AssertionError('Missing blank tail was accepted')
    return {'passed': True, 'case_count': 280, 'scientific_individuals_created': 0,
            'historical_materials_read_only': True, 'complete_window_required': True}


if __name__ == '__main__': print(json.dumps(check()))
