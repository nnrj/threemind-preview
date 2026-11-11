"""Hard wall/RSS limit for this study's own model subprocess only."""
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/host-background-pair-20260910'
seed=int(sys.argv[1])
assert seed in (41701,41702)
assert json.loads((HERE/'quota-monitor.json').read_bytes())['used_percent']<81
previous=sum(json.loads(p.read_bytes())['elapsed_s'] for p in WORK.glob('seed-*-results.json'))
assert previous<300
start=time.monotonic();peak=0;reason=None
with (WORK/f'seed-{seed}.log').open('xb') as stream:
    child=subprocess.Popen([sys.executable,str(HERE/'run.py'),'seed',str(seed)],cwd=ROOT,
                           stdout=stream,stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    process=psutil.Process(child.pid)
    while child.poll() is None:
        try:peak=max(peak,process.memory_info().rss)
        except psutil.NoSuchProcess:break
        if peak>1024**3 or time.monotonic()-start>min(150,300-previous):
            reason='hard resource deadline';child.kill();break
        time.sleep(.1)
    code=child.wait(timeout=10)
(WORK/f'supervision-{seed}.json').write_text(json.dumps(dict(seed=seed,elapsed_s=time.monotonic()-start,
    peak_rss=peak,exit_code=code,stop_reason=reason),indent=2),encoding='utf-8')
print((WORK/f'seed-{seed}.log').read_text(encoding='utf-8'))
raise SystemExit(code or (1 if reason else 0))
