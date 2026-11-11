"""Forty-eight fresh origins; never pools exploratory observations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import assay

N = 48
COURSES = ('massed', 'spaced', 'strong')


def cases():
    return [c for c in assay.cases(N, True)
            if (c['course'] in COURSES and c['delay'] in (1, 300))
            or (c['course'] == 'weak' and c['delay'] == 30)]
