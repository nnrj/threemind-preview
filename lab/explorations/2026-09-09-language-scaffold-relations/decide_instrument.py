"""Freeze failed instrument decision and scoped diagnostic amendment in Lab."""
import hashlib
import json
from uuid import uuid4
from run import HERE, META, WORK, encoded
from threemind_lab import notebooks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database

meta = json.loads(META.read_bytes())
rows = []
for phase in ['calibration','weak_probe']:
    data = json.loads((WORK/meta['completed_phases'][phase]).read_bytes())
    doses = sorted({r['intensity'] for c in data['rows'] for m in c['measurements'].values() for r in m['rows'] if r['cue']})
    for dose in doses:
        probes = [(m, r) for c in data['rows'] for m in c['measurements'].values() for r in m['rows']
                  if r['cue'] and r['intensity']==dose]
        count = sum(all(v['scorable'] for v in m['mapping']['coverage'].values()) and r['available']
                    and r['transport']['sent']>0 and r['delivered_signal_amount']>0
                    and r['max_saturated_fraction']<.2 for m,r in probes)
        rows.append({'dose':dose,'eligible':count,'total':len(probes),
                     'delivered':sum(r['delivered_signal_amount']>0 for _,r in probes),
                     'peak_saturation':max(r['max_saturated_fraction'] for _,r in probes)})
decision = {'calibration_passed':False,'qualified_dose':None,'diagnostic_dose':1,
            'confirmation_cancelled':True,'rows':sorted(rows,key=lambda r:r['dose']),
            'formal_diagnostic_seeds':list(range(41601,41605)), 'materials':'Latin only',
            'rounds':8,'arms':['full','rule_scrambled','teaching_scrambled','crossed_chain','learning_off']}
assert not any(r['eligible']/r['total']>=.8 for r in rows)
with (HERE/'instrument-decision.json').open('xb') as stream:
    stream.write(encoded(decision))
db = Database(Settings.from_env().database_url)
try:
    ident = uuid4()
    notebooks.save_note(db,meta['project_id'],LOCAL_USER,ident,{
        'operation_id':str(uuid4()),'expected_revision':0,'title':'校准失败后的方案修订：仅作诊断，不作理解结论',
        'kind':'note','collection_id':meta['notebook_id'],
        'body':{'format':'markdown','text':(HERE/'amendment.md').read_text(encoding='utf-8')}})
    meta['amendment_note_id']=str(ident)
    meta['amendment_sha256']=hashlib.sha256((HERE/'amendment.md').read_bytes()).hexdigest()
    META.write_bytes(encoded(meta))
finally:
    db.close()
print(encoded(decision).decode())
