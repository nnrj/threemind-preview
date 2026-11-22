"""R51q lossless lesson-state packing and actual-allocation boundary guard."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study_reference as x
from audit import disk_allocation

RAW_IMAGE = x.base.image


def allocated(path): return disk_allocation(path)['allocated_bytes']
def total(folder): return sum(allocated(p) for p in folder.rglob('*') if p.is_file())


def packed_image(path):
    if path.name.startswith('lesson-'):
        with zipfile.ZipFile(path.parent / 'lesson-states.zip') as z:
            return x.base.ArtifactCodec.decode(z.read(path.name))
    return RAW_IMAGE(path)


def save(path, state):
    if not path.name.startswith('lesson-'): return x.storage.save(path, state)
    raw = x.storage.compact(x.base.ArtifactCodec.encode(state))
    assert x.base.ArtifactCodec.decode(raw).digest == state.digest
    archive = path.parent / 'lesson-states.zip'
    with zipfile.ZipFile(archive, 'a', compression=zipfile.ZIP_STORED) as z:
        assert path.name not in z.namelist()
        z.writestr(path.name, raw)
    with archive.open('r+b') as stream: os.fsync(stream.fileno())
    with zipfile.ZipFile(archive) as z: assert z.read(path.name) == raw


def prepare(work):
    x.frozen_check(work)
    assert x.read(work / 'apparatus.json')['passed']
    assert not any((work/n).exists() for n in ('cases', 'summary.json', 'STOP', 'in-flight.json'))
    dest = work / 'storage-amendment'; dest.mkdir(exist_ok=False)
    checks, costs = [], []
    for family, key, probes in (('timing', 'timing/100121/f0/p40000/k0/AB', 2),
                                ('jitter', 'jitter/100121/jitter/AB', 2),
                                ('reference', 'reference/100121/dense/shared/AB', 8)):
        folder = work / 'apparatus' / family / 'train'
        files = sorted(folder.glob('lesson-*.tmind'))
        target = dest / (family + '-lessons.zip')
        with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED) as z:
            for p in files: z.writestr(p.name, p.read_bytes())
        with zipfile.ZipFile(target) as z:
            assert set(z.namelist()) == {p.name for p in files}
            for p in files:
                raw = p.read_bytes(); assert z.read(p.name) == raw
                assert x.base.ArtifactCodec.decode(z.read(p.name)).digest == RAW_IMAGE(p).digest
                checks.append({'path': p.relative_to(work).as_posix(), 'sha256': x.s.sha(p),
                               'state_sha256': RAW_IMAGE(p).digest})
        old = total(x.spec.OLD / 'cases' / key)
        before = total(folder) + probes*total(work/'apparatus'/family/'observed')
        after = before - sum(allocated(p) for p in files) + allocated(target)
        assert after < 2*old
        costs.append({'family': family, 'historical_actual_bytes': old,
                      'unpacked_actual_estimate': before, 'packed_actual_estimate': after})
    assert len(checks) == 192
    paths = [Path(__file__), HERE/'storage-amendment.zh.md', HERE/'storage-amendment.en.md']
    proof = {'passed': True, 'created_engines': 0, 'states': len(checks), 'checks': checks, 'costs': costs,
             'historical_actual_bytes': {p['key']: total(x.spec.OLD/'cases'/p['key']) for p in x.spec.parents()},
             'sources': {p.relative_to(x.ROOT).as_posix(): x.s.sha(p) for p in paths},
             'state_bytes_and_hashes_unchanged': True}
    x.s.base.original(dest/'proof.json', proof)
    for p in paths: shutil.copyfile(p, dest/p.name)
    import httpx
    x.s.base.load_env()
    with x.s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                  password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                  transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = x.s.base.ResearchRecorder(work, x.PROJECT, client=client); rec.resume_recording()
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(x.NS, 'storage-document-'+lang)),
                      'request_id': str(uuid5(x.NS, 'storage-note-'+lang)), 'expected_revision': 0,
                      'kind': 'note', 'title': 'R51q lossless storage '+lang,
                      'markdown': (HERE/f'storage-amendment.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        x.s.base.original(dest/'registration.json', {'pending': rec.status['pending'], 'before_formal_run': True,
                                                    'proof_sha256': x.s.sha(dest/'proof.json')})
    print(json.dumps({'passed': True, 'states': 192, 'created_engines': 0, 'costs': costs}), flush=True)


def check(work):
    x.frozen_check(work)
    assert x.read(work/'apparatus.json')['passed']
    proof = x.read(work/'storage-amendment/proof.json')
    r = x.read(work/'storage-amendment/registration.json')
    assert proof['passed'] and r['pending'] == 0 and r['proof_sha256'] == x.s.sha(work/'storage-amendment/proof.json')
    for rel, digest in proof['sources'].items(): assert x.s.sha(x.ROOT/rel) == digest
    return proof


def run(work):
    import psutil
    proof = check(work)
    assert not any((work/n).exists() for n in ('cases', 'summary.json', 'STOP', 'in-flight.json'))
    x.base.save = save
    start, completed = time.monotonic(), 0
    with x.s.base.worker_lock(work), x.s.base.Guard(work) as guard:
        x.s.base.atomic_json(work/'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for parent in x.spec.parents():
            if (work/'STOP').exists(): break
            assert guard.thread.is_alive()
            x.s.base.resource_check(work)
            begin = time.monotonic()
            x.s.base.original(work/'in-flight.json', {'unit': parent['key'], 'pid': os.getpid(), 'created': psutil.Process().create_time()})
            folder = work/'cases'/parent['key']
            _, taught, observer = x.base.execute(parent, x.spec.stages(parent)[0], folder=folder/'train')
            for stage in x.spec.stages(parent)[1:]:
                x.base.execute(parent, stage, taught, folder/stage['name'], observer_state=observer)
            completed += 1
            x.s.base.atomic_json(work/'current.json', {'completed': completed, 'total': 192, 'last': parent['key']})
            (work/'in-flight.json').unlink()
            size, seconds = total(folder), time.monotonic()-begin
            old = proof['historical_actual_bytes'][parent['key']]
            x.s.base.original(work/'costs'/f'{completed:03d}.json', {'unit': parent['key'], 'allocated_bytes': size,
                    'historical_allocated_bytes': old, 'expected_allocated_bytes': old*1.5,
                    'allocation_method': 'FileStandardInfo', 'wall_seconds': seconds})
            reason = ('actual unit allocation at least twice historical' if size >= 2*old else
                      'actual unit allocation exceeds estimate by 50%' if size > 2.25*old else
                      'unit exceeds ten minutes' if seconds > 600 else
                      'two-hour budget' if time.monotonic()-start > 7200 else None)
            if completed % 16 == 0 and sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > x.CAP:
                reason = 'originals budget'
            print(completed, parent['key'], flush=True)
            if reason:
                x.s.base.original(work/'STOP', {'reason': reason, 'complete_boundary': parent['key']}); break
            del taught, observer; gc.collect()
        if completed == 192:
            x.s.base.original(work/'summary.json', {'status': 'awaiting-analysis', 'references': 192,
                'probes': 576, 'stages': 768, 'independent_blocks': 4, 'wall_seconds': time.monotonic()-start})


def analyze(work):
    check(work)
    import analyze_reference as a
    x.base.image = packed_image
    a.analyze(work)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('prepare', 'run', 'analyze'))
    p.add_argument('--work', type=Path, required=True); args = p.parse_args()
    {'prepare': prepare, 'run': run, 'analyze': analyze}[args.action](args.work.resolve())
