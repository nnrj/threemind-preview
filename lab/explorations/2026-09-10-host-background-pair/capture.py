"""Record real host counters once; never synthesize or loop a recording."""
import json
import shutil
import time
from datetime import datetime,UTC
from pathlib import Path

import psutil
from threemind_runtime.telemetry_probe import SystemTelemetryProbe

HERE=Path(__file__).resolve().parent


def capture():
    target=HERE/'host-recording.jsonl'
    probe=SystemTelemetryProbe()
    probe.reset_rate_baselines({'host'})
    start=time.monotonic()
    with target.open('x',encoding='utf-8') as stream:
        for index in range(1,416):
            while time.monotonic()<start+index:
                time.sleep(min(.2,start+index-time.monotonic()))
            now=time.monotonic()
            assert now-start<435, 'capture exceeded its 435 second deadline'
            assert psutil.virtual_memory().available>3*1024**3
            assert all(shutil.disk_usage(d).free>15*1024**3 for d in ('D:/','E:/'))
            host,_=probe.collect(now,{'host'})
            row=dict(index=index,captured_at=datetime.now(UTC).isoformat(),monotonic_s=now,
                     elapsed_us=round((now-start)*1e6),backend=probe.backend,
                     measurements={k:v.to_dict() for k,v in host.items()})
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
            if index%60==0:print(f'Recorded {index}/415 seconds of real host measurements',flush=True)
    (HERE/'capture-complete.json').write_text(json.dumps(dict(samples=415,duration_s=time.monotonic()-start,
        first_delivery_rule='capture elapsed time plus original 1 second feedback delay',scope='host only'),indent=2),encoding='utf-8')
    print('Host recording complete; no model was run during capture.',flush=True)


if __name__=='__main__':capture()
