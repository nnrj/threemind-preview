"""Rebuild a derived teaching cache from archived original rows, without Core."""
import argparse
from collections import deque
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from lab.tools.activity_controller import ActivityLayout
from lab.tools.continuous_motor import recent_window


def samples(recording,channels):
    history=deque(maxlen=32);layout=ActivityLayout(channels)
    with gzip.open(recording,'rt',encoding='utf-8') as f:
        for line in f:
            rec=json.loads(line)
            for i,row in enumerate(rec['process']):
                if rec['kind']=='teacher' and history and i>0 and (i<10 or i%2==0):
                    yield recent_window(layout,history),recent_window(layout,history,incoming=True),row['eye_action']+row['hand_action']
                history.append(row)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);p.add_argument('layout',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('never overwrite evidence/cache')
    data=list(samples(a.recording,json.loads(a.layout.read_text(encoding='utf-8'))))
    with a.output.open('xb') as f:np.savez_compressed(f,activity=np.stack([v[0] for v in data]),incoming=np.stack([v[1] for v in data]),y=np.stack([v[2] for v in data]))
    print(json.dumps({'samples':len(data),'output':str(a.output)}))


if __name__=='__main__':main()
