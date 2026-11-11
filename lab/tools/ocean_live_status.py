"""Incrementally follow recorded gzip trajectories without touching a world.

Only complete JSON lines become provisional status. No repeated full-file scans,
no world queries, no extra stimuli, and no invented interpolation between samples.
The final result remains the authoritative source for completed-case outcomes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import zlib


class Tail:
    def __init__(self,path):
        self.path=path;self.offset=0;self.decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        self.pending=b'';self.latest=None

    def update(self):
        if not self.path.exists():return
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            while chunk:=stream.read(64*1024):
                self.offset+=len(chunk);self.pending+=self.decoder.decompress(chunk)
                *lines,self.pending=self.pending.split(b'\n')
                for line in lines:
                    row=json.loads(line)
                    self.latest={k:row[k] for k in ('time_us','groups','nutrient_count')}


def follow(root,keys,output,seconds):
    if output.resolve().is_relative_to((root/'cases').resolve()):
        raise ValueError('live status must not overwrite case evidence')
    readers={key:Tail(root/'cases'/key/'trajectory.jsonl.gz') for key in keys}
    deadline=time.monotonic()+seconds;previous=None
    while time.monotonic()<deadline:
        state={};finished=True
        for key,reader in readers.items():
            reader.update();result=root/'cases'/key/'result.json'
            if result.exists():
                row=json.loads(result.read_bytes())
                state[key]={k:row[k] for k in ('time_us','groups','nutrient_count','status')}
            else:
                finished=False
                if reader.latest:state[key]=reader.latest|{'status':'provisional-recorded-frame'}
        payload=json.dumps(state,ensure_ascii=False,sort_keys=True)
        if payload!=previous:
            temp=output.with_suffix('.tmp');temp.write_text(payload,encoding='utf-8');temp.replace(output);previous=payload
        if finished:return
        time.sleep(5)
    raise TimeoutError('read-only observation window ended; simulations unaffected')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True);p.add_argument('--seconds',type=float,default=21600)
    a=p.parse_args();follow(a.root,a.cases,a.output,a.seconds)
