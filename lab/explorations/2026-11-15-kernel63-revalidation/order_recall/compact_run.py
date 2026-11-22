"""Lossless storage amendment for R63k; the frozen experiment executes unchanged."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
from uuid import uuid5
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study as base
assert Path(base.__file__).resolve() == HERE / 'study.py'
s = base.s


def compact(raw):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(out, 'w') as new:
        for name in old.namelist():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            new.writestr(info, old.read(name), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    packed = out.getvalue()
    assert base.ArtifactCodec.decode(raw).digest == base.ArtifactCodec.decode(packed).digest
    with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(io.BytesIO(packed)) as new:
        assert old.namelist() == new.namelist()
        assert all(old.read(name) == new.read(name) for name in old.namelist())
    return packed


def save(path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    return s.blob(path, compact(base.ArtifactCodec.encode(image)))


def prepare(work):
    base.frozen_check(work)
    assert base.read(work / 'apparatus.json')['passed']
    assert not any((work / name).exists() for name in ('cases', 'in-flight.json', 'STOP', 'summary.json'))
    dest = work / 'storage-amendment'
    dest.mkdir(exist_ok=False)
    checks = []
    for path in sorted((work / 'apparatus').rglob('*.tmind')):
        raw = path.read_bytes()
        packed = compact(raw)
        checks.append({'path': path.relative_to(work).as_posix(), 'old_bytes': len(raw), 'new_bytes': len(packed),
                       'original_file_sha256': s.sha(path), 'state_sha256': base.image(path).digest})
    raw = (work / 'apparatus/train/final.tmind').read_bytes()
    s.blob(dest / 'same-state-compressed.tmind', compact(raw))
    proof = {'passed': True, 'states_checked': len(checks), 'created_engines': 0,
             'old_state_bytes': sum(c['old_bytes'] for c in checks), 'new_state_bytes': sum(c['new_bytes'] for c in checks),
             'unchanged': ['all ZIP member bytes', 'decoded full-state hash', 'Core', 'curriculum', 'readout', 'scoring', 'resource limits'],
             'checks': checks, 'sources': {p.relative_to(base.ROOT).as_posix(): s.sha(p) for p in (Path(__file__), HERE / 'storage-amendment.zh.md', HERE / 'storage-amendment.en.md')}}
    s.base.original(dest / 'proof.json', proof)
    for p in (Path(__file__), HERE / 'storage-amendment.zh.md', HERE / 'storage-amendment.en.md'):
        s.blob(dest / p.name, p.read_bytes())
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, base.PROJECT, client=client)
        rec.resume_recording()
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(base.NS, 'storage-amendment-document-'+lang)),
                      'request_id': str(uuid5(base.NS, 'storage-amendment-'+lang)), 'expected_revision': 0, 'kind': 'note',
                      'title': 'R63k lossless storage amendment '+lang, 'markdown': (HERE / f'storage-amendment.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        s.base.original(dest / 'registration.json', {'pending': rec.status['pending'], 'before_formal_run': True,
                                                    'proof_sha256': s.sha(dest / 'proof.json')})
    print(json.dumps({k: v for k, v in proof.items() if k not in ('checks', 'sources')}), flush=True)


def check(work):
    proof = base.read(work / 'storage-amendment/proof.json')
    assert proof['passed'] and base.read(work / 'storage-amendment/registration.json')['pending'] == 0
    for rel, digest in proof['sources'].items(): assert s.sha(base.ROOT / rel) == digest


def run(work):
    check(work)
    base.save = save
    base.run(work)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'run', 'check'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'check': check}[args.action](args.work.resolve())
