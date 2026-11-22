"""Link and read one already immutable file from each project-granted study directory."""
import hashlib
from uuid import uuid5
from apparatus import sha,read
from registration import BATCH,NS,PROJECT,api,directory,exclusive_json
from threemind_lab.research_recorder import ResearchRecorder

WITNESSES={
    "30":("cases/world-0-core/seg-0000/end.zip","checkpoint","6.3 首个水域 60 内部秒的完整状态","application/zip"),
    "28":("apparatus-checks/checks.json","engineering","出生和完整状态恢复的装置校验","application/json"),
    "38":("apparatus-checks/candidate-and-fork.json","engineering","亲代捕食事件与供给分支的装置校验","application/json"),
    "39C":("engineering/engineering-map.html","figure","遗体完整、部分取食与吃尽时的地图（装置校验）","text/html"),
}


def main():
    with api() as client:
        for code,(member,role,title,mime) in WITNESSES.items():
            work=directory(code)
            pub=work/"publication"
            pub.mkdir(exist_ok=True)
            path=work/member
            rid=read(work/"project-grant.json")["resource_id"]
            rec=ResearchRecorder(work,PROJECT,client=client)
            rec.resume_recording()
            request=str(uuid5(NS,f"{BATCH}-{code}-initial-readback"))
            digest=sha(path)
            rec.attach(dict(logical_id=f"OCEAN63-{code}:initial-readback",role=role,label=title,format=mime,
                byte_count=path.stat().st_size,sha256=digest,locator=dict(kind="file",resource_id=rid,member=member)),
                request_id=request)
            rec.synchronize(strict=True)
            evidence=read(rec.control/"receipts"/(request+".json"))["result"]["id"]
            h=hashlib.sha256()
            n=0
            with client.client.stream("GET",f"/api/v2/projects/{PROJECT}/record-evidence/{evidence}/content") as response:
                response.raise_for_status()
                for block in response.iter_bytes(1024*1024):
                    n+=len(block)
                    h.update(block)
            assert path.stat().st_size==n and digest==h.hexdigest() and not rec.status["pending"]
            exclusive_json(pub/"first-verified-readback.json",dict(member=member,bytes=n,sha256=digest,evidence=evidence))
            print(code,n,digest,flush=True)


if __name__=="__main__":
    main()
