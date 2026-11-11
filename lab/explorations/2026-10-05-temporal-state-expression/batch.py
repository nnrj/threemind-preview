"""Run the registered independent stages sequentially, retaining failures."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[2]/'.work/temporal-state-20261005'


def main():
    tasks=[('raw-history','raw_transformer.py','--fields','history'),
           ('raw-activity','raw_transformer.py','--fields','activity'),
           ('raw-cross','raw_transformer.py','--fields','history','--scope','cross'),
           ('raw-shared','raw_transformer.py','--fields','history','--shared'),
           ('full-capture','full_state.py','capture'),('full-node','full_state.py','node'),
           ('full-graph','full_state.py','graph'),('events','events.py','run'),
           ('events-analysis','events.py','analyze')]
    outcomes={};folder=WORK/'stage-execution';folder.mkdir(exist_ok=True)
    for name,script,*args in tasks:
        if name in ('full-node','full-graph') and outcomes.get('full-capture')!=0:continue
        if name=='events-analysis' and outcomes.get('events')!=0:continue
        record=folder/(name+'.json')
        if record.exists():
            outcomes[name]=json.loads(record.read_bytes())['returncode'];continue
        print({'starting':name},flush=True);tick=time.time()
        # Children use the same Study guards. This orchestrator performs no
        # simulation or training while the single child is running.
        with (folder/(name+'.log')).open('x',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,str(HERE/script),*args],stdout=log,stderr=subprocess.STDOUT)
        outcomes[name]=result.returncode
        record.write_text(json.dumps({'stage':name,'returncode':result.returncode,'started_at_epoch':tick,
                                     'elapsed_seconds':time.time()-tick}),encoding='utf-8')
        print({'completed':name,'returncode':result.returncode},flush=True)
        if result.returncode:
            print((folder/(name+'.log')).read_text(encoding='utf-8')[-1800:],flush=True)
    if any(outcomes.values()):raise SystemExit(1)


if __name__=='__main__':main()
