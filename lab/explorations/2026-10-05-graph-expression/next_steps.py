"""One worker, gated instruments and attribution; no automatic unbounded search."""
import subprocess
from common import *


def run(script,*arguments):
    subprocess.run([sys.executable,str(HERE/script),*map(str,arguments)],cwd=ROOT,check=True)


if __name__=='__main__':
    first=read_json(WORK/'models/multi-s223-local.json')
    if first['fit_correct']<30:raise SystemExit('Local tool underfit: stop expansion, preserve evidence.')
    run('teaching.py','--owner',279)
    run('multiview.py','--owner',279,'--mode','local')
    run('attribution.py','--owner',223)
    second=read_json(WORK/'models/multi-s279-local.json')
    if second['fit_correct']>=30:run('attribution.py','--owner',279)
    run('multiview.py','--owner',223,'--mode','sensory')
    run('multiview.py','--owner',223,'--mode','random')
    run('multiview.py','--owner',223,'--mode','local','--late','--continue-from',WORK/'models/multi-s223-local.safetensors')
