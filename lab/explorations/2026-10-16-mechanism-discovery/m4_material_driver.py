"""Register and execute a read-only measurement audit, never an E69 simulation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

import m4_material_review as review
import pilot_m2 as m

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-materials-v1')
NS = UUID('ea95d2f5-3436-4fb9-b5e3-6f3aa1e08494')


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; inspect receipts')
        title = '2026-10-16 机制发现 · M4 E69材料可辨识性只读核查'
        found = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(found) > 1: raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': title})
        resource = 'mechanism-m4-materials-v1-20261016'
        m.original(work/'platform.json', {'project_id': project['id'], 'resource_id': resource})
        paths = [Path(__file__), HERE/'m4_material_review.py', HERE/'m4-material-protocol.zh.md',
                 HERE/'m4-material-protocol.en.md', HERE/'pilot_m2.py', m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        for path in paths:
            m.original(work/'frozen'/path.name, {'utf8': path.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:m4-materials-v1:20261016', 'title': title,
                    'classification': 'calibration', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol_version': m.digest(manifest),
                    'protocol': (HERE/'m4-material-protocol.zh.md').read_text(encoding='utf-8'),
                    'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'study_phase': 'read-only-material-audit',
                                 'Core_engines_loaded': 0, 'new_scientific_individuals': 0,
                                 'source_individuals': 1, 'source_identity': 'e69-5.1-223',
                                 'source_root': str(review.SOURCE), 'E69_resumed': False}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={'resource_id': resource,
            'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m4-materials-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={'project_id': project['id'],
            'resource_id': resource}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M4 material audit v1 '+lang,
                    'markdown': (HERE/f'm4-material-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps({'project': project['id'], 'record': r.experiment, 'status': r.status}), flush=True)


def run(work):
    import psutil
    with m.worker_lock(work), m.connection() as client:
        for name, digest in m.read(work/'runner-manifest.json').items():
            assert review.sha(m.ROOT/name) == digest
        if any((work/p).exists() for p in ('in-flight.json', 'STOP', 'status.json', 'materials.json')):
            raise RuntimeError('already attempted or unresolved marker; inspect before read-only recovery')
        m.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(),
                                       'command': sys.argv, 'read_only': True})
        r = m.recorder(work, client)
        with m.Guard(work) as guard:
            def check():
                if (work/'STOP').exists() or not guard.thread.is_alive():
                    raise RuntimeError('resource guard requested measurement pause')
            check()
            m.original(work/'in-flight.json', {'kind': 'read-only-analysis', 'pid': os.getpid(), 'epoch': time.time()})
            material = review.freeze(work)
            print(json.dumps({'frozen_material': material}), flush=True)
            result = review.analyze(work, boundary_check=check)
            (work/'in-flight.json').unlink()
            r.append('result', 'material-audit', {'sha256': review.sha(work/'analysis-v1.json'), **result},
                     request_id=uuid5(NS, 'result'))
            r.synchronize()
            print(json.dumps({'analysis': result, 'record': r.experiment, 'status': r.status}), flush=True)
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis', 'read_only': True, 'completed': 192})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('register', 'run'))
    p.add_argument('--work', type=Path, default=WORK)
    args = p.parse_args(); {'register': register, 'run': run}[args.command](args.work.resolve())
