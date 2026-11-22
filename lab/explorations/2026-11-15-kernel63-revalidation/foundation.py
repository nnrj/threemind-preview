"""Engineering-only addressing checks on 6.3, before scientific registration."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from threemind_kernels.local63 import KERNEL_ID, Local63Config, Local63Engine
from _threemind_native import _threemind_native as native


def main():
    out = HERE / 'foundation.json'
    assert not out.exists(), 'Engineering checks already completed'
    suite_path = ROOT / '.work/kernel63-rerun-foundation-authorized.xml'
    suites = ET.parse(suite_path).getroot()
    tests = sum(int(s.get('tests', '0')) for s in suites.iter('testsuite'))
    assert tests == 135
    assert not list(suites.iter('error')) and not list(suites.iter('failure'))
    # Reuse unchanged test bodies with only the laboratory factory redirected.
    # Historical production classes, files and states are never changed.
    path = ROOT / 'tests_v2/test_local60.py'
    spec = importlib.util.spec_from_file_location('r63_addressing_checks', path)
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    t.KERNEL_ID, t.Local60Config, t.Local60Engine = KERNEL_ID, Local63Config, Local63Engine
    completed = []
    for backend in ('reference', 'native'):
        for function in ('test_fixed_address_is_order_independent_and_sparse',
                         'test_deleted_node_is_recreated_at_same_address_with_fresh_state'):
            getattr(t, function)(backend)
            completed.append([function, backend])
        for mode in ('address', 'same-birth'):
            for function in ('test_old_arrivals_do_not_create_nodes_and_new_signals_still_arrive',
                             'test_wake_requires_original_endpoints_only_in_same_birth_mode'):
                getattr(t, function)(mode, backend)
                completed.append([function, mode, backend])
    result = {'passed': True, 'kernel': KERNEL_ID, 'scientific_origins': 0,
              'pytest_passed': tests, 'additional_checks': completed,
              'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'pytest_xml': str(suite_path),
              'pytest_xml_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest(),
              'native_path': native.__file__,
              'native_sha256': hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
              'defaults': Local63Config().to_dict(),
              'scope': 'Default identity, Python/Rust continuity, inheritance, observation, fixed addresses and in-flight policies. No scientific result.'}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'passed': True, 'pytest_passed': tests, 'additional_checks': len(completed)}))


if __name__ == '__main__':
    main()
