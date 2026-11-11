import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from test_data_bundles import records  # noqa: F401 - shared disposable record fixture

from threemind_lab import data_cli, research_documents
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.operations_client import OperationsClient
from threemind_lab.worker import Worker


def test_real_cli_api_download_import_native_restore_keeps_original_history(records, tmp_path, monkeypatch, capsys):  # noqa: F811 - imported pytest fixture
    database, project, target, _actor, document, note, _asset = records
    original_hashes = [
        research_documents.get(database, project, document, revision)["content_hash"] for revision in (1, 2)
    ]
    app = create_app(Settings(database.test_url, docs_root=tmp_path), database)
    with TestClient(app) as api:

        def forward(request):
            response = api.request(
                request.method,
                request.url.raw_path.decode("ascii"),
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(response.status_code, content=response.content, headers=dict(response.headers))

        monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(forward)))

        def command(action, destination=project, *arguments):
            data_cli.main([action, "--project", str(destination), *map(str, arguments)])
            return json.loads(capsys.readouterr().out)

        selection = tmp_path / "selection.json"
        selection.write_text(
            json.dumps({"resources": [{"kind": "document", "id": str(document)}, {"kind": "note", "id": str(note)}]}),
            encoding="utf-8",
        )
        plan = command("export-plan", project, "--json", selection)
        task = command("export", project, "--plan", plan["id"])
        worker = Worker(database, backend="reference", name="disposable-data-transport")
        # This fixture advertises only the data handler being tested; no engine,
        # renderer, provider or physical-device capability is probed or claimed.
        worker.capabilities = {
            "schema": "threemind.capabilities/1",
            "backend": "reference",
            "kernels": {},
            "features": {"worker.data_bundle_v1": {"state": "available"}},
        }
        assert worker.once()
        done = command("job-status", project, "--id", task["id"])
        assert done["status"] == "done", done.get("error")
        bundle = done["result"]["bundle_id"]
        output = tmp_path / "records.tmdata"
        downloaded = command("download", project, "--bundle", bundle, "--output", output)
        assert downloaded["bytes"] == output.stat().st_size
        preview = command("preflight", target, "--file", output)
        assert not preview["missing_required"] and preview["can_restore"] and not preview["can_resume"]
        imported = command("import", target, "--file", output)
        restored = command("restore-records", target, "--bundle", imported["id"])
        assert worker.once()
        completed = command("job-status", target, "--id", restored["id"])
        assert completed["status"] == "done", completed.get("error")
        mapping = next(row for row in completed["result"]["mappings"] if row["old_id"] == str(document))
        assert mapping["new_id"] != str(document)
        assert (
            research_documents.get(database, target, mapping["new_id"], 1)["spec"]["blocks"][0]["markdown"]
            == "version 1"
        )
        assert (
            research_documents.get(database, target, mapping["new_id"], 2)["spec"]["blocks"][0]["markdown"]
            == "version 2"
        )
        origin = command("object", target, "--bundle", imported["id"], "--id", "note:" + str(note))
        assert origin["mode"] == "read_only_original" and str(project) in str(origin["original"])
    assert original_hashes == [
        research_documents.get(database, project, document, revision)["content_hash"] for revision in (1, 2)
    ]


def test_offline_cli_export_download_and_project_origin_import(records, tmp_path, monkeypatch, capsys):  # noqa: F811 - imported pytest fixture
    database, _project, target_project, _actor, _document, _note, _asset = records
    root = tmp_path / "offline-source"
    root.mkdir()
    (root / "experiment").mkdir()
    original = b'{"historical_result":true}\r\n'
    (root / "experiment/result.json").write_bytes(original)
    storage = database.blobs.storage
    target = storage.register_target(root, "disposable offline files")
    storage.register_resource("offline-test", storage.locator(target["id"], "experiment"), writer_mode="sealed")
    app = create_app(Settings(database.test_url, docs_root=tmp_path), database)
    with TestClient(app) as api:

        def forward(request):
            response = api.request(
                request.method,
                request.url.raw_path.decode("ascii"),
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(response.status_code, content=response.content, headers=dict(response.headers))

        monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(forward)))

        def host(action, *arguments):
            data_cli.storage_main([action, *map(str, arguments)])
            return json.loads(capsys.readouterr().out)

        operation = str(uuid4())
        exported = host("export", "--id", "offline-test", "--expected-revision", 1, "--request-id", operation)
        assert exported["id"] == operation and exported["state"] == "complete"
        master = tmp_path / "set.tmdata.json"
        volume = tmp_path / "records.tmdata"
        host("export-manifest", "--id", operation, "--output", master)
        host("export-download", "--id", operation, "--output", volume)
        assert host("export-status", "--id", operation)["resource_id"] == "offline-test"

        def project(action):
            data_cli.main(
                [action, "--project", str(target_project), "--manifest-file", str(master), "--file", str(volume)]
            )
            return json.loads(capsys.readouterr().out)

        preview = project("preflight")
        assert not preview["can_restore"] and not preview["can_resume"] and not preview["missing_required"]
        imported = project("import")
        data_cli.main(
            [
                "object",
                "--project",
                str(target_project),
                "--bundle",
                imported["id"],
                "--id",
                "research_directory:offline-test",
            ]
        )
        origin = json.loads(capsys.readouterr().out)
        assert origin["mode"] == "read_only_original"
        assert origin["original"]["read_as"] == "opaque original bytes"
        from threemind_lab.data_archive import DataReader

        with (
            master.open("rb") as master_stream,
            volume.open("rb") as volume_stream,
            DataReader({"manifest": master_stream, "volumes": [volume_stream]}) as archive,
        ):
            assert archive.manifest["recovery"]["source_project"] is None
            assert archive.manifest["recovery"]["source_scope"] == "host-research-resource"
            assert archive.json("research/resource.json")["capabilities"] == {
                "view": True,
                "native_restore": False,
                "resume": False,
            }
            assert b"".join(archive.chunks("research/files/result.json")) == original
    assert (root / "experiment/result.json").read_bytes() == original
