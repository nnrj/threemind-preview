"""Small, declared engineering cost comparison; no model files are restored."""
import gc
import json
from pathlib import Path
import statistics
import time
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec

ROWS=[]
for repeat in range(5):
    order=('6.1','6.2','stability') if repeat%2==0 else ('stability','6.2','6.1')
    for label in order:
        gc.collect()
        version='6.2' if label=='stability' else label
        opts={'novelty_mode':'arrival-window','quiescence_death_us':10**12}
        if label=='stability':opts|={'novelty_mode':'immediate','consolidation_mode':'stability'}
        e=resolve_kernel('threemind.continuous-memory/'+version).create(opts,backend='native')
        for i in range(64):
            e.inject(Stimulus(i*100000,((i,.5),((i+1)%64,.5))))
        begin=time.perf_counter();e.advance_to(10000000);teaching=time.perf_counter()-begin
        begin=time.perf_counter();e.advance_to(300000000);idle=time.perf_counter()-begin
        state=e.capture_state();begin=time.perf_counter();raw=ArtifactCodec.encode(state);save=time.perf_counter()-begin
        assert ArtifactCodec.decode(raw).digest==state.digest
        d=state.to_dict();ROWS.append({'repeat':repeat,'condition':label,'teaching_s':teaching,'idle_s':idle,
            'encode_s':save,'artifact_bytes':len(raw),'nodes':len(d['nodes']),'edges':len(d['edges']),
            'expiry_checks':d['audit']['expiry_checks'],'scan_visits':d['audit']['scan_visits']})
out={'rows':ROWS,'note':'6.1 and 6.2 use the same window configuration. Stability is a distinct optional dynamic rule.'}
out['median']={v:{k:statistics.median(r[k] for r in ROWS if r['condition']==v) for k in
    ('teaching_s','idle_s','encode_s','artifact_bytes','nodes','edges','expiry_checks','scan_visits')} for v in ('6.1','6.2','stability')}
p=Path('.work/kernel62-benchmark.json');assert not p.exists();p.write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out['median']),flush=True)
