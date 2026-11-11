"""E67 r4: resume the two /4 subjects after the existing two-arm pipeline.

This host coordinator reuses the frozen teaching implementation and curricula.
It neither modifies the kernels nor replaces the first two subjects or reports.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil
import httpx
from experiment import (Study, RESOURCE, ROOT, HERE, read, sha, fixed_json,
                        teach, collect, fit)
from threemind_lab.config import load_env
from threemind_lab.client_auth import AuthenticationRequired
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json, file_lock

FIRST = ('2', '3.1')
LATER = ('4-adaptive', '4-legacy')
ALL = FIRST + LATER
STAGES = ['initial-teaching', 'initial-calibration', 'initial-fit', 'development-0']
for _r in range(1, 4):
    STAGES.extend(f'{name}-{_r}' for name in ('correction', 'calibration', 'fit', 'development'))
STAGES.append('final')


class HostPause(RuntimeError):
    pass


def sync_unavailable(error):
    return (isinstance(error, (AuthenticationRequired, httpx.TransportError)) or
            isinstance(error, ValueError) and str(error).startswith(
                ('HTTP 403:', 'HTTP 408:', 'HTTP 429:', 'HTTP 500:', 'HTTP 502:', 'HTTP 503:', 'HTTP 504:')))


class DurableRecorder(ResearchRecorder):
    """Keep already-authorized work running when only platform sync is down.

    The canonical recorder persists every pending request before attempting HTTP.
    File errors and scientific-content conflicts still stop the host.
    """
    allow_deferred = False

    def synchronize(self, *, strict=False):
        try:
            result = super().synchronize(strict=True)
        except (ValueError, httpx.HTTPError) as error:
            if not self.allow_deferred or not sync_unavailable(error):
                raise
            result = self.status
            atomic_json(ROOT/'.work/e67-four-sync-status.json', dict(updated_epoch=time.time(),
                pending=result['pending'], state='pending-authenticated-sync',
                error_kind=type(error).__name__, running_subject_may_continue=True))
            return result
        atomic_json(ROOT/'.work/e67-four-sync-status.json', dict(updated_epoch=time.time(),
            pending=result['pending'], state='synced', running_subject_may_continue=True))
        return result


def ready(work):
    """A stale or failed predecessor is not permission to duplicate its work."""
    state = read(work/'pipeline-status.json')
    if state['phase'] == 'awaiting-report-review':
        if read(work/'computation-complete.json')['arms'] != list(FIRST):
            raise ValueError('predecessor completion scope differs')
        for arm in FIRST:
            for stage in STAGES:
                if not (work/'arms'/arm/stage/'result.json').is_file():
                    raise ValueError('predecessor stage missing: '+arm+'/'+stage)
            if not (work/'replays'/arm/'export.json').is_file():
                raise ValueError('predecessor replay receipt missing: '+arm)
        return True
    if state['phase'] == 'failed':
        raise HostPause('predecessor failed; inspect its saved evidence before continuing')
    try:
        process = psutil.Process(state['pid'])
        command = process.cmdline()
        if not process.is_running() or not any(Path(p).name == 'pipeline.py' for p in command):
            raise HostPause('predecessor is not running and has not completed')
    except psutil.NoSuchProcess as error:
        raise HostPause('predecessor exited before completing') from error
    return False


def verify_course(work):
    names = ['questions.json', 'initial-curriculum.json']
    names.extend(f'round-{r}-curriculum.json' for r in range(1, 4))
    initial = read(work/'initial-curriculum.json')
    courses = [read(work/f'round-{r}-curriculum.json') for r in range(1, 4)]
    if [len(initial), *[len(c['lessons']) for c in courses]] != [104, 165, 120, 108]:
        raise ValueError('the approved existing curriculum differs')
    return {name: sha(work/name) for name in names}


class FourStudy(Study):
    def __init__(self, work):
        super().__init__(work)
        self.recorder = DurableRecorder(self.work, self.project, client=self.client)
        self.recorder.resume_recording()
        self.last_auth_check = time.monotonic()
        self.last_heartbeat = 0
        self.active_stage = {}

    def guard(self):
        if time.monotonic()-self.last_guard < 1:
            return
        super().guard()
        if (self.work/'STOP-4').exists():
            raise HostPause('requested STOP-4; preserve both /4 subjects')
        if shutil.disk_usage(self.work).free < 30*2**30:
            raise HostPause('pause /4 first: preserve 30 GiB free disk')
        if time.monotonic()-self.last_heartbeat >= 30:
            process = psutil.Process()
            atomic_json(ROOT/'.work/e67-four-heartbeat.json', dict(pid=os.getpid(),
                updated_epoch=time.time(), free_disk_bytes=shutil.disk_usage(self.work).free,
                rss=process.memory_info().rss, cpu_s=sum(process.cpu_times()[:2]),
                **self.active_stage))
            self.last_heartbeat = time.monotonic()
        if time.monotonic()-self.last_auth_check >= 120:
            # Existing client renews a still-valid session. Never auto-login or
            # bypass a revoked/expired account after an authentication failure.
            try:
                self.client.request('GET', '/api/v2/me')
            except (ValueError, httpx.HTTPError) as error:
                if not sync_unavailable(error):
                    raise
                atomic_json(ROOT/'.work/e67-four-sync-status.json', dict(updated_epoch=time.time(),
                    state='pending-authenticated-sync', error_kind=type(error).__name__,
                    running_subject_may_continue=True))
            finally:
                self.last_auth_check = time.monotonic()

    def amend(self):
        self.verify_sources()
        course = verify_course(self.work)
        manifest = dict(read(self.work/'source-reference-r3/manifest.json'))
        for name in ('continue_four.py', 'storage_measure.py', 'design-r4.zh.md', 'design-r4.en.md',
                     'analyze.py', 'analyze_four.py', 'export_four.py', 'figures_four.py',
                     'publish_four.py', 'test_continuation.py'):
            path = HERE/name
            manifest[path.relative_to(ROOT).as_posix()] = sha(path)
        frozen = self.work/'source-reference-r4'
        for name, digest in manifest.items():
            original, dest = ROOT/name, frozen/name
            if sha(original) != digest:
                raise ValueError('registered source changed: '+name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and sha(dest) != digest:
                raise ValueError('r4 source freeze conflict: '+name)
            if not dest.exists():
                shutil.copy2(original, dest)
        fixed_json(frozen/'manifest.json', manifest)
        revision = dict(revision=4, active_arms=list(ALL), resumed_arms=list(LATER),
            reason='用户恢复 /4 两方案，确认复用现有课程题库，分列纠错前后、性能、连接规模和全部／纯占用；空间不足优先暂停 /4。',
            curricula_origin='Frozen courses generated from /2 and /3.1 development errors; not recomputed from four arms.',
            course_sha256=course, source_manifest_sha256=sha(frozen/'manifest.json'),
            adaptive_resume='arms/4-adaptive/initial-teaching/checkpoints/lesson-0048',
            adaptive_replay_check='Preserve and byte-check the recorded lesson49-65 clips.',
            legacy_birth='Originally registered independent blank whole subject e67-4-legacy-223.',
            stages=STAGES, correction_rounds=3, teaching_lessons=497, teaching_sim_s=865.5,
            final_questions_per_arm=72, free_disk_reserve_bytes=30*2**30,
            supplementary_training='Separate preregistration if needed; never erase the matched main comparison.',
            unchanged='Kernels, peripheral, adapters, identities, parameters, input/readout rules and final question bank.')
        fixed_json(self.work/'protocol-revision-4.json', revision)
        self.recorder.append('correction', 'resume-four-arms-20261012', revision,
                             request_id=self.rid('resume-four-arms-20261012'))
        for lang in ('zh', 'en'):
            self.recorder.text(dict(request_id=self.rid('protocol-v4:'+lang),
                identity=self.rid('protocol-text:'+lang), expected_revision=3, kind='protocol',
                title=f'E67 四组续行与空间比较 / four-arm continuation {lang}',
                markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8')+'\n\n---\n\n'+
                         (HERE/f'design-r4.{lang}.md').read_text(encoding='utf-8'),
                revision_reason=revision['reason']))
        for name in ('protocol-revision-4.json', 'source-reference-r4/manifest.json'):
            self.attach(self.work/name, 'protocol')
        self.recorder.synchronize(strict=True)
        # The four-arm protocol must be registered before /4 starts. Subsequent
        # account expiry/network loss affects synchronization, not consciousness.
        self.recorder.allow_deferred = True


def run_four(s, stage_status):
    s.amend()
    q = read(s.work/'questions.json')
    initial = read(s.work/'initial-curriculum.json')
    def execute(function, arm, name, *arguments):
        s.active_stage = dict(arm=arm, stage=name)
        s.guard()
        complete = (s.work/'arms'/arm/name/'result.json').exists()
        stage_status('simulation', arm=arm, stage=name, already_complete=complete)
        result = function(s, arm, name, *arguments)
        stage_status('stage-saved', arm=arm, stage=name)
        return result
    for arm in LATER:
        base = s.work/'arms'/arm
        execute(teach, arm, 'initial-teaching', None, initial)
        execute(collect, arm, 'initial-calibration', base/'initial-teaching/system', q['initial'])
        execute(fit, arm, 'initial-fit', base/'initial-teaching/system', ['initial-calibration'])
        execute(collect, arm, 'development-0', base/'initial-fit/system', q['development'])
    corpora = ['initial-calibration']
    for r in range(1, 4):
        course = read(s.work/f'round-{r}-curriculum.json')
        corpora.append(f'calibration-{r}')
        order = LATER[r % len(LATER):] + LATER[:r % len(LATER)]
        for arm in order:
            base = s.work/'arms'/arm
            parent = base/('initial-fit' if r == 1 else f'fit-{r-1}')/'system'
            execute(teach, arm, f'correction-{r}', parent, course['lessons'])
            execute(collect, arm, f'calibration-{r}', base/f'correction-{r}/system', course['calibration'])
            execute(fit, arm, f'fit-{r}', base/f'correction-{r}/system', list(corpora))
            execute(collect, arm, f'development-{r}', base/f'fit-{r}/system', q['development'])
    for arm in LATER:
        execute(collect, arm, 'final', s.work/'arms'/arm/'fit-3/system', q['final'])
    fixed_json(s.work/'computation-complete-r4.json', dict(arms=list(ALL), protocol_revision=4,
        rounds=3, status='awaiting four-arm analysis and video'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    load_env()
    work = (args.work or ResearchStorage().writable_root()/'experiments'/HERE.name).resolve()
    status_path = ROOT/'.work/e67-four-pipeline-status.json'
    def status(phase, **details):
        value = dict(phase=phase, pid=os.getpid(), updated_epoch=time.time(),
                     time=datetime.now(timezone.utc).isoformat(), **details)
        atomic_json(status_path, value)
        print(json.dumps(value, ensure_ascii=False), flush=True)
    with file_lock(ROOT/'.work/e67-four-host.lock'):
        s = None
        try:
            while not ready(work):
                if (work/'STOP-4').exists():
                    raise HostPause('requested STOP-4 before continuation')
                status('waiting-for-two-arm-pipeline')
                time.sleep(30)
            s = FourStudy(work)
            with s.storage.writer(RESOURCE):
                run_four(s, status)
            commands = [
                ('analyze_four.py', []),
                ('export_four.py', []),
                ('storage_measure.py', ['measure', '--output', str(work/'analysis-r4/storage.json')]),
                ('figures_four.py', []),
                ('publish_four.py', ['originals']),
            ]
            for name, extra in commands:
                if name == 'publish_four.py':
                    try:
                        s.client.request('GET', '/api/v2/me')
                        s.recorder.synchronize(strict=True)
                    except (ValueError, httpx.HTTPError) as error:
                        if not sync_unavailable(error):
                            raise
                        status('awaiting-platform-sync', active_arms=list(ALL),
                               simulation_complete=True, originals_and_replays_saved=True,
                               error_kind=type(error).__name__)
                        return
                # Each exporter owns its file evidence. Publishing obtains the
                # cooperative resource lock internally; the others use ours.
                from contextlib import nullcontext
                with (nullcontext() if name == 'publish_four.py' else s.storage.writer(RESOURCE)):
                    status(name)
                    child = subprocess.Popen([sys.executable, '-u', str(HERE/name), *extra, '--work', str(work)], cwd=ROOT)
                    try:
                        while child.poll() is None:
                            s.guard()
                            try:
                                child.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                pass
                        if child.returncode:
                            raise RuntimeError(f'{name} exited with {child.returncode}; preserve and inspect its partial export')
                    except BaseException:
                        if child.poll() is None:
                            # Only this exporter and its descendants are ours.
                            descendants = psutil.Process(child.pid).children(recursive=True)
                            for process in reversed(descendants):
                                try:
                                    process.terminate()
                                except psutil.NoSuchProcess:
                                    pass
                            child.terminate()
                            child.wait(timeout=30)
                        raise
            status('awaiting-report-review', active_arms=list(ALL))
        except BaseException as error:
            status('paused' if isinstance(error, HostPause) else 'failed',
                   error=type(error).__name__+': '+str(error),
                   preservation='Originals and last complete checkpoints retained; do not create replacement subjects.')
            raise
        finally:
            if s is not None:
                s.close()


if __name__ == '__main__':
    main()
