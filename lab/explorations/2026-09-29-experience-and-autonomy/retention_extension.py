"""Frozen causal follow-up to the observed 30-second retention result."""
import argparse
import hashlib
import json
from common import HERE,WORK,Study,new_json,load_case
from experiment import SEEDS,name,symbols,probe
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER

PROTOCOLS=('none','single_high','massed_ordinary','spaced_ordinary','spaced_no_consolidation')
CONDITIONS=('normal','task_edges','matched_edges','off')

def register(s):
    path=WORK/'retention-extension-registration.json'
    if path.exists():raise RuntimeError('extension already registered')
    hashes={}
    for file in ('retention_extension.py','retention-extension.zh.md','retention-extension.en.md'):
        raw=(HERE/file).read_bytes();target=WORK/'frozen-retention-extension'/file
        target.parent.mkdir(exist_ok=True);target.write_bytes(raw);hashes[file]=hashlib.sha256(raw).hexdigest()
    for lang in ('zh','en'):
        notebooks.save_note(s.db,s.project,LOCAL_USER,s.identity('retention-extension:'+lang),{
            'operation_id':s.identity('retention-extension-write:'+lang),'expected_revision':0,'kind':'note',
            'collection_id':s.meta['notebook_id'],'title':'30 秒保持定位 / Retention localization '+lang,
            'body':{'format':'markdown','text':(HERE/f'retention-extension.{lang}.md').read_text(encoding='utf-8')}})
    new_json(path,{'additional_instances':80,'base_instances':722,'files':hashes,'protocols':PROTOCOLS,'conditions':CONDITIONS})

def run(s):
    assert (WORK/'retention-extension-registration.json').exists()
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            parent=load_case(s,f'memory/s{seed}/{protocol}/age30')
            for condition in CONDITIONS:
                for cue in ('A','none'):
                    key=f'retention-extension/s{seed}/{protocol}/{condition}/{cue}'
                    probe(s,key,parent,[] if cue=='none' else [symbols(seed)['A']],born=True,condition=condition,
                          extra={'family':'retention-extension','protocol':protocol,'age_s':30,'cue_name':cue})
            print(json.dumps({'stage':'retention-extension','seed':seed,'protocol':protocol,'done':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','run'))
    cmd=p.parse_args().command;s=Study()
    try:register(s) if cmd=='register' else run(s)
    except Exception as exc:
        if s.active_case:s.active_case.finish({'budget_stop':True,'error':str(exc)})
        raise
    finally:s.db.close()
