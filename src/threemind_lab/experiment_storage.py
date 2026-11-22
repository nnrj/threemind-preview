"""Host placement and peak-space reservations for complete experiments or named parts."""

import hashlib
import os
import tempfile
from contextlib import ExitStack, suppress
from copy import deepcopy
from pathlib import Path

from . import storage_volumes as volumes
from .storage_files import (
    StorageConflict,
    atomic_json,
    file_lock,
    publish_directory,
    read_json,
    relative_key,
    under_root,
)


def component(value):
    if len(relative_key(value).parts) != 1 or len(value) > 120:
        raise ValueError("expected one portable directory name of at most 120 characters")
    return value


def discard_empty_directory(path, identity):
    with suppress(OSError, StorageConflict):
        if volumes.directory_identity(path) == identity:
            path.rmdir()


def integer(value, *, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**53 - 1:
        raise ValueError(f"expected an integer between {minimum} and {2**53 - 1}")
    return value


def has_run_directories(state):
    return any(d.get("role", "run") == "run" for d in state["directories"].values())


def sized_blocks(stream, size):
    while size:
        block = stream.read(min(size, 1024**2))
        if not block or len(block) > size:
            raise ValueError("stream length differs from its declared size")
        yield block
        size -= len(block)
    if stream.read(1):
        raise ValueError("stream exceeds its declared size")


def scan_pool(directories, studies, transfers=(), *, topology=False):
    """Subtract outstanding promises once per directory and once per physical volume."""
    rows, capacity, floor, promised = {}, {}, {}, {}
    devices = {}
    for key, entry in directories.items():
        row = rows[key] = dict(entry, online=False, available_bytes=0, reserved_bytes=0)
        vol = entry["volume"]
        floor[vol] = max(floor.get(vol, 0), entry["reserve_bytes"])
        assigned = [
            p for st in studies.values() if st["status"] == "reserved" for p in st["parts"] if p["directory"] == key
        ]
        remaining = sum(p["bytes"] for p in assigned)
        try:
            root = volumes.mounted_directory(entry)
            if topology:
                if vol not in devices:
                    devices[vol] = volumes.physical_disks(vol, root)
                row["physical_disks"] = devices[vol]
            capacity[vol] = volumes.free_bytes(root)
            used = volumes.tree_usage(root) if entry["limit_bytes"] is not None else None
            remaining = sum(
                max(0, p["bytes"] - volumes.tree_usage(under_root(root, p["relative_path"]))) for p in assigned
            )
            row.update(path=str(root), online=True, used_bytes=used, reserved_bytes=remaining)
        except (OSError, StorageConflict) as exc:
            row["reason"] = str(exc)
        for job in transfers:
            if job["destination"] == key:
                remaining += job.get("remaining_bytes", 0)
        row["reserved_bytes"] = remaining
        promised[vol] = promised.get(vol, 0) + remaining
    shared = {v: max(0, n - floor[v] - promised.get(v, 0)) for v, n in capacity.items()}
    for row in rows.values():
        if row["online"]:
            free = shared[row["volume"]]
            if row["limit_bytes"] is not None:
                free = min(free, row["limit_bytes"] - row["used_bytes"] - row["reserved_bytes"])
            row.update(free_bytes=capacity[row["volume"]], available_bytes=max(0, free))
    return rows, shared


def assign(parts, rows, shared, split):
    available = {
        k: r["available_bytes"] for k, r in rows.items()
        if r["online"] and r["enabled"] and r.get("role", "run") == "run"
    }
    balances = shared.copy()

    def candidates(size):
        room = {k: min(n, balances[rows[k]["volume"]]) for k, n in available.items()}
        return sorted((k for k in room if room[k] >= size), key=lambda k: (rows[k]["priority"], -room[k], k))

    whole = candidates(sum(p["bytes"] for p in parts))
    if whole:
        return dict.fromkeys((p["name"] for p in parts), whole[0])
    if not split:
        return None
    ordered = sorted(parts, key=lambda p: -p["bytes"])
    choices = {}
    remaining_search = 50000

    def place(index):
        nonlocal remaining_search
        if index == len(ordered):
            return True
        remaining_search -= 1
        if remaining_search < 0:
            raise StorageConflict("placement search limit reached; group the budget into fewer parts")
        part = ordered[index]
        size = part["bytes"]
        seen = set()
        for key in candidates(size):
            vol = rows[key]["volume"]
            signature = (vol, available[key])
            if signature in seen:
                continue
            seen.add(signature)
            choices[part["name"]] = key
            available[key] -= size
            balances[vol] -= size
            if place(index + 1):
                return True
            available[key] += size
            balances[vol] += size
        return False

    return choices if place(0) else None


class ExperimentStorage:
    def __init__(self, storage):
        self.storage = storage
        self.file = storage.control_dir / "experiment-storage.json"
        self.lock = storage.control_dir / "experiment-storage.lock"

    def _read(self):
        if not self.file.exists():
            return {"schema": "threemind.experiment-storage/1", "revision": 0, "directories": {}, "studies": {}}
        state = read_json(self.file)
        if state.get("schema") != "threemind.experiment-storage/1":
            raise StorageConflict("unknown experiment storage configuration")
        return state

    def configure(self, directories, expected_revision):
        if not isinstance(directories, list) or len(directories) > 64:
            raise ValueError("expected at most 64 storage directories")
        with file_lock(self.lock), ExitStack() as cleanup:
            s = self._read()
            if integer(expected_revision) != s["revision"]:
                raise StorageConflict("storage configuration changed; refresh before saving")
            in_use = {p["directory"] for st in s["studies"].values() for p in st["parts"]}
            in_use.update(a["directory"] for st in s["studies"].values() for a in st.get("aliases", []))
            in_use.update(j["destination"] for j in s.get("transfers", {}).values() if j["status"] != "cancelled")
            updated, paths = {}, []
            for item in directories:
                key = component(item["id"])
                path = self.storage._outside_control(item["path"])
                if key.casefold() in {k.casefold() for k in updated} or path == Path(path.anchor):
                    raise ValueError("use distinct directory IDs and dedicated subdirectories")
                if any(path.is_relative_to(p) or p.is_relative_to(path) for p in paths):
                    raise ValueError("storage directories must not overlap")
                paths.append(path)
                old = s["directories"].get(key)
                limit = item.get("limit_bytes")
                if limit is not None:
                    integer(limit)
                enabled = item.get("enabled", True)
                role = item.get("role") or (old or {}).get("role", "run")
                if role not in ("run", "archive", "backup"):
                    raise ValueError("directory role must be run, archive or backup")
                if key in in_use and old and old.get("role", "run") != role:
                    raise StorageConflict("existing experiment locations pin this directory role")
                if type(enabled) is not bool:
                    raise ValueError("enabled must be a boolean")
                opts = {
                    "priority": integer(item.get("priority", 0)),
                    "limit_bytes": limit,
                    "reserve_bytes": integer(item.get("reserve_bytes", 0)),
                    "enabled": enabled,
                    "role": role,
                }
                if old and Path(old["path"]) == path:
                    entry = old
                else:
                    # Never fabricate a missing mount tree. Only create a new leaf on an attached disk.
                    if not path.parent.is_dir():
                        raise ValueError(f"parent directory is unavailable: {path.parent}")
                    try:
                        path.mkdir()
                    except FileExistsError:
                        if not path.is_dir():
                            raise ValueError(f"storage location is not a directory: {path}") from None
                        identity = volumes.directory_identity(path)
                    else:
                        identity = volumes.directory_identity(path)
                        cleanup.callback(discard_empty_directory, path, identity)
                    entry = dict(path=str(path), **identity)
                    if key in in_use and (entry["volume"], entry["inode"]) != (old["volume"], old["inode"]):
                        raise StorageConflict("existing experiment placements pin this directory identity")
                updated[key] = dict(entry, **opts)
            if in_use - updated.keys():
                raise StorageConflict("disable a directory with existing placements instead of removing it")
            physical = set()
            for entry in updated.values():
                for vol, rel in physical:
                    a, b = Path(entry["relative"]), Path(rel)
                    if vol == entry["volume"] and (a.is_relative_to(b) or b.is_relative_to(a)):
                        raise ValueError("two directory entries address overlapping space")
                physical.add((entry["volume"], entry["relative"]))
            s.update(directories=updated, revision=s["revision"] + 1)
            atomic_json(self.file, s)
            cleanup.pop_all()
        return self.status()

    def status(self):
        s = self._read()
        rows, _ = scan_pool(s["directories"], s["studies"], s.get("transfers", {}).values(), topology=True)
        return {
            "revision": s["revision"],
            "directories": [dict(id=k, **rows[k]) for k in sorted(rows, key=lambda k: (rows[k]["priority"], k))],
            "studies": [
                {"name": st["name"], "status": st["status"], "residency": st.get("residency", "active")}
                for st in s["studies"].values()
            ],
        }

    def study_lock(self, name):
        identity = hashlib.sha256(component(name).casefold().encode()).hexdigest()
        return file_lock(self.storage.control_dir / "experiment-writers" / (identity + ".lock"))

    @staticmethod
    def _request(name, parts, allow_split):
        component(name)
        if type(allow_split) is not bool or not isinstance(parts, list) or not 1 <= len(parts) <= 128:
            raise ValueError("provide 1 to 128 budgeted parts and a boolean allow_split")
        result, keys = [], set()
        for p in parts:
            key = component(p["name"])
            kind = p.get("kind", "data")
            if key.casefold() in keys or kind not in ("data", "archive", "readback"):
                raise ValueError("part names must be distinct and kinds must be data, archive or readback")
            keys.add(key.casefold())
            result.append({"name": key, "kind": kind, "bytes": integer(p["bytes"], minimum=1)})
        return {"name": name, "allow_split": allow_split, "parts": result}

    def _plan(self, s, request):
        name, parts = request["name"], request["parts"]
        if any(j.get("restore_as") and j["restore_as"].casefold() == name.casefold()
               and j["status"] not in ("complete", "cancelled") for j in s.get("transfers", {}).values()):
            raise StorageConflict("a backup restore has reserved this experiment name")
        existing = s["studies"].get(name.casefold())
        if existing:
            if existing["request"] != request:
                raise StorageConflict("a different placement already exists for this experiment")
            return dict(existing, fits=True)
        if not has_run_directories(s):
            raise StorageConflict(
                "configure a directory to reserve capacity; ordinary single-root workspaces need no setup"
            )
        rows, shared = scan_pool(s["directories"], s["studies"], s.get("transfers", {}).values())
        default = self.storage.writable_root()
        if under_root(default, "experiments/" + name).exists():
            raise StorageConflict("this experiment already has a workspace; choose a new name")
        for row in rows.values():
            if row["online"] and under_root(Path(row["path"]), "experiments/" + name).exists():
                raise StorageConflict("an existing workspace already uses this name")
        if destination := request.get("directory_id"):
            if destination not in rows or rows[destination].get("role", "run") != "run":
                raise StorageConflict("the requested run directory is not registered")
            rows = {destination: rows[destination]}
        chosen = assign(parts, rows, shared, request["allow_split"])
        if chosen is None:
            return dict(
                request,
                fits=False,
                directories=rows,
                split_would_fit=bool(not request["allow_split"] and assign(parts, rows, shared, True)),
                shortage_single_bytes=max(
                    0,
                    sum(p["bytes"] for p in parts)
                    - max((r["available_bytes"] for r in rows.values() if r["enabled"] and r.get("role", "run") == "run"), default=0),
                ),
            )
        mapped = []
        for p in parts:
            rel = "experiments/" + name
            if len(parts) > 1:
                rel += "/" + p["name"]
            mapped.append(dict(p, directory=chosen[p["name"]], relative_path=rel))
        return {"request": deepcopy(request), "name": name, "status": "reserved", "parts": mapped, "fits": True}

    def preview(self, name, parts, allow_split=False, *, directory_id=None):
        request = self._request(name, parts, allow_split)
        if directory_id is not None:
            request["directory_id"] = component(directory_id)
        return self._plan(self._read(), request)

    def reserve(self, name, parts, allow_split=False, *, directory_id=None):
        request = self._request(name, parts, allow_split)
        if directory_id is not None:
            request["directory_id"] = component(directory_id)
        with file_lock(self.lock):
            s = self._read()
            result = self._plan(s, request)
            if not result["fits"]:
                raise StorageConflict("insufficient space for this placement; check the preview")
            if name.casefold() not in s["studies"]:
                s["studies"][name.casefold()] = result
                atomic_json(self.file, s)
            return result

    def study(self, name):
        study = self._read()["studies"].get(component(name).casefold())
        if not study:
            raise ValueError("unknown experiment placement")
        return study

    def binding(self, work):
        """Recognize a physical workspace passed to a legacy path-based study host."""
        if not self.file.exists():
            return None
        work = Path(work)
        state = self._read()
        for key in (work.name, work.parent.name):
            st = state["studies"].get(key.casefold())
            if not st:
                continue
            for p in st["parts"]:
                relative = Path(p["relative_path"])
                if Path(*work.parts[-len(relative.parts) :]) != relative:
                    continue
                entry = state["directories"][p["directory"]]
                root = volumes.mounted_directory(entry)
                if under_root(root, p["relative_path"]) == work:
                    return st["name"], p["name"]
        return None

    def part_root(self, name, part):
        state = self._read()
        study = state["studies"].get(component(name).casefold())
        if study:
            for item in study["parts"]:
                if item["name"] == part:
                    return volumes.mounted_directory(state["directories"][item["directory"]])
        raise ValueError("unknown experiment part")

    def guard(self, name, part, extra_bytes=0, *, check_directory=True):
        """Check actual writes, other reservations, and volume identity at writer boundaries."""
        extra_bytes = integer(extra_bytes)
        state = self._read()
        st = state["studies"].get(component(name).casefold())
        if not st or st["status"] != "reserved":
            raise StorageConflict("no open reservation for this experiment")
        p = next((v for v in st["parts"] if v["name"] == part), None)
        if p is None:
            raise ValueError("unknown experiment part")
        entry = state["directories"][p["directory"]]
        root = volumes.mounted_directory(entry)
        path = under_root(root, p["relative_path"])
        floor = max(r["reserve_bytes"] for r in state["directories"].values() if r["volume"] == entry["volume"])
        if volumes.free_bytes(root) < floor + extra_bytes:
            raise StorageConflict(f"disk reserve reached in {root}")
        if check_directory:
            if volumes.tree_usage(path) + extra_bytes > p["bytes"]:
                raise StorageConflict(f"experiment part exceeds its reservation: {part}")
            if entry["limit_bytes"] is not None and volumes.tree_usage(root) + extra_bytes > entry["limit_bytes"]:
                raise StorageConflict(f"directory quota reached in {root}")
        return path

    def write_file(self, name, part, member, stream, expected_bytes, *, sha256=None):
        """Publish an immutable file within its reserved part, including streamed API readback."""
        expected_bytes = integer(expected_bytes)
        with self.study_lock(name):
            root = self.path(name, part, writing=True)
            target = under_root(root, member)
            if target.exists():
                if target.is_file() and target.stat().st_size == expected_bytes:
                    if sha256 is None:
                        digest = hashlib.sha256()
                        for chunk in sized_blocks(stream, expected_bytes):
                            digest.update(chunk)
                        sha256 = digest.hexdigest()
                    with target.open("rb") as current:
                        if hashlib.file_digest(current, "sha256").hexdigest() == sha256:
                            return target
                raise StorageConflict("file already exists; existing evidence will be retained")
            unit = volumes.allocation_unit(self.part_root(name, part))
            self.guard(name, part, ((expected_bytes + unit - 1) // unit) * unit)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            staging = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=target.parent, prefix=".pool-", suffix=".partial", delete=False
                ) as out:
                    staging = Path(out.name)
                    for chunk in sized_blocks(stream, expected_bytes):
                        if self.guard(name, part, len(chunk), check_directory=False) != root:
                            raise StorageConflict("disk mount changed during write")
                        out.write(chunk)
                        digest.update(chunk)
                    if sha256 is not None and digest.hexdigest() != sha256:
                        raise ValueError("input SHA-256 differs from the expected file")
                    out.flush()
                    os.fsync(out.fileno())
                if self.guard(name, part) != root:
                    raise StorageConflict("disk mount changed before publication")
                publish_directory(staging, target)
                return target
            finally:
                if staging is not None:
                    with suppress(StorageConflict, OSError):
                        if self.path(name, part) == root:
                            staging.unlink(missing_ok=True)

    def cancel(self, name):
        """Only an unused reservation can be discarded. Scientific files are never removed."""
        with self.study_lock(name), file_lock(self.lock):
            state = self._read()
            key = component(name).casefold()
            st = state["studies"].get(key)
            if st is None:
                return {"name": name, "status": "unreserved"}
            if st["status"] != "reserved":
                raise StorageConflict("completed placement is retained")
            for p in st["parts"]:
                path = self.path(name, p["name"])
                if path.exists():
                    raise StorageConflict("experiment has already created a workspace")
            del state["studies"][key]
            atomic_json(self.file, state)
            return {"name": name, "status": "unreserved"}

    def path(self, name, part=None, *, writing=False):
        s = self._read()
        study = s["studies"].get(component(name).casefold())
        if study is None:
            legacy = under_root(self.storage.writable_root(), "experiments/" + name)
            if part is not None or (has_run_directories(s) and not legacy.is_dir()):
                raise StorageConflict("reserve the new experiment and its peak space before requesting its workspace")
            return legacy
        if writing and study["status"] != "reserved":
            raise StorageConflict("experiment placement has been completed")
        parts = study["parts"]
        if part is None:
            if len({p["directory"] for p in parts}) != 1:
                raise StorageConflict("this experiment spans directories; select its named part")
            directory, rel = parts[0]["directory"], parts[0]["relative_path"]
            if len(parts) > 1:
                rel = Path(rel).parent.as_posix()
        else:
            item = next((p for p in parts if p["name"] == component(part)), None)
            if not item:
                raise ValueError("unknown experiment part")
            directory, rel = item["directory"], item["relative_path"]
        return under_root(volumes.mounted_directory(s["directories"][directory]), rel)

    def finish(self, name):
        with self.study_lock(name), file_lock(self.lock):
            s = self._read()
            st = s["studies"].get(component(name).casefold())
            if not st:
                raise ValueError("unknown experiment placement")
            if st["status"] != "complete":
                from .experiment_volumes import verify_archive

                used_volumes = set()
                if any(p["kind"] == "archive" for p in st["parts"]):
                    manifest = verify_archive(self, name)
                    used_volumes = {row["part"] for row in manifest["volumes"]}
                for p in st["parts"]:
                    if p["kind"] == "archive" and p["name"] not in used_volumes:
                        continue
                    root = volumes.mounted_directory(s["directories"][p["directory"]])
                    path = under_root(root, p["relative_path"])
                    if not path.is_dir():
                        raise StorageConflict(f"missing experiment part: {p['name']}")
                    self.guard(name, p["name"])
                st["status"] = "complete"
                atomic_json(self.file, s)
            return st
