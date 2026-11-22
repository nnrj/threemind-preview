"""Original two historical factor matrices, with the applicable 6.3 comparison."""
from copy import deepcopy

RETENTION = {'3.1': ('current', 'legacy-edges', 'legacy-all'),
             '5.1': ('current', 'legacy-edges', 'legacy-all'),
             '6.3': ('current', 'stability')}


def design(previous):
    index = {c['key']: c for c in previous}
    cases = []
    references = []
    for version, retentions in RETENTION.items():
        base = 'v' + version.replace('.', '')
        for retention in retentions:
            for novelty in ('arrival-window', 'immediate'):
                variant = f'v{version}-{retention}-{novelty}'
                source = base + ('' if retention == 'current' else '-' + retention)
                if version == '6.3' and retention == 'current' and novelty == 'immediate':
                    source += '-immediate'
                reused = ((novelty == 'arrival-window' or version == '6.3') and
                          source + '/short/train-0' in index)
                patch = {} if retention == 'current' else {'consolidation_mode':
                    'stability' if version == '6.3' else 'legacy-stability'}
                if retention == 'legacy-all':
                    patch['node_retention_mode'] = 'manual'
                for block in (0, 1):
                    keys = [f'short/train-{block}', f'history/s{block}/101/d1/AB', f'history/s{block}/101/d1/DB']
                    for i, key in enumerate(keys):
                        c = deepcopy(index[(source if reused else base) + '/' + key])
                        c.update(matrix_variant=variant, block=block, retention=retention, novelty=novelty)
                        if reused:
                            references.append(c)
                        else:
                            c.update(key=variant + '/' + key, variant=variant,
                                parent=None if i == 0 else variant + '/' + keys[0],
                                birth_patch=patch | {'novelty_mode': novelty}, cause_patch={})
                            cases.append(c)
    assert len(cases) == 54 and len(references) == 42
    assert sum(c['version'] == '6.3' for c in cases) == 12
    return cases, references


def aggregate(rows, epsilon=1e-6):
    matrix = []
    for version, retentions in RETENTION.items():
        for retention in retentions:
            for novelty in ('arrival-window', 'immediate'):
                rr = [r for r in rows if (r['version'], r['retention'], r['novelty']) == (version, retention, novelty)]
                assert len(rr) == 4
                blocks = [{'block': b, 'passed': all(r['signed_peak'] > epsilon for r in rr if r['block'] == b),
                    'margins': [r['signed_peak'] for r in rr if r['block'] == b]} for b in (0, 1)]
                matrix.append({'version': version, 'retention': retention, 'novelty': novelty, 'blocks': blocks,
                    'passed_blocks': sum(b['passed'] for b in blocks), 'reused': all(r['reused'] for r in rr)})
    return matrix


def compare(matrix, historical):
    lost = []
    comparisons = []
    for old in historical['matrix']:
        new = next(r for r in matrix if (r['version'], r['retention'], r['novelty']) ==
                   (old['version'], old['retention'], old['novelty']))
        item = {k: new[k] for k in ('version', 'retention', 'novelty')}
        item.update(historical_passed_blocks=old['passed_blocks'], new_passed_blocks=new['passed_blocks'])
        comparisons.append(item)
        if old['passed_blocks'] == 2 and new['passed_blocks'] < 2:
            lost.append(item)
    return {'scientific_stop': bool(lost), 'new_adverse_changes': lost, 'historical_comparisons': comparisons,
        'current_63_matrix_separately_reported': True,
        'manual_node_retention_63': 'unsupported; not reintroduced or relabelled as an implemented condition'}
