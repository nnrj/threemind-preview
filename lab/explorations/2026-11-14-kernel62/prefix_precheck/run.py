"""R51t8: bounded causal study. Never mutates a production kernel or old original."""
import argparse
import ast
from copy import deepcopy
from dataclasses import replace
import gc
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import textwrap
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(HERE))
import research_precheck as r
sys.path.insert(0, str(HERE.parent / 'prefix_recovery'))
import continuation_v2 as c
import research_transport as prior
s = c.s
from threemind_core import StateImage, Stimulus

OLD = Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-recovery62-v1')
NS = UUID('bd35cbd7-3f65-503d-a72d-c692af8c39d2')
VARIANTS = {
    'pre-old-high': dict(research_transport='old-inhibition', resource_precheck=True, activation_signal_threshold=.004),
    'old-without-pre': dict(research_transport='old-emission-no-precheck'),
    'pre-current-low': dict(research_transport='reference', resource_precheck=True),
    'pre-current-high': dict(research_transport='reference', resource_precheck=True, activation_signal_threshold=.004),
    'pre-old-low': dict(research_transport='old-inhibition', resource_precheck=True),
}
CONTROLS = {
    'current-low': 'cases/stability-immediate',
    'current-high': 'threshold/cases/threshold-current',
    'old-low': 'transport/cases/old-inhibition',
    'old-high': 'threshold/cases/threshold-old-inhibition',
    'old-full': 'transport/cases/old-emission',
}


class Guard(s.base.Guard):
    """The existing guard's budget plus an explicit unsafe-resource STOP check."""
    def watch(self):
        import psutil
        while not self.stop.is_set():
            try:
                self.last = s.base.resource_check(self.work)
                private = psutil.Process().memory_info().private
                self.peak_private = max(self.peak_private, private)
                for k, v in self.last['available_bytes'].items():
                    self.minimum[k] = min(v, self.minimum.get(k, v))
                if not self.last['safe']:
                    raise RuntimeError('resource reserve breached: ' + str(self.last['violations']))
                if private > 2**30:
                    raise RuntimeError('private memory exceeds 1 GiB')
                if time.monotonic() - self.started > 7200:
                    raise RuntimeError('two-hour host limit')
            except Exception as exc:
                try:
                    with (self.work / 'STOP').open('x', encoding='utf8') as f:
                        json.dump({'reason': str(exc), 'epoch': time.time(), 'last': self.last}, f)
                except FileExistsError:
                    pass
                return
            self.stop.wait(1)


def put(path, image):
    s.packed(path, image.to_dict())


def get(path):
    return StateImage.from_dict(s.unpack(path))


def scientific(image):
    d = deepcopy(image.to_dict() if hasattr(image, 'to_dict') else image)
    for k in ('schema', 'dynamics', 'definition', 'definition_hash'):
        d.pop(k, None)
    for k in ('research_transport', 'resource_precheck'):
        d['config'].pop(k, None)
    return d


def client_context():
    s.base.load_env()
    import httpx
    return s.base.OperationsClient(url='http://127.0.0.1:8877',
        username=os.environ.get('THREEMIND_API_USERNAME'), password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'), transport=httpx.HTTPTransport(trust_env=False),
        require_auth=True, source='ai')


def prepare(work):
    assert not work.exists(), 'new batch only'
    assert not (OLD / 'in-flight.json').exists() and not (OLD / 'STOP').exists()
    receipt = s.read(OLD / 'publication/completion.json')
    assert receipt['coverage'] == 'verified' and receipt['pending'] == 0
    assert s.base.resource_check(work.parent)['safe']
    assert shutil.disk_usage(work.parent).free > 28 * 2**30
    work.mkdir()
    s.write(work / 'prior-delivery.json', receipt)
    shutil.copyfile(OLD / 'cases.json', work / 'cases.json')
    shutil.copytree(OLD / 'materials', work / 'materials')
    # Only the explicit five archived controls are copied; the old study is read-only.
    for name, rel in CONTROLS.items():
        shutil.copytree(OLD / rel, work / 'controls' / name)
    manifest = {p.relative_to(work).as_posix(): s.sha(p) for folder in ('materials', 'controls')
                for p in (work / folder).rglob('*') if p.is_file()}
    s.write(work / 'reference-manifest.json', manifest)
    s.write(work / 'initial-resources.json', s.base.resource_check(work))
    print(json.dumps({'prepared': str(work), 'reference_files': len(manifest)}), flush=True)


def apparatus(work):
    assert not (work / 'apparatus.json').exists()
    case = deepcopy(s.read(work / 'cases.json')['short/train-0'])
    case['end_us'] = 10_000_000
    rows = [x for x in s.inputs(work, case, True) if int(x['source_policy']['resolved_at_us']) <= case['end_us']]
    cfg = dict(seed=9291199, **case['initial_config'], **s.STABLE)
    # Verify the reverse intervention is literally one removed comparison.
    original = textwrap.dedent(inspect.getsource(r.HistoricalEngine._emit))
    expected = original.replace('def _emit(', 'def old_emit_without_precheck(').replace(' or amount < c.activation_floor', '')
    assert ast.dump(ast.parse(expected)) == ast.dump(ast.parse(inspect.getsource(r.old_emit_without_precheck)))
    checks = []

    def drive(e, step=100000, observe=False, restore=False, pause=False):
        index = 0
        altered = False
        while True:
            while index < len(rows) and int(rows[index]['source_policy']['resolved_at_us']) == e.time_us:
                e.inject(Stimulus.from_dict(rows[index]['stimulus'])); index += 1
            e.advance_to(e.time_us)
            if observe:
                before = e.capture_state().digest
                e.observation_nodes(); e.capture_state()
                assert e.capture_state().digest == before
            if not altered and e.time_us >= 2_000_000 and (restore or pause):
                state = e.capture_state()
                if restore:
                    e = type(e)(state=StateImage.from_dict(state.to_dict()))
                if pause:
                    time.sleep(.01)
                assert e.capture_state().digest == state.digest
                altered = True
            if e.time_us == case['end_us']:
                break
            times = [case['end_us'], e.time_us + step]
            if index < len(rows):
                times.append(int(rows[index]['source_policy']['resolved_at_us']))
            e.advance_to(min(times))
        return e.capture_state()

    started = time.monotonic()
    with s.base.worker_lock(work), Guard(work):
        for mode in ('reference', 'old-inhibition', 'old-emission'):
            a = drive(prior.ResearchEngine(prior.ResearchConfig(**cfg, research_transport=mode)))
            b = drive(r.ResearchEngine(r.ResearchConfig(**cfg, research_transport=mode)))
            assert scientific(a) == scientific(b), mode
            checks.append({'prior_equivalence': mode, 'passed': True})
        for name, patch in VARIANTS.items():
            hashes = {}
            for label, step, observe, restore, pause in (
                ('plain', 100000, False, False, False), ('observed', 100000, True, False, False),
                ('restored', 100000, True, True, False), ('partitioned', 37000, True, False, False),
                ('paused', 100000, True, False, True)):
                image = drive(r.ResearchEngine(r.ResearchConfig(**cfg, **patch)), step, observe, restore, pause)
                hashes[label] = image.digest
            assert len(set(hashes.values())) == 1, (name, hashes)
            checks.append({'condition': name, 'hashes': hashes})
            assert not (work / 'STOP').exists()
    s.write(work / 'apparatus.json', {'passed': True, 'checks': checks,
            'single_removed_comparison': True, 'separate_encoding': True, 'wall_seconds': time.monotonic() - started})
    print(json.dumps({'apparatus': True, 'checks': len(checks), 'seconds': time.monotonic() - started}), flush=True)


def register(work):
    assert s.read(work / 'apparatus.json')['passed']
    assert not (work / 'frozen.json').exists()
    files = list(HERE.glob('*.py')) + list(HERE.glob('protocol.*.md'))
    files += list((ROOT / 'src/threemind_kernels').glob('*.py'))
    files += [Path(c.__file__), Path(s.__file__), Path(s.measure.__file__), Path(s.base.__file__), Path(prior.__file__)]
    # Capture all imported project helpers actually used by this driver.
    for module in tuple(sys.modules.values()):
        p = getattr(module, '__file__', None)
        if p and Path(p).suffix == '.py' and Path(p).resolve().is_relative_to(ROOT):
            if '.work' not in Path(p).resolve().relative_to(ROOT).parts:
                files.append(Path(p).resolve())
    frozen = {p.resolve().relative_to(ROOT).as_posix(): s.sha(p) for p in files}
    for rel in frozen:
        target = work / 'frozen-source' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    with client_context() as client:
        rec = s.base.ResearchRecorder(work, s.PROJECT, client=client)
        rec.register({'source_key': 'r51t8:prefix-precheck62:20261115:v1',
            'title': 'R51t8：弱信号筛选、突触资源与前缀区分', 'classification': 'formal',
            'execution_status': 'running', 'executor': 'ai',
            'kernels': ['threemind.continuous-memory/6.2'],
            'protocol': (HERE / 'protocol.zh.md').read_text('utf8'),
            'protocol_version': s.sha(HERE / 'protocol.zh.md'),
            'required_roles': ['protocol', 'report', 'note', 'original'],
            'metadata': {'research_kernel': r.KERNEL_ID, 'material_blocks': 2, 'stages': 30,
                         'reused_controls': CONTROLS, 'main_paused': True}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-doc-' + lang)),
                'request_id': str(uuid5(NS, 'protocol-' + lang)), 'expected_revision': 0, 'kind': 'protocol',
                'title': 'R51t8 protocol ' + lang, 'markdown': (HERE / f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        assert rec.status['pending'] == 0
        s.write(work / 'registration.json', {'project': s.PROJECT, 'record': rec.experiment, 'pending': 0})
    s.write(work / 'frozen.json', {'sources': frozen, 'variants': VARIANTS, 'stages': 30,
        'references_sha256': s.sha(work / 'reference-manifest.json'), 'cases_sha256': s.sha(work / 'cases.json'),
        'originals_cap': 2**30, 'total_peak_bytes': 3 * 2**30})
    print(json.dumps(s.read(work / 'registration.json')), flush=True)


def check(work):
    f = s.read(work / 'frozen.json')
    for rel, digest in f['sources'].items():
        assert s.sha(ROOT / rel) == digest, rel
    assert s.sha(work / 'cases.json') == f['cases_sha256']
    assert s.sha(work / 'reference-manifest.json') == f['references_sha256']
    for rel, digest in s.read(work / 'reference-manifest.json').items():
        assert s.sha(work / rel) == digest, rel
    assert s.read(work / 'apparatus.json')['passed']
    assert s.read(work / 'registration.json')['pending'] == 0


def run(work):
    check(work)
    assert not any((work / p).exists() for p in ('in-flight.json', 'STOP', 'summary.json'))
    import psutil
    index = s.read(work / 'cases.json')
    results = []
    started = time.monotonic()
    with s.base.worker_lock(work), Guard(work) as guard:
        s.write(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for variant, patch in VARIANTS.items():
            for block in (0, 1):
                for cue in ('train', 'AB', 'DB'):
                    if (work / 'STOP').exists():
                        return
                    assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
                    assert time.monotonic() - started < 7200
                    key = f'{variant}/{block}/{cue}'
                    out = work / 'cases' / key
                    # A prior complete stage is read, not rerun; support safe boundary resumption.
                    if (out / 'result.json').exists():
                        q = s.read(out / 'result.json')
                        assert get(out / 'final.rstate.gz').digest == q['final_sha256']
                        results.append(q)
                        continue
                    out.mkdir(parents=True, exist_ok=False)
                    s.write(work / 'in-flight.json', {'key': key, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
                    case = index[f'short/train-{block}' if cue == 'train' else f'history/s{block}/101/d1/{cue}']
                    parent = None if cue == 'train' else get(work / 'cases' / variant / str(block) / 'train/final.rstate.gz')
                    e = (r.ResearchEngine(state=parent) if parent is not None else
                         r.ResearchEngine(r.ResearchConfig(seed=9291000, **(case['initial_config'] | s.STABLE), **patch)))
                    if parent is not None:
                        e.reconfigure(replace(e.config, **case['patch']))
                    initial = e.capture_state()
                    put(out / 'initial.rstate.gz', initial)
                    trace = c.Trace(out / 'teaching.jsonl.gz') if cue == 'train' else None
                    t = time.monotonic()
                    points = c.execute(e, case, s.inputs(work, case), trace)
                    if trace:
                        trace.close()
                    final = e.capture_state()
                    put(out / 'final.rstate.gz', final)
                    assert get(out / 'final.rstate.gz').digest == final.digest
                    if cue != 'train':
                        s.packed(out / 'process.json.gz', points)
                    q = {} if cue == 'train' else s.measure.process(case, points)
                    q.update(key=key, variant=variant, block=block, cue=cue, kernel=r.KERNEL_ID,
                        initial_sha256=initial.digest, final_sha256=final.digest,
                        parent_sha256=parent.digest if parent else None,
                        time_us=e.time_us, wall_seconds=time.monotonic() - t)
                    s.write(out / 'result.json', q)
                    results.append(q)
                    s.base.atomic_json(work / 'current.json', {'complete': len(results), 'total': 30, 'last': key})
                    (work / 'in-flight.json').unlink()
                    print(json.dumps({'complete': len(results), 'key': key, 'margin': q.get('signed_peak'),
                                      'seconds': q['wall_seconds']}), flush=True)
                    del e, points
                    gc.collect()
                assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) < 2**30
        s.write(work / 'summary.json', {'stages': len(results), 'results': results, 'wall_seconds': time.monotonic() - started})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('prepare', 'apparatus', 'register', 'check', 'run'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    globals()[args.action](args.work)
