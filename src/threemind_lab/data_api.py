"""Project data and host storage facades; services retain their canonical checks."""

import hashlib
import json
from copy import deepcopy
from typing import Annotated, Literal
from uuid import UUID

from fastapi import BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import Field

from . import auth
from .database import Forbidden
from .protocols import StrictModel
from .storage_files import StorageConflict, checked_path, read_json, under_root
from .storage_migration import MigrationService


class Operation(StrictModel):
    operation_id: UUID


class ExportPlan(Operation):
    selection: dict


class BundleExport(Operation):
    plan_id: UUID


class ResearchExport(Operation):
    resource_id: str = Field(min_length=1, max_length=160)
    expected_revision: int = Field(ge=1, strict=True)


class BundleResume(Operation):
    object_id: str = Field(min_length=1, max_length=160)
    name: str = Field(default="Imported subject", min_length=1, max_length=120)
    acknowledge_external_changes: bool = False
    backend: Literal["native", "reference"] | None = None


class Target(StrictModel):
    target_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["filesystem", "s3", "db"]
    path: str | None = None
    configuration: dict = Field(default_factory=dict)
    credentials: dict | None = None
    expected_revision: int = Field(ge=0, strict=True)


class Policy(StrictModel):
    target_id: str
    expected_revision: int = Field(ge=0, strict=True)


class Resource(StrictModel):
    resource_id: str
    target_id: str
    relative_path: str
    legacy_paths: list[str] = Field(default_factory=list, max_length=100)
    registered_work_path: str | None = None
    writer_mode: Literal["unknown", "sealed", "cooperative"] = "unknown"
    expected_revision: int = Field(ge=0, strict=True)


class MigrationPlan(StrictModel):
    resource_id: str
    target_id: str
    relative_path: str | None = None
    expected_revision: int = Field(ge=1, strict=True)
    request_id: UUID


class MigrationAction(StrictModel):
    request_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class RootPreview(StrictModel):
    destination: str


class ExperimentDirectory(StrictModel):
    id: str
    path: str
    priority: int = Field(default=0, ge=0, strict=True)
    limit_bytes: int | None = Field(default=None, ge=0, strict=True)
    reserve_bytes: int = Field(default=0, ge=0, strict=True)
    enabled: bool = True
    role: Literal["run", "archive", "backup"] | None = None


class ExperimentDirectories(StrictModel):
    expected_revision: int = Field(ge=0, strict=True)
    directories: list[ExperimentDirectory] = Field(max_length=64)


class ExperimentPart(StrictModel):
    name: str
    bytes: int = Field(gt=0, strict=True)
    kind: Literal["data", "archive", "readback"] = "data"


class ExperimentPlacement(StrictModel):
    name: str
    parts: list[ExperimentPart] = Field(min_length=1, max_length=128)
    allow_split: bool = False


class ExperimentReadback(StrictModel):
    part: str
    member: str


class ExperimentTransfer(StrictModel):
    operation: Literal["sync", "backup", "migrate", "archive", "unarchive", "restore"]
    name: str
    destination: str
    backup: str | None = None
    restore_as: str | None = None


class HistoricalExperiment(StrictModel):
    name: str
    directory: str


class PortableExperimentBackup(HistoricalExperiment):
    backup: str


class RootPlan(RootPreview, Operation):
    expected_revision: int = Field(ge=0, strict=True)


class PayloadMove(Operation):
    kind: Literal["artifact", "media", "note-image", "checkpoint", "blob"]
    object_id: str
    target_id: str


class CheckpointStorage(StrictModel):
    backend: Literal["database", "filesystem"]
    expected_revision: int = Field(ge=0, strict=True)


class Cleanup(StrictModel):
    token: str = Field(min_length=64, max_length=64)
    confirm_name: str = Field(min_length=1, max_length=160)


def host_admin(request, *, write=False):
    from . import permissions
    actor = auth.identity(request, mutate=write)
    return permissions.require(request.app.state.db, actor, "data.manage" if write else "data.read")


def public_target(row):
    result = deepcopy(row)
    config = result["configuration"]
    result["has_secret"] = bool(config.pop("encrypted_secret", None))
    return result


def migration_summary(row):
    result = deepcopy(row)
    entries = result.pop("entries", [])
    result["entries_count"] = len(entries)
    return result


def registered_artifacts(storage):
    """Only published exact-file manifests; no enumeration of archive contents."""
    rows = {}
    for path in (storage.repository_root / "lab/artifact-index").glob("*-relocations.json"):
        manifest = read_json(path)
        if manifest.get("schema") != "threemind.research-artifact-relocations/1":
            raise ValueError("unsupported research artifact location manifest")
        for entry in manifest.get("entries", []):
            if not isinstance(entry, dict):
                raise ValueError("invalid research artifact location metadata")  # noqa: TRY004 - API validation
            if entry.get("state") != "verified":
                continue
            required = {"resource_id", "legacy_path", "archive_path", "bytes", "sha256"}
            if not required <= entry.keys():
                raise ValueError("incomplete verified research artifact location")
            row = {key: entry[key] for key in required} | {
                "state": "verified",
                "batch": manifest.get("batch"),
                "snapshot_commit": manifest.get("snapshot_commit"),
            }
            previous = rows.get(row["resource_id"])
            if previous and any(previous[key] != row[key] for key in required):
                raise StorageConflict("research artifact has conflicting recorded identities")
            rows[row["resource_id"]] = row
    return sorted(rows.values(), key=lambda row: (row["legacy_path"], row["resource_id"]))


def research_export_directory(storage, export_id):
    return checked_path(storage.control_dir / "data-transfers" / ("host-" + str(UUID(str(export_id)))))


def research_export_receipt(storage, export_id):
    destination = research_export_directory(storage, export_id)
    try:
        receipt = read_json(destination / "receipt.json", maximum=4 * 1024**2)
    except FileNotFoundError:
        raise HTTPException(404, "registered offline research data export") from None
    if (
        receipt.get("schema") != "threemind.research-data-export/1"
        or receipt.get("state") != "complete"
        or receipt.get("id") != str(export_id)
        or receipt.get("filename") != "manifest.tmdata.json"
        or not isinstance(receipt.get("volumes"), list)
        or not 1 <= len(receipt["volumes"]) <= 32
        or any(not isinstance(row, dict) or row.get("ordinal") != index for index, row in enumerate(receipt["volumes"]))
        or type(receipt.get("manifest_bytes")) is not int
        or not 0 <= receipt["manifest_bytes"] <= 4 * 1024**2
        or not isinstance(receipt.get("manifest_sha256"), str)
    ):
        raise StorageConflict("offline research export receipt is incomplete or unsupported")
    storage.resource(receipt.get("resource_id"))
    return receipt


def research_export_file(storage, export_id, row):
    name = row.get("filename")
    if not isinstance(name, str) or "/" in name or "\\" in name:
        raise StorageConflict("offline research export file must be registered by basename")
    if type(row.get("bytes")) is not int or not 0 <= row["bytes"] <= 8 * 1024**3:
        raise StorageConflict("offline research export file has an invalid byte budget")
    path = under_root(research_export_directory(storage, export_id), name)
    checksum, size = hashlib.sha256(), 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(4 * 1024**2):
                size += len(chunk)
                if size > row["bytes"]:
                    raise StorageConflict("offline research export byte length differs from its receipt")
                checksum.update(chunk)
    except FileNotFoundError:
        raise HTTPException(503, "registered offline research export file is unavailable") from None
    if size != row["bytes"] or checksum.hexdigest() != row.get("sha256"):
        raise StorageConflict("offline research export bytes differ from their registered receipt")
    return path


def register(app, access):
    @app.middleware("http")
    async def import_admission(request, call_next):
        path = request.url.path
        if (
            request.method == "POST"
            and path.startswith("/api/v2/projects/")
            and path.endswith(("/data/imports", "/data/imports/preflight"))
        ):
            from fastapi.responses import JSONResponse
            from starlette.concurrency import run_in_threadpool

            try:
                await run_in_threadpool(access, request, UUID(path.split("/")[4]), write=True)
                length = request.headers.get("content-length")
                if length is None:
                    return JSONResponse({"detail": "data upload requires a declared bounded content length"}, 411)
                if not 0 <= int(length) <= app.state.settings.max_staged_media_bytes:
                    return JSONResponse({"detail": "data upload exceeds the staging budget"}, 413)
            except HTTPException as error:
                return JSONResponse({"detail": error.detail}, error.status_code)
            except Forbidden as error:
                return JSONResponse({"detail": str(error)}, 403)
            except ValueError:
                return JSONResponse({"detail": "invalid data upload size or project"}, 422)
        return await call_next(request)

    def services():
        from .data_bundles import DataBundles
        from .data_catalog import DataCatalog

        return DataCatalog(app.state.db), DataBundles(app.state.db)

    def storage():
        return app.state.db.blobs.storage

    def migration():
        return MigrationService(storage())

    @app.exception_handler(StorageConflict)
    async def storage_conflict(_, error):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(error)}, 409)

    base = "/api/v2/projects/{project}/data"

    @app.get(base)
    def data_resources(
        project: UUID,
        request: Request,
        q: str = "",
        kind: str | None = None,
        type: str | None = None,
        backend: Literal["db", "filesystem", "s3"] | None = None,
        archived: Literal["all", "active", "archived"] = "all",
        experiment: str | None = None,
        run: str | None = None,
        population: str | None = None,
        batch: str | None = None,
        dataset: str | None = None,
        tag: str | None = None,
        after: str | None = None,
        before: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        actor = access(request, project)
        filters = {
            key: value
            for key, value in locals().copy().items()
            if key
            in (
                "q",
                "kind",
                "type",
                "backend",
                "archived",
                "experiment",
                "run",
                "population",
                "batch",
                "dataset",
                "tag",
                "after",
                "before",
            )
            and value is not None
            and value != ""
        }
        return services()[0].list(project, actor["id"], filters, offset=offset, limit=limit)

    @app.get(base + "/resources/{kind}/{resource_id}")
    def data_detail(project: UUID, kind: str, resource_id: str, request: Request):
        actor = access(request, project)
        return services()[0].detail(project, actor["id"], kind, resource_id)

    @app.post(base + "/export-plans", status_code=201)
    def data_export_plan(project: UUID, request: Request, body: ExportPlan):
        actor = access(request, project, write=True)
        return services()[0].export_plan(project, actor["id"], body.selection, op_id=body.operation_id)

    @app.post(base + "/exports", status_code=202)
    def data_export(project: UUID, request: Request, body: BundleExport):
        actor = access(request, project, write=True)
        return services()[1].export(project, actor["id"], body.plan_id, body.operation_id)

    @app.get(base + "/export-plans/{plan_id}")
    def data_plan(project: UUID, plan_id: UUID, request: Request):
        actor = access(request, project)
        return services()[0].plan(project, actor["id"], plan_id)

    @app.get(base + "/jobs/{job_id}")
    def data_job(project: UUID, job_id: UUID, request: Request):
        actor = access(request, project)
        return services()[1].status(project, actor["id"], job_id)

    @app.post(base + "/jobs/{job_id}/cancel")
    def cancel_data_job(project: UUID, job_id: UUID, request: Request, body: Operation):
        actor = access(request, project, write=True)
        return services()[1].cancel(project, actor["id"], job_id)

    @app.get(base + "/bundles")
    def data_bundles(
        project: UUID, request: Request, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ):
        actor = access(request, project)
        return services()[1].list(project, actor["id"], offset=offset, limit=limit)

    @app.get(base + "/bundles/{bundle_id}")
    def data_bundle_detail(project: UUID, bundle_id: UUID, request: Request):
        actor = access(request, project)
        return services()[1].detail(project, actor["id"], bundle_id)

    @app.get(base + "/bundles/{bundle_id}/manifest")
    def data_bundle_manifest(project: UUID, bundle_id: UUID, request: Request):
        actor = access(request, project)
        detail = services()[1].detail(project, actor["id"], bundle_id)
        raw = json.dumps(detail["manifest"], ensure_ascii=False, default=str).encode()
        return StreamingResponse(
            iter([raw]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{bundle_id}.tmdata.json"'},
        )

    @app.get(base + "/bundles/{bundle_id}/objects/{object_id}")
    def data_object(project: UUID, bundle_id: UUID, object_id: str, request: Request):
        actor = access(request, project)
        return services()[1].object(project, actor["id"], bundle_id, object_id)

    @app.get(base + "/bundles/{bundle_id}/volumes/{volume}")
    def data_bundle_volume(project: UUID, bundle_id: UUID, volume: int, request: Request):
        actor = access(request, project)
        service = services()[1]
        detail = service.detail(project, actor["id"], bundle_id)
        row = next((row for row in detail["volumes"] if row["ordinal"] == volume), None)
        if row is None:
            raise HTTPException(404, "bundle volume")
        # The filename is generated by this server, never a source archive entry.
        return StreamingResponse(
            service.chunks(project, actor["id"], bundle_id, volume=volume),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{bundle_id}-{volume}.tmdata"',
                "Content-Length": str(row["bytes"]),
                "X-Content-SHA256": row["sha256"],
            },
        )

    async def uploads(request, files, manifest):
        budget = app.state.settings.max_staged_media_bytes
        total = 0
        if not files or len(files) > 128:
            raise ValueError("choose one to 128 data bundle volumes")
        for upload in files + ([manifest] if manifest else []):
            size = upload.size
            if size is None or size > (32 * 1024**2 if upload is manifest else 8 * 1024**3):
                raise HTTPException(413, "data bundle volume exceeds its byte budget")
            total += size
            await upload.seek(0)
        if total > budget:
            raise HTTPException(413, "data bundle exceeds the deployment's explicit staging budget")
        if manifest:
            return {"manifest": manifest.file, "volumes": [item.file for item in files]}
        if len(files) != 1:
            raise ValueError("multiple volumes require their total manifest")
        return files[0].file

    @app.post(base + "/imports/preflight")
    async def data_import_preflight(
        project: UUID,
        request: Request,
        files: Annotated[list[UploadFile], File()],
        manifest: Annotated[UploadFile | None, File()] = None,
        backend: Annotated[Literal["native", "reference"] | None, Form()] = None,
    ):
        actor = access(request, project, write=True)
        stream = await uploads(request, files, manifest)
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(
            services()[1].preflight, project, actor["id"], stream, backend=backend or app.state.settings.backend
        )

    @app.post(base + "/imports", status_code=201)
    async def data_import(
        project: UUID,
        request: Request,
        operation_id: Annotated[UUID, Form()],
        files: Annotated[list[UploadFile], File()],
        name: Annotated[str, Form()] = "Imported data bundle",
        manifest: Annotated[UploadFile | None, File()] = None,
    ):
        actor = access(request, project, write=True)
        if not 1 <= len(name) <= 120:
            raise ValueError("bundle name requires one to 120 characters")
        stream = await uploads(request, files, manifest)
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(
            services()[1].import_register, project, actor["id"], stream, operation_id, name=name
        )

    @app.post(base + "/bundles/{bundle_id}/restore-records", status_code=202)
    def restore_records(project: UUID, bundle_id: UUID, request: Request, body: Operation):
        actor = access(request, project, write=True)
        return services()[1].restore_records(project, actor["id"], bundle_id, body.operation_id)

    @app.get(base + "/bundles/{bundle_id}/resume-plan")
    def resume_plan(
        project: UUID,
        bundle_id: UUID,
        request: Request,
        object_id: str,
        backend: Literal["native", "reference"] | None = None,
    ):
        actor = access(request, project)
        return services()[1].resume_plan(
            project, actor["id"], bundle_id, object_id, backend=backend or app.state.settings.backend
        )

    @app.post(base + "/bundles/{bundle_id}/resumes", status_code=202)
    def resume_bundle(project: UUID, bundle_id: UUID, request: Request, body: BundleResume):
        actor = access(request, project, write=True)
        return services()[1].resume(
            project,
            actor["id"],
            bundle_id,
            body.object_id,
            body.operation_id,
            name=body.name,
            acknowledge_external_changes=body.acknowledge_external_changes,
            backend=body.backend or app.state.settings.backend,
        )

    @app.get(base + "/integrity")
    def integrity(
        project: UUID,
        request: Request,
        verify: bool = False,
        maximum_objects: int = Query(100, ge=1, le=1000),
        maximum_bytes: int = Query(1024**3, ge=1, le=20 * 1024**3),
    ):
        actor = access(request, project)
        return app.state.db.blobs.audit(
            app.state.db,
            project,
            actor=actor["id"],
            verify=verify,
            maximum_objects=maximum_objects,
            maximum_bytes=maximum_bytes,
        )

    @app.get(base + "/blob-candidates")
    def blob_candidates(project: UUID, request: Request, maximum_records: int = Query(200, ge=1, le=1000)):
        access(request, project, owner=True)
        return app.state.db.blobs.candidate_inventory(app.state.db, project, maximum_records=maximum_records)

    @app.get(base + "/blob-candidates/{candidate_id}/cleanup-preview")
    def blob_cleanup_preview(project: UUID, candidate_id: UUID, request: Request):
        access(request, project, owner=True)
        return app.state.db.blobs.cleanup_preview(app.state.db, project, candidate_id)

    @app.post(base + "/blob-candidates/{candidate_id}/cleanup")
    def blob_cleanup(project: UUID, candidate_id: UUID, request: Request, body: Cleanup):
        access(request, project, owner=True)
        return app.state.db.blobs.cleanup_execute(
            app.state.db, project, candidate_id, token=body.token, confirm_name=body.confirm_name
        )

    host = "/api/v2/storage"

    def pool():
        from .experiment_storage import ExperimentStorage

        return ExperimentStorage(storage())

    def transfers():
        from .experiment_transfers import ExperimentTransfers

        return ExperimentTransfers(pool())

    transfer_path = host + "/experiment-pool/transfers"

    @app.get(transfer_path)
    def experiment_transfers(request: Request):
        host_admin(request)
        return transfers().catalog()

    @app.get(transfer_path + "/discover")
    def discover_experiments(request: Request, directory: str):
        host_admin(request)
        return {"names": transfers().discover(directory)}

    @app.post(transfer_path + "/adopt")
    def adopt_experiment(request: Request, body: HistoricalExperiment):
        host_admin(request, write=True)
        return transfers().adopt(**body.model_dump())

    @app.post(transfer_path + "/import-backup")
    def register_experiment_backup(request: Request, body: PortableExperimentBackup):
        host_admin(request, write=True)
        return transfers().import_backup(**body.model_dump())

    @app.post(transfer_path + "/preview")
    def preview_experiment_transfer(request: Request, body: ExperimentTransfer):
        host_admin(request)
        return transfers().preview(**body.model_dump())

    @app.post(transfer_path + "/jobs", status_code=202)
    def start_experiment_transfer(request: Request, body: ExperimentTransfer, tasks: BackgroundTasks):
        from .operation_receipts import HEADER

        host_admin(request, write=True)
        service = transfers()
        job = service.create(**body.model_dump(), job_id=request.headers.get(HEADER))
        tasks.add_task(service.background, job["id"], "run")
        return job

    @app.get(transfer_path + "/jobs/{job_id}")
    def experiment_transfer_status(job_id: UUID, request: Request):
        host_admin(request)
        return transfers().job(str(job_id))

    @app.post(transfer_path + "/jobs/{job_id}/{action}")
    def manage_experiment_transfer(job_id: UUID, action: Literal["resume", "cancel", "release"], request: Request,
                                   tasks: BackgroundTasks):
        host_admin(request, write=True)
        service = transfers()
        job = service.job(str(job_id))
        if action == "cancel":
            return service.cancel(job["id"])
        if action == "release" and (job["status"] not in ("complete", "released")
                                    or job["operation"] not in ("migrate", "archive", "unarchive")):
            raise StorageConflict("no verified source is available for release")
        if action == "release" and job["status"] == "complete":
            service.update(job["id"], release_pending=True, error=None)
        tasks.add_task(service.background, job["id"], "release" if action == "release" else "run")
        return service.job(job["id"])

    @app.get(host + "/experiment-pool")
    def pool_status(request: Request):
        host_admin(request)
        return pool().status()

    @app.put(host + "/experiment-pool")
    def pool_configure(request: Request, body: ExperimentDirectories):
        host_admin(request, write=True)
        return pool().configure(**body.model_dump())

    @app.post(host + "/experiment-pool/preview")
    def pool_preview(request: Request, body: ExperimentPlacement):
        host_admin(request)
        return pool().preview(**body.model_dump())

    @app.post(host + "/experiment-pool/reserve")
    def pool_reserve(request: Request, body: ExperimentPlacement):
        host_admin(request, write=True)
        return pool().reserve(**body.model_dump())

    @app.get(host + "/experiment-pool/studies/{name}")
    def pool_study(name: str, request: Request):
        host_admin(request)
        return pool().study(name)

    @app.get(host + "/experiment-pool/studies/{name}/path")
    def pool_path(name: str, request: Request, part: str | None = None):
        host_admin(request)
        return {"path": str(pool().path(name, part))}

    @app.get(host + "/experiment-pool/studies/{name}/manifest")
    def pool_manifest(name: str, request: Request):
        from .experiment_volumes import manifest_path

        host_admin(request)
        service = pool()
        path = manifest_path(service, service.study(name)["name"])
        if not path.exists():
            raise HTTPException(404, "archive has not been published")
        return read_json(path)

    @app.post(host + "/experiment-pool/studies/{name}/extract")
    def pool_extract(name: str, body: ExperimentReadback, request: Request):
        from .experiment_volumes import extract_member

        host_admin(request, write=True)
        return extract_member(pool(), name, body.part, body.member)

    @app.get(host + "/experiment-pool/studies/{name}/member")
    def pool_member(name: str, member: str, request: Request):
        from contextlib import ExitStack
        from urllib.parse import quote

        from starlette.background import BackgroundTask

        from .experiment_volumes import CHUNK, open_member

        host_admin(request)
        stack = ExitStack()
        entry, stream = stack.enter_context(open_member(pool(), name, member))

        def blocks():
            with stack:
                while chunk := stream.read(CHUNK):
                    yield chunk

        filename = quote(member.rsplit("/", 1)[-1], safe="")
        return StreamingResponse(
            blocks(),
            media_type="application/octet-stream",
            background=BackgroundTask(stack.close),
            headers={
                "Content-Length": str(entry.file_size),
                "Content-Disposition": "attachment; filename*=UTF-8''" + filename,
            },
        )

    @app.post(host + "/experiment-pool/studies/{name}/verify")
    def pool_verify(name: str, request: Request):
        from .experiment_volumes import verify_archive

        host_admin(request)
        return verify_archive(pool(), name)

    @app.post(host + "/experiment-pool/studies/{name}/{action}")
    def pool_action(name: str, action: Literal["finish", "cancel", "archive"], request: Request):
        from .experiment_volumes import create_archive

        host_admin(request, write=True)
        service = pool()
        if action == "archive":
            return create_archive(service, name)
        return getattr(service, action)(name)

    @app.get(host + "/experiment-pool/studies/{name}/volumes/{part}")
    def pool_download(name: str, part: str, request: Request):
        from .experiment_volumes import manifest_path

        host_admin(request)
        service = pool()
        study = service.study(name)
        index = manifest_path(service, study["name"])
        if not index.is_file():
            raise HTTPException(404, "archive has not been published")
        manifest = read_json(index)
        if not any(row["part"] == part for row in manifest["volumes"]):
            raise HTTPException(404, "unknown published archive volume")
        return FileResponse(
            under_root(service.path(name, part), "evidence.zip.part"), filename=f"{name}.{part}.zip.part"
        )

    @app.get(host)
    def storage_overview(request: Request):
        host_admin(request)
        return storage().host_info() | {
            "data_root": storage().root_info(),
            "checkpoint_backend": app.state.db.checkpoint_backend,
            "checkpoint_settings": storage().checkpoint_settings(),
            "targets": [public_target(row) for row in storage().targets()],
            "policies": app.state.db.blobs.policies(),
            "features": app.state.db.blobs.features(),
            "resources": storage().resources(),
            "backup": {"interface": "threemind storage backup", "automatic": False},
        }

    @app.put(host + "/checkpoint-backend")
    def checkpoint_backend(request: Request, body: CheckpointStorage):
        host_admin(request, write=True)
        return storage().set_checkpoint_backend(body.backend, expected_revision=body.expected_revision)

    @app.post(host + "/root-changes/preview")
    def root_preview(request: Request, body: RootPreview):
        from .storage_root import RootChanges, summary

        return summary(RootChanges(app.state.db).preview(body.destination, host_admin(request)))

    @app.post(host + "/root-changes", status_code=201)
    def root_plan(request: Request, body: RootPlan):
        from .storage_root import RootChanges, summary

        actor = host_admin(request, write=True)
        return summary(
            RootChanges(app.state.db).plan(
                body.destination, actor, operation_id=body.operation_id, expected_revision=body.expected_revision
            )
        )

    @app.get(host + "/root-changes/{change_id}")
    def root_status(change_id: UUID, request: Request):
        from .storage_root import RootChanges, summary

        host_admin(request)
        return summary(RootChanges(app.state.db).status(change_id))

    @app.get(host + "/root-changes/{change_id}/manifest")
    def root_manifest(change_id: UUID, request: Request):
        from .storage_root import RootChanges

        host_admin(request)
        service = RootChanges(app.state.db)
        service.status(change_id)
        return FileResponse(
            service._path(change_id), media_type="application/json", filename=f"root-change-{change_id}.json"
        )

    @app.post(host + "/root-changes/{change_id}/{action}")
    def root_action(
        change_id: UUID,
        action: Literal["execute", "resume", "cancel", "verify", "rollback"],
        request: Request,
        body: Operation,
    ):
        from .storage_root import RootChanges, summary

        host_admin(request, write=True)
        service = RootChanges(app.state.db)
        if action in ("execute", "resume"):
            return summary(service.start(change_id, resume=action == "resume"))
        result = getattr(service, action)(change_id)
        return summary(result) if action != "verify" else result

    @app.post("/api/v2/projects/{project}/storage/payload-migrations")
    def payload_move(project: UUID, request: Request, body: PayloadMove):
        actor = host_admin(request, write=True)
        access(request, project, write=True)
        return app.state.db.payloads.migrate(
            project, body.kind, body.object_id, body.target_id, operation_id=body.operation_id, actor=actor["id"]
        )

    @app.post("/api/v2/projects/{project}/storage/seals/{run_id}")
    def seal_subject(project: UUID, run_id: UUID, request: Request, body: Operation):
        host_admin(request, write=True)
        access(request, project, write=True)
        return app.state.db.payloads.seal(project, run_id)

    @app.post(host + "/targets", status_code=201)
    def register_target(request: Request, body: Target):
        host_admin(request, write=True)
        config = deepcopy(body.configuration)
        if any(
            key in config
            for key in (
                "encrypted_secret",
                "secret",
                "password",
                "api_key",
                "access_key",
                "access_key_id",
                "secret_access_key",
                "session_token",
            )
        ):
            raise ValueError("credentials use the dedicated encrypted input, never target configuration")
        if body.credentials is not None:
            if body.kind != "s3" or set(body.credentials) - {"access_key_id", "secret_access_key", "session_token"}:
                raise ValueError("invalid S3 credential fields")
            if not all(
                isinstance(body.credentials.get(key), str) and body.credentials[key]
                for key in ("access_key_id", "secret_access_key")
            ):
                raise ValueError("explicit S3 access key and secret are required")
            config["encrypted_secret"] = app.state.db.blobs.secret_box.seal(body.credentials)
        elif body.target_id and body.expected_revision:
            previous = storage().target(body.target_id, body.expected_revision)
            if previous["kind"] == body.kind and previous["configuration"].get("encrypted_secret"):
                config["encrypted_secret"] = previous["configuration"]["encrypted_secret"]
        return public_target(
            storage().register_target(
                body.path,
                body.name,
                target_id=body.target_id,
                kind=body.kind,
                configuration=config,
                expected_revision=body.expected_revision,
            )
        )

    @app.put(host + "/policies/{category}")
    def set_policy(category: str, request: Request, body: Policy):
        host_admin(request, write=True)
        return app.state.db.blobs.set_policy(category, body.target_id, expected_revision=body.expected_revision)

    @app.post(host + "/resources", status_code=201)
    def register_resource(request: Request, body: Resource):
        host_admin(request, write=True)
        locator = storage().locator(body.target_id, body.relative_path)
        return storage().register_resource(
            body.resource_id,
            locator,
            legacy_paths=body.legacy_paths,
            registered_work_path=body.registered_work_path,
            expected_revision=body.expected_revision,
            writer_mode=body.writer_mode,
        )

    @app.get(host + "/resources/{resource_id}")
    def inspect_resource(resource_id: str, request: Request, hashes: bool = False):
        host_admin(request)
        return migration().inspect(resource_id, hashes=hashes)

    @app.post(host + "/data-exports", status_code=201)
    def export_research_resource(request: Request, body: ResearchExport):
        host_admin(request, write=True)
        from .research_data_bundles import export

        return export(
            storage(),
            body.resource_id,
            research_export_directory(storage(), body.operation_id),
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        )

    @app.get(host + "/data-exports/{export_id}")
    def offline_export_status(export_id: UUID, request: Request):
        host_admin(request)
        return research_export_receipt(storage(), export_id)

    @app.get(host + "/data-exports/{export_id}/manifest")
    def offline_export_manifest(export_id: UUID, request: Request):
        host_admin(request)
        receipt = research_export_receipt(storage(), export_id)
        row = {
            "filename": receipt["filename"],
            "bytes": receipt["manifest_bytes"],
            "sha256": receipt["manifest_sha256"],
        }
        path = research_export_file(storage(), export_id, row)
        return FileResponse(
            path, filename=row["filename"], media_type="application/json", headers={"X-Content-SHA256": row["sha256"]}
        )

    @app.get(host + "/data-exports/{export_id}/volumes/{volume}")
    def offline_export_volume(export_id: UUID, volume: int, request: Request):
        host_admin(request)
        receipt = research_export_receipt(storage(), export_id)
        row = next((row for row in receipt["volumes"] if row.get("ordinal") == volume), None)
        if row is None:
            raise HTTPException(404, "registered offline research export volume")
        path = research_export_file(storage(), export_id, row)
        return FileResponse(
            path,
            filename=row["filename"],
            media_type="application/octet-stream",
            headers={"X-Content-SHA256": row["sha256"]},
        )

    @app.post(host + "/migrations", status_code=201)
    def migration_plan(request: Request, body: MigrationPlan):
        host_admin(request, write=True)
        return migration_summary(
            migration().plan(
                body.resource_id,
                body.target_id,
                body.relative_path,
                expected_revision=body.expected_revision,
                request_id=body.request_id,
            )
        )

    @app.get(host + "/migrations/{plan_id}")
    def migration_status(plan_id: UUID, request: Request):
        host_admin(request)
        return migration_summary(migration().status(plan_id))

    @app.post(host + "/migrations/{plan_id}/{action}")
    def migration_action(
        plan_id: UUID,
        action: Literal["execute", "resume", "cancel", "verify", "activate", "rollback"],
        request: Request,
        body: MigrationAction,
    ):
        host_admin(request, write=True)
        method = getattr(migration(), action)
        if action in ("activate", "rollback"):
            if body.expected_revision is None:
                raise ValueError("activation/rollback requires the current resource revision")
            return migration_summary(method(plan_id, expected_revision=body.expected_revision))
        if action in ("execute", "resume"):
            if body.request_id is None:
                raise ValueError("execution/resumption requires a stable request ID")
            return migration_summary(method(plan_id, request_id=body.request_id))
        return migration_summary(method(plan_id))

    @app.get(host + "/research-artifacts")
    def research_artifact_index(
        request: Request,
        q: str = Query("", max_length=256),
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(50, ge=1, le=200),
    ):
        host_admin(request)
        rows = registered_artifacts(storage())
        if q:
            query = q.casefold()
            rows = [
                row
                for row in rows
                if any(query in str(row[key]).casefold() for key in ("resource_id", "legacy_path", "archive_path"))
            ]
        page = rows[offset : offset + limit + 1]
        return {
            "schema": "threemind.research-artifact-catalog/1",
            "rows": page[:limit],
            "more": len(page) > limit,
            "offset": offset,
            "limit": limit,
            "matched": len(rows),
            "scope": "verified exact-file relocation manifests; no archive directory scan",
        }

    @app.get(host + "/research-artifacts/{resource_id}/content")
    def research_artifact(resource_id: str, request: Request):
        host_admin(request)
        row = next((row for row in registered_artifacts(storage()) if row["resource_id"] == resource_id), None)
        if row is None:
            raise HTTPException(404, "registered research artifact")
        try:
            path = storage().resolve_legacy(row["legacy_path"])
        except FileNotFoundError:
            raise HTTPException(503, "registered research artifact is unavailable on this host") from None
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/octet-stream",
            headers={"X-Content-SHA256": row["sha256"]},
        )
