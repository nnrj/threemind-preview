"""External E69 host monitor; never imports, pauses, restores or kills Core.

The only experiment control written here is the existing STOP request. The
frozen host acknowledges it before its next declared unit, after saving the
current complete unit. This cannot protect against a sudden within-unit OOM.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import shutil
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

import psutil

GIB = 2**30


@dataclass(frozen=True)
class Limits:
    commit_gib: float = 8
    ram_gib: float = 4
    system_disk_gib: float = 10
    data_disk_gib: float = 25

    def bytes(self):
        values = {'commit': self.commit_gib, 'ram': self.ram_gib,
                  'system_disk': self.system_disk_gib, 'data_disk': self.data_disk_gib}
        if any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError('positive finite host resource reserves required')
        return {key: int(value * GIB) for key, value in values.items()}


class ResourceUnavailable(RuntimeError):
    """A required host measurement failed; do not start a subject."""


class ResourcePressure(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__('host resource reserve reached: ' + ', '.join(report['violations']))


class _PerformanceInformation(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
        'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
        'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
        (name, wintypes.DWORD) for name in ('HandleCount', 'ProcessCount', 'ThreadCount')]


class _MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in ('total_physical', 'available_physical',
        'total_page_file', 'available_page_file', 'total_virtual', 'available_virtual',
        'available_extended_virtual')]


def snapshot_resources(work):
    """Read system-wide commit, physical RAM and both disks; no Core calls."""
    if os.name != 'nt':
        raise ResourceUnavailable('Windows host resource APIs required')
    try:
        info = _PerformanceInformation()
        info.cb = ctypes.sizeof(info)
        performance = ctypes.WinDLL('psapi', use_last_error=True).GetPerformanceInfo
        performance.argtypes = [ctypes.POINTER(_PerformanceInformation), wintypes.DWORD]
        performance.restype = wintypes.BOOL
        if not performance(ctypes.byref(info), info.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        memory = _MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        physical = ctypes.WinDLL('kernel32', use_last_error=True).GlobalMemoryStatusEx
        physical.argtypes = [ctypes.POINTER(_MemoryStatus)]
        physical.restype = wintypes.BOOL
        if not physical(ctypes.byref(memory)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.PageSize <= 0 or info.CommitLimit <= 0 or memory.total_physical <= 0:
            raise ResourceUnavailable('invalid Windows memory counters')
        available = Path(work).resolve()
        while not available.exists():
            if available == available.parent:
                raise ResourceUnavailable('data volume is unavailable')
            available = available.parent
        system_disk = Path(os.environ.get('SystemDrive', 'C:') + '/')
        return {'measured_epoch': time.time(),
                'commit_total_bytes': int(info.CommitTotal * info.PageSize),
                'commit_limit_bytes': int(info.CommitLimit * info.PageSize),
                'physical_available_bytes': int(memory.available_physical),
                'system_disk_free_bytes': shutil.disk_usage(system_disk).free,
                'data_disk_free_bytes': shutil.disk_usage(available).free,
                'system_volume': str(system_disk), 'data_volume': str(available.anchor),
                'memory_source': 'GetPerformanceInfo + GlobalMemoryStatusEx'}
    except ResourceUnavailable:
        raise
    except (OSError, AttributeError, ValueError) as exc:
        raise ResourceUnavailable('host resource probe failed: ' + str(exc)) from exc


def check_resources(work, *, limits=None, snapshot=None):
    """Return a read-only report or raise ResourcePressure/ResourceUnavailable.

    ``snapshot`` is an injectable zero-argument probe for isolated tests. Real
    callers omit it. No directories, STOP requests or logs are created here.
    """
    limits_bytes = (limits or Limits()).bytes()
    try:
        measured = snapshot() if snapshot else snapshot_resources(work)
        required = ('commit_total_bytes', 'commit_limit_bytes', 'physical_available_bytes',
                    'system_disk_free_bytes', 'data_disk_free_bytes')
        if any(not isinstance(measured[k], int) or isinstance(measured[k], bool) or measured[k] < 0
               for k in required) or measured['commit_limit_bytes'] == 0:
            raise ValueError('invalid resource counters')
        available = {'commit': max(0, measured['commit_limit_bytes'] - measured['commit_total_bytes']),
                     'ram': measured['physical_available_bytes'],
                     'system_disk': measured['system_disk_free_bytes'],
                     'data_disk': measured['data_disk_free_bytes']}
    except ResourceUnavailable:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ResourceUnavailable('host resource probe failed: ' + str(exc)) from exc
    violations = [key for key, reserve in limits_bytes.items() if available[key] < reserve]
    report = {'safe': not violations, 'available_bytes': available, 'limits_bytes': limits_bytes,
              'violations': violations, 'snapshot': measured}
    if violations:
        raise ResourcePressure(report)
    return report


def target_state(pid, started_at):
    """Check PID plus creation time on every poll; never signal a process."""
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - started_at) > .01:
            return 'reused'
        return 'alive' if process.is_running() and process.status() != psutil.STATUS_ZOMBIE else 'exited'
    except psutil.NoSuchProcess:
        return 'exited'
    except psutil.AccessDenied as exc:
        raise ResourceUnavailable('cannot verify monitored process identity') from exc


def request_stop(work, reason):
    """Exclusive creation preserves any existing user/operator STOP bytes."""
    path = Path(work) / 'STOP'
    try:
        with path.open('x', encoding='utf-8') as output:
            json.dump(reason, output, ensure_ascii=False, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        return True
    except FileExistsError:
        return False


def _publish_ready(work, pid, started_at, report, error=None):
    """Startup acknowledgement after an actual probe, never merely after Popen."""
    value = {'guard_pid': os.getpid(), 'guard_started_at': psutil.Process().create_time(),
             'target_pid': pid, 'target_started_at': started_at, 'epoch': time.time(),
             'safe': report is not None and report['safe'], 'report': report, 'error': error}
    folder = work / 'host-resource-guard'
    temporary = folder / f'ready-{os.getpid()}.partial'
    with temporary.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, allow_nan=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, folder / 'ready.json')


def watch(work, pid, started_at, *, interval=1., limits=None, snapshot=None,
          process_probe=None, sleep=time.sleep):
    """Watch until the exact host exits; pressure requests a complete-boundary STOP.

    Returns 0 for an observed host exit, 2 for PID replacement, or 3 for an exit
    with an in-flight marker. It never clears STOP or attempts any recovery.
    """
    work = Path(work).resolve()
    if not work.is_dir():
        raise ValueError('existing explicit experiment work directory required')
    if isinstance(pid, bool) or pid <= 0 or not math.isfinite(started_at) or started_at <= 0:
        raise ValueError('exact host PID and positive creation timestamp required')
    if not math.isfinite(interval) or not .1 <= interval <= 60:
        raise ValueError('poll interval must be between 0.1 and 60 seconds')
    (limits or Limits()).bytes()
    probe = process_probe or target_state
    initial = probe(pid, started_at)
    if initial != 'alive':
        return 2 if initial == 'reused' else 0
    try:
        return _watch_live(work, pid, started_at, interval, limits, snapshot, probe, sleep)
    except BaseException as exc:
        # An unexpected monitor failure must request a boundary pause as well.
        # Forced OS termination cannot run this handler; the launcher must also
        # check guard liveness and request STOP if its child exits unexpectedly.
        try:
            request_stop(work, {'event': 'monitor-failed', 'epoch': time.time(),
                               'error': type(exc).__name__ + ': ' + str(exc),
                               'pid': pid, 'started_at': started_at})
        except OSError as stop_error:
            print('Cannot persist resource guard STOP: ' + str(stop_error), file=sys.stderr)
        raise


def _watch_live(work, pid, started_at, interval, limits, snapshot, probe, sleep):
    folder = work / 'host-resource-guard'
    folder.mkdir(exist_ok=True)
    path = folder / f'{time.time_ns()}-{os.getpid()}.jsonl'
    triggered = ready_written = False

    def record(event, **values):
        row = {'event': event, 'epoch': time.time(), 'pid': pid, 'started_at': started_at, **values}
        with path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
            output.flush()
        return row

    record('watch-started', interval_s=interval, limits_bytes=(limits or Limits()).bytes())
    while True:
        try:
            state = probe(pid, started_at)
        except ResourceUnavailable as exc:
            reason = {'event': 'monitor-unavailable', 'epoch': time.time(), 'error': str(exc),
                      'pid': pid, 'started_at': started_at}
            created = request_stop(work, reason)
            record('pause-requested', reason=reason, created_stop=created)
            raise
        if state != 'alive':
            flight = (work / 'subject' / 'in-flight.json').exists()
            record('target-' + state, stop_exists=(work / 'STOP').exists(),
                   in_flight=flight, pressure_requested=triggered)
            return 2 if state == 'reused' else 3 if flight else 0
        try:
            report = check_resources(work, limits=limits, snapshot=snapshot)
            record('sample', **report)
            if not ready_written:
                _publish_ready(work, pid, started_at, report)
                ready_written = True
        except (ResourcePressure, ResourceUnavailable) as exc:
            reason = {'event': 'resource-pressure' if isinstance(exc, ResourcePressure) else 'probe-unavailable',
                      'epoch': time.time(), 'error': str(exc), 'pid': pid, 'started_at': started_at,
                      'report': exc.report if isinstance(exc, ResourcePressure) else None}
            if not triggered:
                created = request_stop(work, reason)
                record('pause-requested', reason=reason, created_stop=created,
                       in_flight=(work / 'subject' / 'in-flight.json').exists())
                triggered = True
            else:
                record('pressure-remains', reason=reason)
            if not ready_written:
                _publish_ready(work, pid, started_at,
                               exc.report if isinstance(exc, ResourcePressure) else None, str(exc))
                ready_written = True
        sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'watch'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--started-at', type=float)
    args = parser.parse_args()
    try:
        if args.action == 'check':
            print(json.dumps(check_resources(args.work), ensure_ascii=False))
            return 0
        if args.pid is None or args.started_at is None:
            parser.error('watch requires --pid and --started-at')
        return watch(args.work, args.pid, args.started_at)
    except (ResourceUnavailable, ResourcePressure, OSError, ValueError) as exc:
        print(json.dumps({'safe': False, 'error': type(exc).__name__ + ': ' + str(exc),
                          'report': exc.report if isinstance(exc, ResourcePressure) else None}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
