"""Explicit, recoverable local research relocation; originals are never deleted.

This service has no database dependency. Import and construction do not create
files; every operation works on registered host resources and saved plans only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from .research_storage import ResearchStorage
from .storage_files import (
    StorageBusy,
    StorageConflict,
    atomic_json,
    checked_path,
    file_lock,
    publish_directory,
    read_json,
    under_root,
)
from .storage_journal import SelectionJournal

SCHEMA = "threemind.storage-migration/2"
LEGACY_SCHEMA = "threemind.storage-migration/1"
BLOCK = 4 * 1024**2
OPERATIONAL = {"worker.lock"}


class MigrationCancelled(StorageConflict):
    pass


def _hash_file(path):
    checked_path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("only regular files can be migrated")
        while block := stream.read(BLOCK):
            digest.update(block)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise StorageConflict("source changed while being read")
    return digest.hexdigest()


def _snapshot(path, *, max_files, max_bytes, hashes=True):
    path = checked_path(path)
    if not path.exists():
        raise ValueError("research resource does not exist")
    entries, total = [], 0

    def visit(current, relative, depth=0):
        nonlocal total
        if depth > 256:
            raise ValueError("research directory nesting exceeds the migration budget")
        checked_path(current)
        info = current.lstat()
        if stat.S_ISDIR(info.st_mode):
            entries.append({"path": relative, "kind": "directory", "mtime_ns": info.st_mtime_ns})
            with os.scandir(current) as children:
                names = sorted(child.name for child in children)
            for name in names:
                if relative == "." and name in OPERATIONAL:
                    continue
                key = name if relative == "." else relative + "/" + name
                # Apply the same key policy on both source and target hosts.
                under_root(path, key)
                visit(current / name, key, depth + 1)
            if current.lstat().st_mtime_ns != info.st_mtime_ns:
                raise StorageConflict("source directory changed while being inventoried")
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
            if total > max_bytes:
                raise ValueError("research resource exceeds the migration byte budget")
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "bytes": info.st_size,
                    "mtime_ns": info.st_mtime_ns,
                    "sha256": _hash_file(current) if hashes else None,
                }
            )
        else:
            raise ValueError("research resources may contain only regular files and directories")
        if len(entries) > max_files:
            raise ValueError("research resource exceeds the migration member budget")

    visit(path, ".")
    return entries


def _content(entries):
    return [{k: v for k, v in row.items() if k != "mtime_ns"} for row in entries]


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class MigrationService:
    def __init__(self, storage: ResearchStorage, *, max_files=100000, max_bytes=1024**4, min_free_bytes=15 * 1024**3):
        if min(max_files, max_bytes) <= 0 or min_free_bytes < 0:
            raise ValueError("migration budgets must be positive, with a nonnegative disk reserve")
        self.storage = storage
        self.max_files, self.max_bytes, self.min_free_bytes = max_files, max_bytes, min_free_bytes
        self.journal = SelectionJournal(
            storage.control_dir, "migrations", ("entries", "members", "source_member_locations")
        )
        self._cancel_cache = None

    def _path(self, plan_id):
        return self.storage.control_dir / "migrations" / (str(UUID(str(plan_id))) + ".json")

    def _read(self, plan_id):
        row = self.journal.read(self._path(plan_id))
        if row.get("schema") not in (SCHEMA, LEGACY_SCHEMA) or row.get("id") != str(UUID(str(plan_id))):
            raise ValueError("invalid migration journal")
        return row

    def _save(self, row, *, preserve_cancel=True):
        with file_lock(self.storage.control_dir / "migration-journal.lock"):
            path = self._path(row["id"])
            if preserve_cancel and path.exists() and read_json(path, maximum=128 * 1024**2).get("cancel_requested"):
                row["cancel_requested"] = True
            row["updated_at"] = time.time()
            if row["schema"] == LEGACY_SCHEMA:
                atomic_json(path, row)
            else:
                self.journal.write(path, row)

    def _task_lock(self, plan_id):
        return file_lock(self.storage.control_dir / "migration-locks" / (str(UUID(str(plan_id))) + ".lock"))

    def _destination_lock(self, row):
        destination = self.storage.resolve_locator(row["destination_locator"])
        key = hashlib.sha256(os.path.normcase(str(destination)).encode()).hexdigest()
        return file_lock(self.storage.control_dir / "destination-locks" / (key + ".lock"))

    def _snapshot(self, path, *, hashes=True):
        return _snapshot(path, max_files=self.max_files, max_bytes=self.max_bytes, hashes=hashes)

    def _selected(self, path, members, locations=None):
        """Only declared originals; unrelated source documents are not copied/read."""
        if members is None:
            return self._snapshot(path)
        entries = [{"path": ".", "kind": "directory", "mtime_ns": 0}]
        directories = set()
        for member in sorted(set(members)):
            original = (
                self.storage.resolve_locator(locations[member])
                if locations and member in locations
                else under_root(path, member)
            )
            part = self._snapshot(original)
            if len(part) != 1 or part[0]["kind"] != "file":
                raise ValueError("selected migration members must be individual regular files")
            entries.append(part[0] | {"path": member})
            parent = Path(member).parent
            while str(parent) != ".":
                directories.add(parent.as_posix())
                parent = parent.parent
        entries.extend({"path": p, "kind": "directory", "mtime_ns": 0} for p in directories)
        if len(entries) > self.max_files or sum(e.get("bytes", 0) for e in entries) > self.max_bytes:
            raise ValueError("selected originals exceed migration budget")
        return sorted(entries, key=lambda e: Path(e["path"]).parts)

    def _guards(self, source):
        guards = ExitStack()
        try:
            if source.is_dir() and (source / "worker.lock").exists():
                guards.enter_context(file_lock(source / "worker.lock", create=False))
        except BaseException:
            guards.close()
            raise
        return guards

    def _source_matches(self, row):
        path = self.storage.resolve_locator(row["source_locator"])
        if self._selected(path, row.get("members"), row.get("source_member_locations")) != row["entries"]:
            raise StorageConflict("source changed since the saved migration plan")
        return path

    def _destination_matches(self, row):
        path = self.storage.resolve_locator(row["destination_locator"])
        if _content(self._snapshot(path)) != _content(row["entries"]):
            raise StorageConflict("destination contents do not match the complete migration plan")
        return path

    def _space(self, path, required):
        path = checked_path(path)
        while not path.exists():
            path = path.parent
        if not path.is_dir():
            path = path.parent
        if shutil.disk_usage(path).free - required < self.min_free_bytes:
            raise StorageConflict("migration would breach the configured free-disk reserve")

    def inspect(self, resource_id, *, hashes=False):
        resource = self.storage.resource(resource_id)
        path = self.storage.resolve_locator(resource["locator"])
        entries = self._snapshot(path, hashes=hashes)
        return {
            "resource": resource,
            "path": str(path),
            "entries": entries,
            "bytes": sum(e.get("bytes", 0) for e in entries),
            "members": len(entries),
            "excluded_operational_files": sorted(OPERATIONAL),
            "hashes_verified": hashes,
            "can_migrate": resource["writer_mode"] != "unknown" and not resource.get("migration_id"),
            "blockers": (["historical writer safety is undeclared"] if resource["writer_mode"] == "unknown" else [])
            + (["resource has an unfinished migration"] if resource.get("migration_id") else []),
        }

    def plan(
        self, resource_id, target_id, relative_path=None, *, expected_revision=None, request_id=None, members=None
    ):
        host = self.storage.initialize()["host_id"]
        request_id = str(UUID(str(request_id))) if request_id else str(uuid4())
        plan_id = str(uuid5(UUID(host), "storage-plan:" + request_id))
        arguments = {
            "resource_id": resource_id,
            "target_id": target_id,
            "relative_path": relative_path,
            "expected_revision": expected_revision,
            "members": members,
        }
        fingerprint = _digest(arguments)
        with self._task_lock(plan_id):
            if self._path(plan_id).exists():
                previous = self._read(plan_id)
                if previous["fingerprint"] != fingerprint:
                    raise StorageConflict("request identity belongs to a different migration plan")
                return self.status(plan_id)
            with self.storage.resource_lock(resource_id):
                resource = self.storage.resource(resource_id)
                if expected_revision is not None and resource["revision"] != expected_revision:
                    raise StorageConflict("resource revision changed")
                if resource["writer_mode"] == "unknown":
                    raise StorageBusy("declare a sealed resource or use the maintained cooperative writer protocol")
                if resource.get("migration_id"):
                    raise StorageBusy("resource already has an unfinished migration")
                source = self.storage.resolve_locator(resource["locator"])
                locator = self.storage.locator(target_id, relative_path or resource["locator"]["relative_path"])
                destination = self.storage.resolve_locator(locator)
                if ".threemind-migrations" in Path(locator["relative_path"]).parts:
                    raise ValueError("migration destinations cannot overlap internal staging directories")
                if source.is_relative_to(destination) or destination.is_relative_to(source):
                    raise ValueError("migration source and destination must not overlap")
                with self._guards(source):
                    entries = self._selected(source, members, self.storage.member_locations(resource))
                if destination.exists() and _content(self._snapshot(destination)) != _content(entries):
                    raise StorageConflict("destination already contains different data")
                size = sum(e.get("bytes", 0) for e in entries)
                self._space(destination, 0 if destination.exists() else size)
                row = {
                    "schema": SCHEMA,
                    "id": plan_id,
                    "request_id": request_id,
                    "fingerprint": fingerprint,
                    "host_id": host,
                    "resource_id": resource_id,
                    "resource_revision": resource["revision"],
                    "write_epoch": resource["write_epoch"],
                    "source_locator": resource["locator"],
                    "destination_locator": locator,
                    "entries": entries,
                    "members": members,
                    "source_member_locations": self.storage.member_locations(resource),
                    "content_sha256": _digest(_content(entries)),
                    "bytes": size,
                    "state": "planned",
                    "cancel_requested": False,
                    "completed_files": 0,
                    "copied_bytes": 0,
                    "created_at": time.time(),
                    "originals_retained": True,
                    "resumption": "verified_file_boundaries",
                }
                self._save(row)
                return deepcopy(row)

    def status(self, plan_id):
        row = self._read(plan_id)
        resource = self.storage.resource(row["resource_id"])
        event = resource.get("last_migration", {})
        if event.get("plan_id") == row["id"] and event.get("state") in ("activated", "rolled_back"):
            row["state"] = event["state"]
            row["activation_revision"] = event["activation_revision"]
            row["activation_write_epoch"] = event["activation_write_epoch"]
        return row

    def _reserve(self, row):
        with self.storage._edit() as state:
            resource = state["resources"][row["resource_id"]]
            if (
                resource["revision"] != row["resource_revision"]
                or resource["locator"] != row["source_locator"]
                or resource["write_epoch"] != row["write_epoch"]
            ):
                raise StorageConflict("resource registration or write epoch changed since planning")
            if resource.get("migration_id") not in (None, row["id"]):
                raise StorageBusy("resource is reserved by another migration")
            if resource["writer_mode"] == "unknown":
                raise StorageBusy("writer safety is undeclared")
            resource["migration_id"] = row["id"]

    def _release(self, row):
        with self.storage._edit() as state:
            resource = state["resources"][row["resource_id"]]
            if resource.get("migration_id") == row["id"]:
                resource["migration_id"] = None

    def _check_cancel(self, row):
        path = self._path(row["id"])
        stat = path.stat()
        signature = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if self._cancel_cache is None or self._cancel_cache[0] != signature:
            self._cancel_cache = (signature, read_json(path, maximum=128 * 1024**2).get("cancel_requested", False))
        if self._cancel_cache[1]:
            raise MigrationCancelled("migration was canceled; originals and inactive copies are retained")

    def _copy_file(self, source, destination, partial, entry, row):
        self._check_cancel(row)
        if destination.exists():
            if not destination.is_file() or destination.stat().st_size != entry["bytes"]:
                raise StorageConflict("a staged member has different data")
            if _hash_file(destination) != entry["sha256"]:
                raise StorageConflict("a staged member failed its saved checksum")
            return
        checked_path(source)
        checked_path(destination)
        checked_path(partial)
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest, size = hashlib.sha256(), 0
        with source.open("rb") as reader, partial.open("wb") as writer:
            before = os.fstat(reader.fileno())
            if (before.st_size, before.st_mtime_ns) != (entry["bytes"], entry["mtime_ns"]):
                raise StorageConflict("source member changed since planning")
            while block := reader.read(BLOCK):
                self._check_cancel(row)
                self._space(partial, len(block))
                writer.write(block)
                digest.update(block)
                size += len(block)
            writer.flush()
            os.fsync(writer.fileno())
            after = os.fstat(reader.fileno())
        if (
            size != entry["bytes"]
            or digest.hexdigest() != entry["sha256"]
            or (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns)
        ):
            raise StorageConflict("source changed during copy")
        if _hash_file(partial) != entry["sha256"]:
            raise StorageConflict("copied member failed read-back verification")
        shutil.copystat(source, partial, follow_symlinks=False)
        # Exclusive publication also handles a racing creator without overwriting it.
        os.link(partial, destination)
        partial.unlink()

    def execute(self, plan_id, *, request_id=None):
        if request_id is not None:
            UUID(str(request_id))
        with self._task_lock(plan_id):
            row = self.status(plan_id)
            if row["state"] in ("activated", "copied", "verified"):
                return row
            if row["state"] in ("cancelled", "rolled_back"):
                raise StorageConflict("resume a canceled task explicitly; a rolled-back plan cannot be reexecuted")
            with self.storage.resource_lock(row["resource_id"]), self._destination_lock(row):
                self._reserve(row)
                try:
                    source = self._source_matches(row)
                    with self._guards(source):
                        self._check_cancel(row)
                        destination = self.storage.resolve_locator(row["destination_locator"])
                        self._space(destination, 0 if destination.exists() else row["bytes"])
                        row.update(state="copying", error=None, completed_files=0, copied_bytes=0)
                        self._save(row)
                        if destination.exists():
                            self._destination_matches(row)
                        else:
                            target = self.storage.target(
                                row["destination_locator"]["target_id"], row["destination_locator"]["config_revision"]
                            )
                            root = Path(target["configuration"]["path"])
                            stage = under_root(root, ".threemind-migrations/" + row["id"])
                            stage.mkdir(parents=True, exist_ok=True)
                            content = checked_path(stage / "content")
                            for entry in row["entries"]:
                                self._check_cancel(row)
                                target_file = content if entry["path"] == "." else under_root(content, entry["path"])
                                source_file = source if entry["path"] == "." else under_root(source, entry["path"])
                                if entry["kind"] == "file" and entry["path"] in row.get("source_member_locations", {}):
                                    source_file = self.storage.resolve_locator(
                                        row["source_member_locations"][entry["path"]]
                                    )
                                if entry["kind"] == "directory":
                                    checked_path(target_file).mkdir(parents=True, exist_ok=True)
                                else:
                                    partial = stage / ("partial-" + hashlib.sha256(entry["path"].encode()).hexdigest())
                                    self._copy_file(source_file, target_file, partial, entry, row)
                                    row["completed_files"] += 1
                                    row["copied_bytes"] += entry["bytes"]
                                    self._save(row)
                            if _content(self._snapshot(content)) != _content(row["entries"]):
                                raise StorageConflict("staged data are not the complete planned resource")
                            self._source_matches(row)
                            self._check_cancel(row)
                            checked_path(destination.parent).mkdir(parents=True, exist_ok=True)
                            if destination.exists():
                                raise StorageConflict("destination was created concurrently")
                            if content.is_dir():
                                publish_directory(content, destination)
                            else:
                                os.link(content, destination)
                                content.unlink()
                        self._source_matches(row)
                        row.update(
                            state="copied",
                            copied_bytes=row["bytes"],
                            completed_files=sum(e["kind"] == "file" for e in row["entries"]),
                        )
                        self._save(row)
                        return deepcopy(row)
                except MigrationCancelled as error:
                    row.update(state="cancelled", error=str(error), cancel_requested=True)
                    self._save(row)
                    self._release(row)
                    return deepcopy(row)
                except BaseException as error:
                    row.update(state="failed", error=str(error))
                    self._save(row)
                    raise

    def resume(self, plan_id, *, request_id=None):
        with self._task_lock(plan_id):
            row = self.status(plan_id)
            if row["state"] in ("activated", "rolled_back"):
                return row
            row["cancel_requested"] = False
            if row["state"] not in ("copied", "verified"):
                row["state"] = "planned"
            self._save(row, preserve_cancel=False)
        return self.execute(plan_id, request_id=request_id)

    def cancel(self, plan_id):
        # Change only the flag in the latest journal, never replace active copy progress.
        with file_lock(self.storage.control_dir / "migration-journal.lock"):
            row = self.status(plan_id)
            if row["state"] in ("activated", "rolled_back"):
                raise StorageConflict("activated migrations require rollback, not cancellation")
            row["cancel_requested"] = True
            row["updated_at"] = time.time()
            if row["schema"] == LEGACY_SCHEMA:
                atomic_json(self._path(plan_id), row)
            else:
                self.journal.write(self._path(plan_id), row)
        try:
            with self._task_lock(plan_id), self.storage.resource_lock(row["resource_id"]):
                row = self._read(plan_id)
                row["state"] = "cancelled"
                self._save(row)
                self._release(row)
        except StorageBusy:
            return self.status(plan_id) | {"cancellation": "requested; the active copy will stop at a chunk boundary"}
        return deepcopy(row)

    def verify(self, plan_id):
        with self._task_lock(plan_id):
            row = self.status(plan_id)
            if row["state"] not in ("copied", "verified", "activated"):
                raise StorageConflict("only a completely copied resource can be verified")
            with self.storage.resource_lock(row["resource_id"]):
                self._source_matches(row)
                self._destination_matches(row)
                row["verified_at"] = time.time()
                if row["state"] != "activated":
                    row["state"] = "verified"
                self._save(row)
            return deepcopy(row)

    def activate(self, plan_id, *, expected_revision=None):
        with self._task_lock(plan_id):
            row = self.status(plan_id)
            if row["state"] == "activated":
                return row
            if row["state"] != "verified" or row.get("cancel_requested"):
                raise StorageConflict("verify the complete migration before explicit activation")
            with self.storage.resource_lock(row["resource_id"]):
                source = self._source_matches(row)
                with self._guards(source):
                    self._destination_matches(row)
                    # Cancellation and the mapping commit have a defined ordering.
                    with file_lock(self.storage.control_dir / "migration-journal.lock"), self.storage._edit() as state:
                        self._check_cancel(row)
                        resource = state["resources"][row["resource_id"]]
                        revision = row["resource_revision"] if expected_revision is None else expected_revision
                        if (
                            resource["revision"] != revision
                            or revision != row["resource_revision"]
                            or resource["locator"] != row["source_locator"]
                            or resource["write_epoch"] != row["write_epoch"]
                            or resource.get("migration_id") != row["id"]
                        ):
                            raise StorageConflict("resource registration changed before activation")
                        self.storage._assert_available_path(
                            state,
                            self.storage.resolve_locator(row["destination_locator"]),
                            except_id=row["resource_id"],
                        )
                        if row.get("members") is not None:
                            locations = self.storage.member_locations(resource)
                            locations.update(
                                {
                                    member: row["destination_locator"]
                                    | {"relative_path": row["destination_locator"]["relative_path"] + "/" + member}
                                    for member in row["members"]
                                }
                            )
                            self.storage.publish_members(resource, locations)
                        else:
                            resource["locator"] = row["destination_locator"]
                        resource["legacy_paths"] = list(dict.fromkeys(resource["legacy_paths"] + [str(source)]))
                        resource["revision"] += 1
                        resource["migration_id"] = None
                        resource["last_migration"] = {
                            "plan_id": row["id"],
                            "state": "activated",
                            "activation_revision": resource["revision"],
                            "activation_write_epoch": resource["write_epoch"],
                        }
                        row.update(resource["last_migration"])
                        row["state"] = "activated"
                    self._save(row)
            return deepcopy(row)

    def rollback(self, plan_id, *, expected_revision=None):
        row = self.status(plan_id)
        if row["state"] == "rolled_back":
            return row
        if row["state"] != "activated":
            return self.cancel(plan_id)
        with self._task_lock(plan_id), self.storage.resource_lock(row["resource_id"]):
            row = self.status(plan_id)
            self._source_matches(row)
            self._destination_matches(row)
            with self.storage._edit() as state:
                resource = state["resources"][row["resource_id"]]
                revision = row["activation_revision"] if expected_revision is None else expected_revision
                if (
                    resource["revision"] != revision
                    or revision != row["activation_revision"]
                    or (row.get("members") is None and resource["locator"] != row["destination_locator"])
                    or resource["write_epoch"] != row["activation_write_epoch"]
                    or resource.get("migration_id")
                ):
                    raise StorageConflict(
                        "post-activation writes/registration changes require a reverse migration plan"
                    )
                resource["locator"] = row["source_locator"]
                if row.get("members") is not None:
                    self.storage.publish_members(resource, row.get("source_member_locations", {}))
                resource["revision"] += 1
                resource["last_migration"]["state"] = "rolled_back"
                row["state"] = "rolled_back"
            self._save(row)
            return deepcopy(row)
