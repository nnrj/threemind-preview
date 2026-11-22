"""Read-only verification of performance evidence and preregistered decisions."""
import gzip
import json
from pathlib import Path
import statistics
from threemind_core import StateImage

from bench import CASES, HERE, METRICS, ROOT, WORK, interval, numerical, rows, sha


def decision(data, case, metric):
    combined = interval(data, case, metric)
    phases = {phase: interval(data, case, metric, phase=phase) for phase in ('main', 'confirmation')
              if any(r['case']==case and r['phase']==phase for r in data)}
    if len(phases)==2 and all(p['ratio'] >= 1.1 and p['low'] > 1 for p in phases.values()):
        label = 'confirmed-regression'
    elif combined['high'] < 1.1:
        label = 'below-10-percent-bound'
    else:
        label = 'precision-unresolved'
    return combined | {'decision': label, 'phases': phases}


def main():
    manifest = json.loads((WORK/'manifest.json').read_text('utf8'))
    for path, expected in manifest.items(): assert sha((ROOT/path).read_bytes())==expected, path
    data = rows()
    confirm = json.loads((WORK/'confirmation-cases.json').read_text('utf8'))
    assert not (WORK/'in-flight.json').exists()
    for phase, cases in (('main', CASES), ('confirmation', confirm)):
        for case in cases:
            part = [r for r in data if r['phase']==phase and r['case']==case]
            assert len(part)==21, (phase, case, len(part))
            for trial in range(7):
                batch = {r['variant']:r for r in part if r['trial']==trial}
                assert len(batch)==3
                assert len({r['input_sha256'] for r in batch.values()})==1
                assert batch['61']['numerical_sha256']==batch['63-compatible']['numerical_sha256']
    for row in data:
        payload = gzip.decompress((WORK/row['state_file']).read_bytes())
        # StateImage.digest hashes canonical state data, not raw JSON bytes.
        assert StateImage(payload).digest==row['state_sha256']
        assert numerical(json.loads(payload))==row['numerical_sha256']
    cases = {}
    for case in CASES:
        part = [r for r in data if r['case']==case and r['phase'] in ('main','confirmation') and r['trial']>0]
        variants = {}
        for variant in ('61','63','63-compatible'):
            selection = [r for r in part if r['variant']==variant]
            first = selection[0]
            assert len({r['numerical_sha256'] for r in selection})==1, 'timing rounds changed simulation'
            variants[variant] = {key:statistics.median(r[key] for r in selection) for key in METRICS+(
                'birth_seconds', 'advance_cpu_seconds','baseline_commit_bytes','advance_peak_commit_bytes',
                'total_peak_commit_bytes','snapshot_bytes')}
            variants[variant].update({key:first[key] for key in ('nodes','edges','sequence','time_us','life','audit','transport','timer_count')})
        cases[case] = {'backend':CASES[case][0], 'variants':variants,
                       'default_vs61':{m:decision(data,case,m) for m in METRICS},
                       'compatible_vs61':{m:interval(data,case,m,'63-compatible','61') for m in METRICS},
                       'expiry_on_vs_off':{m:interval(data,case,m,'63','63-compatible') for m in METRICS}}
    checks = [c for r in data for c in r['resource_checks']]
    summary = {'date':'2026-11-15', 'kind':'engineering-performance', 'case_count':len(CASES),
               'complete_workers':len(data), 'verified_full_states':len(data),
               'confirmation_cases':confirm,'repeat_counts':json.loads((WORK/'repeat-counts.json').read_text('utf8')),
               'min_free_GiB':{k:min(c[k] for c in checks)/2**30 for k in ('commit','ram','c','e')},
               'raw_total_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
               'frozen_files_unchanged':True,'manifest_sha256':sha((WORK/'manifest.json').read_bytes()),
               'rows_sha256':sha((WORK/'rows.jsonl').read_bytes()),'cases':cases}
    (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
    for case, values in cases.items():
        primary=values['default_vs61']['advance_seconds']
        print(json.dumps({'case':case,'default':primary,'compatible':values['compatible_vs61']['advance_seconds'],
                          'expiry':values['expiry_on_vs_off']['advance_seconds']},ensure_ascii=False))


if __name__=='__main__':main()
