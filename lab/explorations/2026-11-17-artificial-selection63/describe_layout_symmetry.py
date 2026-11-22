"""Retrospective check of the two symmetric starts, not a new success rule."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
destination = ROOT / '.work/artificial-selection63-layout-20261117/analysis-v1'
assert json.loads((destination/'audit.json').read_text('utf8'))['passed']
with (destination/'stages.csv').open(encoding='utf8',newline='') as stream:
    rows = list(csv.DictReader(stream))
closed = [x for x in rows if x['condition'] == 'closed']
lookup = {(x['seed'],x['arm'],x['candidate'],x['start_index']):x for x in closed}
assert len(closed) == 384
symmetry_error = replay_error = 0.
for row in closed:
    opposite = lookup[(row['seed'],row['arm'],row['candidate'],str(2-int(row['start_index'])))]
    symmetry_error = max(symmetry_error,abs(float(row['region1'])-float(opposite['baseline_region1'])))
for row in rows:
    if row['condition'] == 'replay':
        replay_error = max(replay_error,abs(float(row['region1'])+float(row['baseline_region1'])-1))
result = {'interpretation':'retrospective descriptive check; no new success criterion',
          'symmetric_start_pairs':192,'closed_stages':384,'replay_stages':384,
          'maximum_swapped_closed_vs_opposite_original_start_occupancy_error':symmetry_error,
          'maximum_replay_occupancy_complement_error':replay_error}
payload = json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
path = destination/'layout-symmetry.json'
if path.exists(): assert path.read_text('utf8') == payload
else: path.write_text(payload,encoding='utf8')
print(payload)
