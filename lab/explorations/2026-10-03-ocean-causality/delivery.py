"""Small delivery receipts only; never reread the archived raw evidence."""
import json
from experiment import WORK,HERE,study
from lab.tools.ocean_cli import read_json,write_json
from threemind_lab import research_documents

s=study()
try:
    p=read_json(WORK/'publication.json')
    documents=[]
    for key,item in p.items():
        if key.startswith(('report:','record:')):
            row=research_documents.get(s.db,s.project,item['id'])
            documents.append({'key':key,'id':str(row['id']),'revision':row['revision'],'title':row['title']})
    with s.db.tx(s.project) as tx:
        artifact=tx.execute('SELECT id,bytes,sha256 FROM artifacts WHERE id=%s',(p['archive']['artifact_id'],)).fetchone()
        db_size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
    local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file())
    total=0.
    for base in ('cases','calibration','closed-loop','evaluations'):
        total+=sum(read_json(f)['wall_seconds'] for f in (WORK/base).glob('**/result.json'))
    total+=sum(read_json(f)['wall_seconds'] for f in (WORK/'probes').glob('*/summary.json'))
    total+=sum(read_json(f)['wall_seconds_upper_bound'] for f in (WORK/'probes').glob('*/failure.json'))
    value={'project_id':s.project,'documents':documents,
        'artifact':{k:str(v) if k=='id' else v for k,v in artifact.items()},
        'simulation_wall_seconds_upper_bound':total,'local_evidence_bytes_including_zip':local,
        'database_growth_bytes':max(0,db_size-s.meta['database_bytes_before']),
        'account_used_percent':{'start':10,'last_observed':12},
        'tests':{'focused':9,'viewer_widths':[1440,390],'history_chapters':55,'editions':4},
        'verification':'small report revisions and artifact metadata; no raw archive readback',
        'old_data_modified':False,'core_dynamics_modified':False,'core_actions_restricted':False,
        'human_viewers':['views/g0-core.html','views/g1-core.html','views/g1-sham.html','views/g1-region.html']}
    write_json(WORK/'delivery.json',value);write_json(HERE/'delivery.json',value)
    print(json.dumps(value,ensure_ascii=False,indent=2))
finally:s.db.close()
