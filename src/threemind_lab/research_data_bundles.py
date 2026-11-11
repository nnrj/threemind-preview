"""Formal read-only archives of explicitly registered, quiescent research files.

These are host resources, not fabricated Lab projects or runnable individuals.
An archive includes every regular scientific file within the selected resource;
unknown historical coordinators remain evidence. Export never migrates its source.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID, uuid5

from .data_archive import RECOVERY_SCHEMA, SCHEMA, SET_SCHEMA, DataLimits, DataReader, stream_hash
from .experiment_archive import ArchiveWriter, canonical
from .storage_files import StorageBusy, StorageConflict, atomic_json, checked_path, file_lock, read_json, under_root
from .storage_migration import MigrationService

RECEIPT_SCHEMA = "threemind.research-data-export/1"
DEFAULT_LIMITS = DataLimits()


def receipt(destination, *, operation_id=None, verify=True):
    destination = checked_path(destination)
    value = read_json(destination / "receipt.json")
    if value.get("schema") != RECEIPT_SCHEMA or value.get("state") != "complete":
        raise StorageConflict("research data export is incomplete")
    if operation_id is not None and value["id"] != str(UUID(str(operation_id))):
        raise StorageConflict("research data export request identity mismatch")
    if verify:
        with ExitStack() as stack:
            master = stack.enter_context(under_root(destination, value["filename"]).open("rb"))
            streams = [stack.enter_context(under_root(destination, v["filename"]).open("rb")) for v in value["volumes"]]
            actual_size, actual_hash = stream_hash(master)
            if (actual_size, actual_hash) != (value["manifest_bytes"], value["manifest_sha256"]):
                raise StorageConflict("research data export manifest changed")
            with DataReader({"manifest": master, "volumes": streams}) as reader:
                if reader.manifest["bundle_id"] != value["bundle_id"] or reader.volumes != value["volumes"]:
                    raise StorageConflict("research data export volumes changed")
    return value


def export(
    storage,
    resource_id,
    destination,
    *,
    operation_id,
    limits=DEFAULT_LIMITS,
    expected_revision=None,
    volume_bytes=7 * 1024**3,
    check=lambda: None,
):
    operation_id = str(UUID(str(operation_id)))
    destination = checked_path(destination)
    if not 16384 <= volume_bytes <= limits.volume.compressed - 8192:
        raise ValueError("invalid research data volume budget")
    destination_lock = hashlib.sha256(str(destination).encode()).hexdigest()
    with file_lock(storage.control_dir / "research-export-locks" / (destination_lock + ".lock")):
        if destination.exists():
            previous = receipt(destination, operation_id=operation_id)
            if previous["resource_id"] != resource_id:
                raise StorageConflict("research data request belongs to a different resource")
            return previous | {"replayed": True}
        with storage.resource_lock(resource_id):
            resource = storage.resource(resource_id)
            if expected_revision is not None and resource["revision"] != expected_revision:
                raise StorageConflict("research resource revision changed since preview")
            if resource["writer_mode"] == "unknown" or resource.get("migration_id"):
                raise StorageBusy("export requires a sealed/cooperative resource without an unfinished migration")
            source = storage.resolve_resource(resource_id)
            for protected in (storage.control_dir, storage.repository_root / ".git"):
                if source == protected or source.is_relative_to(protected) or protected.is_relative_to(source):
                    raise ValueError("research export cannot include control or Git metadata")
            if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
                raise ValueError("research export source and destination must be disjoint")
            inspector = MigrationService(storage, max_bytes=limits.expanded)
            with inspector._guards(source):
                check()
                entries = inspector._snapshot(source)
                if any(".git" in Path(row["path"]).parts for row in entries):
                    raise ValueError("research export cannot contain embedded Git metadata")
                host = storage.host_info()["host_id"]
                bundle_id = str(uuid5(UUID(host), "research-data-export:" + operation_id))
                object_id = "research_directory:" + resource_id
                descriptor = {
                    "schema": "threemind.data.research_directory/1",
                    "resource": resource,
                    "source_host_id": host,
                    "entries": entries,
                    "excluded_operational_files": ["worker.lock"],
                    "capabilities": {"view": True, "native_restore": False, "resume": False},
                }
                payload = canonical(descriptor)
                if len(payload) > limits.json_bytes:
                    raise ValueError("research directory metadata exceeds its declared budget")
                files = [
                    {
                        "name": "research/resource.json",
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ]
                originals = {}
                for row in entries:
                    if row["kind"] != "file":
                        continue
                    relative = source.name if row["path"] == "." else row["path"]
                    name = "research/files/" + relative
                    files.append({"name": name, "bytes": row["bytes"], "sha256": row["sha256"]})
                    originals[name] = source if row["path"] == "." else under_root(source, row["path"])
                total = sum(f["bytes"] for f in files)
                if total > limits.expanded:
                    raise ValueError("research archive exceeds its expanded-byte budget")
                existing = destination.parent
                while not existing.exists():
                    existing = existing.parent
                if shutil.disk_usage(existing).free < total + 15 * 1024**3:
                    raise ValueError("research archive would breach the 15 GiB free reserve")
                groups, size, part_size = [[]], 0, min(1024**2, volume_bytes // 4)
                for file in files:
                    file["parts"] = []
                    for index in range((file["bytes"] + part_size - 1) // part_size):
                        count = min(part_size, file["bytes"] - index * part_size)
                        if groups[-1] and size + count > volume_bytes:
                            groups.append([])
                            size = 0
                        part = {"volume": len(groups) - 1, "name": file["name"] + f"/part-{index:06d}"}
                        file["parts"].append(part)
                        groups[-1].append(part)
                        size += count
                if len(groups) > limits.volumes:
                    raise ValueError("research archive exceeds its declared volume count")
                limitations = [
                    "Read-only host research archive; no Lab project or execution history was invented.",
                    "Only the selected directory/file is closed; outside dependencies and historical coordinators are not inferred.",
                    "The archive cannot natively restore or continue an individual; original bytes remain available.",
                ]
                recovery = {
                    "schema": RECOVERY_SCHEMA,
                    "source_scope": "host-research-resource",
                    "source_project": None,
                    "source_host_id": host,
                    "source_actor": None,
                    "scope": {
                        "resource_id": resource_id,
                        "revision": resource["revision"],
                        "write_epoch": resource["write_epoch"],
                    },
                    "snapshot_id": operation_id,
                    "private": True,
                    "complete_history": False,
                    "limitations": limitations,
                    "files": files,
                    "objects": [
                        {
                            "object_id": object_id,
                            "kind": "research_directory",
                            "schema": descriptor["schema"],
                            "source_id": resource_id,
                            "payload": "research/resource.json",
                            "dependencies": [],
                            "adapter": None,
                        }
                    ],
                }
                if len(canonical(recovery)) > 4 * 1024**2 - 8192:
                    raise ValueError("research recovery manifest exceeds the bounded import manifest budget")
                destination.mkdir(parents=True)
                atomic_json(
                    destination / "receipt.json",
                    {"schema": RECEIPT_SCHEMA, "id": operation_id, "resource_id": resource_id, "state": "incomplete"},
                )
                with ExitStack() as stack:
                    streams = [
                        stack.enter_context((destination / f"{bundle_id}.v{i + 1:03d}.tmdata").open("x+b"))
                        for i in range(len(groups))
                    ]
                    writers = [
                        ArchiveWriter(
                            stream,
                            {"bundle_id": bundle_id, "volume": i, "volume_count": len(groups), "recovery": recovery},
                            schema=SCHEMA,
                            limits=limits.volume,
                            check=check,
                        )
                        for i, stream in enumerate(streams)
                    ]
                    for writer in writers:
                        stack.callback(writer.close)
                    for file in files:
                        check()
                        if file["name"] == "research/resource.json":
                            import io

                            reader = stack.enter_context(io.BytesIO(payload))
                        else:
                            reader = stack.enter_context(originals[file["name"]].open("rb"))
                        for part in file["parts"]:
                            data = reader.read(part_size)
                            writers[part["volume"]].add(part["name"], [data])
                        if reader.read(1):
                            raise StorageConflict("research source grew while being exported")
                    for writer in writers:
                        writer.finish()
                    volumes = []
                    for i, stream in enumerate(streams):
                        stream.flush()
                        os.fsync(stream.fileno())
                        count, sha = stream_hash(stream)
                        volumes.append(
                            {
                                "ordinal": i,
                                "filename": f"{bundle_id}.v{i + 1:03d}.tmdata",
                                "bytes": count,
                                "sha256": sha,
                            }
                        )
                    manifest = {"schema": SET_SCHEMA, "bundle_id": bundle_id, "recovery": recovery, "volumes": volumes}
                    if len(canonical(manifest)) > 4 * 1024**2:
                        raise ValueError("research archive manifest exceeds the bounded import budget")
                    with DataReader({"manifest": manifest, "volumes": streams}, limits=limits, check=check):
                        pass
                    if inspector._snapshot(source) != entries or storage.resource(resource_id) != resource:
                        raise StorageConflict("research resource changed across the archive boundary")
                    atomic_json(destination / "manifest.tmdata.json", manifest)
                master = (destination / "manifest.tmdata.json").read_bytes()
                result = {
                    "schema": RECEIPT_SCHEMA,
                    "id": operation_id,
                    "bundle_id": bundle_id,
                    "resource_id": resource_id,
                    "state": "complete",
                    "filename": "manifest.tmdata.json",
                    "volumes": volumes,
                    "bytes": sum(v["bytes"] for v in volumes),
                    "manifest_bytes": len(master),
                    "manifest_sha256": hashlib.sha256(master).hexdigest(),
                    "private": True,
                    "limitations": limitations,
                }
                atomic_json(destination / "receipt.json", result)
                return result
