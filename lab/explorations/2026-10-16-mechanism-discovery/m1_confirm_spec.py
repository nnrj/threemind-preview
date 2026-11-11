"""Independent confirmation cases; no scientific state is created on import."""
from itertools import product

N = 48
SEED_BASE = 1076100
APPARATUS_SEED = 1076002
ARMS = ('intact', 'sham', 'target-bundle', 'matched-bundle', 'persistent', 'fast', 'restored')
CUES = ('X', 'Y', 'XY', 'XN', 'YN', 'Z', 'W', 'ZW', 'ZN', 'WN')
DOSE = .88


def cue_values(cue):
    if cue.endswith('N'):
        return {cue[0]: DOSE*.85, 'N': DOSE*.15}
    return dict.fromkeys(cue, DOSE/len(cue))


def cases():
    strata = list(product((.38, .42, .46), (2, 5)))
    return [{'origin': i, 'seed': SEED_BASE+i, 'teaching_dose': strata[(i+i//6) % 6][0],
             'delay_s': strata[(i+i//6) % 6][1], 'histories': [0, 1], 'arms': list(ARMS),
             'cues': [{'cue': cue, 'values': cue_values(cue)} for cue in CUES]} for i in range(N)]
