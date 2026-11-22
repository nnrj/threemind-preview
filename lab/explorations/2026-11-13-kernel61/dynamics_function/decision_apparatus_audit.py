"""Verify completed calibration records; normalize only independent observer identities."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import decision as h

def audit(work):
    h.check(work);assert not (work/'apparatus.json').exists() and not (work/'cases').exists()
    hashes={};observers=[];identities=[]
    for mode in ('observed','dense','plain','restored','paused'):
        folder=work/'apparatus'/mode;r=h.read(folder/'result.json');im=h.e.base.image(folder/'final.tmind')
        assert r['status']=='complete' and r['calibration'] and r['final_sha256']==im.digest
        assert im.to_dict()['config']['seed']==941199
        hashes[mode]=im.digest
        ob=h.e.unpacked(folder/'observer.json.xz');assert ob['session_id']==ob['readouts']['run_id']
        identities.append({'mode':mode,'session_id':ob['session_id']})
        normalized=deepcopy(ob);normalized.pop('session_id');normalized['readouts'].pop('run_id');observers.append(normalized)
    assert len(set(hashes.values()))==1 and all(v==observers[0] for v in observers)
    ids,_=h.d.mapping(941199)
    points=[{'time_us':t,'nodes':[{'channel':ids['C'],'activation':.2},{'channel':ids['E'],'activation':.1}]} for t in range(0,500001,50000)]
    answer=h.x.score(points,ids,500000,'C');assert answer['correct'] and abs(answer['margin_C_minus_E']-.05)<1e-12
    evidence={'passed':True,'hashes':hashes,'same_observers_except_declared_identities':True,'identities':identities,
        'synthetic_score':answer,'separate_encoding':True,'original_failure':'asserted equality of independently created observer UUIDs',
        'scientific_state_difference':False,'reexecuted':False,'audit_source_sha256':h.s.sha(Path(__file__))}
    h.s.base.original(work/'apparatus.json',evidence)
    shutil.copyfile(Path(__file__),work/'apparatus-audit-source.py')
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps(evidence),flush=True)

if __name__=='__main__':audit(Path(sys.argv[1]))
