"""Read-only arithmetic, provenance and completion audit; never runs a subject."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

import _threemind_native

from bench import HERE, ROOT, WORK


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    main_rows = [json.loads(line) for line in (WORK / 'rows.jsonl').read_text('utf8').splitlines()]
    diag_rows = [json.loads(line) for line in (WORK / 'diagnostic/rows.jsonl').read_text('utf8').splitlines()]
    summary = json.loads((HERE / 'summary.json').read_text('utf8'))
    diagnostic = json.loads((HERE / 'diagnostic-summary.json').read_text('utf8'))
    assert len(main_rows) == 195 and len(diag_rows) == 40
    assert not list(WORK.rglob('in-flight.json'))
    for name, values in summary['cases'].items():
        pairs = {}
        for row in main_rows:
            if row['case'] == name and row['phase'] != 'calibration' and row['trial'] > 0:
                pairs.setdefault((row['phase'], row['trial']), {})[row['variant']] = row['advance_seconds']
        ratio = statistics.geometric_mean(row['63'] / row['61'] for row in pairs.values())
        assert abs(ratio - values['default_vs61']['advance_seconds']['ratio']) < 1e-12
    for name, cases in diagnostic['cases'].items():
        for value in cases.values():
            timings = [r['advance_seconds'] for r in diag_rows if r['case'] == name
                       and r['trial'] > 0 and r['expiry'] == value['expiry'] and r['retain'] == value['retain']]
            assert statistics.median(timings) == value['median_seconds']
    for file, expected in json.loads((WORK / 'manifest.json').read_text('utf8')).items():
        assert digest(ROOT / file) == expected
    files = sorted(p for p in WORK.rglob('*') if p.is_file())
    start = (WORK / 'manifest.json').stat().st_mtime
    end = (WORK / 'diagnostic/rows.jsonl').stat().st_mtime
    binaries = []
    for name, module in sorted(sys.modules.items()):
        path = getattr(module, '__file__', None)
        if not name.startswith('_threemind_native') or not path:
            continue
        path = Path(path)
        if path.suffix != '.pyd':
            continue
        binaries.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path),
                         'mtime_before_benchmark_start': path.stat().st_mtime < start,
                         'hash_recorded_after_measurement': True})
    assert len(binaries) == 1 and binaries[0]['mtime_before_benchmark_start']
    result = {'complete_worker_processes': 235, 'verified_complete_state_files': 235,
              'timed_and_warmup_instances': sum(r['repeats'] for r in main_rows + diag_rows),
              'additional_profile_instances': 4, 'measurement_elapsed_seconds': end - start,
              'raw_bytes': sum(p.stat().st_size for p in files),
              'raw_inventory_sha256': hashlib.sha256(json.dumps(
                  [(str(p.relative_to(WORK)), digest(p)) for p in files],
                  separators=(',', ':')).encode()).hexdigest(),
              'arithmetic_verified': True, 'frozen_manifest_verified': True,
              'native_extension_post_run': binaries,
              'provenance_note': 'The preregistered native path resolved to the Python package loader. '
                  'The actual extension hash above was added after measurement; it is not a preregistered binary hash.',
              'summary_sha256': digest(HERE / 'summary.json'),
              'diagnostic_summary_sha256': digest(HERE / 'diagnostic-summary.json')}
    assert result['raw_bytes'] < 256 * 2**20 and result['measurement_elapsed_seconds'] < 1200
    (HERE / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
