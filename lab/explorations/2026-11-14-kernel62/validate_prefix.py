"""Bounded engineering replay of the two frozen E12 prefix materials.

New 6.2 subjects only. A trained complete state supplies two declared probe
branches, as in the historical causal apparatus. No ordinary subject reset.
Outputs belong in ignored validation storage, never the historical data tree.
"""
import argparse
from dataclasses import replace
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / 'lab/explorations/2026-11-13-kernel61/memory_timescales'
sys.path.insert(0, str(ROOT/'src'))
from threemind_core import Stimulus
from threemind_kernels.local62 import KERNEL_ID
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


measure = module('k62_prefix_measurement', PRIOR/'measurement_timescales.py')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'xb') as f:
        f.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf8'))


def frames(root, case):
    path = root/'materials'/case['material_key']/'frames.jsonl'
    lines = [json.loads(x) for x in path.read_bytes().splitlines()]
    assert lines.pop(0)['run_id'] == case['old_id']
    for r in lines:
        assert r['status'] == 'delivered' and not r['labels']
        assert r['delivered_time_us'] == r['scheduled_time_us'] == r['stimulus']['time_us']
    lines.sort(key=lambda r:(int(r['source_policy']['resolved_at_us']), r['core_event_id']))
    return lines, hashlib.sha256(path.read_bytes()).hexdigest()


def execute(engine, case, inputs):
    """Preserve enqueue timing, event order, and the complete 15-second process."""
    index = 0; points = []; probe = case.get('probe_start_us')
    next_point = probe; started = False
    def observe():
        before = engine.capture_state().digest
        nodes = [n for n in engine.observation_nodes() if n['channel'] in measure.TOKENS.values()]
        assert before == engine.capture_state().digest
        return {'time_us': engine.time_us, 'nodes': nodes}
    while True:
        if probe == engine.time_us and not started:
            points.append(observe())
        while index < len(inputs) and int(inputs[index]['source_policy']['resolved_at_us']) == engine.time_us:
            engine.inject(Stimulus.from_dict(inputs[index]['stimulus']));index += 1
        engine.advance_to(engine.time_us)
        if probe == engine.time_us and not started:
            started = True; points.append(observe());next_point += 10000
        elif started and engine.time_us == next_point:
            points.append(observe()); next_point += 10000
        if engine.time_us == case['end_us']:
            break
        targets = [case['end_us'], engine.time_us+100000]
        if index < len(inputs):
            targets.append(int(inputs[index]['source_policy']['resolved_at_us']))
        if next_point is not None:
            targets.append(next_point)
        target = min(targets);assert target > engine.time_us
        engine.advance_to(target)
        assert engine.life != 'dead'
    assert index == len(inputs)
    return points


def main():
    p=argparse.ArgumentParser();p.add_argument('--materials',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists();a.out.mkdir(parents=True)
    allcases=json.loads((a.materials/'cases.json').read_bytes())
    cases={c['material_key']:c for c in allcases if c['variant']=='v5.1-legacy-edges-immediate'}
    contract={'kernel':KERNEL_ID,'blocks':2,'branching':'two declared prefix probes from intact taught parent',
              'conditions': ['adaptive-half-life','stability'],'novelty':['arrival-window','immediate'],
              'criterion':'both signed activation peak differences > 1e-6 in each block',
              'readout':'activation, inhibition, direct, associative; 15 s at 10 ms; passive',
              'default_promotion':'immediate is promoted only if the registered functional comparison succeeds',
              'sources':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                  [Path(__file__),PRIOR/'measurement_timescales.py',ROOT/'src/threemind_kernels/local62.py',ROOT/'src/threemind_kernels/local62_config.py']}}
    (a.out/'contract.json').write_text(json.dumps(contract,indent=2),encoding='utf8')
    results=[];began=time.monotonic()
    for backend in ('reference','native'):
        for mode in contract['conditions']:
            for novelty in contract['novelty']:
                for block in (0,1):
                    c=cases[f'short/train-{block}'];rows,sha=frames(a.materials,c)
                    config={'seed':9291000,**c['initial_config'],'consolidation_mode':mode,'novelty_mode':novelty}
                    engine=resolve_kernel(KERNEL_ID).create(config,backend=backend)
                    name=f'{backend}/{mode}/{novelty}/{block}';folder=a.out/name
                    t=time.monotonic();execute(engine,c,rows);parent=engine.capture_state()
                    save(folder/'parent.json.gz',parent.to_dict())
                    assert ArtifactCodec.decode(ArtifactCodec.encode(parent)).digest == parent.digest
                    margins=[]
                    for cue in ('AB','DB'):
                        c=cases[f'history/s{block}/101/d1/{cue}'];rows,sha=frames(a.materials,c)
                        probe=resolve_kernel(KERNEL_ID).create(state=parent,backend=backend)
                        probe.reconfigure(replace(probe.config,**c['patch']))
                        points=execute(probe,c,rows);q=measure.process(c,points)
                        q.update(backend=backend,retention=mode,novelty=novelty,block=block,
                                 parent_sha256=parent.digest,input_sha256=sha,final_sha256=probe.capture_state().digest)
                        margins.append(q['signed_peak']);results.append(q)
                        save(folder/f'{cue}-process.json.gz',points)
                        save(folder/f'{cue}-final.json.gz',probe.capture_state().to_dict())
                    print(json.dumps({'condition':name,'margins':margins,'passed':all(x>measure.EPS for x in margins),
                                      'wall_seconds':time.monotonic()-t}),flush=True)
    # Independent implementations must agree on every scored trajectory summary.
    for x,y in zip(results[:16],results[16:]):
        assert (x['retention'],x['novelty'],x['block'],x['cue']) == (y['retention'],y['novelty'],y['block'],y['cue'])
        assert abs(x['signed_peak']-y['signed_peak']) < 1e-12
    (a.out/'results.json').write_text(json.dumps({'results':results,'wall_seconds':time.monotonic()-began},indent=2),encoding='utf8')


if __name__=='__main__':main()
