"""Run each independent M5 origin in a fresh serial host, preserving its whole life."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study as original
s = original.s


def read(path):
    return json.loads(Path(path).read_bytes())


def one(work, origin):
    import psutil
    original.frozen_check(work)
    assert origin in range(8)
    coordinator = read(work / 'hosts/coordinator.json')
    parent = psutil.Process(coordinator['pid'])
    assert abs(parent.create_time() - coordinator['created']) < .001
    assert not any((work / name).exists() for name in ('STOP', 'in-flight.json', 'summary.json'))
    current = read(work / 'current.json')
    assert current['completed'] == origin
    case = read(work / 'cases.json')[origin]
    assert case == {'origin': origin, 'seed': 1056100 + origin}
    folder = work / 'units' / f'o{origin}'
    assert not folder.exists()
    assert time.time() - coordinator['epoch'] < 7200
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.resource_check(work)
        assert guard.thread.is_alive()
        host = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv}
        s.base.atomic_json(work / 'host.json', host)
        s.base.original(work / 'in-flight.json', {'unit': f'o{origin}', **host})
        result = original.measure.unit(folder, origin)
        s.base.original(folder / 'result.json', result)
        (work / 'in-flight.json').unlink()
        s.base.atomic_json(work / 'current.json', {'completed': origin + 1, 'total': 8, 'last': f'o{origin}'})
        reason = ('invalid matching or continuity' if not result['valid'] else
                  'source originals budget' if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) > original.RAW_CAP / 8 else
                  'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > original.RAW_CAP else
                  'cumulative two-hour budget' if time.time() - coordinator['epoch'] > 7200 else None)
        if reason and not (work / 'STOP').exists():
            s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': f'o{origin}'})
    s.base.original(work / 'hosts' / f'o{origin}.json', read(work / 'resource-summary.json') | {'host': host, 'complete_origin': origin})
    print(json.dumps({'complete_origin': origin, 'valid': result['valid']}), flush=True)


def run(work):
    import psutil
    original.frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / name).exists() for name in ('STOP', 'in-flight.json', 'summary.json', 'hosts', 'units'))
    s.base.resource_check(work)
    dest = work / 'hosts'
    dest.mkdir()
    (dest / 'logs').mkdir()
    s.base.original(dest / 'coordinator.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv, 'epoch': time.time()})
    s.base.atomic_json(work / 'current.json', {'completed': 0, 'total': 8, 'last': None})
    for origin in range(8):
        if (work / 'STOP').exists() or (work / 'in-flight.json').exists():
            break
        with (dest / 'logs' / f'o{origin}.stdout.log').open('xb') as out, (dest / 'logs' / f'o{origin}.stderr.log').open('xb') as err:
            child = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), 'one', '--work', str(work), '--origin', str(origin)], stdout=out, stderr=err)
        print(json.dumps({'host_complete': origin, 'exit': child.returncode}), flush=True)
        if child.returncode:
            s.base.original(dest / f'o{origin}-host-failure.json', {'exit': child.returncode, 'in_flight_preserved': (work / 'in-flight.json').exists()})
            break
        if (work / 'STOP').exists():
            break
    rows = [read(p) for p in sorted(dest.glob('o[0-7].json'))]
    if rows:
        resources = {'peak_private_bytes': max(r['peak_private_bytes'] for r in rows),
                     'minimum_available_bytes': {k: min(r['minimum_available_bytes'][k] for r in rows) for k in rows[0]['minimum_available_bytes']},
                     'wall_seconds': sum(r['wall_seconds'] for r in rows), 'complete_source_hosts': len(rows)}
        s.base.atomic_json(work / 'resource-summary.json', resources)
    if len(rows) == 8 and read(work / 'current.json')['completed'] == 8 and not (work / 'STOP').exists():
        s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'origins': 8, 'readout_conditions': ['temporal', 'endpoint'],
                                               'wall_seconds': resources['wall_seconds'], 'host_strategy': 'one complete origin per serial host'})
    else:
        print('Paused; preserve complete boundaries, STOP and any in-flight evidence.', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['run', 'one'])
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--origin', type=int)
    a = p.parse_args()
    if a.action == 'one':
        one(a.work.resolve(), a.origin)
    else:
        run(a.work.resolve())
