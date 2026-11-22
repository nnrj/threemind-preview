"""Observe the scientific worker's closed results and publish each once, independently."""
import argparse
import os
from pathlib import Path
import shutil
import time
import traceback

from apparatus import HERE, read
from followthrough import ORDER, timestamp
from lab.tools.study_lock import worker_lock
from publication import deliver
from registration import directory,exclusive_json,pool,BATCH
from report import prepare
from threemind_lab.storage_files import atomic_json


def repository_copy(src,dest):
    if dest.exists():
        if dest.read_bytes()!=src.read_bytes():
            raise RuntimeError(f"{dest} already contains a different report")
        return
    with dest.open("xb") as stream, src.open("rb") as original:
        shutil.copyfileobj(original,stream)


def closed(code):
    work=directory(code)
    stamp=work/"publication"
    stamp.mkdir(exist_ok=True)
    marker=stamp/"local-report.json"
    if not marker.exists():
        findings=prepare(code)
        out=HERE/"results"/("ocean63-"+code.lower())
        out.mkdir(parents=True,exist_ok=True)
        for lang in ("zh","en"):
            f=f"report.{lang}.md"
            repository_copy(work/"analysis"/f,out/f)
        exclusive_json(marker,dict(code=code,targets=findings["targets"]))
    if (stamp/"local-verification.json").exists() and not (work/"project-grant.json").exists():
        return False
    return deliver(code)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--once",action="store_true")
    args=p.parse_args()
    root=directory("30").parent
    with worker_lock(root/"results-worker"):
        statuses={}
        while True:
            for code in ORDER:
                if statuses.get(code)=="API verified":
                    continue
                work=directory(code)
                if not (work/"calculation-complete.json").exists():
                    statuses[code]="awaiting scientific endpoint"
                    continue
                try:
                    statuses[code]="API verified" if closed(code) else "locally verified; awaiting project readback"
                except Exception as error:
                    statuses[code]="verification requires attention: "+str(error)
                    traceback.print_exc()
                    atomic_json(root/"results-status.json",dict(utc=timestamp(),pid=os.getpid(),status=statuses))
                    raise
            status=dict(utc=timestamp(),pid=os.getpid(),status=statuses)
            atomic_json(root/"results-status.json",status)
            if all(v=="API verified" for v in statuses.values()):
                receipts={c:read(directory(c)/"publication/complete.json") for c in ORDER}
                exclusive_json(HERE/"results"/"verified.json",receipts)
                pool().finish(BATCH)
                return
            if args.once or (root/"STOP").exists():
                return
            time.sleep(45)


if __name__=="__main__":
    main()
