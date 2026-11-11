"""Durable host continuation and observational export for the two E67 arms.

Runs independently of the chat turn. Subject execution remains the frozen r3
runner; analysis/rendering starts only after simulation exits successfully.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from experiment import Study, RESOURCE, HERE, ROOT, read, run, fixed_json
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json


def main():
    work=ResearchStorage().writable_root()/'experiments'/HERE.name
    state=work/'pipeline-status.json'
    def status(phase, **details):
        value=dict(phase=phase,pid=os.getpid(),updated_epoch=time.time(),**details)
        atomic_json(state,value);print(json.dumps(value),flush=True)
    s=Study(work)
    try:
        with s.storage.writer(RESOURCE):
            s.verify_sources()
            if read(work/'protocol-revision-3.json')['active_arms']!=['2','3.1']:
                raise ValueError('only the two authorized active arms may resume')
            stop=work/'STOP';prior=work/'STOP-20261011T2008-preserved.json'
            if stop.exists():
                if prior.exists():raise ValueError('new STOP requires explicit review; do not clear it automatically')
                stop.rename(prior)
            s.recorder.append('correction','resume-two-arms-20261012',dict(
                decision='Continue /2 and /3.1 only; both /4 arms remain deferred.',
                actual_resume_date='2026-10-12',
                interruption='Previous turn edited the runner but did not register revision3 or launch execution; no experiment ran overnight.',
                subjects='Existing complete initial-fit systems; no new birth or peripheral reset.',
                protocol_revision=3),request_id=s.rid('resume-two-arms-20261012'))
            s.recorder.finalize('running',request_id=s.rid('resume-two-arms-status-20261012'))
            s.recorder.synchronize(strict=True)
            status('simulation',active_arms=['2','3.1'],deferred_arms=['4-adaptive','4-legacy'])
            run(s)
        s.close()
        # Use the same cooperative storage lock while writing derived originals.
        for name, extra in [('analyze.py',['--audit-inputs']),('figures.py',[]),('replay.py',[])]:
            with ResearchStorage().writer(RESOURCE):
                status(name)
                subprocess.run([sys.executable,'-u',str(HERE/name),'--work',str(work),*extra],check=True,cwd=ROOT)
        status('publish-originals')
        subprocess.run([sys.executable,'-u',str(HERE/'publish.py'),'originals','--work',str(work)],check=True,cwd=ROOT)
        status('awaiting-report-review',active_arms=['2','3.1'])
    except BaseException as error:
        status('failed',error=type(error).__name__+': '+str(error))
        raise
    finally:
        s.close()


if __name__=='__main__':main()
