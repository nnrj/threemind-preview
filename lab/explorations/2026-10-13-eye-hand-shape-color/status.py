"""Read-only E69 status. Does not import a subject, create files or call Lab."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))


def read(path):
    return json.loads(path.read_bytes()) if path.exists() else None


def status(work):
    work = Path(work).resolve()
    available = work
    while not available.exists():
        available = available.parent
    result = {'time_epoch': time.time(), 'work': str(work), 'exists': work.exists(),
              'free_GiB': shutil.disk_usage(available).free / 2**30,
              'available_memory_GiB': psutil.virtual_memory().available / 2**30,
              'pipeline': read(work / 'pipeline-status.json'), 'host': read(work / 'host-status.json'),
              'progress': read(work / 'progress.json'), 'sync': read(work / 'sync-status.json'),
              'complete': read(work / 'computation-complete.json'),
              'publication': read(work / 'publication-status.json'), 'stop': (work / 'STOP').exists(),
              'processes': [], 'subjects': {}, 'process_access_denied': []}
    for process in psutil.process_iter(['name']):
        if not process.info['name'] or 'python' not in process.info['name'].lower():
            continue
        try:
            command = process.cmdline()
            if any(HERE.name in item and Path(item).name in (
                    'pipeline.py', 'experiment.py', 'analyze.py', 'replay.py', 'publish.py') for item in command):
                result['processes'].append({'pid': process.pid, 'cmd': command,
                                           'cpu_s': sum(process.cpu_times()[:2]),
                                           'rss': process.memory_info().rss})
        except psutil.AccessDenied:
            result['process_access_denied'].append(process.pid)
        except psutil.NoSuchProcess:
            pass
    # Supported host layouts. No recursive walk through large checkpoint data.
    bases = [work / 'subject', work / 'subjects' / '5.1', work / 'arms' / '5.1']
    for base in bases:
        if not base.exists():
            continue
        latest, flight = read(base / 'latest.json'), read(base / 'in-flight.json')
        result['subjects'][base.relative_to(work).as_posix()] = {
            'latest': {k: latest[k] for k in ('sequence', 'key', 'end_us', 'identity')} if latest else None,
            'in_flight': flight}
    result['pending'] = len(list((work / '.research-records' / 'pending').glob('*.json')))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    from threemind_lab.config import load_env
    from threemind_lab.research_storage import ResearchStorage
    load_env()
    work = args.work or ResearchStorage().writable_root() / 'experiments' / HERE.name
    print(json.dumps(status(work), ensure_ascii=False))


if __name__ == '__main__':
    main()
