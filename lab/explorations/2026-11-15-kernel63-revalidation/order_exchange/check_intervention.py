"""Pure-data exchange checks; deliberately does not validate native execution."""
import copy
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(ROOT / 'src')]
from intervention import exchange, GROUPS, deadline
from threemind_core import StateImage
from threemind_runtime import ArtifactCodec


def check(path):
    a = ArtifactCodec.decode(Path(path).read_bytes()).to_dict()
    # Synthetic records only: these clock replacements are never restored.
    for row in a['nodes'] + a['edges']: row['state_us'] = a['time_us']
    for edge in a['edges']:
        for field in ('short_term', 'fast'):
            if edge[field]: edge[field]['time_us'] = a['time_us']
    b = copy.deepcopy(a)
    b['edges'][0]['weight'] *= .8
    b['edges'][1]['decay_age'] += .1
    b['nodes'][0]['touches'] += 1
    b['nodes'][1]['fatigue'] += .01
    A, B = StateImage.from_dict(a), StateImage.from_dict(b)
    digests = A.digest, B.digest
    for bits in itertools.product((0, 1), repeat=4):
        groups = [g for g, on in zip(GROUPS, bits) if on]
        d = exchange(A, B, groups)[0].to_dict()
        assert d['time_us'] == a['time_us'] and d['queue'] == a['queue']
        for section, index, name, group in (
            ('edges', 0, 'weight', 'W'), ('edges', 1, 'decay_age', 'S'),
            ('nodes', 0, 'touches', 'N'), ('nodes', 1, 'fatigue', 'D')):
            assert d[section][index][name] == (b if group in groups else a)[section][index][name]
        assert exchange(A, A, groups)[0].digest == A.digest, 'self-exchange must be exact'
    assert (A.digest, B.digest) == digests
    assert exchange(A, B, ())[0].digest == A.digest
    for field in ('state_us', 'novelty_deadline_us'):
        bad = copy.deepcopy(b)
        bad['edges'][0][field] = '0'
        try: exchange(A, StateImage.from_dict(bad), ('W',))
        except ValueError: pass
        else: raise AssertionError('invalid exchange boundary accepted: ' + field)
    assert deadline(1000000, '1000000', 0, 100000) == 1100000
    assert deadline(1000000, '1000000', None, 100000) is None
    return {'passed': True, 'group_combinations': 16, 'self_exchanges': 16,
            'created_engines': 0, 'advanced_us': 0, 'native_validation': 'pending'}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1])))
