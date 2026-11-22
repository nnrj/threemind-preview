"""Own this batch's serial simulation queue independently of the interactive shell."""
import argparse
from datetime import datetime, timezone
import os
import time
import traceback

import psutil
from apparatus import read
from baseline import execute, validate_freeze
from lab.tools.study_lock import worker_lock
from registration import directory
from threemind_lab.storage_files import atomic_json

ORDER=("30","28","38","39C")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def is_worker(receipt):
    if not receipt.exists():
        return False
    worker=read(receipt)
    if worker["pid"]==os.getpid():
        return False
    try:
        p=psutil.Process(worker["pid"])
        return p.is_running() and abs(p.create_time()-worker["created"])<0.02
    except psutil.NoSuchProcess:
        return False


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--observe-only",action="store_true",help="print the batch status without starting work")
    args=p.parse_args()
    base=directory("30").parent
    state=base/"queue.json"
    if args.observe_only:
        for code in ORDER:
            path=directory(code)
            print(code,"complete" if (path/"calculation-complete.json").exists() else
                  "running" if is_worker(path/"worker.json") else "waiting",
                  read(path/"progress.json") if (path/"progress.json").exists() else "")
        return
    with worker_lock(base/"coordinator"):
        def status(stage,code,**extra):
            atomic_json(state,dict(utc=timestamp(),pid=os.getpid(),created=psutil.Process().create_time(),
                                   stage=stage,code=code,order=ORDER,**extra))
        try:
            for code in ORDER:
                work=validate_freeze(code)
                if code=="39C" and not (work/"engineering/checks.json").is_file():
                    raise RuntimeError("carrion apparatus has no qualification record")
                if not (work/"calculation-complete.json").exists() and is_worker(work/"worker.json"):
                    status("observing existing process",code)
                    while is_worker(work/"worker.json"):
                        time.sleep(20)
                    if not (work/"calculation-complete.json").is_file():
                        raise RuntimeError(f"existing study {code} stopped before its endpoint; see its log and last checkpoint")
                if not (work/"calculation-complete.json").is_file():
                    status("computing",code)
                    execute([code])
                print(timestamp(),code,"natural observations complete",flush=True)
            status("all calculations complete",None)
        except Exception as exc:
            status("requires attention",code,error=str(exc))
            traceback.print_exc()
            raise


if __name__=="__main__":
    main()
