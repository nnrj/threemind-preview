"""Write one standard ZIP stream directly to budgeted volumes. Its manifest is published last."""

import hashlib
import io
import os
import zipfile
from bisect import bisect_right
from contextlib import contextmanager
from itertools import accumulate
from pathlib import Path
from tempfile import NamedTemporaryFile

from . import storage_volumes
from .storage_files import StorageConflict, atomic_json, checked_path, publish_directory, read_json, under_root

CHUNK = 1024**2


def manifest_path(pool, name):
    return under_root(pool.storage.control_dir, "experiment-archives/" + name.casefold() + ".json")


def digest_file(path):
    with checked_path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class VolumeWriter:
    def __init__(self, pool, study, parts):
        self.pool, self.study, self.parts = pool, study, parts
        self.rows, self.stream, self.part = [], None, None
        self.size, self.total = 0, 0
        self.digest = hashlib.sha256()

    def tell(self):
        return self.total

    def flush(self):
        if self.stream:
            self.stream.flush()

    def start(self):
        index = len(self.rows)
        if index >= len(self.parts):
            raise StorageConflict("archive exceeds its reserved volumes")
        self.part = self.parts[index]
        directory = self.pool.guard(self.study["name"], self.part["name"], check_directory=False)
        directory.mkdir(parents=True, exist_ok=True)
        unit = storage_volumes.allocation_unit(directory)
        self.limit = self.part["bytes"] // unit * unit
        if not self.limit:
            raise ValueError(f"archive volume budget is smaller than a disk allocation unit ({unit} bytes)")
        self.path = under_root(directory, "evidence.zip.part")
        self.temp = under_root(directory, ".evidence.zip.partial")
        # A retry can reuse a completely written volume without needing room for a second copy.
        self.reused = self.path.exists()
        if not self.reused and self.temp.exists():
            self.temp.unlink()
        self.stream = self.path.open("rb") if self.reused else self.temp.open("xb")
        self.size, self.digest = 0, hashlib.sha256()
        self.checked_until = 0

    def write(self, data):
        remaining = memoryview(data)
        while remaining:
            if self.stream is None:
                self.start()
            # Leave room for filesystem allocation rounding even with a non-aligned budget.
            limit = self.limit
            piece = remaining[: min(len(remaining), limit - self.size, CHUNK)]
            if not self.reused and self.size + len(piece) > self.checked_until:
                window = min(limit - self.size, CHUNK)
                self.check_mount(window)
                self.checked_until = self.size + window
            if self.reused:
                if self.stream.read(len(piece)) != piece:
                    raise StorageConflict("existing archive volume differs from the current evidence")
            else:
                self.stream.write(piece)
            self.digest.update(piece)
            self.size += len(piece)
            self.total += len(piece)
            remaining = remaining[len(piece) :]
            if self.size == limit:
                self.end()
        return len(data)

    def check_mount(self, next_bytes=0):
        directory = self.pool.guard(self.study["name"], self.part["name"], next_bytes, check_directory=False)
        if directory != self.path.parent:
            raise StorageConflict("archive disk mount changed; reopen the experiment and retry")

    def end(self):
        if not self.stream:
            return
        if self.reused:
            if self.stream.read(1):
                raise StorageConflict("existing archive volume has different length")
        else:
            self.stream.flush()
            os.fsync(self.stream.fileno())
        self.stream.close()
        self.stream = None
        self.check_mount()
        self.pool.guard(self.study["name"], self.part["name"])
        if not self.reused:
            publish_directory(self.temp, self.path)
        self.rows.append({"part": self.part["name"], "bytes": self.size, "sha256": self.digest.hexdigest()})


def create_archive(pool, name):
    dest = manifest_path(pool, name)
    with pool.study_lock(name):
        study = pool.study(name)
        if dest.exists():
            return verify_archive(pool, name)
        if study["status"] != "reserved":
            raise StorageConflict("reserve archive volumes before completing the placement")
        parts = [p for p in study["parts"] if p["kind"] == "archive"]
        data = [p for p in study["parts"] if p["kind"] == "data"]
        if not parts or not data:
            raise ValueError("declare data and archive parts in the experiment budget")
        for part in parts:
            pool.guard(name, part["name"])
        out = VolumeWriter(pool, study, parts)
        members = evidence_inventory(pool, name, data)
        try:
            archive = zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3)
            try:
                for member, (path, *_) in members.items():
                    archive.write(path, member)
            except BaseException:
                # An interrupted archive must not emit or publish its central directory.
                archive.fp = None
                raise
            finally:
                archive.close()
            out.end()
        finally:
            if out.stream:
                out.stream.close()
        if evidence_inventory(pool, name, data) != members:
            raise StorageConflict("experiment files changed while archiving; retain the original evidence and retry")
        result = {
            "schema": "threemind.experiment-zip-volumes/1",
            "name": study["name"],
            "members": len(members),
            "bytes": out.total,
            "volumes": out.rows,
        }
        check_volumes(pool, result)
        atomic_json(dest, result)
        return result


def _raise_io(error):
    raise error


def evidence_inventory(pool, name, parts):
    members = {}
    for part in parts:
        root = pool.path(name, part["name"])
        if not root.is_dir():
            raise StorageConflict(f"missing experiment data: {part['name']}")
        for parent, dirs, files in os.walk(root, onerror=_raise_io):
            dirs.sort()
            for child in dirs:
                checked_path(os.path.join(parent, child))
            for file in sorted(files):
                path = checked_path(os.path.join(parent, file))
                if not path.is_file():
                    raise StorageConflict(f"not a regular evidence file: {path}")
                stat = path.stat()
                member = part["name"] + "/" + path.relative_to(root).as_posix()
                members[member] = path, stat.st_size, stat.st_mtime_ns, stat.st_ino
    return members


def check_volumes(pool, manifest):
    for row in manifest["volumes"]:
        path = under_root(pool.path(manifest["name"], row["part"]), "evidence.zip.part")
        if not path.is_file() or path.stat().st_size != row["bytes"] or digest_file(path) != row["sha256"]:
            raise StorageConflict("archive verification failed for part " + row["part"])


def verify_archive(pool, name):
    dest = manifest_path(pool, pool.study(name)["name"])
    if not dest.is_file():
        raise StorageConflict("the experiment has no published archive manifest")
    manifest = read_json(dest)
    check_volumes(pool, manifest)
    return manifest


class VolumeReader(io.RawIOBase):
    """Seek across an ordered ZIP without assembling a second full copy on one disk."""

    def __init__(self, pool, manifest):
        self.pool, self.manifest = pool, manifest
        self.ends = list(accumulate(row["bytes"] for row in manifest["volumes"]))
        self.pos = 0
        self.index, self.file = None, None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=os.SEEK_SET):
        base = {os.SEEK_SET: 0, os.SEEK_CUR: self.pos, os.SEEK_END: self.ends[-1]}[whence]
        if base + offset < 0:
            raise OSError("cannot seek before the start of the archive")
        self.pos = base + offset
        return self.pos

    def readinto(self, buffer):
        index = bisect_right(self.ends, self.pos)
        if index == len(self.ends):
            return 0
        if self.index != index:
            if self.file:
                self.file.close()
            part = self.manifest["volumes"][index]["part"]
            root = self.pool.path(self.manifest["name"], part)
            self.file = under_root(root, "evidence.zip.part").open("rb")
            self.index = index
        self.file.seek(self.pos - (self.ends[index - 1] if index else 0))
        view = memoryview(buffer)[: self.ends[index] - self.pos]
        count = self.file.readinto(view)
        if not count and len(view):
            raise StorageConflict("archive segment ended early")
        self.pos += count
        return count

    def close(self):
        if self.file:
            self.file.close()
        super().close()


@contextmanager
def open_member(pool, name, member):
    """Verify the stored segments and open one original, including after completion."""
    from .storage_files import relative_key

    relative_key(member)
    manifest = verify_archive(pool, name)
    with io.BufferedReader(VolumeReader(pool, manifest)) as segments, zipfile.ZipFile(segments) as archive:
        try:
            entry = archive.getinfo(member)
        except KeyError as exc:
            raise ValueError("archive does not contain the requested file") from exc
        with archive.open(entry) as stream:
            yield entry, stream


def extract_member(pool, name, part, member):
    if not any(p["kind"] == "readback" and p["name"] == part for p in pool.study(name)["parts"]):
        raise ValueError("choose a reserved readback part")
    with open_member(pool, name, member) as (entry, stream):
        target = pool.write_file(name, part, member, stream, entry.file_size)
    return {"member": member, "path": str(target), "bytes": entry.file_size, "sha256": digest_file(target)}


def export_member(pool, name, member, output):
    """Copy a verified member to a new caller-selected local file."""
    target = checked_path(Path(output).absolute())
    if target.exists():
        raise StorageConflict("output already exists")
    with open_member(pool, name, member) as (entry, stream):
        if storage_volumes.free_bytes(target.parent) < entry.file_size:
            raise StorageConflict("insufficient space at the destination")
        stage, digest, count = None, hashlib.sha256(), 0
        try:
            with NamedTemporaryFile(dir=target.parent, suffix=".partial", delete=False) as temp:
                stage = Path(temp.name)
                while block := stream.read(CHUNK):
                    temp.write(block)
                    digest.update(block)
                    count += len(block)
                temp.flush()
                os.fsync(temp.fileno())
            if count != entry.file_size:
                raise StorageConflict("incomplete ZIP member")
            publish_directory(stage, target)
        finally:
            if stage is not None:
                stage.unlink(missing_ok=True)
        return {"member": member, "path": str(target), "bytes": count, "sha256": digest.hexdigest()}
