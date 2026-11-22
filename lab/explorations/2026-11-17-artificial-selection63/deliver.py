"""Register only this study's storage and deliver audited immutable evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid5
import zipfile

import layout
import ring as r
import study
from threemind_lab.research_recorder import ResearchRecorder


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def resource(client, work, tag):
    overview = client.request("GET", "/api/v2/storage")
    parent = work.parent.resolve()
    target = next(t for t in overview["targets"] if t["kind"] == "filesystem"
                  and Path(t["configuration"]["path"]).resolve() == parent)
    identity = tag.lower()+"-20261117"
    existing = next((x for x in overview["resources"] if x["id"] == identity), None)
    if existing is None:
        existing = client.request("POST", "/api/v2/storage/resources", body={
            "resource_id": identity, "target_id": target["id"], "relative_path": work.name,
            "registered_work_path": str(work), "writer_mode": "cooperative", "expected_revision": 0})
    assert existing["locator"]["target_id"] == target["id"]
    assert existing["locator"]["relative_path"] == work.name
    client.request("POST", "/api/v2/storage/record-evidence-grants",
                   body={"project_id": study.PROJECT, "resource_id": identity})
    return identity


def verify(pack, manifest):
    with zipfile.ZipFile(pack) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert set(archive.namelist()) == {x["path"] for x in manifest["members"]} | {"manifest.json"}
        assert json.loads(archive.read("manifest.json")) == manifest
        for member in manifest["members"]:
            h, total = hashlib.sha256(), 0
            with archive.open(member["path"]) as stream:
                for block in iter(lambda: stream.read(2**20), b""):
                    total += len(block)
                    h.update(block)
            assert total == member["bytes"] and h.hexdigest() == member["sha256"], member["path"]


def deliver(work, tag, cap):
    completion = work / "publication/completion.json"
    if completion.exists():
        print(completion.read_text("utf8"))
        return
    assert not (work / "in-flight.json").exists()
    assert (work / "science-complete.json").exists()
    assert r.read(work / "analysis-v1/audit.json")["passed"]
    main = tag == "AS63-01"
    report_name = "report" if main else "layout-report"
    ident = lambda name: uuid5(r.NS, tag+":"+name)
    with layout.client_context() as client:
        rid = resource(client, work, tag)
        rec = ResearchRecorder(work, study.PROJECT, client=client)
        rec.resume_recording()
        print(f"{tag}: collecting final reports, code, and figures", flush=True)
        for p in r.HERE.iterdir():
            if p.suffix in (".py", ".md", ".json", ".csv", ".diff") and p.name != "HANDOFF.md":
                rec.save_original("delivery-tools/"+p.name, p.read_bytes())
        for p in (r.HERE / "figures").glob("*"):
            if p.is_file():
                rec.save_original("delivery-figures/"+p.name, p.read_bytes())
        for lang in ("zh", "en"):
            rec.text({"identity": str(ident("report-document-"+lang)), "request_id": str(ident("report-"+lang)),
                "kind": "report", "expected_revision": 0, "title": tag+" report "+lang,
                "markdown": (r.HERE / f"{report_name}.{lang}.md").read_text("utf8")})
        rec.text({"identity": str(ident("note-document")), "request_id": str(ident("note")),
            "kind": "note", "expected_revision": 0, "title": tag+" evidence and provenance",
            "markdown": "The author authorized this new artificial-selection experiment and its separate layout control. "
                        "Parent assessment uses complete-state copies; birth is applied only to descendants. "
                        "Main selection criteria and the later layout-control criteria are registered separately. "
                        "Raw trajectories, input deliveries and complete states are retained without overwriting old evidence. "
                        "The assistant performed the analysis and independent arithmetic audit; this is not external replication. "
                        "Other paused revalidations and the manuscript were not resumed or changed."})
        excluded = {".research-records", "publication", "readback", "__pycache__"}
        files = sorted(p for p in work.rglob("*") if p.is_file()
                       and not set(p.relative_to(work).parts) & excluded
                       and p.name not in ("originals.zip", "manifest.json") and not p.name.endswith(".lock"))
        assert not any(p.name.endswith(".partial") for p in files)
        total = sum(p.stat().st_size for p in files)
        assert total < cap * 2**30
        assert shutil.disk_usage(work).free > 25*2**30 + total*2 + 64*2**20
        manifest = {"schema": "artificial-selection63/original-manifest/1",
                    "tag": tag, "members": [{"path": p.relative_to(work).as_posix(),
                       "bytes": p.stat().st_size, "sha256": file_sha(p)} for p in files]}
        r.save(work / "manifest.json", manifest)
        print(f"{tag}: {len(files)} original members, {total} bytes; packaging and verifying", flush=True)
        pack = work / "originals.zip"
        if not pack.exists():
            part = work / "originals.zip.partial"
            with zipfile.ZipFile(part, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for p in files+[work / "manifest.json"]:
                    archive.write(p, p.relative_to(work).as_posix())
            verify(part, manifest)
            part.rename(pack)
        verify(pack, manifest)
        assert pack.stat().st_size < cap * 2**30
        print(f"{tag}: complete local archive verified; attaching evidence", flush=True)
        for name, role, fmt in (("originals.zip", "original", "application/zip"),
                               ("manifest.json", "manifest", "application/json"),
                               ("analysis-v1/analysis.json", "analysis", "application/json")):
            p = work / name
            rec.attach({"logical_id": tag+":"+name, "role": role, "label": tag+" "+name,
                "format": fmt, "byte_count": p.stat().st_size, "sha256": file_sha(p),
                "locator": {"kind": "file", "resource_id": rid, "member": name}}, request_id=ident("attach-"+name))
        for p in sorted((work / "delivery-figures").glob("*.png")):
            if p.name.startswith("04-") == main:
                continue
            name = p.relative_to(work).as_posix()
            rec.attach({"logical_id": tag+":"+name, "role": "figure", "label": tag+" "+p.name,
                "format": "image/png", "byte_count": p.stat().st_size, "sha256": file_sha(p),
                "locator": {"kind": "file", "resource_id": rid, "member": name}}, request_id=ident("attach-"+name))
        rec.synchronize(strict=True)
        args = {"path": {"project": study.PROJECT, "experiment": rec.experiment}, "query": {"hashes": True}}
        checked = client.call("records.verify", args)
        assert checked["coverage"] == "verified" and not checked["problems"]
        print(f"{tag}: API evidence hashes verified; downloading complete archive", flush=True)
        row = next(x for x in checked["evidence"] if x["logical_id"] == tag+":originals.zip")
        readback = work / "readback/originals.zip"
        readback.parent.mkdir(exist_ok=True)
        if not readback.exists():
            client.call("records.download", {"path": {"project": study.PROJECT, "evidence": row["id"]}},
                        output=readback, maximum=pack.stat().st_size)
        assert file_sha(readback) == file_sha(pack)
        verify(readback, manifest)
        print(f"{tag}: full API readback and every archive member verified", flush=True)
        for lang in ("zh", "en"):
            doc = client.request("GET", f"/api/v2/projects/{study.PROJECT}/research-documents/{ident('report-document-'+lang)}")
            assert doc["spec"]["blocks"][0]["markdown"] == (r.HERE / f"{report_name}.{lang}.md").read_text("utf8")
        rec.finalize(request_id=ident("finalize"))
        rec.synchronize(strict=True)
        checked = client.call("records.verify", args)
        assert checked["coverage"] == "verified" and not checked["problems"]
        assert rec.status["pending"] == 0
        result = {"project": study.PROJECT, "record": rec.experiment, "resource_id": rid,
            "coverage": "verified", "pending": 0, "members": len(manifest["members"]),
            "raw_bytes": total, "archive_bytes": pack.stat().st_size, "archive_sha256": file_sha(pack)}
        r.save(completion, result)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("storage", "deliver"))
    parser.add_argument("--layout", action="store_true")
    args = parser.parse_args()
    work = layout.WORK if args.layout else study.DEFAULT_WORK
    tag = "AS63-02" if args.layout else "AS63-01"
    if args.command == "storage":
        with layout.client_context() as client:
            print(resource(client, work, tag))
    else:
        cap = 1 if args.layout else (4 if (work / "continuation-v2/registration.json").exists() else 3)
        deliver(work, tag, cap)
