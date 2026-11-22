"""Read-only audit correction; original scientific scoring functions are reused."""
import argparse
import gc
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze as old
sys.path.insert(0,str(HERE))
import audit_readout_v2 as corrected

def analyze(work):
    assert not any((work/n).exists() for n in ('in-flight.json','STOP','analysis.json','audit.json'))
    assert old.read(work/'summary.json')['origins']==8
    note=old.read(work/'postprocessing/audit-v2/registration.json')
    assert note['pending']==0
    for rel,sha in note['tools'].items(): assert old.s.sha(old.ROOT/rel)==sha
    temporal=[];endpoint=[];corrections=[]
    progress=work/'postprocessing/audit-v2/scores';progress.mkdir(exist_ok=True)
    for i in range(8):
        source=work/'units'/f'o{i}'/'result.json';dest=progress/f'o{i}.json'
        sha=old.s.sha(source)
        if dest.exists():
            scored=old.read(dest);assert scored['source_sha256']==sha
        else:
            result=old.read(source)
            assert result['origin']==i and result['seed']==1056100+i
            scored={'source_sha256':sha,'temporal':old.summarize_unit(result),
                    'endpoint':old.summarize_unit(old.endpoint_view(result)),
                    'correction_rounds':len(result['calibration']['corrections'])}
            old.s.base.original(dest,scored);del result;gc.collect()
        temporal.append(scored['temporal']);endpoint.append(scored['endpoint']);corrections.append(scored['correction_rounds'])
        print(json.dumps({'scored_origins':i+1,'total':8}),flush=True)
    checked=corrected.audit(work);assert checked['passed']
    main,legacy=old.goals(temporal),old.goals(endpoint)
    valid=all(u['valid'] for u in temporal+endpoint)
    keys=('ports-first_expression','ports-causal_attribution')
    stop=not valid or (not all(main[k]['verdict']=='PASS' for k in keys) and not all(legacy[k]['verdict']=='PASS' for k in keys))
    files=[p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result={'schema':'threemind.r51k-analysis/1','analysis_revision':2,'kernel':'6.1','independent_origins':8,
            'valid':valid,'primary_condition':'temporal','temporal_goals':main,'endpoint_goals':legacy,
            'temporal_units':temporal,'endpoint_units':endpoint,'old_correction_rounds':corrections,
            'scientific_stop':stop,'timing':old.read(work/'summary.json'),'resources':old.read(work/'resource-summary.json'),
            'storage':{'logical_bytes':sum(p.stat().st_size for p in files),
                       'allocated_bytes':sum(old.disk_allocation(p)['allocated_bytes'] for p in files)}}
    checked.update(scientific_stop=stop,Core_engines_loaded=0)
    old.s.base.original(work/'analysis.json',result);old.s.base.original(work/'audit.json',checked)
    print(json.dumps({k:v for k,v in result.items() if k not in ('temporal_units','endpoint_units')},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);analyze(p.parse_args().work.resolve())
