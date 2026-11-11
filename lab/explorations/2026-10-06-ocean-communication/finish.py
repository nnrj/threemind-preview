"""Explicitly resume the zero-advance usage pause, then finish the amended E53."""
from experiment import WORK, execute, read_json
from batch import stage
from joint import main as joint_main


def main():
    failed = WORK / 'cases/s1-matched'
    status = read_json(failed / 'result.json')
    if status['observed_us'] != 0 or 'refresh account usage' not in str(status['error']):
        raise RuntimeError('this recovery is only registered for the zero-advance usage pause')
    # The original final snapshot already contains the matched silencing.
    stage(failed / 'final', 's1-matched-resume', 20)
    for seed in (0, 1):
        stage(WORK / f'cases/s{seed}-development-01/final', f's{seed}-rescue', 5, lesion='rescue')
    for mode in ('live', 'muted'):
        stage(WORK / 'cases/s0-development-00/final', f's0-early-{mode}', 5, mode)
    joint_main()


if __name__ == '__main__':
    main()
