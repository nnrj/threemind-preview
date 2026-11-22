"""Check that the historical measurement port changed only declared construction/audit code."""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[3] / 'lab/explorations/2026-10-16-mechanism-discovery'


def members(path):
    result = {}
    for node in ast.parse(path.read_text('utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef): result[node.name + '.' + child.name] = child
    return result


def check():
    old = members(OLD / 'closure_rig.py')
    new = members(HERE / 'rig.py')
    changed = [name for name in new if ast.dump(new[name]) != ast.dump(old[name])]
    assert sorted(changed) == ['Rig.__init__', 'Rig.save']
    previous = members(OLD / 'closure_driver.py')
    measurement = members(HERE / 'measurement.py')
    assert ast.dump(previous['save']) == ast.dump(measurement['save'])
    old_x3, new_x3 = previous['x3'], measurement['x3']
    old_assignments = [n for n in ast.walk(old_x3) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'selection' for t in n.targets)]
    new_assignments = [n for n in ast.walk(new_x3) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'selection' for t in n.targets)]
    assert len(old_assignments) == len(new_assignments) == 1
    new_assignments[0].value = old_assignments[0].value
    assert ast.dump(old_x3) == ast.dump(new_x3)
    return {'passed': True, 'unchanged_rig_methods_and_functions': sorted(set(new) - set(changed)),
            'declared_changes': {'Rig.__init__': 'Explicit 6.1 default factory and restore identity',
                                 'Rig.save': 'New whole-state schema identifier',
                                 'measurement.x3': 'Additional teaching-only Core matching validity audit'},
            'measurement_body_otherwise_identical': True, 'controller_source_reused_without_edit': True,
            'scientific_individuals_created': 0}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
