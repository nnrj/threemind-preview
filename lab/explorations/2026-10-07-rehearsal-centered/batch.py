"""Sequential bounded study commands, one simulation worker, per-case logs."""
import argparse
from pathlib import Path
import subprocess
import sys
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=ROOT/'.work/rehearsal-centered-20261007'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('phase',choices=('motor-rest','recognition-primary','recognition-controls','recognition-corrected','calibration-transfer'))
a=p.parse_args()
if a.phase=='motor-rest':
    commands=[('experiment.py','evaluate','--policy','recent')]
    for policy in ('reservoir','representative'):
        commands.extend([('experiment.py','rehearsal','--policy',policy),('experiment.py','evaluate','--policy',policy)])
elif a.phase=='recognition-primary':commands=[('recognition.py','train'),('recognition.py','evaluate')]
elif a.phase=='recognition-controls':
    commands=[('recognition.py','evaluate','--mode',mode) for mode in ('silence','rescue','blank-core')]
elif a.phase=='calibration-transfer':
    commands=[('recognition.py','evaluate','--corrected'),
              ('recognition.py','evaluate','--variant-test'),
              ('recognition.py','calibrate'),
              ('recognition.py','evaluate','--source-case','centered-calibration')]
else:
    commands=[('recognition.py','correct')]+[('recognition.py','evaluate','--corrected','--mode',mode) for mode in ('normal','silence','rescue','blank-core')]
for index,cmd in enumerate(commands):
    log=WORK/f'{a.phase}-{index}.log'
    if log.exists():raise RuntimeError('preserve prior log; resume individual CLI commands')
    print(json.dumps({'starting':cmd,'log':str(log)}),flush=True)
    with log.open('x',encoding='utf-8') as f:
        result=subprocess.run([sys.executable,'-u',str(HERE/cmd[0]),*cmd[1:]],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    print(json.dumps({'finished':cmd,'returncode':result.returncode}),flush=True)
    if result.returncode:raise SystemExit(result.returncode)
