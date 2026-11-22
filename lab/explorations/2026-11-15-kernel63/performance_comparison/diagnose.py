"""Isolated factorial diagnosis; no kernel file or default is modified."""
import argparse
import cProfile
import gc
import gzip
import json
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
import time

from bench import CASES, HERE, ROOT, WORK, inputs, numerical, resources, sha

DEST = WORK/'diagnostic'
CONDITIONS = ((False,False),(True,False),(False,True),(True,True))


def worker(q):
    from threemind_kernels.local63_config import Local63Config
    from threemind_kernels.registry import resolve_kernel
    d = resolve_kernel('threemind.continuous-memory/6.3')
    c = Local63Config(subthreshold_expiry_enabled=q['expiry'],retain_nodes=q['retain'])
    course, until = inputs(q['case'])
    backend = CASES[q['case']][0]
    samples=[]
    e=None
    for _ in range(q['repeats']):
        e=None;gc.collect();e=d.create(c,backend=backend)
        for s in course:e.inject(s)
        start=time.perf_counter();e.advance_to(until);samples.append(time.perf_counter()-start)
    image=e.capture_state();state=image.to_dict()
    filename=f"{q['case']}-{q['trial']}-{int(q['expiry'])}{int(q['retain'])}"
    (DEST/(filename+'.json.gz')).write_bytes(gzip.compress(image.payload,mtime=0))
    result=q|{'advance_seconds':statistics.mean(samples),'raw_timings':samples,
              'nodes':len(state['nodes']),'edges':len(state['edges']),'audit':state['audit'],
              'sequence':state['sequence'],'life':state['life'],'time_us':state['time_us'],
              'state_sha256':image.digest,'numerical_sha256':numerical(state),
              'state_file':filename+'.json.gz'}
    if backend=='reference' and q['trial']==4:
        e=None;gc.collect();e=d.create(c,backend=backend)
        for s in course:e.inject(s)
        profiler=cProfile.Profile();profiler.enable();e.advance_to(until);profiler.disable()
        assert e.capture_state().digest==image.digest
        profiler.dump_stats(str(DEST/(filename+'.pstats')))
        stats=pstats.Stats(profiler)
        result['profile']=[{'file':k[0],'line':k[1],'function':k[2],'primitive_calls':v[0],
                            'calls':v[1],'self_seconds':v[2],'cumulative_seconds':v[3]}
                           for k,v in stats.stats.items()]
    return result


def run():
    for path,expected in json.loads((WORK/'manifest.json').read_text('utf8')).items():
        assert sha((ROOT/path).read_bytes())==expected,path
    DEST.mkdir(exist_ok=False)
    manifest={p.name:sha(p.read_bytes()) for p in (Path(__file__),HERE/'diagnostic.zh.md',HERE/'diagnostic.en.md')}
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    repeats=json.loads((WORK/'repeat-counts.json').read_text('utf8'))
    results=[]
    for case in ('native-weak128','python-weak32'):
        for trial in range(5):
            order=CONDITIONS if trial==0 else CONDITIONS[(trial-1)%4:]+CONDITIONS[:(trial-1)%4]
            for expiry,retain in order:
                resources()
                q={'case':case,'trial':trial,'expiry':expiry,'retain':retain,'repeats':repeats[case]}
                (DEST/'in-flight.json').write_text(json.dumps(q),'utf8')
                p=subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--worker',json.dumps(q)],
                                   cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
                start=time.monotonic();pressure=None
                while True:
                    try:out,err=p.communicate(timeout=1);break
                    except subprocess.TimeoutExpired:
                        try:resources()
                        except Exception as exc:pressure=str(exc)
                        if time.monotonic()-start>180:
                            p.kill();p.communicate();raise TimeoutError(q)
                if p.returncode:
                    (DEST/'worker-error.txt').write_text(err,'utf8');raise RuntimeError(err)
                row=json.loads(out);results.append(row)
                with (DEST/'rows.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
                (DEST/'in-flight.json').unlink()
                if pressure:raise RuntimeError('Complete-boundary resource stop: '+pressure)
            print(json.dumps({'case':case,'trial':trial,'seconds':[
                {'expiry':r['expiry'],'retain':r['retain'],'time':r['advance_seconds']} for r in results[-4:]]}),flush=True)
    summaries={}
    for case in ('native-weak128','python-weak32'):
        summaries[case]={}
        for expiry,retain in CONDITIONS:
            sample=[r for r in results if r['case']==case and r['trial']>0 and r['expiry']==expiry and r['retain']==retain]
            assert len(sample)==4 and len({r['numerical_sha256'] for r in sample})==1
            summaries[case][f'{int(expiry)}{int(retain)}']={'expiry':expiry,'retain':retain,
                'median_seconds':statistics.median(r['advance_seconds'] for r in sample),
                'nodes':sample[0]['nodes'],'audit':sample[0]['audit']}
    for row in results:
        assert sha(gzip.decompress((DEST/row['state_file']).read_bytes()))==row['state_sha256']
    (HERE/'diagnostic-summary.json').write_text(json.dumps({'cases':summaries,'verified_states':len(results),
        'rows_sha256':sha((DEST/'rows.jsonl').read_bytes())},indent=2)+'\n','utf8')
    print(json.dumps(summaries),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');args=parser.parse_args()
    if args.worker:print(json.dumps(worker(json.loads(args.worker))))
    else:run()
