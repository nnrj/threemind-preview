"""Preregistered independent M5 confirmation; contains no subject or host code."""
from itertools import product

N = 48
SEED_BASE = 1066100
APPARATUS_SEED = 1066002
DOSES = (.74, .82, .94)
DELAYS = (2, 5)
HELDOUT_DOSES = (.86, .96)
ARMS = ('sham', 'target', 'matched', 'restored', 'plasticity-off')


def cases():
    strata = list(product(DOSES, DELAYS))
    return [{'origin': i, 'seed': SEED_BASE+i, 'dose': strata[(i+i//6) % 6][0],
             'delay_s': strata[(i+i//6) % 6][1], 'histories': [0, 1], 'arms': list(ARMS),
             'heldout_doses': list(HELDOUT_DOSES)} for i in range(N)]
