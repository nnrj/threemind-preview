"""Read physical curves only; do not inspect target-ranking outcomes for calibration."""
import json
from run import META, WORK
from threemind_lab import calibration
from threemind_lab.config import Settings
from threemind_lab.database import Database

meta = json.loads(META.read_bytes())
data = json.loads((WORK/meta['completed_phases']['calibration']).read_bytes())
db = Database(Settings.from_env().database_url)
try:
    summary = []
    for case in data['rows']:
        result = calibration.result(db, meta['project_id'], case['measurements']['family']['id'])
        rows = [r for r in result['rows'] if r['cue'] and r['intensity']==1]
        print('case',case['seed'],case['family'])
        for t in [0, 100000, 120000, 200000, 400000, 600000, 1000000]:
            points=[next(p for p in r['curve'] if p['offset_us']==t) for r in rows]
            value={'time_us':t,'saturation_min':min(p['saturated_fraction'] for p in points),
                   'saturation_max':max(p['saturated_fraction'] for p in points),
                   'sent_min':min(p['transport']['sent'] for p in points)}
            summary.append({'seed':case['seed'],'family':case['family'],**value})
            print(value)
    from run import HERE,encoded
    (HERE/'physical-timing.json').write_bytes(encoded(summary))
finally:
    db.close()
