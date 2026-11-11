"""Publish immutable evidence and authored reports through existing Lab services."""

import hashlib
import json
import threading
import zipfile
from contextlib import contextmanager

from common import HERE, KERNELS, WORK, Study, encoded, read_json

from threemind_lab import notebooks, report_exports, report_sources, research_documents
from threemind_lab.database import LOCAL_USER


class Publisher(Study):
    def __init__(self):
        super().__init__()
        self.path = WORK / "publication.json"
        self.state = read_json(self.path) if self.path.exists() else {}
        self.worker = "continuous-mechanisms-publication-20260929"

    def remember(self, key, value):
        self.state[key] = json.loads(encoded(value))
        staging = self.path.with_suffix(".tmp")
        staging.write_bytes(encoded(self.state))
        staging.replace(self.path)
        return value

    @contextmanager
    def owned(self, job_id):
        # Check before admission. This publisher must never execute another project.
        with self.db.tx() as db:
            pending = db.execute("SELECT id FROM jobs WHERE status IN ('pending','leased')").fetchall()
        if any(str(r["id"]) != str(job_id) for r in pending):
            raise RuntimeError("another task is pending; publish later without taking its work")
        with self.db.tx(self.project) as db:
            task = db.execute("SELECT required_features FROM jobs WHERE id=%s", (job_id,)).fetchone()
        cap = {
            "schema": "threemind.worker-capabilities/1",
            "queue": "runtime",
            "scope": "bounded study publication",
            "features": {f: {"state": "available"} for f in task["required_features"]},
        }
        job = self.db.claim(self.worker, capabilities=cap, max_active=1)
        if not job or str(job["id"]) != str(job_id):
            raise RuntimeError("publication lease unavailable; no job executed")
        stop = threading.Event()

        def renew():
            while not stop.wait(15):
                self.db.renew(job)

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield job
        finally:
            stop.set()
            thread.join(timeout=2)

    def archive(self):
        key = "archive"
        if key in self.state and self.state[key].get("artifact_id"):
            return self.state[key]
        path = WORK / "evidence.zip"
        if not path.exists():
            entries = [
                p
                for p in WORK.rglob("*")
                if p.is_file()
                and p not in (path, self.path)
                and p.suffix not in (".tmp", ".pyc")
                and "__pycache__" not in p.parts
            ]
            manifest = []
            with zipfile.ZipFile(path, "x", allowZip64=True) as z:
                for p in sorted(entries):
                    self.guard()
                    name = p.relative_to(WORK).as_posix()
                    with p.open("rb") as f:
                        sha = hashlib.file_digest(f, "sha256").hexdigest()
                    manifest.append({"path": name, "bytes": p.stat().st_size, "sha256": sha})
                    z.write(
                        p,
                        name,
                        compress_type=zipfile.ZIP_STORED
                        if p.suffix in (".gz", ".tmt", ".png")
                        else zipfile.ZIP_DEFLATED,
                    )
                for p in sorted(HERE.iterdir()):
                    if p.is_file() and p.suffix in (".py", ".md"):
                        raw = p.read_bytes()
                        name = "publication-sources/" + p.name
                        manifest.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                        z.writestr(name, raw, compress_type=zipfile.ZIP_DEFLATED)
                z.writestr(
                    "archive-manifest.json",
                    encoded(
                        {
                            "files": manifest,
                            "model_state_location": "Parent states in parent-state.json.gz; probe snapshots and diagnostic states included. Final checkpoints also reside in the study database, identified by result.json hashes.",
                            "old_data_included": False,
                        }
                    ),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
        # A partial archive left by an interrupted publisher is never uploaded
        # merely because the path exists. Read every declared member back.
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("archive-manifest.json"))["files"]
            assert len(z.namelist()) == len(manifest) + 1
            assert set(z.namelist()) == {r["path"] for r in manifest} | {"archive-manifest.json"}
            for member in manifest:
                self.guard()
                assert z.getinfo(member["path"]).file_size == member["bytes"]
                with z.open(member["path"]) as f:
                    assert hashlib.file_digest(f, "sha256").hexdigest() == member["sha256"]
        item = self.state.get(key)
        if not item:
            item = self.remember(
                key,
                {
                    "job_id": self.db.enqueue(
                        self.project,
                        "analysis",
                        {"purpose": "archive continuous mechanism evidence; no Core execution"},
                    )["id"]
                },
            )
        with self.owned(item["job_id"]) as job:
            with path.open("rb") as f:
                artifact = self.db.put_artifact_stream(
                    job,
                    "continuous-mechanisms-evidence.zip",
                    "application/zip",
                    f,
                    metadata={"schema": "continuous-mechanisms-evidence/1", "study": self.meta["design_sha256"]},
                )
            self.db.finish(job, result={"artifact_id": str(artifact["id"]), "evidence_archive": True})
        return self.remember(
            key,
            item
            | {
                "artifact_id": str(artifact["id"]),
                "sha256": artifact["sha256"],
                "bytes": artifact["bytes"],
                "verified_members": len(manifest),
            },
        )

    def document(self, key, kind, title, body, sources=(), blocks=()):
        if key in self.state:
            return self.state[key]["id"]
        value = research_documents.save(
            self.db,
            self.project,
            LOCAL_USER,
            self.identity(key),
            {
                "operation_id": self.identity(key + ":write"),
                "expected_revision": 0,
                "spec": {
                    "kind": kind,
                    "title": title,
                    "sources": list(sources),
                    "blocks": [
                        {"id": "narrative", "type": "commentary", "markdown": body, "section": "results"},
                        *blocks,
                    ],
                },
            },
        )
        self.remember(key, value)
        return value["id"]

    def publish(self):
        import re
        analysis = read_json(WORK / "analysis-v2.json")
        audit = read_json(WORK / "audit.json")
        if audit["cases"] != 341 or audit["failed"]:
            raise RuntimeError("expected complete, audited experiment")
        archive = self.archive()
        image_id = self.identity("overview-image")
        notebooks.save_asset(self.db, self.project, LOCAL_USER, image_id,
                             "continuous-mechanisms.png", (WORK / "overview.png").read_bytes())
        for lang in ("zh", "en"):
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            body = body.replace(
                "](../../../docs/images/continuous-mechanisms-2026-09-29.png)",
                f"](/api/v2/projects/{self.project}/note-assets/{image_id})")
            body = body.replace("[English](report.en.md)\n\n", "").replace("[中文](report.zh.md)\n\n", "")
            # The in-app report is not a filesystem document. Its local sibling
            # documents are included in the archive and the Documentation menu.
            body = re.sub(r"\[([^\]]+)\]\(([^):]+\.md)\)", r"\1", body)
            body += f"\n\n[完整原始证据 / Verified raw evidence](/api/v2/projects/{self.project}/artifacts/{archive['artifact_id']})\n"
            title = "连续版机制归因：短时资源、抑制与门槛" if lang == "zh" else "Continuous kernel: resources, inhibition and thresholds"
            self.document("report:" + lang, "report", title, body)
            key = "results-note:" + lang
            if key not in self.state:
                note = notebooks.save_note(self.db, self.project, LOCAL_USER, self.identity(key), {
                    "operation_id": self.identity(key + ":write"), "expected_revision": 0,
                    "kind": "note", "collection_id": self.meta["notebook_id"], "title": title,
                    "body": {"format": "markdown", "text": body}})
                self.remember(key, note)
        for bits, result in analysis["factorial"].items():
            title = f"机制组合 S/F/C={bits}：四种教学、六种提示"
            text = (f"短时资源/快痕迹/局部上下文开关依次为 {bits}（1 开、0 关）。"
                    f"四个独立训练父本，每个父本六种测试，合计 24 个测试副本。"
                    f"\n\n两种完整提示共 {result['n']} 条，匹配结尾峰值领先 {result['positive']} 条；"
                    f"平均差 {result['mean']:.12g}；合格时序收敛输出 {result['converged']} 条。"
                    "\n\n完整逐次结果位于证据包 factorial-"+bits+".json；原始轨迹位于 cases/factorial/"+bits+"。"
                    f"\n\n[原始证据](/api/v2/projects/{self.project}/artifacts/{archive['artifact_id']})")
            self.document("record:"+bits, "record", title, text)
        self.document("record:diagnostic", "record", "局部作用链诊断：六组配置、两条提示", (
            "12 个独立副本在相同父本上检验抑制、恢复速度和门槛。每 10 毫秒保存全部状态。"
            "\n\n默认副本精确复现；门槛 0.0036 时两条反向，0.0044 时仅一条匹配；关闭抑制后两条都偏 C。"
            "门槛兼有归零与逐边筛选作用，不能当成单一发送门槛的纯消融。"
            f"\n\n[完整记录与状态](/api/v2/projects/{self.project}/artifacts/{archive['artifact_id']})"))
        self.guard(force=True)
        print(json.dumps({"project": self.project, "reports": {lang: self.state['report:'+lang]['id'] for lang in ('zh','en')},
                          "archive": archive}, default=str), flush=True)


if __name__ == "__main__":
    publisher = Publisher()
    try:
        publisher.publish()
    finally:
        publisher.db.close()
