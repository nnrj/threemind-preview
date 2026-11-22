"""Independently check engineering evidence and write a small tracked summary."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from threemind_kernels.local61_config import Local61Config
from threemind_kernels.local63_config import Local63Config
import _threemind_native

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / '.work/kernel63-default-alignment'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def benchmark(name):
    path = WORK / name
    data = json.loads(path.read_text('utf8'))
    # The first run predates the optional expiry-enabled comparison. Its fixed
    # compatible configuration explicitly disabled expiry for every /6.3 trial.
    expiry = data.get('expiry_enabled', False)
    summaries = []
    matched = 0
    for n in (32, 128):
        for topology in ('sparse', 'dense'):
            all_rows = [r for r in data['trials'] if r['nodes'] == n and r['topology'] == topology]
            assert len(all_rows) == 18
            row = {'nodes': n, 'initial_topology': topology}
            for variant in ('61', 'compatible', 'precheck'):
                sample = [r for r in all_rows if r['variant'] == variant and r['trial'] > 0]
                assert len(sample) == 5
                row[variant] = {key: statistics.median(r[key] for r in sample) for key in (
                    'wall_seconds', 'cpu_seconds', 'save_seconds', 'snapshot_bytes', 'peak_commit_bytes', 'events', 'edges')}
            row['precheck_ratio'] = row['precheck']['wall_seconds'] / row['compatible']['wall_seconds']
            row['63_vs_61_ratio'] = row['compatible']['wall_seconds'] / row['61']['wall_seconds']
            for trial in range(6):
                pair = {r['variant']: r for r in all_rows if r['trial'] == trial}
                equal = pair['61']['state_sha256'] == pair['compatible']['state_sha256']
                matched += equal
                if not expiry:
                    assert equal, (n, topology, trial)
            summaries.append(row)
    ratio = math.exp(statistics.mean(math.log(row['precheck_ratio']) for row in summaries))
    assert math.isclose(ratio, data['geometric_precheck_ratio'], abs_tol=1e-14)
    minima = {key: min(r[key] for r in data['resource_checks']) / 2**30 for key in ('commit', 'ram', 'c', 'e')}
    for key, reserve in zip(('commit', 'ram', 'c', 'e'), (5, 4, 5, 25)):
        assert minima[key] >= reserve
    return {'file': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
            'expiry_enabled': expiry, 'cases': summaries,
            'geometric_precheck_ratio': ratio, 'meets_substantial_gain_rule': ratio <= .8 and max(r['precheck_ratio'] for r in summaries) <= 1.2,
            'identical_61_63_final_states': matched, 'compared_final_state_pairs': 24,
            'minimum_free_GiB': minima}


def main():
    manifest_path = WORK / 'witnesses/manifest.json'
    manifest = json.loads(manifest_path.read_text('utf8'))
    for name, value in manifest['historical_sources'].items(): assert digest(ROOT/name) == value
    for name, value in manifest['witnesses'].items(): assert digest(WORK/'witnesses'/name) == value
    suites = []
    passed_ids = set()
    for name in ('kernel-tests.xml', 'runtime-tests.xml'):
        path = WORK / name
        suite = ET.parse(path).getroot().find('testsuite')
        assert int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
        skipped = []
        for case in suite.findall('testcase'):
            skip = case.find('skipped')
            if skip is not None:
                skipped.append({'test': case.attrib['name'], 'reason': skip.attrib.get('message')})
            else:
                passed_ids.add((case.attrib['classname'], case.attrib['name']))
        suites.append({'file': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
                       'tests': int(suite.attrib['tests']), 'passed': int(suite.attrib['tests']) - len(skipped),
                       'failures': 0, 'errors': 0, 'skipped': skipped})
    old, new = Local61Config().to_dict(), Local63Config().to_dict()
    assert all(new[key] == value for key, value in old.items())
    changes = {key: new[key] for key in ('resource_precheck_enabled', 'subthreshold_expiry_enabled',
                                        'inhibition_updates_usage', 'inhibition_bypasses_resources',
                                        'separate_inhibition_resources')}
    sources = ['src/threemind_kernels/local63_config.py', 'crates/threemind-core/src/local63-defaults.json',
               'src/threemind_lab/configuration.py', 'src/threemind_kernels/local63.py',
               'crates/threemind-core/src/local63_transitions.rs']
    summary = {'date': '2026-11-15', 'kind': 'engineering-default-adjustment', 'final_defaults': changes,
               '61_shared_parameter_count': len(old), '61_shared_parameter_differences': {},
               'extra_63_parameters': {key: value for key, value in new.items() if key not in old},
               'benchmark_without_expiry': benchmark('performance-before.json'),
               'benchmark_with_expiry': benchmark('performance-final.json'),
               'test_suites': suites, 'distinct_passed_tests': len(passed_ids),
               'historical_source_count': len(manifest['historical_sources']),
               'pre_edit_witness_files': len(manifest['witnesses']), 'witness_manifest_sha256': digest(manifest_path),
               'delivered_source_sha256': {name: digest(ROOT/name) for name in sources},
               'native_sha256': digest(Path(_threemind_native.__file__)),
               'standalone_sha256': digest(ROOT/'target/release/threemind-runtime.exe')}
    assert not summary['benchmark_without_expiry']['meets_substantial_gain_rule']
    assert not summary['benchmark_with_expiry']['meets_substantial_gain_rule']
    destination = Path(__file__).with_name('summary.json')
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(json.dumps({'distinct_passed_tests': len(passed_ids), 'defaults': changes,
                      'precheck_gain_percent': 100*(1-summary['benchmark_with_expiry']['geometric_precheck_ratio'])}))


if __name__ == '__main__': main()
