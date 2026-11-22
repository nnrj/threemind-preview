"""Verify the originals on their own drive and read them back through the local research API."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile
from uuid import uuid5

from apparatus import HERE, sha, read
from registration import api, directory, BATCH, NS, PROJECT, pool, exclusive_json
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.storage_files import atomic_json
from threemind_lab.storage_volumes import directory_identity


def grant_target():
    """Explicit human-confirmed enrollment of this batch only. Does not change any storage policy."""
    base=directory("30").parent
    with api() as client:
        state=client.request("GET","/api/v2/storage")
        candidates=[r for r in state["targets"] if r["kind"]=="filesystem" and
                    Path(r["configuration"]["path"]).resolve()==base.resolve()]
        if candidates:
            target=candidates[0]
        else:
            target=client.request("POST","/api/v2/storage/targets",body=dict(
                target_id=BATCH+"-originals",name=BATCH+" local research originals",
                kind="filesystem",path=str(base),configuration={"volume_identity":directory_identity(base)},expected_revision=0))
        target_id=target["id"]
        for c in ("28","30","38","39C"):
            path=directory(c)
            rid=BATCH+"-study-"+c.lower()
            current=next((r for r in state["resources"] if r["id"]==rid),None)
            if current is None:
                current=client.request("POST","/api/v2/storage/resources",body=dict(resource_id=rid,target_id=target_id,
                    relative_path=path.name,registered_work_path=str(path),expected_revision=0,writer_mode="cooperative"))
            assert current["locator"]["target_id"]==target_id and current["locator"]["relative_path"]==path.name
            receipt=client.request("POST","/api/v2/storage/record-evidence-grants",body=dict(project_id=PROJECT,resource_id=rid))
            exclusive_json(path/"project-grant.json",receipt)
        print("Local project grants verified",target_id,flush=True)


def inventory(work):
    files=[]
    for folder in ("frozen","cases","analysis","engineering","audit-sources","apparatus-checks"):
        files.extend(p for p in (work/folder).rglob("*") if p.is_file())
    files+= [p for p in work.iterdir() if p.is_file() and
             (p.suffix==".tmspecies" or (p.suffix==".json" and p.name not in
             ("worker.json","progress.json","project-grant.json","manifest.json")))]
    if any(p.suffix==".partial" for p in files):
        raise RuntimeError("incomplete original file")
    return sorted(files)


def pack(code):
    work=directory(code)
    assert (work/"calculation-complete.json").is_file() and (work/"analysis/findings.json").is_file()
    readonly=work/"audit-sources"
    readonly.mkdir(exist_ok=True)
    for name in ("ocean_results.py","report.py","map_view.py","publication.py","check_analysis.py",
                 "check_carrion.py","check_worlds.py","check_lineage.py"):
        source=HERE/name
        dest=readonly/name
        if not dest.exists():
            shutil.copyfile(source,dest)
        if sha(dest)!=sha(source):
            raise RuntimeError("preserved audit program changed: "+name)
    from report import HISTORICAL
    if code in HISTORICAL:
        for lang in ("zh","en"):
            source=HERE.parent/HISTORICAL[code]/f"report.r2.{lang}.md"
            dest=readonly/("historical-"+source.name)
            if not dest.exists():
                shutil.copyfile(source,dest)
            if sha(dest)!=sha(source):
                raise RuntimeError("historical source differs from its preserved copy")
    files=inventory(work)
    members=[dict(path=p.relative_to(work).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    manifest=dict(schema="threemind.ocean-originals/1",code=code,members=members)
    exclusive_json(work/"manifest.json",manifest)
    target=work/"originals.zip"
    if not target.exists():
        temp=target.with_suffix(".zip.partial")
        required=sum(e["bytes"] for e in members)+8*2**20
        pool().guard(BATCH,"study-"+code.lower(),extra_bytes=required)
        with zipfile.ZipFile(temp,"x",compression=zipfile.ZIP_STORED,allowZip64=True) as z:
            for p in files+[work/"manifest.json"]:
                z.write(p,p.relative_to(work).as_posix())
        verify_members(temp,manifest,work/"manifest.json")
        temp.rename(target)
    verify_members(target,manifest,work/"manifest.json")
    return target,manifest


def verify_members(path,manifest,listing):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        assert len(names)==len(set(names)) and set(names)=={e["path"] for e in manifest["members"]}|{"manifest.json"}
        assert z.read("manifest.json")==listing.read_bytes()
        for e in manifest["members"]:
            assert z.getinfo(e["path"]).file_size==e["bytes"]
            with z.open(e["path"]) as stream:
                assert hashlib.file_digest(stream,"sha256").hexdigest()==e["sha256"],e["path"]


def deliver(code):
    work=directory(code)
    evidence=work/"publication"
    evidence.mkdir(exist_ok=True)
    receipt=evidence/"complete.json"
    if receipt.exists():
        return True
    archive,manifest=pack(code)
    grant=work/"project-grant.json"
    if not grant.exists():
        atomic_json(evidence/"local-verification.json",dict(members=len(manifest["members"]),sha256=sha(archive),
                    full_local_byte_check=True,api_readback=False))
        return False
    rid=read(grant)["resource_id"]
    with api() as client:
        client.client.timeout=3600
        rec=ResearchRecorder(work,PROJECT,client=client)
        rec.resume_recording()
        ident=lambda s:str(uuid5(NS,f"{BATCH}-{code}-{s}"))
        for lang in ("zh","en"):
            rec.text(dict(identity=ident("doc-"+lang),request_id=ident("report-"+lang),expected_revision=0,
                kind="report",title="OCEAN63-"+code+" "+lang,markdown=(work/f"analysis/report.{lang}.md").read_text(encoding="utf8")))
        rec.text(dict(identity=ident("doc-note"),request_id=ident("note"),expected_revision=0,
            kind="note",title="OCEAN63-"+code+" evidence and units",
            markdown="Native 6.3. Original input frames, world snapshots, provenance, analysis and engineering fixtures are identified separately. "
                     "Independent environments are the units for environmental comparisons. A fork shares its pre-intervention history."))
        for key,role,fmt in (("originals.zip","original","application/zip"),("manifest.json","manifest","application/json"),
                             ("analysis/findings.json","analysis","application/json")):
            file=work/key
            rec.attach(dict(logical_id="OCEAN63-"+code+":"+key,role=role,label=key,format=fmt,
                byte_count=file.stat().st_size,sha256=sha(file),locator=dict(kind="file",resource_id=rid,member=key)),
                request_id=ident("evidence-"+key))
        rec.synchronize(strict=True)
        args=dict(path=dict(project=PROJECT,experiment=rec.experiment),query=dict(hashes=True))
        checked=client.call("records.verify",args)
        assert checked["coverage"]=="verified" and not checked["problems"]
        row=next(e for e in checked["evidence"] if e["logical_id"].endswith(":originals.zip"))
        h=hashlib.sha256()
        size=0
        client._prepare_authentication()
        with client.client.stream("GET",f"/api/v2/projects/{PROJECT}/record-evidence/{row['id']}/content") as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size=2**20):
                h.update(chunk)
                size+=len(chunk)
        assert h.hexdigest()==sha(archive) and size==archive.stat().st_size
        for lang in ("zh","en"):
            doc=client.request("GET",f"/api/v2/projects/{PROJECT}/research-documents/{ident('doc-'+lang)}")
            assert doc["spec"]["blocks"][0]["markdown"]==(work/f"analysis/report.{lang}.md").read_text(encoding="utf8")
        rec.finalize(request_id=ident("finalize"))
        rec.synchronize(strict=True)
        final=client.call("records.verify",args)
        assert final["coverage"]=="verified" and not final["problems"] and rec.status["pending"]==0
        exclusive_json(receipt,dict(record=rec.experiment,resource=rid,bytes=size,sha256=h.hexdigest(),
            members=len(manifest["members"]),pending=0,api_readback=True,bilingual_reports=True))
    return True


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("confirmed-target","deliver"))
    p.add_argument("code",nargs="?",choices=("30","28","38","39C"))
    a=p.parse_args()
    grant_target() if a.action=="confirmed-target" else print(deliver(a.code))
