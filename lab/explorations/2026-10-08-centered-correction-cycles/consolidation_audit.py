"""Read saved E66 states and frozen code; never instantiate or advance Core."""
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from threemind_lab.provenance import capture_implementation

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/centered-correction-cycles-20261008'
KEYS = (
    'plasticity', 'edge_consolidation_enabled', 'stability_gain',
    'stability_tau', 'stability_decay_enabled', 'forgetting_rate',
    'eligibility_tau', 'eligibility_decay_enabled', 'associative_gain',
    'learning_rate', 'novelty_mode', 'prune_weight', 'node_prune_after_us',
    'propagation_interval_us',
)


def main():
    meta = json.loads((WORK / 'platform.json').read_bytes())
    assert capture_implementation('native') == meta['implementation']
    paths = (
        'crates/threemind-core/src/continuous.rs',
        'crates/threemind-core/src/restoration.rs',
        'crates/threemind-core/src/novelty.rs',
        'src/threemind_kernels/continuous.py',
        'src/threemind_core/restoration.py',
        'src/threemind_kernels/memory.py',
        'src/threemind_kernels/novelty.py',
    )
    source_hashes = {}
    for relative in paths:
        original = (WORK / 'frozen-sources' / relative).read_bytes()
        assert original == (ROOT / relative).read_bytes(), relative
        source_hashes[relative] = hashlib.sha256(original).hexdigest()
    states = []
    for case in ('initial-teaching/birth', 'initial-teaching/system',
                 'correction-1/system', 'correction-2/system', 'fit-3/system'):
        path = WORK / 'cases' / case / 'system.json.gz'
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            c = json.load(f)['session']['core']
        assert c['dynamics'] == 'threemind.continuous-memory/2'
        assert c['config'] == c['definition']['config']
        config = {key: c['config'][key] for key in KEYS}
        assert config['plasticity'] and config['edge_consolidation_enabled']
        assert config['stability_decay_enabled']
        if states:
            assert config == states[0]['config']
        edges = c['edges']
        states.append(dict(
            case=case, kernel=c['dynamics'], time_us=c['time_us'],
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            config=config, edges=len(edges),
            stability_ge_09=sum(e['stability'] >= .9 for e in edges),
            stability_ge_099=sum(e['stability'] >= .99 for e in edges),
            stability_max=max((e['stability'] for e in edges), default=None),
            touches_max=max((e['touches'] for e in edges), default=0),
            persisted_edge_fields=sorted(edges[0]) if edges else [],
            silenced_edges=len(c['silenced_edges']),
            silenced_nodes=len(c['silenced_nodes']),
        ))
    result = dict(
        schema='threemind.e66-consolidation-audit/1',
        recorded_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        read_only=True, simulations=0, core_changes=0,
        implementation_matches_registered_native=True,
        frozen_sources_match=source_hashes, states=states,
        findings={
            'positive_existing_edge_consolidation_enabled': True,
            'coactivation_and_successful_associative_traversal_raise_stability': True,
            'stability_reduces_weight_forgetting': True,
            'stability_itself_can_decay': True,
            'per_edge_permanently_lengthened_decay_time_constant': False,
            'behavioral_failure_cause_established': False,
        },
    )
    destination = HERE / 'consolidation-audit.json'
    with destination.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
