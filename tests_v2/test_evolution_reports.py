import copy
import io
import json
import zipfile
from uuid import uuid4

import pytest
from test_api import client_for
from test_evolution import campaign, drain

from threemind_lab import evolution_export, research_ai
from threemind_lab.worker import Worker


def test_complete_generation_sources_preserve_losers_blocks_and_verification_boundary(database):
    project, created, _ = campaign(database)
    worker = Worker(database)
    with client_for(database) as client:
        base = f"/api/v2/projects/{project}"
        declaration = {
            "operation_id": str(uuid4()),
            "kind": "evolution",
            "evolution_id": str(created["id"]),
            "evolution_generation": 0,
            "evolution_stage": "selection",
        }
        assert client.post(base + "/report-sources", json=declaration).status_code == 409
        assert drain(worker, project, created["id"])["status"] == "completed"
        assert client.post(base + "/report-sources", json=declaration | {"run_id": str(uuid4())}).status_code == 422
        assert client.post(base + "/report-sources", json=declaration | {"metrics": ["activation"]}).status_code == 422
        assert (
            client.post(base + "/report-sources", json=declaration | {"evolution_stage": "verification"}).status_code
            == 422
        )
        sources = []
        for stage, generation, count in (("selection", 0, 2), ("evaluation", 0, 4), ("verification", 1, 4)):
            request = declaration | {
                "operation_id": str(uuid4()),
                "evolution_stage": stage,
                "evolution_generation": generation,
            }
            response = client.post(base + "/report-sources", json=request)
            assert response.status_code == 202, response.text
            identity = response.json()["id"]
            assert client.post(base + "/report-sources", json=request).json()["id"] == identity
            assert worker.once()
            source = client.get(base + f"/report-sources/{identity}").json()
            assert source["status"] == "done", source["error"]
            assert source["row_count"] == count
            assert source["manifest"]["provenance"]["stage"] == stage
            assert source["manifest"]["coverage"]["lifetime_right_censored_blocks"] == 4
            assert source["manifest"]["coverage"]["verification_used_for_selection"] is False
            rows = client.get(base + f"/report-sources/{identity}/rows").json()["rows"]
            assert {row["provenance"]["slot"] for row in rows} == {0, 1}
            assert all(row["time_us"] is None for row in rows)
            if stage == "selection":
                assert {r["provenance"]["selected"] for r in rows} == {True, False}
                assert all(len(r["provenance"]["evidence"]["blocks"]) == 2 for r in rows)
            else:
                assert all(row["provenance"]["checkpoint_id"] for row in rows)
            template = client.get(base + f"/report-sources/{identity}/template").json()
            rendered = client.post(base + "/research-documents/preview", json=template)
            assert rendered.status_code == 200, rendered.text
            assert any(block.get("chart") == "histogram" for block in rendered.json()["blocks"])
            sources.append(identity)
        with database.tx(project) as db:
            evidence = research_ai.prepare(
                db, {"kind": "record", "sources": sources, "objective": "Summarize the declared experiment"}
            )
            assert all(s["provenance"]["inference_boundary"] for s in evidence["evidence"]["sources"])
        document = str(uuid4())
        saved = client.put(
            base + f"/research-documents/{document}",
            json={"operation_id": str(uuid4()), "expected_revision": 0, "spec": template},
        )
        assert saved.status_code == 200, saved.text
        exported = client.post(
            base + f"/research-documents/{document}/exports",
            json={"operation_id": str(uuid4()), "revision": 1, "format": "html", "include_data": True},
        )
        assert exported.status_code == 202, exported.text
        old_runtime = copy.deepcopy(worker.capabilities)
        old_runtime["features"].pop("worker.evolution_v1")
        assert database.claim("old-document-worker", capabilities=old_runtime) is None
        assert worker.once()
        record = client.get(base + f"/research-documents/{document}/exports").json()["rows"][0]
        assert record["status"] == "done", record.get("error")
        from cryptography.fernet import Fernet
        from test_ai_providers import create, get_call
        from test_research_ai import ask, reply

        from threemind_lab.config import Settings

        settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
        provider = create(database, settings, project)
        scope = {"kind": "record", "sources": [sources[-1]], "objective": "Describe the held-out verification fixture"}
        call, _, _ = ask(database, settings, project, provider, scope)
        old_ai = {
            "queue": "ai",
            "features": {
                name: {"state": "available"}
                for name in ("worker.ai", "worker.research_events_v1", "worker.research_ai_v1")
            },
        }
        assert database.claim("old-evolution-author", queue="ai", capabilities=old_ai) is None
        template["blocks"][-1]["markdown"] = (
            "Engineering fixture; shared ancestry is not independent evolutionary replication."
        )
        assert reply(database, settings, json.dumps(template)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "recorded"


def test_campaign_export_budget_fails_without_a_truncated_success_file(monkeypatch):
    monkeypatch.setattr(evolution_export, "EXPORT_BYTES", 20)
    with zipfile.ZipFile(io.BytesIO(), "w") as archive:
        package = evolution_export.CampaignArchive(archive)
        package.bytes("one", b"1234567890")
        with pytest.raises(ValueError, match="未保存截断文件"):
            package.write("two", [b"12345", b"123456"])
        assert "two" not in package.files
