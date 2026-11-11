"""Detached E68 execution followed by read-only audits and curve-video exports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from threemind_lab.config import load_env
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json,file_lock


def main():
    load_env();work=ResearchStorage().writable_root()/'experiments'/HERE.name
    def status(phase,**extra):
        value=dict(phase=phase,pid=os.getpid(),updated_epoch=time.time(),**extra)
        atomic_json(work/'pipeline-status.json',value);print(json.dumps(value),flush=True)
    with file_lock(work/'pipeline.lock'):
        if (work/'STOP').exists():raise RuntimeError('STOP requires human decision; not cleared automatically')
        try:
            commands=[]
            if not (work/'computation-complete.json').exists():commands.append(('experiment.py',['run']))
            if not (work/'analysis/verified-results.json').exists():commands.append(('analyze.py',[]))
            commands += [('replay.py',[]),('publish.py',['originals'])]
            for script,args in commands:
                status(script)
                subprocess.run([sys.executable,'-X','utf8','-u',str(HERE/script),*args,'--work',str(work)],check=True,cwd=ROOT)
            status('awaiting-report-review')
        except BaseException as exc:
            status('attention-required',error=type(exc).__name__+': '+str(exc),automatic_rollback=False)
            raise


if __name__=='__main__':main()
