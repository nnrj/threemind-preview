"""Read-only status for the authorized E69 restored attempt, no Core imports."""
import argparse
import json
from pathlib import Path

import psutil
from journal import read
from status import status


def continuation_status(work):
    work = Path(work).resolve()
    value = status(work)
    for name in ('continuation-envelope.json', 'continuation-status.json', 'continuation-complete-envelope.json',
                 'host-resource-guard/status.json', 'host-resource-guard/ready.json'):
        value[name] = read(work / name) if (work / name).exists() else None
    for process in psutil.process_iter(['name']):
        if not process.info['name'] or 'python' not in process.info['name'].lower():
            continue
        try:
            command = process.cmdline()
            if str(work) in command and any(Path(arg).name in ('continuation.py', 'host_resource_guard.py') for arg in command):
                value['processes'].append({'pid': process.pid, 'cmd': command,
                                          'cpu_s': sum(process.cpu_times()[:2]), 'rss': process.memory_info().rss})
        except psutil.AccessDenied:
            value['process_access_denied'].append(process.pid)
        except psutil.NoSuchProcess:
            pass
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    print(json.dumps(continuation_status(parser.parse_args().work), ensure_ascii=False))


if __name__ == '__main__':
    main()
