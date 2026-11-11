"""Bounded causal study using unchanged public Core and Lab interfaces."""
import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from common import HERE, ROOT, WORK, Study, encoded, load_case, new_json, prepare, read_json

PREVIOUS = HERE.parent / '2026-09-29-input-rate-and-autonomy'
PREVIOUS_WORK = ROOT / '.work/input-rate-autonomy-20260929'
# Reuse the frozen world, recorded telemetry, and public input machinery.
# Their common imports resolve to this study's new common.py and new WORK.
sys.path.append(str(PREVIOUS))
from calibrate import done
from world import Body, SPEC, WorldTrial, motor, run_world
from threemind_core import StateImage, Stimulus
from threemind_runtime.adapters import channel_id

CONDITIONS = ('normal', 'sham', 'communication_off', 'excitation_off', 'inhibition_off',
              'temporary_off', 'edges_even', 'edges_odd')

def write_gzip(path, value):
    with gzip.open(path, 'xb') as f:
        f.write(encoded(value))

def read_gzip(path):
    return json.loads(gzip.decompress(path.read_bytes()))

def parents():
    return [c for c in read_json(PREVIOUS_WORK / 'selection-results.json')['champions'] if c['arm'] != 'random']

def parent_name(champ):
    return f"s{champ['seed']}/{champ['arm']}"

def load_old(champ):
    folder = PREVIOUS_WORK / 'cases' / champ['key']
    value = read_json(folder / 'result.json')
    image = StateImage(gzip.decompress((folder / 'parent-state.json.gz').read_bytes()))
    assert image.digest == value['state_sha256']
    return value | {'image': image, 'external_project': '59aee7a1-5248-417f-a03b-b56f858a04d9'}

def edge_keys(image):
    return [(int(e['source']), int(e['target'])) for e in image.to_dict()['edges']]

def edge_group(edge):
    return hashlib.sha256(f'internal-study-edges:{edge[0]}:{edge[1]}'.encode()).digest()[0] & 1

def change(case, changes=None, *, action=None, edges=(), label):
    before = case.engine.capture_state()
    if changes is not None:
        case.engine.reconfigure(replace(case.engine.config, **changes))
    if action is not None:
        valid = set(edge_keys(case.engine.capture_state()))
        applied = [e for e in edges if tuple(e) in valid]
        case.engine.intervene(edges=applied, action=action)
    else:
        applied = []
    case.events.append({'key': f'research:{label}:{case.engine.time_us}', 'kind': 'research_intervention',
                        'time_us': str(case.engine.time_us), 'payload': {
                            'label': label, 'changes': changes, 'action': action,
                            'requested_edges': edges, 'applied_edges': applied,
                            'before': before.digest, 'after': case.engine.capture_state().digest,
                            'method': 'public reconfigure/intervene'}})

def freeze():
    prepare()
    files = [p for p in HERE.iterdir() if p.suffix in ('.py', '.md')]
    files += [PREVIOUS / n for n in ('common.py', 'calibrate.py', 'world.py')]
    hashes = {}
    for p in files:
        relative = p.relative_to(ROOT)
        target = WORK / 'frozen-tools' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
        hashes[relative.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    new_json(WORK / 'registration.json', {'parents': parents(), 'conditions': CONDITIONS,
                                        'files': hashes, 'body': SPEC, 'kernel_changed': False})

def warmup(study, champ):
    key = 'warm/' + parent_name(champ)
    return run_world(study, key, champ['seed'], .3125, parent=load_old(champ), seconds=20)

def trial_world(study, champ, parent, condition, reference=None):
    key = 'expression/' + parent_name(champ) + '/' + condition
    if saved := done(study, key):
        return saved
    case = WorldTrial(study, key, champ['seed'], parent=parent, inherited=False)
    initial = case.engine.capture_state()
    assert initial.digest == parent['image'].digest
    body = Body(**read_gzip(WORK / 'cases' / parent['key'] / 'world.json.gz')['final_body'])
    begin = case.engine.time_us
    original = {k: case.engine.config.to_dict()[k] for k in ('propagation_rate', 'inhibition_diffusion_rate')}
    edges = edge_keys(initial)
    group = [e for e in edges if edge_group(e) == (condition == 'edges_odd')]
    rows, senses = [], []
    if condition == 'sham':
        change(case, {}, label='sham')
        assert initial.digest == case.engine.capture_state().digest
    changes = {
        'communication_off': dict.fromkeys(original, 0),
        'excitation_off': {'propagation_rate': 0},
        'inhibition_off': {'inhibition_diffusion_rate': 0},
    }.get(condition)
    if changes:
        change(case, changes, label=condition)
    for elapsed in range(0, 20_000_000, 100_000):
        if elapsed in (5_000_000, 10_000_000):
            on = elapsed == 10_000_000
            if condition == 'temporary_off':
                change(case, original if on else dict.fromkeys(original, 0), label='restore' if on else 'block')
            elif condition.startswith('edges_'):
                change(case, action='unsilence' if on else 'silence', edges=group, label='restore' if on else 'block')
        if elapsed % SPEC['sensor_interval_us'] == 0:
            stim = (body.sense(champ['seed'], case.engine.time_us) if reference is None else
                    Stimulus(case.engine.time_us, tuple(tuple(v) for v in reference['senses'][len(senses)]['channels']),
                             reference['senses'][len(senses)]['intensity']))
            case.inputs.automatic(f'ring:{elapsed}', 'ring-study', stim, configuration=SPEC,
                                  transduction={'body': asdict(body), 'mode': 'closed' if reference is None else 'matched-replay'})
            senses.append(stim.to_dict())
        case.step(case.engine.time_us)
        nodes = case.engine.observation_nodes()
        control = motor(champ['seed'], nodes)
        rows.append({'relative_us': elapsed, 'nodes': nodes, 'control': control, 'body': asdict(body),
                     'region': body.region, 'transport': case.engine.metrics()['transport']})
        body.move(control, .1)
        case.advance(begin + elapsed + 100_000)
        if case.engine.life == 'dead':
            break
    write_gzip(case.folder / 'behavior.json.gz', {'rows': rows, 'senses': senses, 'final_body': asdict(body),
                                                'supply': case.supply.capture()})
    energy = case.engine.capture_state().to_dict()['energy']
    assert energy['unserved_total'] == 0
    return case.finish({'stage': 'expression', 'condition': condition, 'begin_us': begin,
                        'start_state': initial.digest, 'parent': parent['id'], 'arm': champ['arm'],
                        'energy': energy, 'edge_group_count': len(group), 'edges_at_start': len(edges),
                        'region1_fraction': sum(r['region'] for r in rows) / len(rows)})

def expression(study):
    for champ in parents():
        parent = warmup(study, champ)
        normal = trial_world(study, champ, parent, 'normal')
        reference = read_gzip(WORK / 'cases' / normal['key'] / 'behavior.json.gz')
        for condition in CONDITIONS[1:]:
            result = trial_world(study, champ, parent, condition, reference)
            if condition == 'sham':
                assert result['state_sha256'] == normal['state_sha256'], 'identical-input replay differs'
                actual = read_gzip(WORK / 'cases' / result['key'] / 'behavior.json.gz')
                assert actual['rows'] == reference['rows']
        print(json.dumps({'stage': 'expression', 'parent': parent_name(champ), 'complete': True}), flush=True)

def channel_map(seed):
    return {name: channel_id(seed, SPEC['sensory_namespace'], i) for name, i in zip('ABCD', (0, 1, 4, 5))}

def experience(study, champ, parent, curriculum, training):
    key = f"experience/{parent_name(champ)}/{curriculum}/{training}"
    if saved := done(study, key):
        return saved
    case = WorldTrial(study, key, champ['seed'], parent=parent, inherited=False)
    baseline_rates = {k: case.engine.config.to_dict()[k] for k in ('propagation_rate', 'inhibition_diffusion_rate')}
    if training == 'blocked':
        change(case, dict.fromkeys(baseline_rates, 0), label='formation-communication-off')
    symbols = channel_map(champ['seed'])
    existing = {n['channel'] for n in case.engine.capture_state().to_dict()['nodes']}
    assert set(symbols.values()) <= existing, 'receptor identities must already exist'
    pairs = ('AB', 'CD') if curriculum == 'P' else ('AD', 'CB')
    for i, pair in enumerate([p for repeat in (20, 10, 10) for p in pairs for _ in range(repeat)]):
        case.pulse([symbols[x] for x in pair], .8, 1_000_000, source='controlled-experience')
        if case.engine.life == 'dead':
            raise RuntimeError('training ended unexpectedly; preserve and stop')
    return case.finish({'stage': 'experience', 'curriculum': curriculum, 'training': training,
                        'baseline_rates': baseline_rates, 'channels': symbols, 'last_input_age_us': 1_000_000,
                        'parent': parent['id'], 'energy': case.engine.capture_state().to_dict()['energy']})

def test_experience(study, champ, parent, cue, communication, *, inherited=False):
    key = parent['key'].replace('experience/', 'birth-probe/' if inherited else 'probe/', 1) + f'/{cue}/{communication}'
    if saved := done(study, key):
        return saved
    case = WorldTrial(study, key, champ['seed'], parent=parent, inherited=inherited)
    rates = parent['extra']['baseline_rates']
    change(case, rates if communication == 'on' else dict.fromkeys(rates, 0), label='expression-communication')
    begin = case.engine.time_us
    carrier = None
    if cue != 'none':
        carrier = case.send([parent['extra']['channels'][cue]], .5, source='manual-probe')
    case.step(begin)
    rows = []
    body = Body(.3125)
    while case.engine.time_us < begin + 15_000_000 and case.engine.life != 'dead':
        elapsed = case.engine.time_us - begin
        nodes = case.engine.observation_nodes()
        control = motor(champ['seed'], nodes)
        delta = 10_000 if elapsed < 2_000_000 else 100_000
        rows.append({'relative_us': elapsed, 'nodes': nodes, 'control': control, 'body': asdict(body),
                     'transport': case.engine.metrics()['transport']})
        body.move(control, delta / 1e6)
        case.advance(case.engine.time_us + delta)
    # Exact terminal sample is retained for temporal-window end rankings.
    rows.append({'relative_us': case.engine.time_us - begin, 'nodes': case.engine.observation_nodes(),
                 'control': motor(champ['seed'], case.engine.observation_nodes()), 'body': asdict(body),
                 'transport': case.engine.metrics()['transport']})
    write_gzip(case.folder / 'behavior.json.gz', {'rows': rows, 'cue': cue, 'carrier': carrier})
    energy = case.engine.capture_state().to_dict()['energy']
    assert energy['unserved_total'] == 0
    return case.finish({'stage': 'birth-probe' if inherited else 'probe', 'cue': cue, 'communication': communication,
                        'curriculum': parent['extra']['curriculum'], 'training': parent['extra']['training'],
                        'channels': parent['extra']['channels'], 'begin_us': begin, 'carrier': carrier,
                        'parent': parent['id'], 'energy': energy})

def validate_birth(study):
    from threemind_lab import notebooks
    from threemind_lab.database import LOCAL_USER
    path=WORK/'birth-validation-registration.json'
    if not path.exists():
        files={}
        for name in ('validation.zh.md','validation.en.md','experiment.py'):
            raw=(HERE/name).read_bytes()
            target=WORK/'frozen-extension'/name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw)
            files[name]=hashlib.sha256(raw).hexdigest()
        for lang in ('zh','en'):
            notebooks.save_note(study.db,study.project,LOCAL_USER,study.identity('birth-design:'+lang),{
                'operation_id':study.identity('birth-design-write:'+lang),'expected_revision':0,'kind':'note',
                'collection_id':study.meta['notebook_id'],'title':'出生后经历保留验证 / Birth validation '+lang,
                'body':{'format':'markdown','text':(HERE/f'validation.{lang}.md').read_text(encoding='utf-8')}})
        new_json(path,{'files':files,'new_instances':32,'selection':'all four parents, both normal-training histories'})
    for champ in parents():
        for curriculum in ('P','Q'):
            parent=load_case(study,f'experience/{parent_name(champ)}/{curriculum}/normal')
            for cue in ('A','none'):
                for communication in ('on','off'):
                    test_experience(study,champ,parent,cue,communication,inherited=True)
        print(json.dumps({'stage':'birth-validation','parent':parent_name(champ),'complete':True}),flush=True)

def histories(study):
    for champ in parents():
        base = warmup(study, champ)
        for curriculum in ('P', 'Q'):
            for training in ('normal', 'blocked'):
                parent = experience(study, champ, base, curriculum, training)
                for cue in ('A', 'C', 'none'):
                    for communication in ('on', 'off'):
                        test_experience(study, champ, parent, cue, communication)
                print(json.dumps({'stage': 'history', 'parent': parent_name(champ), 'curriculum': curriculum,
                                  'training': training, 'complete': True}), flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['register', 'expression', 'histories', 'validate-birth'])
    command = parser.parse_args().command
    if command == 'register':
        return freeze()
    study = Study()
    try:
        {'expression':expression,'histories':histories,'validate-birth':validate_birth}[command](study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({'budget_stop': True, 'error': str(exc)})
        raise
    finally:
        study.db.close()

if __name__ == '__main__':
    main()
