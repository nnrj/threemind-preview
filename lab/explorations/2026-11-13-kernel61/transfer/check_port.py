"""AST checks for the historical X1 port; no Core is instantiated."""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[3] / 'lab/explorations/2026-10-16-mechanism-discovery'


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text('utf-8')).body if isinstance(n, ast.FunctionDef)}


def check():
    old = functions(OLD / 'closure_rig.py')
    new = functions(HERE / 'transfer_rig.py')
    assert ast.dump(old['settle']) == ast.dump(new['settle'])
    # Only the diagnostic error message changes to the actual kernel identity.
    for node in ast.walk(new['transfer']):
        if isinstance(node, ast.Constant) and node.value == 'compatible same-time /6.1 required':
            node.value = 'compatible same-time /5.1 required'
    assert ast.dump(old['transfer']) == ast.dump(new['transfer'])
    old, new = functions(OLD / 'closure_driver.py'), functions(HERE / 'measurement.py')
    for name in ('save', 'x1'): assert ast.dump(old[name]) == ast.dump(new[name])
    # Pure saved-value examples: declared visit increments are accounted for,
    # while unexplained bookkeeping or physical-state differences still fail.
    from study import settlement_comparison
    import copy
    before = {'model': {'audit': {'node_visits': 10, 'edge_visits': 20, 'arrivals': 4}, 'weight': .5}}
    after = copy.deepcopy(before)
    after['model']['audit'].update(node_visits=14, edge_visits=22)
    left = copy.deepcopy(before); right = copy.deepcopy(after)
    left['model']['audit']['arrivals'] += 1; right['model']['audit']['arrivals'] += 1
    assert settlement_comparison(left, right, before, after)[0]
    for change in ('node_visits', 'arrivals', 'weight'):
        bad = copy.deepcopy(right)
        if change == 'weight': bad['model']['weight'] += .01
        else: bad['model']['audit'][change] += 1
        assert not settlement_comparison(left, bad, before, after)[0]
    return {'passed': True, 'unchanged': ['settle', 'transfer behavior', 'save', 'x1'],
            'settlement_counter_cases': 4, 'scientific_individuals_created': 0, 'kernel_identity': '6.1'}


if __name__ == '__main__': print(json.dumps(check()))
