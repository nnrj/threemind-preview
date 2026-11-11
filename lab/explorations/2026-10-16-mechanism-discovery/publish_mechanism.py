"""Publish reviewed confirmation or measurement evidence, including large archives; no subject loading."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import shutil
import zipfile
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.study_lock import worker_lock
from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder

NS = UUID('c32b6142-818f-4613-bb1a-b30d6d5127af')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def file_set(work):
    excluded = {'.research-records', 'publication', 'readback'}
    return sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts) & excluded
                  and p.name not in ('originals-v1.zip', 'originals-v1.zip.partial', 'originals-manifest-v1.json')
                  and not p.name.endswith('.lock'))


def archive(work, recorder):
    files = file_set(work)
    if not (work/'originals-v1.zip').exists():
        # Reserve space for an archive and its independent API readback.
        needed = 25*2**30 + 2*sum(p.stat().st_size for p in files)*1.01 + 64*2**20
        if shutil.disk_usage(work).free < needed:
            raise RuntimeError('insufficient space for originals, archive, API readback and 25GiB reserve')
    if any(p.name.endswith('.partial') for p in files):
        raise RuntimeError('unfinished original exists; do not publish as complete')
    manifest = {'schema': 'threemind.mechanism-original-manifest/1', 'members': [
        {'path': p.relative_to(work).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files]}
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode()
    recorder.save_original('originals-manifest-v1.json', raw)
    target = work/'originals-v1.zip'
    if not target.exists():
        temporary = target.with_suffix('.zip.partial')
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as pack:
            for p in files+[work/'originals-manifest-v1.json']:
                pack.write(p, p.relative_to(work).as_posix())
        os.link(temporary, target)
        temporary.unlink()
    verify_archive(target, manifest)
    return manifest, target


def verify_archive(path, manifest):
    with zipfile.ZipFile(path) as pack:
        if json.loads(pack.read('originals-manifest-v1.json')) != manifest:
            raise ValueError('embedded manifest mismatch')
        if set(pack.namelist()) != {m['path'] for m in manifest['members']} | {'originals-manifest-v1.json'}:
            raise ValueError('archive membership mismatch')
        if len(pack.namelist()) != len(set(pack.namelist())):
            raise ValueError('duplicate archive member')
        for member in manifest['members']:
            with pack.open(member['path']) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != member['sha256'] or pack.getinfo(member['path']).file_size != member['bytes']:
                raise ValueError('archive member mismatch: '+member['path'])


def publish(work, review_path):
    import psutil
    review = read(review_path)
    if review.get('reviewer') != 'assistant' or review.get('approved_for_publication') is not True:
        raise RuntimeError('explicit assistant review receipt required; not external/human review')
    if review['work'] != str(work):
        raise RuntimeError('review applies to different work')
    for name, expected in review['reviewed_files'].items():
        if sha(ROOT/name) != expected:
            raise RuntimeError('reviewed file changed: '+name)
    if sha(work/'analysis-v1.json') != review['analysis_sha256']:
        raise RuntimeError('analysis changed after review')
    for name, expected in review.get('reviewed_originals', {}).items():
        if sha(work/name) != expected:
            raise RuntimeError('reviewed original changed: '+name)
    with worker_lock(work):
        host = read(work/'host.json')
        if psutil.pid_exists(host['pid']) and abs(psutil.Process(host['pid']).create_time()-host['created_at']) < .01:
            raise RuntimeError('computation host is still alive')
        if any((work/p).exists() for p in ('in-flight.json', 'apparatus-in-flight.json', 'STOP')):
            raise RuntimeError('unresolved marker prevents complete publication')
        if read(work/'status.json')['state'] != 'awaiting-analysis':
            raise RuntimeError('batch has not reached analysis boundary')
        load_env()
        with OperationsClient.from_environment(source='ai') as client:
            platform = read(work/'platform.json')
            recorder = ResearchRecorder(work, platform['project_id'], client=client)
            recorder.resume_recording()
            recorder.save_original('postprocessing/review.json', review_path.read_bytes())
            for name in review['reviewed_files']:
                recorder.save_original('postprocessing/'+Path(name).name, (ROOT/name).read_bytes())
            manifest, pack = archive(work, recorder)
            key = work.name
            for relative, label, role, fmt in [
                ('originals-v1.zip', 'Complete original states, inputs, lineage and analysis', 'original', 'application/zip'),
                ('originals-manifest-v1.json', 'Per-member SHA256 manifest', 'manifest', 'application/json'),
                ('analysis-v1.json', 'Preregistered recomputed endpoints', 'analysis', 'application/json')]:
                path = work/relative
                recorder.attach({'logical_id': 'mechanism-v2:'+relative, 'role': role, 'label': label, 'format': fmt,
                                 'byte_count': path.stat().st_size, 'sha256': sha(path),
                                 'locator': {'kind': 'file', 'resource_id': platform['resource_id'], 'member': relative}},
                                request_id=uuid5(NS, key+':attach:'+relative))
            for name in review['reports']:
                language = 'zh' if '.zh.' in name else 'en'
                recorder.text({'request_id': str(uuid5(NS, key+':report:'+language)),
                               'identity': str(uuid5(NS, key+':report-doc:'+language)), 'expected_revision': 0,
                               'kind': 'report', 'title': key+' '+review['study_phase']+' report '+language,
                               'markdown': (ROOT/name).read_text(encoding='utf-8')})
            recorder.text({'request_id': str(uuid5(NS, key+':note')), 'identity': str(uuid5(NS, key+':note-doc')),
                           'expected_revision': 0, 'kind': 'note', 'title': key+' review and limitations',
                           'markdown': review['review_note']})
            recorder.synchronize(strict=True)
            args = {'path': {'project': platform['project_id'], 'experiment': recorder.experiment}}
            verification = client.call('records.verify', args | {'query': {'hashes': True}})
            if verification['coverage'] != 'verified' or verification['problems']:
                raise RuntimeError('registered evidence did not verify')
            evidence = next(e for e in verification['evidence'] if e['logical_id'] == 'mechanism-v2:originals-v1.zip')
            destination = work/'readback/originals-v1.zip'
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                receipt = client.call('records.download', {'path': {'project': platform['project_id'], 'evidence': evidence['id']}},
                                      output=destination, maximum=pack.stat().st_size)
                recorder.save_original('publication/download-receipt.json', json.dumps(receipt, sort_keys=True).encode())
            if shutil.disk_usage(work).free < 25*2**30:
                raise RuntimeError('25GiB post-download reserve violated; preserve data and do not finalize')
            if sha(destination) != sha(pack):
                raise RuntimeError('API download differs from originals')
            verify_archive(destination, manifest)
            recorder.save_original('publication/verification-before-finalize.json', json.dumps(verification, sort_keys=True).encode())
            recorder.finalize(request_id=uuid5(NS, key+':finalize'))
            recorder.synchronize(strict=True)
            final = client.call('records.verify', args | {'query': {'hashes': True}})
            if recorder.status['pending'] or final['execution_status'] != 'completed' or final['coverage'] != 'verified':
                raise RuntimeError('final record did not reach verified completion')
            recorder.save_original('publication/final-verification.json', json.dumps(final, sort_keys=True).encode())
            print(json.dumps({'record': recorder.experiment, 'status': recorder.status,
                              'coverage': final['coverage'], 'members': len(manifest['members']),
                              'archive_bytes': pack.stat().st_size, 'archive_sha256': sha(pack)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    args = parser.parse_args()
    publish(args.work.resolve(), args.review.resolve())
