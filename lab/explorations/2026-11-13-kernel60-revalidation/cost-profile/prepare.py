"""Create a disposable instrumentation tree; never edit production crates."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEST = ROOT / '.work/kernel60-cost/checkout'

PROFILE = r'''
use std::cell::RefCell;
use std::time::Instant;
const N: usize = 64;
struct Data { level:u8, stack:Vec<(usize,u128)>, calls:[u64;N], total:[u128;N], own:[u128;N] }
impl Data { fn new(level:u8)->Self { Self{level,stack:Vec::new(),calls:[0;N],total:[0;N],own:[0;N]} } }
thread_local! { static DATA:RefCell<Data> = RefCell::new(Data::new(0)); }
pub struct Scope { start:Option<Instant>, id:usize }
pub fn enter(id:usize, level:u8)->Scope {
    let enabled=DATA.with(|d| d.borrow().level>=level);
    if enabled {
        DATA.with(|d|d.borrow_mut().stack.push((id,0)));
        Scope{start:Some(Instant::now()),id}
    } else { Scope{start:None,id} }
}
impl Drop for Scope {
    fn drop(&mut self) {
        if let Some(start)=self.start {
            let ns=start.elapsed().as_nanos();
            DATA.with(|d|{let mut d=d.borrow_mut();let (id,child)=d.stack.pop().unwrap();assert_eq!(id,self.id);
                d.calls[id]+=1;d.total[id]+=ns;d.own[id]+=ns.saturating_sub(child);
                if let Some(parent)=d.stack.last_mut(){parent.1+=ns;}
            });
        }
    }
}
pub fn count(id:usize) {DATA.with(|d|{let mut d=d.borrow_mut();if d.level>0 {d.calls[id]+=1;}});}
pub fn reset(level:u8) {DATA.with(|d|{assert!(d.borrow().stack.is_empty());*d.borrow_mut()=Data::new(level);});}
pub fn report()->String {DATA.with(|d|{let d=d.borrow();assert!(d.stack.is_empty());
    let rows:Vec<_>=(0..N).filter(|&i|d.calls[i]>0).map(|i|serde_json::json!({"id":i,"calls":d.calls[i],"inclusive_ns":d.total[i],"exclusive_ns":d.own[i]})).collect();
    serde_json::json!({"level":d.level,"rows":rows}).to_string()})}
'''

LABELS = {0:'advance',1:'structure_check',2:'expiry_other',3:'settle_node',4:'node_value',
          5:'settle_edge',6:'edge_value',7:'decay_value',8:'discrete_edge_state',9:'node_timers',
          10:'structure_timer',11:'timer',12:'pulse',13:'emit',14:'receive',15:'receive_batch',
          16:'connected',17:'remove_edge',18:'delete_node',19:'log_remaining',20:'settings_choice',
          21:'settings_num',22:'settings_uint',40:'emission_calls',41:'zero_source_offer',
          42:'connection_attempts',43:'zero_transmission',44:'positive_transmission',45:'negative_transmission'}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def insert_scope(text, name, expr):
    match = re.search(r'    (?:pub )?fn '+name+r'\([^\{]+\{', text)
    assert match, name
    return text[:match.end()] + '\n        let _cost_scope = crate::cost_profile::enter('+expr+');' + text[match.end():]

def prepare():
    assert not DEST.exists(), 'Do not overwrite an instrument tree.'
    files = subprocess.check_output(['git','ls-files','crates','Cargo.toml','Cargo.lock'],cwd=ROOT,text=True).splitlines()
    manifest = {}
    for rel in files:
        source, target = ROOT/rel, DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(source.read_bytes());manifest[rel]=sha(source)
    (DEST/'crates/threemind-core/src/cost_profile.rs').write_text(PROFILE,encoding='utf-8')
    p=DEST/'crates/threemind-core/src/lib.rs'
    p.write_text(p.read_text('utf-8')+'\npub mod cost_profile;\n',encoding='utf-8')
    names={0:'advance_impl',3:'settle_node',4:'node_value',5:'settle_edge',6:'edge_value',8:'discrete_edge_state',
           9:'node_timers',10:'structure_timer',11:'timer',12:'pulse',13:'emit',14:'receive',15:'receive_batch',
           16:'connected',17:'remove_edge',18:'delete_node',20:'choice',21:'num',22:'uint'}
    for file in ('local60_transitions.rs','local_shared.rs'):
        p=DEST/'crates/threemind-core/src'/file
        text=p.read_text('utf-8')
        for index,name in names.items():
            if name=='structure_timer' and file=='local_shared.rs':continue
            level=1 if index in (0,13,14) else 2
            text=insert_scope(text,name,f'{index}, {level}')
        text=insert_scope(text,'expiry','if kind==6 {1} else {2}, 1')
        if file=='local60_transitions.rs':
            old='        let keys: Vec<_> = self.outgoing_keys(id)'
            assert text.count(old)==1
            text=text.replace(old,'        crate::cost_profile::count(40);\n        if positive <= 0.0 && negative <= 0.0 {crate::cost_profile::count(41);}\n'+old)
            old='            let [pos, neg] = transmitted;'
            text=text.replace(old,old+'\n            crate::cost_profile::count(42);\n            if pos==0.0 && neg==0.0 {crate::cost_profile::count(43);}\n            if pos>0.0 {crate::cost_profile::count(44);}\n            if neg>0.0 {crate::cost_profile::count(45);}')
        p.write_text(text,encoding='utf-8')
    p=DEST/'crates/threemind-core/src/local60.rs'
    text=insert_scope(p.read_text('utf-8'),'decay_value','7, 2')
    text=insert_scope(text,'log_remaining','19, 2')
    p.write_text(text,encoding='utf-8')
    p=DEST/'crates/threemind-native/src/lib.rs'
    text=p.read_text('utf-8')
    text=text.replace('    m.add_class::<NativeEngine>()?;', '    m.add_function(wrap_pyfunction!(cost_profile_reset, m)?)?;\n    m.add_function(wrap_pyfunction!(cost_profile_report, m)?)?;\n    m.add_class::<NativeEngine>()?;')
    text+='\n#[pyfunction]\nfn cost_profile_reset(level:u8){threemind_core::cost_profile::reset(level);}\n#[pyfunction]\nfn cost_profile_report()->String{threemind_core::cost_profile::report()}\n'
    p.write_text(text,encoding='utf-8')
    result={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'source_files':manifest,'modified_files':{p.relative_to(DEST).as_posix():sha(p) for p in DEST.rglob('*')
                if p.is_file() and (p.relative_to(DEST).as_posix() not in manifest or sha(p)!=manifest[p.relative_to(DEST).as_posix()])},
            'labels':LABELS,'protocol_sha256':sha(HERE/'protocol.md'),'prepare_sha256':sha(Path(__file__))}
    out=DEST.parent/'instrumentation.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'checkout':str(DEST),'modified':list(result['modified_files'])}))

if __name__=='__main__':prepare()
