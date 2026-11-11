"""Recover finished E62 trials after snapshot rename failure; no simulation."""
import gzip
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
p = ROOT / '.work/continuous-development-20261007/cases/s223-direct-aligned-system-visible-cue-normal'
if (p / 'result.json').exists():
    raise FileExistsError('Recovery is append-only and runs once')
records = []
with gzip.open(p / 'process.jsonl.gz', 'rt', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        records.append(row['trial'])
        if len(row['process']) != 80:
            raise ValueError('Incomplete trial')
if len(records) != 12:
    raise ValueError('Incomplete evaluation')
manifest = json.loads((p / 'system/complete.json').read_text(encoding='utf-8'))
assert manifest['core_time_us'] == 464000000 and manifest['motor_steps'] == 4054
stopped = json.loads((p / 'stopped.json').read_text(encoding='utf-8'))
started = json.loads((p / 'started.json').read_text(encoding='utf-8'))
assert 'system.partial' in stopped['error'] and 'WinError 5' in stopped['error']
result = dict(seed=223, group='direct', mode='normal', checkpoint='system', n=12,
    ever_reached=sum(r['ever_reached'] for r in records),
    end_reached=sum(r['end_reached'] for r in records),
    mean_eye_error_rad=statistics.mean(r['eye_end_error_rad'] for r in records if r['mode'] != 'point'),
    mean_hand_error_m=statistics.mean(r['hand_end_error_m'] for r in records if r['mode'] != 'look'),
    motor_steps=4054, silenced_edges=0, whole_system_checkpoint=str(p/'system'), cue_seconds=4.,
    wall_seconds=stopped['wall_seconds'], tools=started['tools'], runner=started['runner'],
    recovered_after_save_error=True)
for name, value in [('scores.json', records), ('recovery.json', {
        'method':'Completed snapshot renamed in place; scores read from all twelve original process records',
        'simulation_repeated':False, 'original_error_preserved':'stopped.json'}), ('result.json', result)]:
    with (p/name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps(result, ensure_ascii=False))
