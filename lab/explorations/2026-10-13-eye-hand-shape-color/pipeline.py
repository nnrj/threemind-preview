"""Continue missing E69 steps once; never finalize reports without review."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from journal import HERE, ROOT, BoundaryPause, ContinuityUncertain, read, sha

from threemind_lab.storage_files import atomic_json, file_lock


def run_command(script, args, work):
    logs = work / 'logs'
    logs.mkdir(exist_ok=True)
    with (logs / (script + '.stdout.log')).open('ab') as output, (logs / (script + '.stderr.log')).open('ab') as error:
        subprocess.run([sys.executable, '-X', 'utf8', '-u', str(HERE / script), *args, '--work', str(work)],
                       check=True, cwd=ROOT, stdout=output, stderr=error)


def validate_completed_step(work, step):
    latest = read(work / 'subject/latest.json')
    if step == 'computation':
        value = read(work / 'computation-complete.json')
        expected = value.get('latest', {}).get('boundary_sha256')
        if expected != latest['boundary_sha256'] or value.get('time_us') != latest['end_us']:
            raise ContinuityUncertain('computation receipt differs from the current complete subject')
    elif step == 'analysis':
        value = read(work / 'analysis/verified-results.json')
        if value.get('last_boundary') != latest['boundary_sha256'] or not value.get('continuous'):
            raise ContinuityUncertain('analysis does not describe the current complete subject')
    elif step == 'video':
        value = read(work / 'replays/export.json')
        video = (work / value['video']).resolve()
        if (not video.is_relative_to(work) or not video.exists() or sha(video) != value['sha256'] or
                value.get('activity_curves') != ['activation', 'inhibition', 'direct', 'associative'] or
                value.get('core_advanced') is not False or not value.get('full_decode_verified')):
            raise ValueError('video receipt is incomplete or its bytes changed')
    elif step == 'originals':
        value = read(work / 'originals-publication.json')
        if (value.get('last_boundary') != latest['boundary_sha256'] or value.get('pending') != 0 or
                value.get('analysis_sha256') != sha(work / 'analysis/verified-results.json') or
                value.get('export_sha256') != sha(work / 'replays/export.json')):
            raise ValueError('published original references do not match current evidence')


def run_pipeline(work, *, command=run_command):
    work = Path(work).resolve()
    if not (work / '.research-records/identity.json').exists() or not (work / 'platform.json').exists():
        raise ValueError('explicit canonical registration must precede the independent pipeline')

    def status(phase, **extra):
        value = {'phase': phase, 'pid': os.getpid(), 'updated_epoch': time.time(), **extra}
        atomic_json(work / 'pipeline-status.json', value)
        print(json.dumps(value, ensure_ascii=False), flush=True)

    with file_lock(work / 'pipeline.lock'):
        current_step = None
        try:
            if (work / 'STOP').exists():
                raise BoundaryPause('STOP retained; pause at the current complete boundary')
            if (work / 'subject/in-flight.json').exists():
                raise ContinuityUncertain('in-flight experience exists; inspect actual host and current state before continuing')
            steps = [('computation', 'computation-complete.json', 'experiment.py', ['run']),
                     ('analysis', 'analysis/verified-results.json', 'analyze.py', []),
                     ('video', 'replays/export.json', 'replay.py', []),
                     ('originals', 'originals-publication.json', 'publish.py', ['originals'])]
            for name, receipt, script, args in steps:
                current_step = name
                if (work / receipt).exists():
                    validate_completed_step(work, name)
                    continue
                if (work / 'STOP').exists():
                    raise BoundaryPause('STOP retained; no further step started')
                if name == 'computation':
                    # Probe only. The child owns this lock while it really runs.
                    # A competing manual launch after this probe is rejected by the child.
                    with file_lock(work / 'runner.lock'):
                        pass
                status(script, step=name)
                command(script, args, work)
                if not (work / receipt).exists():
                    raise ValueError('successful child returned without its completion receipt: ' + name)
                validate_completed_step(work, name)
            publication = work / 'publication-status.json'
            if publication.exists() and read(publication).get('phase') == 'completed':
                status('completed', report_publication='existing reviewed finalization receipt')
                return 'completed'
            status('awaiting-report-review', automatic_report_finalization=False)
            return 'awaiting-report-review'
        except BaseException as failure:
            host = work / 'host-status.json'
            host_error = str(read(host).get('error', '')) if host.exists() else ''
            safe_child_pause = (current_step == 'computation' and isinstance(failure, subprocess.CalledProcessError) and
                                not (work / 'subject/in-flight.json').exists() and
                                ((work / 'STOP').exists() or host_error.startswith('BoundaryPause:')))
            phase = 'paused' if isinstance(failure, BoundaryPause) or safe_child_pause else 'attention-required'
            # A failed process is not permission to rewind or rerun its experience.
            status(phase, error=type(failure).__name__ + ': ' + str(failure), automatic_rollback=False)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    from threemind_lab.config import load_env
    from threemind_lab.research_storage import ResearchStorage
    load_env()
    work = args.work or ResearchStorage().writable_root() / 'experiments' / HERE.name
    run_pipeline(work)


if __name__ == '__main__':
    main()
