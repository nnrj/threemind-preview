"""Host-owned locations for research files, separate from Lab scientific state.

Targets and mappings are explicit, revisioned local registrations. No database,
network probe, directory creation or migration occurs at import/construction.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from .storage_files import (
    StorageBusy,
    StorageConflict,
    atomic_json,
    checked_path,
    file_lock,
    read_json,
    relative_key,
    under_root,
)

SCHEMA = "threemind.research-storage/1"
KINDS = ("filesystem", "s3", "db")
WRITERS = ("unknown", "sealed", "cooperative")


def identity(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value):
        raise ValueError("invalid storage identity")
    return value


class ResearchStorage:
    def __init__(self, control_dir=None, *, repository_root=None):
        self.repository_root = checked_path(repository_root or Path(__file__).resolve().parents[2])
        self.control_dir = checked_path(control_dir or self.repository_root / "data/storage-control")
        self.registry_path = self.control_dir / "registry.json"
        self._artifact_cache = {}
        self._registry_cache = None
        self._member_cache = OrderedDict()
        self._member_cache_bytes = 0

    def _load(self, *, copy_state=True):
        if not self.registry_path.exists():
            self._registry_cache = None
            return {"schema": SCHEMA, "host_id": None, "targets": {}, "resources": {}}
        checked_path(self.registry_path)
        stat = self.registry_path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        cached = self._registry_cache
        if cached is not None and cached[0] == signature:
            return deepcopy(cached[1]) if copy_state else cached[1]
        state = read_json(self.registry_path)
        if state.get("schema") != SCHEMA:
            raise ValueError("unsupported research storage registry")
        # One bounded host-metadata snapshot; never cache model state, file bytes
        # or authorization. Atomic registry replacement invalidates its identity.
        # Copies prevent an unfinished _edit or a caller from mutating the cache.
        if stat.st_size <= 1024**2:
            self._registry_cache = (signature, state)
            return deepcopy(state) if copy_state else state
        self._registry_cache = None
        return state

    @contextmanager
    def _edit(self):
        with file_lock(self.control_dir / "registry.lock"):
            state = self._load()
            if not state["host_id"]:
                state["host_id"] = str(uuid4())
            yield state
            atomic_json(self.registry_path, state)

    def initialize(self):
        with self._edit():
            pass
        return self.host_info()

    def host_info(self):
        state = self._load()
        return {"schema": SCHEMA, "host_id": state["host_id"], "initialized": bool(state["host_id"])}

    def root_info(self):
        """A configuration edit requests a move; it never rewrites existing mappings."""
        active = self._load(copy_state=False).get(
            "data_root", {"path": str(self.repository_root / "data"), "revision": 0}
        )
        requested = checked_path(os.getenv("THREEMIND_DATA_ROOT") or active["path"])
        return deepcopy(active) | {
            "requested_path": str(requested),
            "migration_required": requested != Path(active["path"]),
        }

    def writable_root(self):
        info = self.root_info()
        if info["migration_required"] and self.resources():
            raise StorageConflict(
                "THREEMIND_DATA_ROOT differs from registered storage; execute a root-change plan first"
            )
        return checked_path(info["requested_path"])

    def workspace_path(self, name):
        """Resolve a new study workspace without creating or moving anything."""
        key = relative_key(name)
        if len(key.parts) != 1:
            raise ValueError("a study workspace name must be one portable path component")
        return under_root(self.writable_root(), "experiments/" + name)

    def checkpoint_settings(self):
        path = self.control_dir / "checkpoint-settings.json"
        return (
            read_json(path)
            if path.exists()
            else {"schema": "threemind.checkpoint-storage/1", "revision": 0, "backend": "database"}
        )

    def set_checkpoint_backend(self, backend, *, expected_revision):
        if backend not in ("database", "filesystem"):
            raise ValueError("invalid checkpoint storage backend")
        if backend == "filesystem":
            self.writable_root()
        with file_lock(self.control_dir / "checkpoint-settings.lock"):
            current = self.checkpoint_settings()
            if current["revision"] != expected_revision:
                raise StorageConflict("checkpoint storage configuration changed")
            current.update(backend=backend, revision=expected_revision + 1)
            atomic_json(self.control_dir / "checkpoint-settings.json", current)
        return current

    def _outside_control(self, path):
        path = checked_path(path)
        if path.is_relative_to(self.control_dir) or self.control_dir.is_relative_to(path):
            raise ValueError("storage roots/resources must not include or overlap the host control area")
        for name in (".git", ".agents", ".codex", ".aws"):
            if name in [part.casefold() for part in path.parts]:
                raise ValueError("private repository metadata cannot be a research storage root")
        return path

    def register_target(
        self, path=None, name="", *, target_id=None, expected_revision=0, kind="filesystem", configuration=None
    ):
        if kind not in KINDS:
            raise ValueError("unsupported storage target kind")
        target_id = identity(target_id or str(uuid4()))
        configuration = deepcopy(configuration or {})
        for key in ("secret", "password", "api_key", "access_key", "access_key_id", "secret_access_key"):
            if key in configuration:
                raise ValueError("plaintext credentials are not stored in the target registry")
        if kind == "filesystem":
            path = path or configuration.get("path")
            if path is None:
                raise ValueError("filesystem targets require an explicit absolute path")
            configuration["path"] = str(self._outside_control(path))
            if Path(configuration["path"]).exists() and not Path(configuration["path"]).is_dir():
                raise ValueError("a filesystem target must be a directory")
        elif path is not None:
            raise ValueError("non-filesystem targets use configuration metadata, not directory paths")
        with self._edit() as state:
            row = state["targets"].get(target_id, {"id": target_id, "current_revision": 0, "versions": {}})
            if row["current_revision"] != expected_revision:
                raise StorageConflict("storage target revision changed")
            revision = expected_revision + 1
            version = {
                "id": target_id,
                "target_id": target_id,
                "config_revision": revision,
                "revision": revision,
                "host_id": state["host_id"],
                "kind": kind,
                "name": name,
                "configuration": configuration,
            }
            row["versions"][str(revision)] = version
            row["current_revision"] = revision
            state["targets"][target_id] = row
        return deepcopy(version)

    def target(self, target_id, revision=None):
        row = self._load(copy_state=False)["targets"].get(identity(target_id))
        if row is None:
            raise ValueError("storage target is not registered on this host")
        version = row["versions"].get(str(row["current_revision"] if revision is None else revision))
        if version is None:
            raise ValueError("storage target configuration revision is not registered")
        return deepcopy(version)

    def targets(self):
        return [deepcopy(r["versions"][str(r["current_revision"])]) for r in self._load()["targets"].values()]

    def locator(self, target_id, relative_path, *, config_revision=None):
        target = self.target(target_id, config_revision)
        locator = {
            "target_id": target["id"],
            "config_revision": target["config_revision"],
            "relative_path": relative_path,
            "host_id": target["host_id"],
        }
        self.resolve_locator(locator)
        return locator

    def resolve_locator(self, locator):
        target = self.target(locator["target_id"], locator["config_revision"])
        if target["kind"] != "filesystem":
            raise ValueError("directory operations require a filesystem target")
        if locator.get("host_id", target["host_id"]) != target["host_id"]:
            raise StorageConflict("storage locator belongs to another host")
        return self._outside_control(under_root(Path(target["configuration"]["path"]), locator["relative_path"]))

    def safe_path(self, target_id, relative_path, *, config_revision=None):
        return self.resolve_locator(self.locator(target_id, relative_path, config_revision=config_revision))

    def register_resource(
        self,
        resource_id,
        locator,
        *,
        legacy_paths=(),
        registered_work_path=None,
        expected_revision=0,
        writer_mode="unknown",
    ):
        resource_id = identity(resource_id)
        if writer_mode not in WRITERS:
            raise ValueError("declare unknown, sealed or cooperative writer mode")
        proposed_path = self.resolve_locator(locator)
        aliases = list(dict.fromkeys(str(p) for p in legacy_paths))
        if registered_work_path is not None:
            registered_work_path = str(registered_work_path)
            if registered_work_path not in aliases:
                aliases.append(registered_work_path)
        with self.resource_lock(resource_id), self._edit() as state:
            old = state["resources"].get(resource_id)
            if (old["revision"] if old else 0) != expected_revision:
                raise StorageConflict("research resource registration changed")
            if old and old.get("migration_id"):
                raise StorageBusy("resource has an unfinished migration")
            if old:
                aliases = list(dict.fromkeys(old["legacy_paths"] + aliases))
                registered_work_path = old["registered_work_path"]
            for other in state["resources"].values():
                if other["id"] != resource_id and set(other["legacy_paths"]) & set(aliases):
                    raise StorageConflict("a historical path is already registered to another resource")
            self._assert_available_path(state, proposed_path, except_id=resource_id)
            row = {
                "id": resource_id,
                "revision": expected_revision + 1,
                "locator": deepcopy(locator),
                "legacy_paths": aliases,
                "registered_work_path": old["registered_work_path"] if old else registered_work_path,
                "writer_mode": writer_mode,
                "write_epoch": old["write_epoch"] if old else 0,
                "migration_id": None,
            }
            state["resources"][resource_id] = row
        return deepcopy(row)

    def _assert_available_path(self, state, path, *, except_id=None):
        """Each managed writable tree has one lock owner, including its children."""
        for other in state["resources"].values():
            if other["id"] == except_id:
                continue
            location = self.resolve_locator(other["locator"])
            if location.is_relative_to(path) or path.is_relative_to(location):
                raise StorageConflict("managed research resource locations cannot overlap")

    def resource(self, resource_id):
        row = self._load(copy_state=False)["resources"].get(identity(resource_id))
        if row is None:
            raise ValueError("research resource is not registered")
        return deepcopy(row)

    def resources(self):
        return deepcopy(list(self._load()["resources"].values()))

    def resolve_resource(self, resource_id, *, for_write=False):
        row = self.resource(resource_id)
        if for_write and (row["writer_mode"] != "cooperative" or row.get("migration_id")):
            raise StorageBusy("resource is sealed, unmanaged, or reserved for migration")
        return self.resolve_locator(row["locator"])

    def resolve_member(self, resource_id, member=None):
        row = self.resource(resource_id)
        locations = self.member_locations(row, copy_state=False)
        if member and member in locations:
            return self.resolve_locator(locations[member])
        root = self.resolve_locator(row["locator"])
        return under_root(root, member) if member else root

    def member_locations(self, resource, *, copy_state=True):
        reference = resource.get("member_manifest")
        if reference:
            path = under_root(self.control_dir, reference["path"])
            stat = path.stat()
            signature = (
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
                reference["sha256"],
            )
            cached = self._member_cache.get(str(path))
            if cached and cached[0] == signature:
                self._member_cache.move_to_end(str(path))
                return deepcopy(cached[1]) if copy_state else cached[1]
            if cached:
                self._member_cache_bytes -= cached[2]
                del self._member_cache[str(path)]
            data = read_json(path)
            if data.get("resource_id") != resource["id"]:
                raise StorageConflict("resource member manifest belongs to another identity")
            raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
                raise StorageConflict("resource member manifest failed its registered hash")
            if stat.st_size <= 8 * 1024**2:
                self._member_cache[str(path)] = (signature, data["locations"], stat.st_size)
                self._member_cache_bytes += stat.st_size
                while len(self._member_cache) > 8 or self._member_cache_bytes > 32 * 1024**2:
                    _, evicted = self._member_cache.popitem(last=False)
                    self._member_cache_bytes -= evicted[2]
            return deepcopy(data["locations"]) if copy_state else data["locations"]
        return deepcopy(resource.get("member_locations", {}))

    def publish_members(self, resource, locations):
        data = {"schema": "threemind.resource-members/1", "resource_id": resource["id"], "locations": locations}
        sha = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        key = "resource-members/" + hashlib.sha256(resource["id"].encode()).hexdigest() + "/" + sha + ".json"
        path = under_root(self.control_dir, key)
        if not path.exists():
            atomic_json(path, data)
        resource["member_manifest"] = {"path": key, "sha256": sha}
        resource.pop("member_locations", None)

    @contextmanager
    def resource_lock(self, resource_id):
        key = hashlib.sha256(identity(resource_id).encode()).hexdigest()
        with file_lock(self.control_dir / "resource-locks" / (key + ".lock")) as stream:
            yield stream

    @contextmanager
    def writer(self, resource_id):
        """Maintained writers use this guard; an unmanaged writer remains unsafe."""
        with self.resource_lock(resource_id):
            path = self.resolve_resource(resource_id, for_write=True)
            with self._edit() as state:
                row = state["resources"][resource_id]
                if row.get("migration_id") or row["writer_mode"] != "cooperative":
                    raise StorageBusy("resource cannot accept writes")
                row["write_epoch"] += 1
            yield path

    def resolve_legacy(self, path, *, verify=True):
        """Resolve only declared aliases; preserve original registration text."""
        raw = str(path)
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.repository_root / candidate
        candidate = checked_path(candidate)
        matches = []
        for row in self.resources():
            for alias in row["legacy_paths"]:
                original = Path(alias)
                if not original.is_absolute():
                    original = self.repository_root / original
                original = checked_path(original)
                if candidate == original or candidate.is_relative_to(original):
                    suffix = candidate.relative_to(original)
                    mapped = self.resolve_locator(row["locator"])
                    resolved = mapped if str(suffix) == "." else self.resolve_member(row["id"], suffix.as_posix())
                    matches.append((len(original.parts), resolved))
        if not matches:
            # P1's tracked, exact-file index never makes the archive directory public.
            index_root = checked_path(self.repository_root / "lab/artifact-index")
            if index_root.exists():
                archived = []
                candidate_key = os.path.normcase(str(candidate))
                for manifest_path in sorted(index_root.glob("*-relocations.json")):
                    checked_path(manifest_path)
                    info = manifest_path.stat()
                    signature = (info.st_mtime_ns, info.st_size, info.st_ino)
                    cached = self._artifact_cache.get(str(manifest_path))
                    if not cached or cached[0] != signature:
                        manifest = read_json(manifest_path)
                        if manifest.get("schema") != "threemind.research-artifact-relocations/1":
                            raise ValueError("unsupported research artifact location manifest")
                        lookup = {}
                        for item in manifest.get("entries", []):
                            key = os.path.normcase(str(self.repository_root / Path(item["legacy_path"])))
                            lookup.setdefault(key, []).append(item)
                        cached = (signature, lookup)
                        self._artifact_cache[str(manifest_path)] = cached
                    for entry in cached[1].get(candidate_key, []):
                        if entry.get("state") != "verified":
                            continue
                        # Compare the lexical key first. Only the matched file
                        # touches the filesystem; the index may contain thousands.
                        original = self.repository_root / Path(entry["legacy_path"])
                        if candidate != original:
                            continue
                        under_root(self.repository_root, entry["legacy_path"])
                        archive = under_root(self.repository_root, entry["archive_path"])
                        archive_root = self.repository_root / "data/experiments"
                        if not archive.is_relative_to(archive_root) or archive == archive_root:
                            raise ValueError("artifact archive location escapes the research archive")
                        # The original relocation manifest remains immutable. Resolve
                        # its exact registered archive member through current mappings.
                        for resource in self.resources():
                            aliases = resource.get("legacy_paths", [])
                            source = self.resolve_locator(resource["locator"])
                            roots = [source] + [
                                self.repository_root / a if not Path(a).is_absolute() else Path(a) for a in aliases
                            ]
                            for original_root in roots:
                                if archive.is_relative_to(original_root) and archive != original_root:
                                    archive = self.resolve_member(
                                        resource["id"], archive.relative_to(original_root).as_posix()
                                    )
                                    break
                        if archive.exists() and not archive.is_file():
                            raise ValueError("an artifact location must identify one regular file")
                        if verify:
                            checksum, size = hashlib.sha256(), 0
                            with archive.open("rb") as stream:
                                while block := stream.read(4 * 1024**2):
                                    checksum.update(block)
                                    size += len(block)
                            if size != entry.get("bytes") or checksum.hexdigest() != entry.get("sha256"):
                                raise StorageConflict("archived research artifact failed its recorded size/hash")
                        archived.append(archive)
                if archived:
                    if len(set(archived)) != 1:
                        raise StorageConflict("historical artifact has conflicting location manifests")
                    return archived[0]
            raise ValueError(f"historical location is not registered: {raw}")
        return max(matches, key=lambda item: item[0])[1]
