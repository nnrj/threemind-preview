"""R63k: continuous teaching and registered single-test diagnostic copies."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'src')]
import spec
import support as s
from allocation import disk_allocation
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.readout_session import ReadoutSession

sys.path.insert(0, str(HERE))
assert Path(spec.__file__).resolve() == HERE / 'spec.py'

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('45f4b62f-ad9b-547c-bbe6-0fb3f77c54f0')
RAW_CAP = 2**30
READERS = {k: {'enabled': False} for k in ('structural_readout', 'temporal_readout', 'activity_readout')}


def read(p): return json.loads(Path(p).read_bytes())
def image(p): return ArtifactCodec.decode(Path(p).read_bytes())
def engine(config=None, state=None): return resolve_kernel(spec.KERNEL).create(config, state, backend='native')


def save(p, state):
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = ArtifactCodec.encode(state)
    assert ArtifactCodec.decode(raw).digest == state.digest
    return s.blob(p, raw)


def observe(e):
    before = e.capture_state().digest
    nodes, graph, metrics = e.observation_nodes(), e.graph(), e.metrics()
    assert before == e.capture_state().digest
    assert len(nodes) <= 2000 and metrics['edges'] <= 20000
    return {'time_us': e.time_us, 'nodes': nodes, 'graph': graph, 'metrics': metrics}


def execute(parent, stage, initial=None, folder=None, mode='observed', observer_state=None):
    """Execute declared time advances. All captures are passive at the current clock."""
    started = time.monotonic()
    e = engine(None if initial else {'seed': parent['seed'], 'stp_facilitation_tau_s': parent['tau']}, initial)
    born = e.capture_state()
    assert e.time_us == stage['begin_us'] and (initial is None or born.digest == initial.digest)
    delivered, scheduled, events, points, snapshots = [], [], [], [], {}
    def sink(event, entry):
        if entry: delivered.append(entry)
    session = ReadoutSession(e, record=events.append, config=READERS, state=observer_state, event_sink=sink)
    assert e.capture_state().digest == born.digest
    if folder:
        folder.mkdir(parents=True, exist_ok=False)
        save(folder / 'initial.tmind', born)
        s.base.original(folder / 'initial-observer.json', session.capture())
    observing = False
    restored = False
    commands = spec.commands(parent, stage)

    def budget():
        if time.monotonic() - started > 600:
            raise RuntimeError('condition budget exceeded; preserve in-flight')

    for number, command in enumerate(commands):
        budget()
        if command['op'] == 'input':
            assert e.time_us == command['enqueue_us']
            receipts = session.schedule([{'stimulus': Stimulus.from_dict(command['stimulus'])}],
                                        source=command['source'], adapter_id='anonymous-frames', at=0,
                                        envelope_id=uuid5(NS, parent['key'] + '/' + stage['name'] + f'/{number}'))
            scheduled.append({'command_index': number, 'enqueue_us': e.time_us, 'receipt': receipts[0]})
        elif command['op'] == 'snapshot':
            before = e.capture_state()
            snapshots[command['name']] = {'sha256': before.digest, 'observation': None if mode == 'plain' else observe(e)}
            if folder: save(folder / (command['name'] + '.tmind'), before)
            assert e.capture_state().digest == before.digest
        elif command['op'] == 'begin_observation':
            observing = True
            if mode != 'plain': points.append(observe(e))
        elif command['op'] == 'advance':
            until = command['until_us']
            # The final same-time call also processes newly enqueued current-time input.
            first = True
            while first or e.time_us < until:
                first = False
                step = 20000 if observing and mode != 'sparse' else 100000
                target = min(until, e.time_us + step)
                session.advance_to(target, guard=budget)
                assert e.time_us == target and e.life != 'dead', 'unexpected incomplete state'
                if observing and mode != 'plain': points.append(observe(e))
                if mode in ('restored', 'paused') and not restored and observing and e.time_us >= stage['probe_us'] + 1000000:
                    checkpoint, reader = e.capture_state(), session.capture()
                    if mode == 'restored':
                        e = engine(state=ArtifactCodec.decode(ArtifactCodec.encode(checkpoint)))
                        session = ReadoutSession(e, record=events.append, state=reader, event_sink=sink)
                    else:
                        time.sleep(.01)
                    assert e.capture_state().digest == checkpoint.digest
                    restored = True
                if e.time_us >= until: break
        else:
            raise AssertionError(command)
    assert e.time_us == stage['end_us'] and session.bus.pending_count() == 0
    assert len(delivered) == sum(c['op'] == 'input' for c in commands)
    final = e.capture_state()
    result = {'parent': parent, 'stage': stage, 'status': 'complete', 'kernel': spec.KERNEL,
              'initial_sha256': born.digest, 'final_sha256': final.digest,
              'parent_sha256': initial.digest if initial else None, 'life': e.life,
              'inputs': len(delivered), 'wall_seconds': time.monotonic() - started,
              'snapshots': {k: v['sha256'] for k, v in snapshots.items()}}
    if folder:
        save(folder / 'final.tmind', final)
        s.base.original(folder / 'observer.json', session.capture())
        s.base.original(folder / 'input.json', {'parent': parent, 'stage': stage, 'commands': commands, 'mappings': spec.ids(parent['seed'])})
        s.base.original(folder / 'trajectory.json.gz', {'points': points, 'snapshots': snapshots}, compressed=True)
        s.base.original(folder / 'delivered.json.gz', delivered, compressed=True)
        s.base.original(folder / 'scheduled.json.gz', scheduled, compressed=True)
        s.base.original(folder / 'cursor.json', {'next_command': len(commands), 'end_us': e.time_us, 'mode': mode})
        s.base.original(folder / 'result.json', result)
    return result, final, session.capture()


def frozen_check(work):
    frozen = read(work / 'frozen.json')
    for rel, digest in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT / rel) == digest, rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == frozen['native_sha256']
    assert s.sha(work / 'cases.json') == frozen['cases_sha256']
    assert read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    previous = read(work.parent / 'transfer-confirmation-63-rerun-v1/publication/completion.json')
    assert previous['coverage'] == 'verified' and previous['pending'] == 0 and not previous['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 28.125 * 2**30
    historical = spec.history_check()
    historic_costs = {}
    for parent in spec.parents():
        files = [p for p in (spec.OLD / 'cases/sequence' / parent['key']).rglob('*') if p.is_file()]
        historic_costs[parent['key']] = {'logical_bytes': sum(p.stat().st_size for p in files),
                                       'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}
    work.mkdir()
    s.base.original(work / 'historical-check.json', historical)
    s.base.original(work / 'cases.json', spec.parents())
    from check_measurement import check
    s.base.original(work / 'measurement-check.json', check())
    paths = [HERE / name for name in ('study.py', 'spec.py', 'analyze.py', 'check_measurement.py', 'compact_run.py', 'storage-amendment.zh.md', 'storage-amendment.en.md', 'protocol.zh.md', 'protocol.en.md')]
    paths += [HERE.parent / 'support.py', HERE.parent / 'allocation.py', ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py',
              ROOT / 'lab/explorations/2026-10-01-priority-memory/sequence.py',
              ROOT / 'lab/explorations/2026-10-01-priority-memory/runner.py',
              ROOT / 'lab/explorations/2026-10-01-priority-memory/analyze.py',
              ROOT / 'lab/explorations/2026-10-01-priority-memory/analyze_sequence.py']
    from _threemind_native import _threemind_native as native
    frozen = {'kernel': spec.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': read(work.parent / 'criteria-63-rerun-v1/frozen.json')['production_sources'],
              'cases_sha256': s.sha(work / 'cases.json'), 'independent_blocks': 4,
              'historical_unit_costs': historic_costs, 'estimate_multiplier': 1.5,
              'historical_allocated_multiplier_stop': 2., 'source_cost_multiplier_stop': 1.5}
    s.base.original(work / 'frozen.json', frozen)
    for p in paths:
        dest = work / 'frozen-source' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63k:order-recall:20261115:v1', 'title': 'R63k：6.3事件先后顺序的保持与表达',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [spec.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_blocks': 4, 'teaching_parents': 96, 'diagnostic_copies': 576, 'stages': 672}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63k protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        receipt = {'project': PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', receipt)
        print(json.dumps(receipt), flush=True)


def apparatus(work):
    import psutil
    frozen_check(work)
    assert not any((work / n).exists() for n in ('apparatus.json', 'in-flight.json', 'STOP'))
    with s.base.worker_lock(work), s.base.Guard(work):
        s.base.original(work / 'in-flight.json', {'phase': 'apparatus', 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        p = next(p for p in spec.parents((spec.APPARATUS_SEED,)) if p['shared'] and p['gap_s'] == .05 and p['order'] == 'AB' and p['tau'] == 0)
        train = spec.stages(p)[0]
        _, parent, observer = execute(p, train, folder=work / 'apparatus/train')
        hashes = {}
        stage = next(x for x in spec.stages(p) if x.get('delay_s') == 1 and x.get('cue') == .5)
        for mode in ('plain', 'observed', 'sparse', 'restored', 'paused'):
            _, final, _ = execute(p, stage, parent, work / 'apparatus' / mode, mode, observer)
            hashes[mode] = final.digest
        assert len(set(hashes.values())) == 1
        result = {'passed': True, 'scientific_blocks': 0, 'seed': spec.APPARATUS_SEED,
                  'observation_restore_pause_hashes': hashes}
        s.base.original(work / 'apparatus.json', result)
        (work / 'in-flight.json').unlink()
    s.base.original(work / 'apparatus-resources.json', read(work / 'resource-summary.json'))
    print(json.dumps(result), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / n).exists() for n in ('summary.json', 'in-flight.json', 'STOP'))
    start = time.monotonic()
    completed = 0
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for p in spec.parents():
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            unit = work / 'cases' / p['key']
            assert not unit.exists(), 'Inspect complete boundary; never silently resume'
            s.base.original(work / 'in-flight.json', {'unit': p['key'], 'pid': os.getpid(), 'created': psutil.Process().create_time()})
            unit_start = time.monotonic()
            for stage in spec.stages(p):
                if stage['kind'] == 'train':
                    _, parent, observer = execute(p, stage, folder=unit / stage['name'])
                else:
                    execute(p, stage, parent, unit / stage['name'], observer_state=observer)
            (work / 'in-flight.json').unlink()
            completed += 1
            s.base.atomic_json(work / 'current.json', {'completed': completed, 'total': 96, 'last': p['key']})
            print(p['key'], flush=True)
            files = [f for f in unit.rglob('*') if f.is_file()]
            size = sum(f.stat().st_size for f in files)
            allocated = sum(disk_allocation(f)['allocated_bytes'] for f in files)
            budget = read(work / 'frozen.json')
            old_cost = budget['historical_unit_costs'][p['key']]['allocated_bytes']
            expected_cost = old_cost * budget['estimate_multiplier']
            s.base.original(work / 'costs' / (str(completed) + '.json'), {'parent': p['key'], 'bytes': size,
                'allocated_bytes': allocated, 'historical_allocated_bytes': old_cost,
                'expected_allocated_bytes': expected_cost, 'wall_seconds': time.monotonic() - unit_start})
            reason = ('allocated unit cost at least twice historical' if allocated >= 2 * old_cost else
                      'unit cost exceeds estimate by 50%' if allocated > expected_cost * 1.5 else
                      'unit duration exceeds 10 minutes' if time.monotonic() - unit_start > 600 else
                      'two-hour budget' if time.monotonic() - start > 7200 else
                      'originals budget' if sum(f.stat().st_size for f in work.rglob('*') if f.is_file()) > RAW_CAP else None)
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': p['key']})
                break
            gc.collect()
        if completed == 96:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'parents': 96, 'stages': 672,
                                                  'independent_blocks': 4, 'wall_seconds': time.monotonic() - start})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register', 'apparatus', 'run'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
