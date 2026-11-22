"""Create an isolated, reproducible no-independent-pool performance reference."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4]
DEST=ROOT/'.work/kernel63-bypass/shared-only-source'
BASE='b7adf1b5'

def replace_once(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)

def prepare():
    assert not DEST.exists()
    DEST.mkdir()
    for name in ('Cargo.toml','Cargo.lock'):
        shutil.copyfile(ROOT/name,DEST/name)
    shutil.copytree(ROOT/'crates',DEST/'crates',ignore=shutil.ignore_patterns('target','__pycache__','*.pyd','*.whl'))
    directory=DEST/'crates/threemind-core/src'
    for name in ('local63_transitions.rs','local63-defaults.json'):
        raw=subprocess.check_output(['git','show',f'{BASE}:crates/threemind-core/src/{name}'],cwd=ROOT)
        (directory/name).write_bytes(raw)
    p=directory/'local63_transitions.rs';text=p.read_text('utf8')
    text=replace_once(text,'    "inhibition_distribution",\n','    "inhibition_distribution",\n    "inhibition_bypasses_resources",\n')
    text=replace_once(text,'    inhibition_distribution: String,','    inhibition_distribution: String,\n    inhibition_bypasses_resources: bool,')
    text=replace_once(text,'"resource_precheck_enabled", "subthreshold_expiry_enabled"]',
        '"resource_precheck_enabled", "subthreshold_expiry_enabled", "inhibition_bypasses_resources"]')
    text=replace_once(text,'            if o.stp_enabled {\n                let mut st = e.short_term',
        '            if o.stp_enabled && (!self.s.f.inhibition_bypasses_resources || p_offer > 0.0) {\n                let mut st = e.short_term')
    text=replace_once(text,'* signal * fraction * distance;',
        '* signal * (if i == 1 && self.s.f.inhibition_bypasses_resources { 1.0 } else { fraction }) * distance;')
    p.write_text(text,encoding='utf8')
    p=directory/'local63-defaults.json';config=json.loads(p.read_text('utf8'))
    config['inhibition_bypasses_resources']=True
    assert 'separate_inhibition_resources' not in config
    p.write_text(json.dumps(config,indent=2)+'\n',encoding='utf8')
    manifest={'base_commit':subprocess.check_output(['git','rev-parse',BASE],cwd=ROOT,text=True).strip(),
        'purpose':'isolated no-independent-pool reference; new instances only',
        'files':{p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in DEST.rglob('*') if p.is_file()}}
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'prepared':str(DEST),'files':len(manifest['files'])}))

if __name__=='__main__':prepare()
