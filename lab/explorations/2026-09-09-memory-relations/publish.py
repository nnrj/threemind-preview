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
WORK = HERE.parents[2] / ".work" / "memory-relations-20260909"
META = HERE / "platform.json"
WORKER = "exploration-reporter-20260909"
METRICS = ["n", "control_mean", "treatment_mean", "difference", "ci95_low", "ci95_high", "p", "p_holm"]
TITLES = {
    "anonymous_birth": "匿名默认探针：12轮，结构继承",
    "anonymous_live": "匿名默认探针：12轮，持续路径",
    "literal_1": "明文1轮：同协议一致性对照",
    "literal_4": "明文4轮：稳定对混合配对",
    "literal_12": "明文12轮：稳定对混合配对",
    "dose_2": "匿名探针强度2：稳定对混合配对",
    "dose_4": "匿名探针强度4：稳定对混合配对",
    "relations": "关系组合：正确对错误模板",
}


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
            for path in sorted(WORK.glob("*-raw.zip")):
                self.artifact(job, path, "application/zip")
            for path in sorted(WORK.glob("*-check.json")):
                self.artifact(job, path, "application/json")
            for name, mime in (
                ("memory-summary.csv", "text/csv"),
                ("relations-summary.csv", "text/csv"),
                ("summary.json", "application/json"),
                ("analyze.py", "text/x-python"),
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
        summary = analyze()  # Recompute from retained measurements, never re-run Core.
        sources = {}
        for index, (key, value) in enumerate(summary["analyses"].items()):
            artifact_id = self.analysis(key, value, attachments=index == 0)
            sources[key] = self.source(key, artifact_id)
        text = (HERE / "report.md").read_text(encoding="utf-8")
        for filename in ("memory-results.png", "relation-results.png"):
            item = self.entry("image:" + filename)
            notebooks.save_asset(
                self.db, self.project, LOCAL_USER, item["id"], filename, (HERE / filename).read_bytes()
            )
            text = text.replace(f"]({filename})", f"](/api/v2/projects/{self.project}/note-assets/{item['id']})")
        links = ["\n## 冻结原始证据下载\n"]
        for key, item in self.state.items():
            if key.startswith("artifact:"):
                links.append(
                    f"- [{key[9:]}](/api/v2/projects/{self.project}/artifacts/{item['artifact_id']}) — SHA256 `{item['sha256']}`"
                )
        text += "\n".join(links)
        records = []
        groups = [
            (
                "memory",
                "实验记录一：重复配对与结构记忆",
                ["anonymous_birth", "anonymous_live", "literal_1", "literal_4", "literal_12"],
                (
                    "稳定对混合配对。匿名默认探针未测到净联想；明文条件出现配对特异激活。明文1轮是完全同协议的一致性对照。\n\n"
                    "匿名主终点 n=8 个编码种子；明文 n=2，仅描述，不把两者当独立统计证据。所有曲线、交换配对及关闭可塑性对照均在原始包和 CSV 中。"
                ),
            ),
            (
                "sensitivity",
                "实验记录二：匿名探针强度敏感性",
                ["dose_2", "dose_4"],
                (
                    "观察默认零结果后，仅复用前两个种子12轮训练父本，提高探针强度到2/4。训练结构、编码、内核均不变。"
                    "稳定与交换配对出现相反方向，关闭可塑性对照为零；不能将这个追加探索当作默认条件或预注册验证成功。n=2，仅描述。"
                ),
            ),
            (
                "relations",
                "实验记录三：关系组合与错误模板",
                ["relations"],
                (
                    "正确模板对错误祖父模板；两个种子内平均两个家系。某个正确名字虽出现过，但无关名字、错误模板、反向链也产生相近激活。"
                    "未验证出角色组合迁移，更不能据此宣称真实世界因果发现。查询排除共享/直接通道后，有的候选只剩1–2个专属通道；这是测量限制。n=2，仅描述。"
                ),
            ),
        ]
        for key, title, endpoints, description in groups:
            blocks = [
                commentary("purpose", description, "purpose"),
                commentary(
                    "method",
                    "主要量为探针后0.2–1.0秒目标减干扰、再减无探针的平均激活；先在种子内平均探针。零值如实保留，未实施推断的区间和 p 值为空。",
                    "methods",
                ),
            ]
            for endpoint in endpoints:
                blocks.extend(
                    [
                        {
                            "id": "chart_" + endpoint,
                            "type": "chart",
                            "source": sources[endpoint],
                            "metric": "difference",
                            "chart": "bar",
                            "analysis_metric": summary["analyses"][endpoint]["metrics"][0]["metric"],
                            "title": TITLES[endpoint] + "（处理组减对照组）",
                        },
                        {
                            "id": "table_" + endpoint,
                            "type": "table",
                            "source": sources[endpoint],
                            "metrics": METRICS,
                            "title": TITLES[endpoint] + "：冻结数值",
                        },
                    ]
                )
            blocks.append(commentary("downloads", "\n".join(links), "other"))
            record = self.document(key, "record", title, [sources[k] for k in endpoints], blocks)
            records.extend(
                {
                    "id": f"ref_{endpoint}_{type_}",
                    "type": "record_block",
                    "record_id": record,
                    "revision": 1,
                    "block_id": f"{type_}_{endpoint}",
                }
                for endpoint in endpoints
                for type_ in ("chart", "table")
            )
        report_id = self.document(
            "report",
            "report",
            "探索报告：重复关联与关系组合（2026-09-09）",
            [],
            [commentary("report", text, "discussion"), *records],
        )
        item = self.entry("note:results")
        if not item.get("revision"):
            saved = notebooks.save_note(
                self.db,
                self.project,
                LOCAL_USER,
                item["id"],
                {
                    "operation_id": item["operation_id"],
                    "expected_revision": 0,
                    "title": "实验总结：可读配对关联、匿名探针敏感性与关系组合边界",
                    "kind": "note",
                    "collection_id": self.meta["notebook_id"],
                    "body": {"format": "markdown", "text": text},
                },
            )
            item["revision"] = saved["revision"]
            self.flush()
        for format_ in ("markdown", "html"):
            item = self.entry("export:" + format_)
            self.service_job(
                item,
                lambda item=item, format_=format_: report_exports.request(
                    self.db,
                    self.project,
                    LOCAL_USER,
                    report_id,
                    {
                        "operation_id": item["operation_id"],
                        "revision": 1,
                        "format": format_,
                        "language": "zh-CN",
                        "include_data": True,
                    },
                ),
                report_exports.execute,
            )
        self.flush()
        print("Published three records, one report, final note and Markdown/HTML evidence exports.")


if __name__ == "__main__":
    publisher = Publisher()
    try:
        publisher.publish()
    finally:
        publisher.db.close()
