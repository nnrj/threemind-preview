"""Windows process-tree budget enforcement around the frozen experiment runner.

This supplements (and does not edit) run.py: a Windows venv launcher can have
its own Python child, so a timeout must stop the entire owned process tree.
"""
import json
import os
import subprocess
import sys
import time

import psutil
from run import HERE, WORK, META, Database, Settings, resources


def main(args):
    meta = json.loads(META.read_bytes())
    import hashlib
    for name, expected in meta['frozen_hashes'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected
    db = Database(Settings.from_env().database_url)
    r = resources(db)
    db.close()
    assert max(0,r['database_bytes']-meta['resources_before']['database_bytes'])+r['local_bytes'] < 400*1024**2
    spent = sum(json.loads(p.read_bytes())['wall_seconds'] for p in WORK.glob('*-summary.json'))
    assert spent < 720
    start = time.monotonic()
    owned = {}
    label = '-'.join(args)
    log_path = WORK/(label+'.log')
    with log_path.open('xb') as log:
        p = subprocess.Popen([sys.executable,str(HERE/'run.py'),*args],stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            parent = psutil.Process(p.pid)
            while p.poll() is None:
                for proc in [parent,*parent.children(recursive=True)]:
                    owned[(proc.pid,proc.create_time())] = proc
                rss = sum(proc.memory_info().rss for proc in owned.values() if proc.is_running())
                if time.monotonic()-start > min(180,720-spent) or rss > 1024**3:
                    raise RuntimeError('Owned process tree reached time or memory budget; no automatic retry')
                if psutil.virtual_memory().available < 3*1024**3:
                    raise RuntimeError('Host memory reserve reached')
                time.sleep(.5)
            if p.returncode:
                raise RuntimeError('Experiment stopped; inspect '+str(log_path))
        except BaseException:
            # Only processes descended from the child launched above, with
            # creation times checked by psutil. Never stop a platform service.
            for proc in reversed(list(owned.values())):
                try: proc.kill()
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            p.wait(timeout=10)
            raise
    print(log_path.read_text(encoding='utf-8'),flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
