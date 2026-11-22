"""Verify that isolated copied methods differ only at the declared switches."""
import ast
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def methods(text,class_name):
    cls=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name==class_name)
    return {n.name:ast.get_source_segment(text,n) for n in cls.body if isinstance(n,ast.FunctionDef)}

def audit():
    spec=json.loads((HERE/'source-diff.json').read_text('utf8'))
    src=ROOT/spec['historical_source'];assert hashlib.sha256(src.read_bytes()).hexdigest()==spec['sha256']
    reference=methods(src.read_text('utf8'),'LocalEngine')
    actual=methods((HERE/'research_kernel.py').read_text('utf8'),'ResearchEngine')
    assert set(actual)==set(spec['replacements'])
    for name,pairs in spec['replacements'].items():
        changed=actual[name]
        for before,after in pairs:
            assert changed.count(after)==1,(name,after)
            changed=changed.replace(after,before)
        assert ast.dump(ast.parse(changed),include_attributes=False)==ast.dump(ast.parse(reference[name]),include_attributes=False),name
    return {'copied_methods':list(actual),'only_declared_changes':True,'source_sha256':spec['sha256']}

if __name__=='__main__':print(json.dumps(audit()))
