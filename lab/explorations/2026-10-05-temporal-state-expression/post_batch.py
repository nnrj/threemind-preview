"""Bounded registered follow-ups after the original sequential batch."""
import subprocess
from experiment import *


def run(name,args):
    folder=WORK/'stage-execution';record=folder/(name+'.json')
    if record.exists():
        if read_json(record)['returncode']!=0:raise RuntimeError('retained failed stage: '+name)
        return
    print({'starting':name},flush=True);tick=time.time()
    with (folder/(name+'.log')).open('x',encoding='utf-8') as f:
        result=subprocess.run([sys.executable,str(HERE/args[0]),*args[1:]],stdout=f,stderr=subprocess.STDOUT)
    new_json(record,{'stage':name,'returncode':result.returncode,'started_at_epoch':tick,'elapsed_seconds':time.time()-tick})
    print({'completed':name,'returncode':result.returncode},flush=True)
    if result.returncode:
        print((folder/(name+'.log')).read_text(encoding='utf-8')[-1800:],flush=True)
        raise RuntimeError('stage failed, preserved evidence')


def main():
    s=study()
    try:s.allow_extension()
    finally:s.db.close()
    run('decoder-6000', ['raw_transformer.py','--fields','history','--steps','6000','--owners','223'])
    fit=read_json(WORK/'raw-models/223-words-history-all-steps6000.json')
    if fit['fit_correct']>=17:
        run('decoder-6000-replication',['raw_transformer.py','--fields','history','--steps','6000','--owners','251','279'])
    run('trajectory101',['trajectory.py'])
    run('timing-followup',['timing_followup.py'])


if __name__=='__main__':main()
