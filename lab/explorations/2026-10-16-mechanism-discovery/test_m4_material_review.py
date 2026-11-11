import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location('materials', HERE/'m4_material_review.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


def test_sustained_motion_requires_contiguous_frames_and_keeps_last_segment():
    assert m.runs(['eye-only']*6+['neither']*5+['eye-only']*5+['joint']*7) == {
        'eye-only': [6], 'neither': [], 'joint': [7]}
    assert m.runs([]) == {}
    assert m.runs(['hand-only']*120) == {'hand-only': [120]}


def test_material_output_is_exclusive_and_analysis_has_no_runtime_imports():
    import ast
    from uuid import uuid4
    tmp_path = HERE.parents[2]/'.work'/('m4-material-test-'+uuid4().hex)
    target = tmp_path/'manifest.json'
    m.write_once(target, {'fixture': True})
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        m.write_once(target, {'fixture': False})
    assert target.read_bytes() == original
    tree = ast.parse((HERE/'m4_material_review.py').read_text(encoding='utf-8'))
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {v.name for n in ast.walk(tree) if isinstance(n, ast.Import) for v in n.names}
    assert imports <= {'argparse', 'collections', 'gzip', 'hashlib', 'json', 'math', 'pathlib'}
