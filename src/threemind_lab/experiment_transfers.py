"""Verified file transfers for named experiments, with one authoritative placement catalog."""

import os
import shutil
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from time import time
from uuid import UUID, uuid4

from . import experiment_transfer_files as files
from . import storage_volumes as volumes
from .experiment_storage import component, scan_pool
from .storage_files import (
    StorageConflict,
    atomic_json,
    checked_path,
    file_lock,
    publish_directory,
    read_json,
    under_root,
)

MOVES = {"migrate", "archive", "unarchive"}
OPERATIONS = MOVES | {"sync", "backup", "restore"}
FINISHED = {"complete", "released", "cancelled"}


def locations(state, parts):
    return {
        p["name"]: under_root(volumes.mounted_directory(state["directories"][p["directory"]]), p["relative_path"])
        for p in parts
    }


def mapped_parts(parts, directory, base):
    return [
        dict(p, directory=directory, relative_path=base if len(parts) == 1 else base + "/" + p["name"]) for p in parts
    ]


def overlaps(a, b):
    return a.is_relative_to(b) or b.is_relative_to(a)


def same_workspace(paths, expected):
    existing = {k: p for k, p in paths.items() if p.is_dir()}
    if not existing:
        return False
    if len(paths) > 1:
        for parent in {p.parent for p in existing.values()}:
            if set(parent.iterdir()) != {p for p in existing.values() if p.parent == parent}:
                return False
    return files.inventory(existing) == expected


class ExperimentTransfers:
    def __init__(self, pool):
        self.pool = pool
        self.storage = pool.storage
        self.control = self.storage.control_dir / "experiment-transfers"

    def manifest(self, job_id):
        return self.control / (str(UUID(job_id)) + ".jsonl.gz")

    def verified_inventory(self, job):
        path = self.manifest(job["id"])
        if files.digest(path, {}) != job["inventory_sha256"]:
            raise StorageConflict("host transfer inventory failed its checksum")
        return files.read_inventory(path)

    def job(self, job_id):
        row = self.pool._read().get("transfers", {}).get(str(UUID(job_id)))
        if not row:
            raise ValueError("unknown experiment transfer")
        return row

    def update(self, job_id, **fields):
        with file_lock(self.pool.lock):
            state = self.pool._read()
            state["transfers"][job_id].update(fields)
            atomic_json(self.pool.file, state)

    def catalog(self):
        state = self.pool._read()
        return {
            "jobs": sorted(state.get("transfers", {}).values(), key=lambda j: j["created"]),
            "studies": [
                {
                    "name": s["name"],
                    "status": s["status"],
                    "residency": s.get("residency", "active"),
                    "directories": sorted({p["directory"] for p in s["parts"]}),
                }
                for s in state["studies"].values()
            ],
        }

    def discover(self, directory):
        state = self.pool._read()
        root = self.directory(state, directory)
        if root.get("role", "run") != "run":
            raise ValueError("select a run directory to discover historical experiments")
        base = under_root(volumes.mounted_directory(root), "experiments")
        if not base.exists():
            return []
        return sorted(
            p.name
            for p in base.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name.casefold() not in state["studies"]
        )

    @staticmethod
    def directory(state, key):
        entry = state["directories"].get(component(key))
        if entry is None:
            raise ValueError("unknown storage directory")
        return entry

    def adopt(self, name, directory):
        """Operator identifies a completed historical workspace in a configured run directory."""
        name = component(name)
        with self.pool.study_lock(name), file_lock(self.pool.lock):
            state = self.pool._read()
            entry = self.directory(state, directory)
            if entry.get("role", "run") != "run":
                raise ValueError("adoption requires a run directory")
            rel = "experiments/" + name
            root = under_root(volumes.mounted_directory(entry), rel)
            if not root.is_dir():
                raise ValueError("historical experiment directory is missing")
            old = state["studies"].get(name.casefold())
            if old:
                if old.get("adopted") and old["parts"][0]["directory"] == directory:
                    return old
                raise StorageConflict("this study ID already belongs to an experiment")
            for key, other in state["directories"].items():
                if key == directory or other.get("role", "run") != "run":
                    continue
                try:
                    duplicate = under_root(volumes.mounted_directory(other), rel).exists()
                except volumes.VolumeOffline:
                    continue
                if duplicate:
                    raise StorageConflict("multiple run directories contain this historical study name")
            p = {"name": "main", "kind": "data", "bytes": 0}
            with self.guards({"main": root}):
                row = {
                    "name": name,
                    "parts": [dict(p, directory=directory, relative_path=rel)],
                    "status": "complete",
                    "request": {"name": name, "parts": [p], "allow_split": False},
                    "adopted": True,
                }
                state["studies"][name.casefold()] = row
                atomic_json(self.pool.file, state)
                return row

    @contextmanager
    def guards(self, roots, *, moving=False, resource_roots=None, resources=True):
        """Guard cooperating resource writers and worker locks, including nested study workers."""
        with ExitStack() as stack:
            handles = {}
            physical = list((resource_roots or roots).values())
            configs = {}
            for resource in self.storage.resources() if resources else ():
                locator = resource["locator"]
                target = self.storage.target(locator["target_id"], locator["config_revision"])
                touched = False
                if target["kind"] == "filesystem":
                    raw = Path(target["configuration"]["path"]) / locator["relative_path"]
                    try:
                        actual = self.storage.resolve_locator(locator)
                    except volumes.VolumeOffline:
                        actual = raw
                    touched = any(overlaps(p, actual) or overlaps(p, raw) for p in physical)
                    if moving and any(p != actual and p.is_relative_to(actual) for p in physical):
                        raise StorageConflict(f"experiment shares a larger registered resource: {resource['id']}")
                if not touched:
                    for m in self.storage.member_locations(resource, copy_state=False).values():
                        key = (m["target_id"], m["config_revision"])
                        if key not in configs:
                            configs[key] = self.storage.target(*key)
                        cfg = configs[key]
                        if cfg["kind"] == "filesystem":
                            path = Path(cfg["configuration"]["path"]) / m["relative_path"]
                            if any(overlaps(p, path) for p in physical):
                                touched = True
                                break
                if touched:
                    if resource.get("migration_id") or (moving and resource["writer_mode"] == "unknown"):
                        raise StorageConflict(f"unmanaged writer or resource migration: {resource['id']}")
                    stack.enter_context(self.storage.resource_lock(resource["id"]))
            for root in roots.values():
                for parent, dirs, names in os.walk(checked_path(root), onerror=_raise):
                    for name in dirs:
                        checked_path(Path(parent) / name)
                    if "worker.lock" in names:
                        lock = checked_path(Path(parent) / "worker.lock")
                        handles[lock] = stack.enter_context(file_lock(lock, create=False))
            yield handles

    def _request(self, state, operation, name, destination, backup=None, restore_as=None):
        if operation not in OPERATIONS:
            raise ValueError("unknown transfer operation")
        name = component(name)
        entry = self.directory(state, destination)
        role = entry.get("role", "run")
        if not entry["enabled"]:
            raise StorageConflict("destination directory is disabled")
        if operation in ("migrate", "unarchive", "restore") and role != "run":
            raise ValueError("select a run directory for this operation")
        if operation == "archive" and role != "archive":
            raise ValueError("cold archives require an archive directory")
        if operation == "backup" and role == "run":
            raise ValueError("select a backup or archive directory for a versioned backup")
        study = state["studies"].get(name.casefold())
        if study is None and operation != "restore":
            raise ValueError("select a registered experiment or adopt a historical workspace first")
        if operation == "restore":
            version = state.get("transfers", {}).get(str(UUID(backup or "")))
            if not version or (version["name"].casefold(), version["operation"], version["status"]) != (
                name.casefold(),
                "backup",
                "complete",
            ):
                raise ValueError("select a completed backup version of this experiment")
            component(restore_as)
            if restore_as.casefold() in state["studies"]:
                raise StorageConflict("restore requires a new experiment name")
            parts = version["target_parts"]
        else:
            if backup or restore_as:
                raise ValueError("backup version and restore name are only used when restoring")
            parts = study["parts"]
        if operation in MOVES:
            if study["status"] != "complete":
                raise StorageConflict("finish the experiment before changing its location")
            archived = study.get("residency") == "archived"
            if archived != (operation == "unarchive"):
                raise StorageConflict("select the operation that matches the experiment's current location")
            if {p["directory"] for p in parts} == {destination}:
                raise StorageConflict("experiment already resides in that directory")
        return {
            "operation": operation,
            "name": version["name"] if operation == "restore" else study["name"],
            "destination": destination,
            "backup": backup,
            "restore_as": restore_as,
            "source_parts": deepcopy(parts),
        }

    def _source(self, state, job):
        roots = locations(state, job["source_parts"])
        for p in job["source_parts"]:
            path = roots[p["name"]]
            if p["kind"] in ("archive", "readback") and not path.exists():
                del roots[p["name"]]
        if not roots:
            raise StorageConflict("no experiment files or directories are available")
        if job.get("source_inodes") and {k: str(p.stat().st_ino) for k, p in roots.items()} != job["source_inodes"]:
            raise StorageConflict("source directory identity changed since the transfer started")
        if len(job["source_parts"]) > 1:
            for parent in {p.parent for p in roots.values()}:
                owned = {p for p in roots.values() if p.parent == parent}
                if any(child not in owned for child in parent.iterdir()):
                    raise StorageConflict(f"multi-part workspace contains unassigned files: {parent}")
        return roots

    def preview(self, operation, name, destination, backup=None, restore_as=None):
        state = self.pool._read()
        req = self._request(state, operation, name, destination, backup, restore_as)
        roots = self._source(state, req)
        entries = files.inventory(roots, hashes=False)
        rows, _ = scan_pool(state["directories"], state["studies"], state.get("transfers", {}).values(), topology=True)
        space = {k: volumes.tree_usage(p) for k, p in roots.items()}
        source_volumes = {p["name"]: rows[p["directory"]]["volume"] for p in req["source_parts"]}
        other = sum(size for k, size in space.items() if source_volumes[k] != rows[destination]["volume"])
        return {
            **req,
            "files": sum(e["kind"] == "file" for e in entries.values()),
            "bytes": sum(e.get("bytes", 0) for e in entries.values()),
            "source_allocated_bytes": sum(space.values()),
            "source_bytes_on_other_volumes": other,
            "available_bytes": rows[destination]["available_bytes"],
            "online": rows[destination]["online"],
        }

    def create(self, operation, name, destination, backup=None, restore_as=None, *, job_id=None):
        job_id = str(UUID(job_id)) if job_id else str(uuid4())
        with file_lock(self.pool.lock):
            state = self.pool._read()
            jobs = state.setdefault("transfers", {})
            if job_id in jobs:
                old = jobs[job_id]
                if (operation, name.casefold(), destination, backup, restore_as) != (
                    old["operation"],
                    old["name"].casefold(),
                    old["destination"],
                    old["backup"],
                    old["restore_as"],
                ):
                    raise StorageConflict("transfer ID belongs to a different request")
                return old
            req = self._request(state, operation, name, destination, backup, restore_as)
            requested_names = {name.casefold(), (restore_as or "").casefold()} - {""}
            for other in jobs.values():
                if other["status"] not in FINISHED and requested_names & {
                    other["name"].casefold(),
                    (other["restore_as"] or "").casefold(),
                }:
                    raise StorageConflict("resume or cancel the outstanding transfer for this experiment")
            job = dict(req, id=job_id, status="ready", created=time(), remaining_bytes=0)
            jobs[job_id] = job
            atomic_json(self.pool.file, state)
            return job

    def _base(self, job):
        op, name = job["operation"], job["name"]
        if op == "backup":
            return f"backups/{name}/{job['id']}/data"
        if op == "sync":
            return f"replicas/{name}"
        if op == "archive":
            return f"archives/{name}/{job['id']}"
        if op == "migrate" and any(p["directory"] == job["destination"] for p in job["source_parts"]):
            return f"relocated/{job['id']}/{name}"
        return "experiments/" + (job["restore_as"] or name)

    def run(self, job_id):
        job = self.job(job_id)
        with self.pool.study_lock(job["name"]), ExitStack() as locks:
            if job["restore_as"]:
                locks.enter_context(self.pool.study_lock(job["restore_as"]))
            job = self.job(job_id)
            if job["status"] in FINISHED:
                return job
            try:
                return self._run(job)
            except (OSError, ValueError) as exc:
                self.update(job_id, status="paused", error=str(exc), remaining_bytes=0)
                raise

    def background(self, ident, action):
        from .storage_files import StorageBusy

        try:
            getattr(self, action)(ident)
        except StorageBusy:
            # Another process may already be doing the identical job.
            if action == "release":
                self.update(ident, release_pending=False, error="source or destination is busy; retry release")
        except (OSError, ValueError) as exc:
            self.update(ident, error=str(exc), release_pending=False)
        else:
            if action == "release":
                self.update(ident, release_pending=False)

    def _run(self, job):
        state = self.pool._read()
        op, ident = job["operation"], job["id"]
        req = self._request(state, op, job["name"], job["destination"], job["backup"], job["restore_as"])
        if req["source_parts"] != job["source_parts"]:
            raise StorageConflict("experiment location changed since the transfer was prepared")
        entry = state["directories"][job["destination"]]
        disk = volumes.mounted_directory(entry)
        sources = self._source(state, job)
        parents = {p.parent for p in sources.values()}
        wrapper = parents.pop() if len(job["source_parts"]) > 1 and len(parents) == 1 else None
        wrapper_times = files.times(wrapper.stat()) if wrapper else None
        self.update(ident, status="running", error=None)
        with self.guards(sources, moving=op in MOVES) as handles:
            expected = files.inventory(sources, handles)
            manifest = self.manifest(ident)
            if manifest.exists() and files.read_inventory(manifest) != expected:
                raise StorageConflict("source changed since this transfer started; cancel and start a new transfer")
            if op == "restore" and self._backup_inventory(state, job["backup"]) != expected:
                raise StorageConflict("backup files differ from their version manifest")
            if not manifest.exists():
                files.write_inventory(manifest, expected)
            latest = self._replica(state, job)
            base = job.get("target_base", self._base(job))
            if not job.get("target_base") and op == "archive" and latest:
                previous = locations(state, latest["target_parts"])
                if same_workspace(previous, expected):
                    base = latest["target_base"]
            final = under_root(disk, base)
            stage = under_root(disk, ".threemind-transfers/" + ident)
            targets = mapped_parts(job["source_parts"], job["destination"], base)
            paths = locations(state, targets)
            for path in paths.values():
                if any(overlaps(path, src) for src in sources.values()):
                    raise StorageConflict("source and destination overlap")
            owned_sync = latest and latest["target_base"] == base and op == "sync"
            present = final.exists()
            if present and not owned_sync:
                published = job.get("publishing") and str(final.stat().st_ino) == job.get("publication_inode")
                owned = (
                    published
                    or (latest and base == latest["target_base"])
                    or any(
                        a["directory"] == job["destination"] and a["relative_path"] == p["relative_path"]
                        for a in state["studies"].get(job["name"].casefold(), {}).get("aliases", [])
                        for p in targets
                    )
                )
                if not owned or op == "restore" and not job.get("publishing"):
                    raise StorageConflict("destination already exists and is not owned by this transfer")
                if not same_workspace(paths, expected):
                    raise StorageConflict("retained destination differs; choose an empty destination")
            self.update(
                ident,
                target_base=base,
                source_inodes={k: str(p.stat().st_ino) for k, p in sources.items()},
                source_parents={k: str(p.parent.stat().st_ino) for k, p in sources.items()} if len(targets) > 1 else {},
            )
            self._stage(stage, ident)
            work = final if present else stage / "data"
            output = {k: work if len(targets) == 1 else work / k for k in sources}
            known = self.verified_inventory(latest) if owned_sync else {}
            count, copied = self._copy(
                state,
                job,
                entry,
                disk,
                sources,
                output,
                stage,
                expected,
                known,
                handles,
                mutable=bool(owned_sync),
                exact=not owned_sync,
            )
            if files.inventory(sources, handles) != expected:
                raise StorageConflict("source changed before publication")
            if wrapper and files.times(wrapper.stat()) != wrapper_times:
                raise StorageConflict("source workspace changed before publication")
            if volumes.mounted_directory(entry) != disk:
                raise StorageConflict("destination disk changed before publication")
            if not present:
                final.parent.mkdir(parents=True, exist_ok=True)
                self.update(ident, publishing=True, publication_inode=str(work.stat().st_ino))
                publish_directory(work, final)
                # Windows can carry a previous creation time across a rename (file tunneling).
                for key in sources:
                    files.set_times(paths[key], expected[key, "."])
                if files.inventory({k: paths[k] for k in sources}) != expected:
                    raise StorageConflict("published destination failed verification")
            if wrapper_times:
                files.set_times(final, wrapper_times)
            if entry["limit_bytes"] is not None and volumes.tree_usage(disk) > entry["limit_bytes"]:
                raise StorageConflict("directory exceeded its quota before activation")
            if op == "backup":
                self._backup_receipt(job, final, targets)
            self._commit(job, targets, base, expected, count, copied)
            try:
                (stage / "owner.json").unlink()
                stage.rmdir()
            except OSError:
                pass
        return self.job(ident)

    @staticmethod
    def _stage(path, ident):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir()
        except FileExistsError:
            if read_json(path / "owner.json").get("id") != ident:
                raise StorageConflict("staging directory belongs to another operation") from None
        else:
            atomic_json(path / "owner.json", {"id": ident})

    @staticmethod
    def _replica(state, job):
        return max(
            (
                j
                for j in state.get("transfers", {}).values()
                if j["name"] == job["name"]
                and j["operation"] == "sync"
                and j["status"] == "complete"
                and j["destination"] == job["destination"]
            ),
            key=lambda j: j["created"],
            default=None,
        )

    def _copy(self, state, job, entry, disk, sources, output, stage, expected, known, handles, *, mutable, exact):
        ident = job["id"]
        unit = volumes.allocation_unit(disk)
        floor = max(d["reserve_bytes"] for d in state["directories"].values() if d["volume"] == entry["volume"])
        temp = under_root(stage, "copy.partial")
        temp.unlink(missing_ok=True)
        changed, directories = [], []
        needed = 0
        for (part, key), meta in expected.items():
            dest = files.member(output[part], key)
            if meta["kind"] == "directory":
                directories.append((dest, meta))
                continue
            if dest.exists():
                if not dest.is_file():
                    raise StorageConflict(f"file conflicts with a directory: {dest}")
                same = dest.stat().st_size == meta["bytes"] and files.digest(dest, {}) == meta["sha256"]
                if same:
                    if files.times(dest.stat()) != {k: meta[k] for k in files.times(dest.stat())}:
                        if dest.stat().st_nlink > 1:
                            raise StorageConflict(f"destination timestamp is shared through a hard link: {dest}")
                        if mutable and (part, key) not in known:
                            raise StorageConflict(f"unmanaged destination file: {dest}")
                        files.set_times(dest, meta)
                    continue
                if mutable and known.get((part, key), {}).get("sha256") != files.digest(dest, {}):
                    raise StorageConflict(f"destination file has independent changes: {dest}")
            changed.append((part, key, dest, meta))
            needed += ((meta["bytes"] + unit - 1) // unit) * unit
        with file_lock(self.pool.lock):
            s = self.pool._read()
            others = [j for j in s["transfers"].values() if j["id"] != ident]
            rows, _ = scan_pool(s["directories"], s["studies"], others)
            if rows[job["destination"]]["available_bytes"] < needed:
                raise StorageConflict("insufficient destination space after reservations and disk floor")
            s["transfers"][ident]["remaining_bytes"] = needed
            atomic_json(self.pool.file, s)

        next_quota_check = 0

        def check(size):
            nonlocal next_quota_check
            if volumes.mounted_directory(entry) != disk or volumes.free_bytes(disk) < size + floor:
                raise StorageConflict("destination disconnected or disk reserve reached")
            if entry["limit_bytes"] is not None and next_quota_check <= 0:
                if volumes.tree_usage(disk) + size > entry["limit_bytes"]:
                    raise StorageConflict("directory quota reached during transfer")
                next_quota_check = 64 * 1024**2
            next_quota_check -= size

        for path, _meta in directories:
            path.mkdir(parents=True, exist_ok=True)
        count = copied = pending = 0
        for part, key, dest, meta in changed:
            files.copy_file(files.member(sources[part], key), dest, temp, meta, handles, check)
            count += 1
            copied += meta["bytes"]
            used = ((meta["bytes"] + unit - 1) // unit) * unit
            needed -= used
            pending += used
            if pending >= 64 * 1024**2:
                self.update(ident, remaining_bytes=needed, copied_bytes=copied)
                pending = 0
        for path, meta in reversed(directories):
            files.set_times(path, meta)
        actual = files.inventory(output)
        if (actual if exact else {k: actual.get(k) for k in expected}) != expected:
            raise StorageConflict("destination content or timestamps failed verification")
        return count, copied

    def _backup_receipt(self, job, final, targets):
        from .experiment_volumes import manifest_path

        dest = final.parent / "inventory.jsonl.gz"
        with self.manifest(job["id"]).open("rb") as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
            out.flush()
            os.fsync(out.fileno())
        zip_manifest = manifest_path(self.pool, job["name"])
        receipt = {
            "schema": "threemind.experiment-backup/1",
            "id": job["id"],
            "name": job["name"],
            "parts": targets,
            "root_times": files.times(final.stat()),
            "inventory_sha256": files.digest(dest, {}),
            "zip_manifest": read_json(zip_manifest) if zip_manifest.exists() else None,
        }
        atomic_json(final.parent / "receipt.json", receipt)

    def _backup_inventory(self, state, ident):
        job = state["transfers"][ident]
        base = under_root(volumes.mounted_directory(state["directories"][job["destination"]]), job["target_base"])
        receipt_path = base.parent / "receipt.json"
        receipt = read_json(receipt_path)
        index = checked_path(base.parent / "inventory.jsonl.gz")
        if (
            receipt["id"] != ident
            or receipt["name"] != job["name"]
            or files.digest(index, {}) != receipt["inventory_sha256"]
            or receipt["inventory_sha256"] != job["backup_sha256"]
            or files.times(base.stat()) != receipt["root_times"]
            or files.digest(receipt_path, {}) != job["receipt_sha256"]
        ):
            raise StorageConflict("backup inventory integrity check failed")
        return files.read_inventory(index)

    def _commit(self, job, parts, base, expected, count, copied):
        from .experiment_volumes import manifest_path

        with file_lock(self.pool.lock):
            state = self.pool._read()
            row = state["transfers"][job["id"]]
            op = job["operation"]
            study = state["studies"].get(job["name"].casefold())
            if op in MOVES:
                if study["parts"] != job["source_parts"]:
                    raise StorageConflict("experiment placement changed before activation")
                aliases = study.setdefault("aliases", [])
                for part in study["parts"]:
                    alias = {k: part[k] for k in ("name", "directory", "relative_path")}
                    alias["original_path"] = str(
                        Path(state["directories"][part["directory"]]["path"]) / part["relative_path"]
                    )
                    if alias not in aliases:
                        aliases.append(alias)
                study.update(parts=parts, residency="archived" if op == "archive" else "active", transfer_id=job["id"])
            if op == "backup":
                row["backup_sha256"] = files.digest(self.manifest(job["id"]), {})
                disk = volumes.mounted_directory(state["directories"][job["destination"]])
                row["receipt_sha256"] = files.digest(under_root(disk, base).parent / "receipt.json", {})
            if op == "restore":
                name = job["restore_as"]
                if name.casefold() in state["studies"]:
                    raise StorageConflict("restored experiment name has already been used")
                version = state["transfers"][job["backup"]]
                disk = volumes.mounted_directory(state["directories"][version["destination"]])
                receipt = read_json(under_root(disk, version["target_base"]).parent / "receipt.json")
                if receipt["zip_manifest"]:
                    atomic_json(manifest_path(self.pool, name), dict(receipt["zip_manifest"], name=name))
                state["studies"][name.casefold()] = {
                    "name": name,
                    "request": {
                        "name": name,
                        "allow_split": False,
                        "parts": [{k: p[k] for k in ("kind", "name", "bytes")} for p in parts],
                    },
                    "status": "complete",
                    "parts": parts,
                    "restored_from": version["id"],
                    "residency": "active",
                }
            row.update(
                target_parts=parts,
                target_base=base,
                status="complete",
                remaining_bytes=0,
                error=None,
                inventory_sha256=files.digest(self.manifest(job["id"]), {}),
                copied_files=count,
                copied_bytes=copied,
                files=sum(m["kind"] == "file" for m in expected.values()),
                bytes=sum(m.get("bytes", 0) for m in expected.values()),
                completed=time(),
            )
            atomic_json(self.pool.file, state)

    def cancel(self, ident):
        job = self.job(ident)
        with self.pool.study_lock(job["name"]):
            job = self.job(ident)
            if job["status"] == "cancelled":
                return job
            if job["status"] in FINISHED or job.get("publishing"):
                raise StorageConflict("this transfer has published its destination; resume or retain it")
            if not job.get("target_base"):
                self.update(ident, status="cancelled", remaining_bytes=0)
                return self.job(ident)
            state = self.pool._read()
            root = volumes.mounted_directory(state["directories"][job["destination"]])
            stage = under_root(root, ".threemind-transfers/" + job["id"])
            if stage.exists():
                if read_json(stage / "owner.json").get("id") != ident:
                    raise StorageConflict("unrecognized staging directory")
                files.inventory({"staging": stage}, hashes=False)
                shutil.rmtree(checked_path(stage))
            self.update(ident, status="cancelled", remaining_bytes=0)
        return self.job(ident)

    def release(self, ident):
        job = self.job(ident)
        with self.pool.study_lock(job["name"]):
            job = self.job(ident)
            if job["status"] == "released":
                return job
            if job["operation"] not in MOVES or job["status"] != "complete":
                raise StorageConflict("only a verified location change has an old copy to release")
            state = self.pool._read()
            active = locations(state, state["studies"][job["name"].casefold()]["parts"])
            old = locations(state, job["source_parts"])
            if any(overlaps(a, b) for a in active.values() for b in old.values()):
                raise StorageConflict("the old location is in use again")
            expected = self.verified_inventory(job)
            active = {k: p for k, p in active.items() if p.is_dir()}
            old = {k: old[k] for k in job["source_inodes"]}
            all_roots = {str(p): p for p in [*active.values(), *old.values()]}
            with (
                self.guards(active, moving=True, resource_roots=all_roots) as handles,
                file_lock(self.storage.control_dir / "registry.lock"),
            ):
                if files.inventory(active, handles) != expected:
                    raise StorageConflict("active copy differs from the transfer; original retained")
                progress = job.get("release_parts", {})
                if not progress:
                    with self.guards(old, resources=False) as locked:
                        if files.inventory(old, locked) != expected:
                            raise StorageConflict("original changed since the verified copy; retained")
                        for key, path in old.items():
                            if str(path.stat().st_ino) != job["source_inodes"][key]:
                                raise StorageConflict("original directory identity changed")
                            self._check_links(path)
                for part in job["source_parts"]:
                    key = part["name"]
                    if key not in old or progress.get(key) == "released":
                        continue
                    original = old[key]
                    disk = volumes.mounted_directory(state["directories"][part["directory"]])
                    retired = under_root(disk, ".threemind-retired/" + ident + "/" + key)
                    if retired.exists():
                        if original.exists() or key not in progress:
                            raise StorageConflict("source or retirement directory has been replaced")
                    elif progress.get(key) == "pruning" and not original.exists():
                        progress[key] = "released"
                        self.update(ident, release_parts=progress)
                        continue
                    else:
                        if not original.is_dir() or str(original.stat().st_ino) != job["source_inodes"][key]:
                            raise StorageConflict("original directory identity changed")
                        subset = {k: v for k, v in expected.items() if k[0] == key}
                        with self.guards({key: original}, resources=False) as locked:
                            if files.inventory({key: original}, locked) != subset:
                                raise StorageConflict("original changed since the verified copy; retained")
                            self._check_links(original)
                        progress[key] = "verified"
                        self.update(ident, release_parts=progress)
                        retired.parent.mkdir(parents=True, exist_ok=True)
                        publish_directory(original, retired)
                    if str(retired.stat().st_ino) != job["source_inodes"][key]:
                        raise StorageConflict("retired directory identity changed")
                    subset = {k: v for k, v in expected.items() if k[0] == key}

                    def mounted(retired=retired, disk=disk, key=key, part=part):
                        for p in state["studies"][job["name"].casefold()]["parts"]:
                            volumes.mounted_directory(state["directories"][p["directory"]])
                        if (
                            volumes.mounted_directory(state["directories"][part["directory"]]) != disk
                            or str(retired.stat().st_ino) != job["source_inodes"][key]
                        ):
                            raise StorageConflict("retired source volume or directory has changed")

                    self._prune(ident, key, retired, subset, progress, mounted)
                for part in job["source_parts"]:
                    key = part["name"]
                    if key not in job.get("source_parents", {}):
                        continue
                    disk = volumes.mounted_directory(state["directories"][part["directory"]])
                    parent = under_root(disk, part["relative_path"]).parent
                    if (
                        parent != disk
                        and parent.exists()
                        and str(parent.stat().st_ino) == job["source_parents"][key]
                        and not any(parent.iterdir())
                    ):
                        parent.rmdir()
            self.update(ident, status="released", released=time())
        return self.job(ident)

    @staticmethod
    def _check_links(root):
        for parent, _, names in os.walk(root, onerror=_raise):
            for name in names:
                if checked_path(Path(parent) / name).stat().st_nlink > 1:
                    raise StorageConflict("source has hard-linked files; retain it or resolve shared ownership")

    def _prune(self, ident, key, root, expected, progress, mounted):
        with self.guards({key: root}, resources=False) as handles:
            actual = files.inventory({key: root}, handles)
            partial = progress.get(key) == "pruning"
            if (not partial and actual != expected) or any(
                k not in expected or (v != expected[k] and (v["kind"] != "directory" or not partial))
                for k, v in actual.items()
            ):
                raise StorageConflict("retired source contents changed; remaining files retained")
            self._check_links(root)
            progress[key] = "pruning"
            self.update(ident, release_parts=progress)
        for (_, rel), meta in reversed(list(actual.items())):
            path = files.member(root, rel)
            mounted()
            if meta["kind"] == "directory":
                path.rmdir()
            else:
                if (
                    path.stat().st_nlink != 1
                    or files.digest(path, {}) != meta["sha256"]
                    or (files.times(path.stat()) != {k: meta[k] for k in files.times(path.stat())})
                ):
                    raise StorageConflict(f"retired source file changed: {path}")
                path.unlink()
        progress[key] = "released"
        self.update(ident, release_parts=progress)

    def import_backup(self, name, directory, backup):
        """Register a self-contained backup generation on a newly configured host."""
        from .experiment_storage import integer

        name, backup = component(name), str(UUID(backup))
        with file_lock(self.pool.lock):
            state = self.pool._read()
            entry = self.directory(state, directory)
            base = f"backups/{name}/{backup}/data"
            path = under_root(volumes.mounted_directory(entry), base)
            receipt = read_json(path.parent / "receipt.json")
            if (receipt.get("schema"), receipt.get("name"), receipt.get("id")) != (
                "threemind.experiment-backup/1",
                name,
                backup,
            ):
                raise StorageConflict("backup receipt does not match this experiment and version")
            disk_manifest = checked_path(path.parent / "inventory.jsonl.gz")
            if files.digest(disk_manifest, {}) != receipt["inventory_sha256"]:
                raise StorageConflict("backup inventory failed its receipt checksum")
            parts = []
            for item in receipt["parts"]:
                if item["kind"] not in ("data", "archive", "readback"):
                    raise StorageConflict("invalid part type in backup")
                parts.append({"name": component(item["name"]), "bytes": integer(item["bytes"]), "kind": item["kind"]})
            if not 1 <= len(parts) <= 128 or len({p["name"].casefold() for p in parts}) != len(parts):
                raise StorageConflict("invalid backup part list")
            parts = mapped_parts(parts, directory, base)
            jobs = state.setdefault("transfers", {})
            if backup in jobs:
                if (
                    jobs[backup].get("backup_sha256") == receipt["inventory_sha256"]
                    and jobs[backup]["destination"] == directory
                ):
                    return jobs[backup]
                raise StorageConflict("backup ID collision")
            jobs[backup] = {
                "id": backup,
                "name": name,
                "operation": "backup",
                "destination": directory,
                "status": "complete",
                "backup": None,
                "restore_as": None,
                "created": time(),
                "target_parts": parts,
                "target_base": base,
                "backup_sha256": receipt["inventory_sha256"],
                "receipt_sha256": files.digest(path.parent / "receipt.json", {}),
            }
            atomic_json(self.pool.file, state)
            return jobs[backup]


def _raise(exc):
    raise exc
