"""Equal-size engineering graphs, separate from registered scientific learners."""
import argparse
import json
from pathlib import Path
import statistics
import time

import psutil
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_kernels.weight_decay import KERNEL_ID, RULES, configuration
from threemind_runtime import ArtifactCodec


def trial(backend, rule, pairs, passive):
    e=resolve_kernel(KERNEL_ID).create(configuration(908774,rule,quiescence_death_us=10**12),backend=backend)
    start=time.perf_counter()
    for i in range(pairs): e.inject(Stimulus(0,((2*i,.8),(2*i+1,.8))))
    e.advance_to(0)
    if passive: e.intervene(nodes=list(range(2*pairs)),action='silence')
    setup=time.perf_counter()-start
    start=time.perf_counter();e.advance_to(1_000_000);advance=time.perf_counter()-start
    start=time.perf_counter();state=e.capture_state();blob=ArtifactCodec.encode(state,'tmind');save=time.perf_counter()-start
    assert ArtifactCodec.decode(blob).digest==state.digest==e.capture_state().digest
    d=state.to_dict()
    return dict(setup_seconds=setup,advance_seconds=advance,save_seconds=save,nodes=len(d['nodes']),directed_edges=len(d['edges']),json_bytes=len(state.payload),tmind_bytes=len(blob),audit=d['audit'],transport=d['transport'],process_private_bytes_after=psutil.Process().memory_info().private)


def run(path):
    rows=[]
    for backend in ('reference','native'):
        for pairs in ((32,512) if backend=='reference' else (32,512,4096)):
            for passive in (True,False):
                results={r:[] for r in RULES}
                for rep in range(3):
                    # Rotate order across repetitions; same declared graph per trial.
                    order=RULES[rep:]+RULES[:rep]
                    for rule in order: results[rule].append(trial(backend,rule,pairs,passive))
                for rule,repeats in results.items():
                    row=dict(backend=backend,rule=rule,initial_nodes=2*pairs,initial_directed_edges=2*pairs,silenced=passive,internal_seconds=1,repeats=repeats,median_advance_seconds=statistics.median(r['advance_seconds'] for r in repeats),median_save_seconds=statistics.median(r['save_seconds'] for r in repeats))
                    rows.append(row)
                    print(json.dumps({k:v for k,v in row.items() if k!='repeats'}),flush=True)
    with path.open('x',encoding='utf-8') as f: json.dump(dict(schema='threemind.r48-runtime-benchmark/1',engineering_only=True,rows=rows,topology='disjoint reciprocal pairs',scope='Three repeats; setup, advancement and serialization separated. Private bytes are after each trial, not per-trial peak. Actual event counters retained; no trained adapters or research individuals.'),f,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
