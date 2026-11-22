"""Recompute all primary contrasts directly from saved trajectories using Decimal."""
from decimal import Decimal
import gzip
import json
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import support as s


def verify(work):
    analysis = json.loads((work / 'analysis.json').read_bytes())
    results = []
    for origin in range(8):
        arms = {}
        for arm in ('intact', 'sham', 'target', 'matched', 'restored'):
            scores = []
            for history in (0, 1):
                p = work / 'parents' / f'o{origin}-h{history}' / arm / 'final.json.gz'
                d = json.loads(gzip.decompress(p.read_bytes()), parse_float=Decimal)
                rows = [r for r in d['rows'] if 18100000 <= r['time_us'] <= 18300000]
                assert len(rows) == 5
                scores.append(sum(r['projection']['activation'][0] - r['projection']['activation'][1] for r in rows) / 5)
            arms[arm] = float((scores[0] - scores[1]) / 2)
            assert abs(arms[arm] - analysis['origins'][origin]['effects'][arm]['primary']) < 1e-12
        # Scientific outcomes are evaluated by the frozen protocol, not required
        # as a precondition for an arithmetically valid negative result.
        assert arms['intact'] == arms['sham'] == arms['restored']
        results.append(arms)
    receipt = {'passed': True, 'independent_origins': 8, 'trajectories': 80,
               'method': 'Decimal arithmetic from five preregistered samples per trajectory', 'effects': results}
    s.base.original(work / 'arithmetic-verification.json', receipt)
    print(json.dumps({'passed': True, 'trajectories': 80, 'independent_origins': 8}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    verify(p.parse_args().work)
