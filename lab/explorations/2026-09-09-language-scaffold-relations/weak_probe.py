"""Additional instrument calibration after the initial physical gate failed.

No retraining, altered dynamics, or target-score selection. The original source
checkpoints and failed calibration remain intact.
"""
import json
from run import META, WORK, Study, protocols

study = Study('weak_probe')
error = None
try:
    source = json.loads((WORK/study.meta['completed_phases']['calibration']).read_bytes())
    for case in source['rows']:
        old = case['measurements']['family']
        run, cp = {'id': old['run_id']}, {'id': old['checkpoint_id']}
        measurements = {k: study.probe(run, cp, p)
                        for k, p in protocols(case['names'], [.03125, .0625, .125, .25, .5]).items()}
        study.rows.append({k:v for k,v in case.items() if k != 'measurements'} | {'measurements': measurements})
        study.refresh_budget()
        print('weaker probes',len(study.rows),'/4',flush=True)
except Exception as ex:
    error = f'{type(ex).__name__}: {ex}'
    raise
finally:
    study.close(error)
