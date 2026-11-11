"""Check corpus controls, withheld answers and query scoring before training."""
from collections import Counter

from run import ARMS, curriculum, protocols
from threemind_runtime.calibration import transduction
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def check():
    cover = []
    for seed in range(41601, 41613):
        for family in range(2):
            for n in [8, 24]:
                full, names = curriculum(seed, family, n, 'full')
                assert len(full) == 20 * n + 32
                for arm in ARMS:
                    text, _ = curriculum(seed, family, n, arm)
                    assert len(text) == len(full)
                    assert sum(map(len, text)) == sum(map(len, full))
                    assert Counter(''.join(text)) == Counter(''.join(full))
                    if arm != 'crossed_chain':
                        assert text[-32:] == full[-32:]
                    else:
                        assert text[:-32] == full[:-32]
                assert curriculum(seed, family, n, 'learning_off')[0] == full
            for group, p in protocols(names, [2.0]).items():
                m = transduction(TextSensor(seed, TextSensorConfig()), p)
                cover.append((seed, family, group, all(c['scorable'] for c in m['coverage'].values())))
    print('Corpus balance and withheld-answer checks passed.')
    print('Formal mapping coverage (not an outcome-based seed filter):', sum(x[-1] for x in cover), '/', len(cover))
    for row in cover:
        if not row[-1]:
            print('Unscorable planned group:', row[:3])


if __name__ == '__main__':
    check()
