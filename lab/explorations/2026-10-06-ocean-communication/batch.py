"""Sequential E53 stages; completed immutable stages are reused, never overwritten."""
import time
from experiment import WORK, execute, read_json


def stage(snapshot, name, seconds, mode='live', lesion=None):
    folder = WORK / 'cases' / name
    if (folder / 'result.json').exists():
        result = read_json(folder / 'result.json')
        if result['status'] not in ('horizon_paused', 'physical_extinction'):
            raise RuntimeError('partial stage retained; explicit continuation required: ' + name)
        return folder / 'final'
    if folder.exists():
        raise RuntimeError('unfinished stage must not be silently restarted: ' + name)
    execute(snapshot, name, seconds, mode, lesion)
    return folder / 'final'


def main():
    # The explicitly launched first stage is allowed to finish; no second worker.
    pending = WORK / 'cases/s0-development-01'
    if pending.exists() and not (pending / 'result.json').exists():
        import psutil
        pid = read_json(pending / 'worker.json')['pid']
        while not (pending / 'result.json').exists():
            if not psutil.pid_exists(pid):
                raise RuntimeError('development process ended without a result; recovery required')
            time.sleep(5)
    roots = {}
    roots[0] = stage(WORK / 'cases/s0-development-00/final', 's0-development-01', 130)
    stage(WORK / 'sources/1', 's1-development-00', 20)
    roots[1] = stage(WORK / 'cases/s1-development-00/final', 's1-development-01', 130)
    # Interleave the two independent environments instead of exhausting the
    # budget on every variant of one environment first.
    for mode in ('live', 'muted', 'scrambled'):
        for source in (0, 1):
            stage(roots[source], f's{source}-{mode}', 40, mode)
    for lesion in ('target', 'matched', 'rescue'):
        for source in (0, 1):
            old = WORK / f'cases/s{source}-{lesion}/result.json'
            if old.exists() and read_json(old)['status'] == 'paused_error':
                raise RuntimeError('use the explicit finish.py zero-advance recovery; never overwrite a paused stage')
            stage(roots[source], f's{source}-{lesion}', 5 if lesion == 'rescue' else 20, lesion=lesion)
    # See the dated structural diagnosis. The unexecuted factorials and second
    # early pair are deferred, not silently reported as completed.
    for source in (0,):
        for mode in ('live', 'muted'):
            stage(WORK / f'cases/s{source}-development-00/final', f's{source}-early-{mode}', 5, mode)
    from joint import main as joint_main
    joint_main()


if __name__ == '__main__':
    main()
