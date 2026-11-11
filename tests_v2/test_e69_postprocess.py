"""Synthetic recorded evidence for E69 audit and rendering, never a formal subject."""
import copy
import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


def modules(monkeypatch):
    values = {}
    for name in ('journal', 'analyze', 'replay'):
        spec = importlib.util.spec_from_file_location('e69_postprocess_' + name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setitem(sys.modules, name, module)
        values[name] = module
    return values


def fixture(work, j):
    blank = {'identity': 'engineering-e69-render', 'time_us': 0,
             'learning': {'motor': {'computed_updates': 0, 'committed_updates': 0},
                          'words': {'computed_updates': 0, 'committed_updates': 0}}}
    dependency = work / 'corpora/engineering.npz'
    dependency.parent.mkdir(parents=True)
    dependency.write_bytes(b'engineering opaque original; no organism weights')
    references = [{'path': 'corpora/engineering.npz', 'sha256': j.sha(dependency)}]

    def save(system, folder):
        folder.mkdir()
        refs = references if system['time_us'] else []
        body = {'identity': system['identity'], 'history': [], 'current': None, 'corpora': refs,
                'session': {'core': {'time_us': str(system['time_us']), 'nodes': [], 'edges': [],
                                     'dynamics': 'threemind.continuous-memory/5.1'},
                            'world': {'time_s': system['time_us'] / 1e6}, 'dt_us': 50000},
                'meter': {'sensor_core_body_ns': 1200000}}
        with gzip.open(folder / 'system.json.gz', 'wt', encoding='utf-8') as stream:
            json.dump(body, stream)
        (folder / 'complete.json').write_bytes(j.encoded(system))
        (folder / 'dependencies.json').write_bytes(j.encoded({'corpora': refs}))

    ledger = j.BoundaryJournal(work / 'subject', blank['identity'], save, None, copy.deepcopy,
                              work=work, reserve_gib=0, reserve_memory_gib=0)
    ledger.open_current(lambda: blank)
    camera = {'origin_m': [0., -1., 2.], 'forward': [0., .4472136, -.8944272],
              'right': [1., 0., 0.], 'up': [0., .8944272, .4472136]}
    rows = []
    for i in range(1, 9):
        rows.append({'observation': {'time_s': (i-1)*.05, 'items': [[0, 0], [1, 1], [2, 2], [3, 3]],
                     'positions': [[-.55, -.55], [.55, -.55], [-.55, .55], [.55, .55]],
                     'pointer': {'x': -.03*i, 'y': -.02*i}, 'teacher_marker': [-.55, -.55] if i < 4 else None,
                     'camera': camera, 'eye_angle_rad': [-.02*i, .01*i], 'eye_velocity_rad_s': [-.1, .04],
                     'retinal_centers': [[-.04, -.04], [.04, -.04], [-.04, .04], [.04, .04]],
                     'retinal_widths': [[.08, .08]]*4, 'eye_config': {'center_half_width': .08, 'aperture': .6},
                     'values': [1., 1., 0., 0., 1., 1., 1., 0., 1., 0., 0., 1., 1., 0., 1., 0.]},
                     'activity': {'time_us': str(i*50000), 'nodes': [{'activation': .2*i, 'inhibition': .1,
                                                                   'direct': .03*i, 'associative': .02*i}]},
                     'own_intent': {'eye_receptor': 0, 'hand_receptor': 1, 'move': i > 4},
                     'own_eye_action': [-.2, .1], 'own_hand_action': [-.1, -.2],
                     'eye_action': [-.2, .1], 'hand_action': [-.1, -.2], 'assistance': False,
                     'utterance': '请先看红色的物体，再指出。'})
    rows[-1]['expression'] = {'selected': 0, 'expected_for_scoring': 0}
    stage = work / 'stages/semantic-final'
    stage.mkdir(parents=True)
    task = {'target': 0, 'text': '请先看红色的物体，再指出。'}

    def operation(system):
        system['time_us'] = 400000
        j.put(stage / 'clips/000000.json.gz', gzip.compress(j.encoded({'kind': 'test', 'task': task, 'process': rows})))

    ledger.execute('semantic-final:000000', operation)
    score = {'start_us': 0, 'end_us': 400000, 'answer': 0, 'success': False, 'word_correct': True,
             'eye_success': False, 'hand_success': False, 'eye_before_hand': False}
    j.fixed_json(stage / 'units/000000.json', score)
    j.fixed_json(stage / 'result.json', {'start_us': 0, 'end_us': 400000, 'results': [score]})
    j.fixed_json(work / 'computation-complete.json', {'engineering': True, 'latest': ledger.pointer, 'time_us': 400000})
    return dependency


def test_audit_complete_dependency_and_video_frame(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    dependency = fixture(tmp_path, m['journal'])
    data = m['analyze'].audit(tmp_path)
    assert data['continuous'] and data['frames'] == 8 and data['boundaries'] == 2
    assert data['storage']['current_external_corpora_bytes'] == dependency.stat().st_size
    assert data['stages'][0]['summary']['word_correct'] == {'correct': 1, 'n': 1}
    receipt = m['journal'].read(tmp_path / 'analysis/audit-receipt.json')
    assert receipt['continuity_verified'] and not receipt['video_verified'] and not receipt['reports_reviewed']
    clip = m['replay'].pack(tmp_path / 'stages/semantic-final/clips/000000.json.gz')
    renderer = m['replay'].Renderer([{'t': f['t'], 'totals': f['totals']} for f in clip['frames']])
    image = renderer.frame(clip, 7)
    assert image.size == (1440, 1080)
    image.save(tmp_path / 'synthetic-frame.png')


def test_reanswer_record_and_null_order_are_not_lost(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    fixture(tmp_path, m['journal'])
    stage = tmp_path / 'stages/semantic-final'
    clip = stage / 'clips/reanswer-000000.json.gz'
    clip.write_bytes((stage / 'clips/000000.json.gz').read_bytes())
    expected = {'success': True, 'autonomous_success': True, 'eye_before_hand': None}
    m['journal'].fixed_json(stage / 'reanswers/000000.json', expected)
    assert m['replay'].pack(clip)['score'] == expected
    counts = m['analyze'].summarize_results([expected, {
        'success': True, 'autonomous_success': None, 'eye_before_hand': None}])
    assert counts['autonomous_success'] == {'correct': 1, 'n': 1}
    assert 'eye_before_hand' not in counts
    assert counts['success'] == {'correct': 2, 'n': 2}


def test_audit_rejects_lost_external_corpus(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    dependency = fixture(tmp_path, m['journal'])
    dependency.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='dependency hash mismatch'):
        m['analyze'].audit(tmp_path)


def test_audit_rejects_duplicated_simulated_frame(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    fixture(tmp_path, m['journal'])
    path = tmp_path / 'stages/semantic-final/clips/000000.json.gz'
    record = m['analyze'].load_clip(path)
    record['process'][3]['activity']['time_us'] = record['process'][2]['activity']['time_us']
    path.write_bytes(gzip.compress(json.dumps(record).encode()))
    with pytest.raises(ValueError, match='missing, duplicate or backwards'):
        m['analyze'].audit(tmp_path)
