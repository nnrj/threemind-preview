"""Post-computation inventory and reviewed API delivery; never advances a subject."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

import psutil
import driver as s


def ready(work):
    h=s.load(work/"host.json")
    if psutil.pid_exists(h["pid"]) and psutil.Process(h["pid"]).create_time()==h["created_at"]:
        raise RuntimeError("scientific host still alive")
    assert s.load(work/"status.json")==dict(state="awaiting-analysis",sequences_completed=32)
    assert s.load(work/"independent-audit-v1.json")["passed"]
    assert not any((work/n).exists() for n in ("STOP","in-flight.json"))
    s.frozen(work);s.base.resource_check(work)


def members(work):
    excluded={".research-records","publication","readback"}
    return sorted(p for p in work.rglob("*") if p.is_file()
        and not set(p.relative_to(work).parts)&excluded and not p.name.endswith(".lock")
        and not p.name.startswith("originals-v1") and p.name!="originals-manifest-v1.json")


def inventory(work):
    ready(work)
    sys.path.insert(0,str(s.ROOT/"lab/explorations/2026-11-09-retention-causality"))
    from storage_inventory import sum_files
    files=members(work)
    analysis=s.load(work/"analysis-v1.json")
    states=[work/row["final_state"] for row in analysis["subjects"]]
    assert len(states)==32
    inventories=[]
    for path in states:
        state=s.load(path)
        deps=[work/state["adapter_ref"]["path"]/name for name in state["adapter_ref"]["files"]]
        inventories.append((sum_files([path,*deps]),path,state,deps))
    whole,largest,state,deps=max(inventories,key=lambda x:x[0]["logical_bytes"])
    costs={}
    for case in s.load(work/"cases.json"):
        receipts=[s.load(p) for p in (work/"subjects"/case["key"]).rglob("complete.json")]
        row=costs.setdefault(case["curve"],dict(individuals=0,operation_wall_seconds=0.,internal_seconds=0.,optimizer_updates=0,teacher_lessons=0))
        row["individuals"]+=1
        row["operation_wall_seconds"]+=sum(r["wall_seconds"] for r in receipts)
        result=next(x for x in analysis["subjects"] if x["key"]==case["key"])
        row["internal_seconds"]+=int(result["final_time_us"])/1e6
        last=s.load(work/result["final_state"])
        row["teacher_lessons"]+=last["learning"]["teacher_lessons"]
        for receipt in receipts:
            data=s.load(work/receipt["result_file"])
            row["optimizer_updates"]+=data.get("updates",0)
    out=dict(study=sum_files(files),one_complete_individual=whole,adapter_dependencies=sum_files(deps),
        largest_state=dict(path=largest.relative_to(work).as_posix(),compressed_bytes=largest.stat().st_size,
                           nodes=len(state["core"]["nodes"]),edges=len(state["core"]["edges"])),
        cost_by_curve=costs,host=s.load(work/"resource-summary.json"),
        scope="Final whole subject includes Core, full personal Transformer and optimizer/RNG dependencies, body, mapping, samples, history and random states. File streams only; hard links deduplicated by file identity. Directory/MFT/database overhead excluded.")
    s.save(work/"storage-inventory-v1.json",out);print(json.dumps(out))


def verify_archive(pack,manifest):
    with zipfile.ZipFile(pack) as z:
        names={r["path"] for r in manifest["members"]}
        assert set(z.namelist())==names|{"originals-manifest-v1.json"}
        assert json.loads(z.read("originals-manifest-v1.json"))==manifest
        import hashlib
        for row in manifest["members"]:
            raw=z.read(row["path"])
            assert len(raw)==row["bytes"] and hashlib.sha256(raw).hexdigest()==row["sha256"]


def publish(work,review_path):
    review=s.load(review_path)
    assert review["reviewer"]=="assistant" and review["approved_for_publication"] is True
    assert Path(review["work"]).resolve()==work
    for rel,h in review["reviewed_files"].items(): assert s.sha(s.ROOT/rel)==h
    for rel,h in review["reviewed_originals"].items(): assert s.sha(work/rel)==h
    assert {"analysis-v1.json","independent-audit-v1.json","storage-inventory-v1.json"}<=set(review["reviewed_originals"])
    if (work/"publication/completion.json").exists(): print(json.dumps(s.load(work/"publication/completion.json")));return
    with s.base.worker_lock(work):
        ready(work)
        with s.connection() as client:
            project=s.load(work/"platform.json")["project_id"]
            recorder=s.base.ResearchRecorder(work,project,client=client);recorder.resume_recording()
            recorder.save_original("postprocessing/review.json",review_path.read_bytes())
            for rel in review["reviewed_files"]: recorder.save_original("postprocessing/repo/"+rel,(s.ROOT/rel).read_bytes())
            files=members(work)
            if any(p.name.endswith(".partial") for p in files): raise RuntimeError("unfinished original")
            manifest=dict(schema="threemind.retention-original-manifest/1",members=[dict(path=p.relative_to(work).as_posix(),bytes=p.stat().st_size,sha256=s.sha(p)) for p in files])
            recorder.save_original("originals-manifest-v1.json",json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2).encode())
            pack=work/"originals-v1.zip"
            if not pack.exists():
                assert shutil.disk_usage(work).free>=25*2**30+2.02*sum(r["bytes"] for r in manifest["members"])+64*2**20
                part=work/"originals-v1.zip.partial"
                with zipfile.ZipFile(part,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                    for p in files+[work/"originals-manifest-v1.json"]: z.write(p,p.relative_to(work).as_posix())
                os.link(part,pack);part.unlink()
            verify_archive(pack,manifest)
            for rel,role,fmt in (("originals-v1.zip","original","application/zip"),("originals-manifest-v1.json","manifest","application/json"),("analysis-v1.json","analysis","application/json")):
                p=work/rel
                recorder.attach(dict(logical_id="kernel53-r47c-v1:"+rel,role=role,label="R47c "+rel,format=fmt,
                    byte_count=p.stat().st_size,sha256=s.sha(p),locator=dict(kind="file",resource_id=s.RESOURCE,member=rel)),request_id=s.ident("publication-attach:"+rel))
            for lang in ("zh","en"):
                recorder.text(dict(request_id=str(s.ident("report-"+lang)),identity=str(s.ident("report-doc-"+lang)),
                    expected_revision=0,kind="report",title="R47c single-age retention results "+lang,
                    markdown=(s.ROOT/review["reports"][lang]).read_text("utf-8")))
            recorder.text(dict(request_id=str(s.ident("publication-note")),identity=str(s.ident("publication-note-doc")),
                expected_revision=0,kind="note",title="R47c independent arithmetic and provenance review",markdown=review["review_note"]))
            recorder.synchronize(strict=True)
            args=dict(path=dict(project=project,experiment=recorder.experiment),query=dict(hashes=True))
            verified=client.call("records.verify",args)
            assert verified["coverage"]=="verified" and not verified["problems"]
            checks=[]
            for kind in ("protocol","report"):
                for lang in ("zh","en"):
                    doc=client.request("GET",f'/api/v2/projects/{project}/research-documents/{s.ident(kind+"-doc-"+lang)}')
                    text=(s.HERE/f"protocol.{lang}.md" if kind=="protocol" else s.ROOT/review["reports"][lang]).read_text("utf-8")
                    assert len(doc["spec"]["blocks"])==1 and doc["spec"]["blocks"][0]["markdown"]==text
                    checks.append(dict(kind=kind,language=lang,text_equal=True,revision=doc["revision"]))
            recorder.save_original("publication/document-readback.json",json.dumps(checks).encode())
            evidence=next(e for e in verified["evidence"] if e["logical_id"]=="kernel53-r47c-v1:originals-v1.zip")
            dest=work/"readback/originals-v1.zip";dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                receipt=client.call("records.download",dict(path=dict(project=project,evidence=evidence["id"])),output=dest,maximum=pack.stat().st_size)
                recorder.save_original("publication/download-receipt.json",json.dumps(receipt).encode())
            assert s.sha(dest)==s.sha(pack);verify_archive(dest,manifest);s.base.resource_check(work)
            recorder.save_original("publication/verification-before-finalize.json",json.dumps(verified).encode())
            recorder.finalize(request_id=s.ident("publication-finalize"));recorder.synchronize(strict=True)
            final=client.call("records.verify",args)
            assert final["execution_status"]=="completed" and final["coverage"]=="verified" and not final["problems"] and recorder.status["pending"]==0
            recorder.save_original("publication/final-verification.json",json.dumps(final).encode())
            out=dict(record=recorder.experiment,project=project,pending=0,coverage="verified",execution_status="completed",
                archive_bytes=pack.stat().st_size,archive_sha256=s.sha(pack),members=len(manifest["members"]),documents_read_back=4)
            recorder.save_original("publication/completion.json",json.dumps(out,indent=2).encode());print(json.dumps(out))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("inventory","publish"));p.add_argument("--work",type=Path,default=s.WORK);p.add_argument("--review",type=Path)
    a=p.parse_args()
    if a.command=="inventory": inventory(a.work.resolve())
    else: publish(a.work.resolve(),a.review.resolve())
