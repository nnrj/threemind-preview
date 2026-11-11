"""Publish this completed exploration through Lab's evidence/document services.

This scoped executor leases only job IDs it created. It never starts a general
worker, claims another project, advances a consciousness, or changes raw data.
The publication journal makes completed uploads and document saves retryable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from analyze import analyze
from psycopg.types.json import Jsonb

from threemind_lab import notebooks, report_exports, report_sources, research_documents
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / ".work" / "calibrated-generalization-20260909"
META = HERE / "platform.json"
WORKER = "calibrated-generalization-publisher"
METRICS = ["n", "control_mean", "treatment_mean", "difference", "ci95_low", "ci95_high", "p", "p_holm"]
TITLES = {"memory": "扩大词表：稳定配对减混合配对", "relations": "未见名字：正确模板减错误模板"}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False).encode()


def commentary(key, markdown, section="results"):
    return {"id": key, "type": "commentary", "markdown": markdown, "section": section}


class Publisher:
    def __init__(self):
        self.meta = json.loads(META.read_text(encoding="utf-8"))
        self.project = self.meta["project_id"]
        self.state = self.meta.setdefault("publication", {})
        self.db = Database(Settings.from_env().database_url)
        self.capabilities = {
            "executor": str(Path(__file__).relative_to(HERE.parents[2])),
            "scope": self.project,
            "purpose": "completed exploration evidence publication",
        }
        self.db.announce_worker(WORKER, self.capabilities)

    def flush(self):
        META.write_bytes(encoded(self.meta) + b"\n")

    def entry(self, key):
        if key not in self.state:
            self.state[key] = {"id": str(uuid4()), "operation_id": str(uuid4())}
            self.flush()
        return self.state[key]

    def claim_owned(self, job_id):
        # The IDs come only from this publication journal or a service request
        # made below. The normal global scheduler is deliberately not invoked.
        with self.db.tx(self.project) as db:
            row = db.execute(
                "UPDATE jobs SET status='leased',worker_id=%s,generation=generation+1,attempts=attempts+1,"
                "lease_until=clock_timestamp()+interval '5 minutes' WHERE id=%s AND project_id=%s "
                "AND (status='pending' OR (status='leased' AND worker_id=%s AND lease_until<clock_timestamp())) "
                "RETURNING *",
                (WORKER, job_id, self.project, WORKER),
            ).fetchone()
            if not row:
                raise RuntimeError("Publication job is not pending or its owned lease has not expired")
            db.execute(
                "INSERT INTO job_assignments(project_id,job_id,generation,worker_id,required_features,capabilities) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (self.project, job_id, row["generation"], WORKER, row["required_features"], Jsonb(self.capabilities)),
            )
            return row

    def artifact(self, job, path, mime):
        key = "artifact:" + path.name
        item = self.entry(key)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if item.get("artifact_id"):
            if item["sha256"] != sha:
                raise RuntimeError(f"Published evidence changed: {path.name}")
            return item["artifact_id"]
        with path.open("rb") as stream:
            artifact = self.db.put_artifact_stream(
                job, path.name, mime, stream, {"sha256_local": sha, "exploration": HERE.name}
            )
        item.update(artifact_id=str(artifact["id"]), sha256=sha, bytes=artifact["bytes"])
        self.flush()
        return item["artifact_id"]

    def analysis(self, key, value, *, attachments=False):
        item = self.entry("analysis:" + key)
        if item.get("result"):
            return item["result"]["artifact_id"]
        if not item.get("job_id"):
            pending = self.db.enqueue(
                self.project,
                "analysis",
                {
                    "executor": self.capabilities["executor"],
                    "endpoint": key,
                    "protocol_note_id": self.meta["protocol_note_id"],
                    "unit": value["unit"],
                    "inference": value["inference"],
                    "input_hashes": {
                        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in WORK.glob("*-results.json")
                    },
                    "analysis_script_sha256": hashlib.sha256((HERE / "analyze.py").read_bytes()).hexdigest(),
                },
            )
            item["job_id"] = str(pending["id"])
            self.flush()
        with self.db.tx(self.project) as db:
            previous = db.execute("SELECT status,result FROM jobs WHERE id=%s", (item["job_id"],)).fetchone()
        if previous["status"] == "done":
            item["result"] = previous["result"]
            self.flush()
            return item["result"]["artifact_id"]
        job = self.claim_owned(item["job_id"])
        if attachments:
            for path in sorted(WORK.glob("*-results.json")):
                self.artifact(job, path, "application/json")
            for name, mime in (
                ("memory-cases.csv", "text/csv"),
                ("relations-cases.csv", "text/csv"),
                ("summary.json", "application/json"),
                ("calibration-decision.json", "application/json"),
                ("analyze.py", "text/x-python"),
                ("run.py", "text/x-python"),
                ("protocol.md", "text/markdown"),
                ("evidence-index.json", "application/json"),
                ("implementation-source.zip", "application/zip"),
            ):
                self.artifact(job, HERE / name, mime)
        result = self.db.put_artifact(
            job,
            key + ".json",
            "application/json",
            encoded(value),
            {
                "title": TITLES[key],
                "units": "model activation a.u.",
                "inference": value["inference"],
                "not_accuracy": True,
            },
        )
        completion = {"artifact_id": str(result["id"]), "sha256": result["sha256"]}
        self.db.finish(job, result=completion)
        item["result"] = completion
        self.flush()
        return completion["artifact_id"]

    def service_job(self, item, request, execute):
        if item.get("result"):
            return item["result"]
        requested = request()
        item.update(request_id=str(requested["id"]), job_id=str(requested["job_id"]))
        self.flush()
        with self.db.tx(self.project) as db:
            row = db.execute("SELECT status,result FROM jobs WHERE id=%s", (item["job_id"],)).fetchone()
        if row["status"] == "done":
            completion = row["result"]
        else:
            job = self.claim_owned(item["job_id"])
            completion = execute(self.db, job)
            self.db.finish(job, result=completion)
        item["result"] = completion
        self.flush()
        return completion

    def source(self, key, artifact_id):
        item = self.entry("source:" + key)
        self.service_job(
            item,
            lambda: report_sources.request(
                self.db,
                self.project,
                LOCAL_USER,
                {
                    "operation_id": item["operation_id"],
                    "kind": "analysis",
                    "analysis_artifact_id": artifact_id,
                    "metrics": METRICS,
                },
            ),
            report_sources.capture,
        )
        return item["request_id"]

    def document(self, key, kind, title, sources, blocks):
        item = self.entry("document:" + key)
        if not item.get("revision"):
            saved = research_documents.save(
                self.db,
                self.project,
                LOCAL_USER,
                item["id"],
                {
                    "operation_id": item["operation_id"],
                    "expected_revision": 0,
                    "spec": {"kind": kind, "title": title, "sources": sources, "blocks": blocks},
                    "review": "draft",
                },
            )
            item.update(revision=saved["revision"], content_hash=saved["content_hash"])
            self.flush()
        rendered = research_documents.render(self.db, self.project, item["id"])
        assert len(rendered["blocks"]) == len(blocks)
        print(f"Verified {kind}: {title} ({item['id']})", flush=True)
        return item["id"]

    def publish(self):
        summary = analyze()
        sources = {
            key: self.source(key, self.analysis(key, value, attachments=index == 0))
            for index, (key, value) in enumerate(summary["analyses"].items())
        }
        text = (HERE / "report.md").read_text(encoding="utf-8")
        for filename in ("memory-results.png", "relation-results.png"):
            item = self.entry("image:" + filename)
            notebooks.save_asset(
                self.db, self.project, LOCAL_USER, item["id"], filename, (HERE / filename).read_bytes()
            )
            text = text.replace(f"]({filename})", f"](/api/v2/projects/{self.project}/note-assets/{item['id']})")
        links = ["\n## 可复查证据\n"]
        for key, item in self.state.items():
            if key.startswith("artifact:"):
                links.append(
                    f"- [{key[9:]}](/api/v2/projects/{self.project}/artifacts/{item['artifact_id']}) — SHA256 `{item['sha256']}`"
                )
        links.append(
            "\n每次测量的完整 ZIP 和最终模型均保存在数据库；上面的 evidence-index.json 给出全部下载路径与哈希。"
        )
        text += "\n" + "\n".join(links)
        cal = json.loads((HERE / "calibration-decision.json").read_bytes())
        self.document(
            "calibration",
            "record",
            "实验记录一：独立感官与探针校准",
            [],
            [
                commentary("method", "独立词表和种子校准，不使用期望词命中率选择剂量。", "methods"),
                commentary(
                    "decision",
                    "预先规定的物理可观测性合格案例：强度1为3/16，强度2、4为16/16。固定最低合格强度2。\n\n"
                    + json.dumps(cal, ensure_ascii=False, indent=2),
                    "results",
                ),
                commentary("evidence", "\n".join(links), "other"),
            ],
        )
        refs = []
        for key in ["memory", "relations"]:
            blocks = [
                commentary("method", summary["analyses"][key]["unit"], "methods"),
                {
                    "id": "chart",
                    "type": "chart",
                    "source": sources[key],
                    "metric": "difference",
                    "chart": "bar",
                    "analysis_metric": summary["analyses"][key]["metrics"][0]["metric"],
                    "title": TITLES[key],
                },
                {
                    "id": "table",
                    "type": "table",
                    "source": sources[key],
                    "metrics": METRICS,
                    "title": "冻结数据与两主比较的Holm校正",
                },
                commentary(
                    "interpretation", (HERE / f"{key}-interpretation.md").read_text(encoding="utf-8"), "discussion"
                ),
                commentary("evidence", "\n".join(links), "other"),
            ]
            ident = self.document(
                key,
                "record",
                ("实验记录二：配对效应的扩大验证" if key == "memory" else "实验记录三：未见名字家系的独立角色组合检验"),
                [sources[key]],
                blocks,
            )
            refs.extend(
                {"id": key + "_" + b, "type": "record_block", "record_id": ident, "revision": 1, "block_id": b}
                for b in ["chart", "table"]
            )
        report = self.document(
            "report",
            "report",
            "校准后验证报告：配对关联与未见名字家系（2026-09-09）",
            [],
            [commentary("report", text, "discussion"), *refs],
        )
        for key, title, body in [
            ("decision", "冻结校准结果与实验执行说明", (HERE / "execution-notes.md").read_text(encoding="utf-8")),
            ("results", "校准后验证：完整分析报告与图表", text),
        ]:
            item = self.entry("note:" + key)
            if not item.get("revision"):
                saved = notebooks.save_note(
                    self.db,
                    self.project,
                    LOCAL_USER,
                    item["id"],
                    {
                        "operation_id": item["operation_id"],
                        "expected_revision": 0,
                        "title": title,
                        "kind": "note",
                        "collection_id": self.meta["notebook_id"],
                        "body": {"format": "markdown", "text": body},
                    },
                )
                item.update(revision=saved["revision"], content_hash=saved["content_hash"])
                self.flush()
        for fmt in ["markdown", "html"]:
            item = self.entry("export:" + fmt)
            self.service_job(
                item,
                lambda item=item, fmt=fmt: report_exports.request(
                    self.db,
                    self.project,
                    LOCAL_USER,
                    report,
                    {
                        "operation_id": item["operation_id"],
                        "revision": 1,
                        "format": fmt,
                        "language": "zh-CN",
                        "include_data": True,
                    },
                ),
                report_exports.execute,
            )
        self.flush()
        print("Published three records, three notes and a report with Markdown/HTML exports.")


if __name__ == "__main__":
    p = Publisher()
    try:
        p.publish()
    finally:
        p.db.close()
