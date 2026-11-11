"""Bounded assay calibration; selection never uses a trained-versus-naive benefit."""
N = 8
SEED_BASE = 1086100
APPARATUS_SEED = 1086002
TEST_SEED = 1086004
DOSES = (.10, .20, .30, .40)
PROBE_DOSE = .40
DELAY_SECONDS = 30
LESSONS = 16
MARGIN = 1e-4


def cases():
    return [{'origin': i, 'seed': SEED_BASE+i, 'mode': 'S', 'delay_s': DELAY_SECONDS,
             'probe_dose': PROBE_DOSE, 'lesson_doses': list(DOSES), 'lessons': LESSONS}
            for i in range(N)]
