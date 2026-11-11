"""E53: bounded full-world development and causal forks. No Core edits."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_communication import CommunicationOcean, CommunicationProtocol, load
from lab.tools.ocean_contact_cli import save, run
from lab.tools.ocean_species import seed_founders
from lab.tools.service_study import Study, StudyConfig

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/ocean-communication-20261006'
SOURCES = {
    'turn44': ROOT / '.work/ocean-species-20261004/turning-species/E38-control-02-44-900000000.tmspecies',
    'turn59': ROOT / '.work/ocean-species-20261004/turning-species/E38-control-02-59-900000000.tmspecies',
    'engulf15': ROOT / '.work/ocean-species-20261004/event-species/shared-00-199620000-15.tmspecies',
}


def study(prepare=False, usage=None):
    if usage is None:
        usage = read_json(WORK / 'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-communication/1', 'E53 个体间声音、学习与交流', HERE, WORK, usage,
                            instance_limit=24, wall_seconds=7200, storage_soft=3 * 2**30,
                            storage_hard=4 * 2**30, usage_soft_delta=6, usage_hard_delta=8), prepare=prepare)


def register(usage):
    s = study(True, usage)
    try:
        write_json(WORK / 'usage.json', {'used_percent': usage, 'observed_epoch': time.time()})
        for source in range(2):
            p = read_json(ROOT / 'lab/templates/ocean-material-full-habitat.json')
            p.update(schema='threemind.ocean-communication/1', founders=37, population_limit=67,
                     seed=530100, environment_seed=532101 + source, total_birth_limit=128)
            w = CommunicationOcean(p)
            cohorts = {}
            for k, (name, path) in enumerate(SOURCES.items()):
                ids = list(range(k, 37, 3))
                seed_founders(w, path.read_bytes(), ids)
                cohorts.update({i: name for i in ids})
                destination = WORK / 'founders' / path.name
                destination.parent.mkdir(exist_ok=True)
                if not destination.exists():
                    shutil.copy2(path, destination)
            # Candidate installation replaces newborn engines at time zero.
            w.input_buses = {}
            w.configure(cohorts, {name: 'core' for name in SOURCES}, cross_only=True)
            save(w, WORK / 'sources' / str(source))
        for path in (ROOT / 'lab/tools').glob('ocean*.py'):
            target = WORK / 'apparatus' / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)
        print(json.dumps({'project': s.project, 'sources': 2, 'founders': 37, 'cap': 67}), flush=True)
    finally:
        s.db.close()


def intervene(world, operation):
    """Only experimental copies: hearing edges, matched nonhearing edges, rescue."""
    receipt = {}
    for i, engine in world.engines.items():
        if not world.bodies[i].physical or engine.life == 'dead':
            continue
        state = engine.capture_state().to_dict()
        nodes = {n['id'] for n in state['nodes'] if n['channel'] in world.hearing_channels(i)}
        target = [e for e in state['edges'] if e['source'] in nodes or e['target'] in nodes]
        target.sort(key=lambda e: (-e['weight'], e['source'], e['target']))
        target = target[:64]
        others = [e for e in state['edges'] if e['source'] not in nodes and e['target'] not in nodes]
        matched = []
        for edge in target:
            if not others:
                break
            k = min(range(len(others)), key=lambda n: abs(others[n]['weight'] - edge['weight']))
            matched.append(others.pop(k))
        chosen = matched if operation == 'matched' else target
        pairs = [(e['source'], e['target']) for e in chosen]
        engine.intervene(edges=pairs, action='silence')
        if operation == 'rescue':
            engine.intervene(edges=pairs, action='unsilence')
        receipt[str(i)] = {'target': [(e['source'], e['target']) for e in target],
                           'matched': [(e['source'], e['target']) for e in matched],
                           'target_weight': sum(e['weight'] for e in target),
                           'matched_weight': sum(e['weight'] for e in matched)}
    world.research['hearing_edge_intervention'] = {'time_us': world.time_us, 'operation': operation, 'receipt': receipt}
    return receipt


def execute(snapshot, name, seconds, mode='live', lesion=None, checkpoint_seconds=None):
    s = study()
    try:
        s.allow_extension()
        world = load(snapshot)
        world.p = world.protocol_model.model_validate(world.p.model_dump(by_alias=True) | {'hearing_mode': mode})
        world.research['hearing_control'] = {'time_us': world.time_us, 'mode': mode, 'scope': 'other individuals only'}
        if lesion:
            intervene(world, lesion)
        folder = WORK / 'cases' / name
        if folder.exists():
            raise RuntimeError('existing case retained; choose a new stage name')
        # The ordinary runner creates the folder. Open the process stream lazily.
        process = None
        old_step = world.step
        def step(record=None):
            nonlocal process
            def observed(row):
                nonlocal process
                if record:
                    record(row)
                if row['communication']['emitted'] or row['communication']['received']:
                    if process is None:
                        process = gzip.open(folder / 'communication.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1)
                    members = []
                    for i, body in world.bodies.items():
                        if not body.physical:
                            continue
                        engine = world.engines[i]
                        nodes = engine.observation_nodes()
                        hearing = world.hearing_channels(i)
                        members.append({'id': i, 'cohort': world.cohorts[i], 'position': body.position,
                                        'action': world.action(i), 'grains': body.grains, 'captured': body.captured,
                                        'active_nodes': sum(n['activation'] > 0 for n in nodes),
                                        'hearing_activation': sum(n['activation'] for n in nodes
                                                                  if n['channel'] in hearing)})
                    process.write(json.dumps({'time_us': row['time_us'], 'members': members,
                                              **row['communication']}, separators=(',', ':')) + '\n')
            return old_step(observed)
        world.step = step
        class Clock:
            born_wall = time.monotonic()
        s.active_case = Clock()
        try:
            result = run(world, folder, seconds, guard=s.guard,
                         checkpoint_s=min(150, seconds) if checkpoint_seconds is None else checkpoint_seconds,
                         trajectory_interval_us=200000, activity_interval_us=1000000)
        finally:
            if process:
                process.close()
            s.active_case = None
        print(json.dumps({'case': name, 'project': s.project, 'status': result['status'], 'error': result['error'],
                          'wall_seconds': result['wall_seconds'], 'groups': result['groups'],
                          'communication': result['communication']}), flush=True)
        if result['status'] not in ('horizon_paused', 'physical_extinction'):
            raise RuntimeError('bounded run stopped; partial evidence and final state retained')
    finally:
        s.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['register', 'run'])
    parser.add_argument('--usage', type=int)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--name')
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--mode', choices=['live', 'muted', 'scrambled'], default='live')
    parser.add_argument('--lesion', choices=['target', 'matched', 'rescue'])
    args = parser.parse_args()
    if args.command == 'register':
        if args.usage is None:
            parser.error('actual account usage required')
        register(args.usage)
    else:
        if not args.snapshot or not args.name or not args.seconds or args.seconds <= 0:
            parser.error('--snapshot, --name and positive --seconds required')
        execute(args.snapshot, args.name, args.seconds, args.mode, args.lesion)
