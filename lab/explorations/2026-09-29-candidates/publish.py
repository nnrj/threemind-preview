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
        self.worker = "candidate-study-publication-20260929"

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
                            "model_state_location": "ThreeMind checkpoints referenced by result.json; archive includes inputs, measurements and hashes",
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
                        {"purpose": "archive candidate experiment evidence; no Core execution"},
                    )["id"]
                },
            )
        with self.owned(item["job_id"]) as job:
            with path.open("rb") as f:
                artifact = self.db.put_artifact_stream(
                    job,
                    "candidate-experiment-evidence.zip",
                    "application/zip",
                    f,
                    metadata={"schema": "candidate-evidence/1", "study": self.meta["design_sha256"]},
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

    def source(self, key, run_id, kind):
        key = "source:" + key + ":" + kind
        if key in self.state and self.state[key].get("done"):
            return self.state[key]["id"]
        item = self.state.get(key)
        if not item:
            item = report_sources.request(
                self.db, self.project, LOCAL_USER, {"operation_id": self.identity(key), "kind": kind, "run_id": run_id}
            )
            self.remember(key, item)
        with self.owned(item["job_id"]) as job:
            value = report_sources.capture(self.db, job)
            self.db.finish(job, result=value)
        self.remember(key, item | {"done": True})
        return item["id"]

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
        summary = read_json(WORK / "summary.json")
        if summary["complete_blocks"] != 6:
            raise RuntimeError("do not publish incomplete evidence as final")
        archive = self.archive()
        image_id = self.identity("overview-image")
        notebooks.save_asset(
            self.db, self.project, LOCAL_USER, image_id, "overview.png", (WORK / "overview.png").read_bytes()
        )
        sources = []
        blocks = []
        for kernel in KERNELS:
            short = kernel.split(".")[-1].replace("/", "-")
            key = f"block-0/{short}/pair-bg1-trained/hold-1000000-cue0"
            run = read_json(WORK / "cases" / key / "result.json")
            source = self.source(short, run["id"], "temporal_nodes")
            sources.append(source)
            blocks.append(
                {
                    "id": short + "-plot",
                    "type": "chart",
                    "source": source,
                    "metric": "last_activation",
                    "chart": "bar",
                    "title": f"{kernel}: observed end state ({run['extra']['classification']}); block 0, host on, hold 1 s, cue 0",
                }
            )
            blocks.append(
                {
                    "id": short,
                    "type": "table",
                    "source": source,
                    "metrics": ["last_activation", "peak_activation"],
                    "title": f"{kernel}: raw activation / projection (block 0, host on, hold 1 s, cue 0)",
                }
            )
        for lang in ("zh", "en"):
            text = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            text = text.replace(
                "](../../../docs/images/candidate-exploration-2026-09-29.png)",
                f"](/api/v2/projects/{self.project}/note-assets/{image_id})",
            )
            # Published documents have project routes, not local Markdown siblings.
            text = text.replace("[English](report.en.md)\n\n", "").replace("[中文](report.zh.md)\n\n", "")
            text += f"\n\n[完整原始证据 / Raw evidence](/api/v2/projects/{self.project}/artifacts/{archive['artifact_id']})\n"
            title = (
                "多内核初步实验：适应、配对与上下文"
                if lang == "zh"
                else "Candidate kernels: adaptation, pairing and context"
            )
            self.document("report:" + lang, "report", title, text, sources, blocks)
            key = "note:results:" + lang
            if key not in self.state:
                note = notebooks.save_note(
                    self.db,
                    self.project,
                    LOCAL_USER,
                    self.identity(key),
                    {
                        "operation_id": self.identity(key + ":write"),
                        "expected_revision": 0,
                        "kind": "note",
                        "collection_id": self.meta["notebook_id"],
                        "title": title,
                        "body": {"format": "markdown", "text": text},
                    },
                )
                self.remember(key, note)
        # Each block has an independently addressable record, not a rewritten past report.
        for block in range(6):
            data = read_json(WORK / f"block-{block}.json")
            self.document(
                f"record:{block}",
                "record",
                f"多内核对照：输入／环境块 {block}",
                f"本块完成 {len(data)} 个测量结果。输入使用本块独有的匿名通道与真实宿主记录。"
                f"\n\n设计笔记与总报告列出冻结条件、全部指标和限制；原始行位于证据包 block-{block}.json。"
                f"\n\n[证据包](/api/v2/projects/{self.project}/artifacts/{archive['artifact_id']})",
            )
        for lang in ("zh", "en"):
            for fmt in ("markdown", "html"):
                key = f"export:{lang}:{fmt}"
                if key in self.state and self.state[key].get("done"):
                    continue
                item = self.state.get(key)
                if not item:
                    item = report_exports.request(
                        self.db,
                        self.project,
                        LOCAL_USER,
                        self.state["report:" + lang]["id"],
                        {
                            "operation_id": self.identity(key),
                            "revision": 1,
                            "format": fmt,
                            "language": "zh-CN" if lang == "zh" else "en",
                            "include_data": True,
                        },
                    )
                    self.remember(key, item)
                with self.owned(item["job_id"]) as job:
                    result = report_exports.execute(self.db, job)
                    self.db.finish(job, result=result)
                self.remember(key, item | {"done": True, "result": result})
        print(json.dumps({"project": self.project, "reports": [self.state["report:" + l]["id"] for l in ("zh", "en")]}))


if __name__ == "__main__":
    p = Publisher()
    try:
        p.publish()
    finally:
        p.db.close()
