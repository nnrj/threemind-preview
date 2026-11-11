"""Bounded, content-addressed experiment archives. No executable serialization.

ZIP members are fixed-size SHA-256 chunks; logical names never become disk paths.
Readers verify both chunks and whole entries before permitting a resume.
"""

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass

SCHEMA = "threemind.experiment-bundle/1"
CHUNK = 4 * 1024**2
MANIFEST_LIMIT = 4 * 1024**2
SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ArchiveLimits:
    compressed: int = 8 * 1024**3
    expanded: int = 20 * 1024**3
    files: int = 4096
    chunks: int = 32768


DEFAULT_LIMITS = ArchiveLimits()


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str
    ).encode()


def safe_name(name):
    if (
        not isinstance(name, str)
        or not name
        or len(name) > 240
        or name.startswith("/")
        or "\\" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
        or any(ord(c) < 32 for c in name)
        or ":" in name
    ):
        raise ValueError("invalid logical archive name")
    return name


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


class ArchiveWriter:
    def __init__(self, stream, metadata, *, limits=DEFAULT_LIMITS, check=lambda: None, schema=SCHEMA):
        self.stream, self.metadata, self.limits, self.check = stream, metadata, limits, check
        self.schema = schema
        self.archive = zipfile.ZipFile(stream, "w", allowZip64=True)
        self.files, self.chunks, self.expanded = {}, set(), 0

    def add(self, name, values, *, media_type="application/octet-stream", compressed=False):
        safe_name(name)
        if name in self.files or len(self.files) >= self.limits.files:
            raise ValueError("duplicate entry or too many logical files")
        pending, chunks, digest, size = bytearray(), [], hashlib.sha256(), 0

        def emit(part):
            nonlocal size
            self.check()
            size += len(part)
            self.expanded += len(part)
            if self.expanded > self.limits.expanded:
                raise ValueError("experiment expanded-byte budget exceeded")
            digest.update(part)
            checksum = hashlib.sha256(part).hexdigest()
            chunks.append(checksum)
            if checksum not in self.chunks:
                if len(self.chunks) >= self.limits.chunks:
                    raise ValueError("too many experiment chunks")
                info = zipfile.ZipInfo(f"chunks/{checksum}")
                info.compress_type = zipfile.ZIP_STORED if compressed else zipfile.ZIP_DEFLATED
                with self.archive.open(info, "w", force_zip64=True) as member:
                    member.write(part)
                self.chunks.add(checksum)
            if self.stream.tell() > self.limits.compressed:
                raise ValueError("experiment compressed-byte budget exceeded")

        iterator = iter(values)
        try:
            for value in iterator:
                view = memoryview(value)
                while view:
                    count = min(CHUNK - len(pending), len(view))
                    pending.extend(view[:count])
                    view = view[count:]
                    if len(pending) == CHUNK:
                        emit(pending)
                        pending.clear()
            if pending:
                emit(pending)
        finally:
            close = getattr(iterator, "close", None)
            if close:
                close()
        self.files[name] = {"bytes": size, "sha256": digest.hexdigest(), "chunks": chunks, "media_type": media_type}

    def json(self, name, value):
        self.add(name, [canonical(value)], media_type="application/json")

    def finish(self):
        manifest = {"schema": self.schema, "metadata": self.metadata, "files": self.files, "expanded_bytes": self.expanded}
        raw = canonical(manifest)
        if len(raw) > MANIFEST_LIMIT:
            raise ValueError("experiment manifest too large")
        self.archive.writestr("manifest.json", raw, compress_type=zipfile.ZIP_DEFLATED)
        self.archive.close()
        if self.stream.tell() > self.limits.compressed:
            raise ValueError("experiment compressed-byte budget exceeded")
        self.stream.seek(0)
        return manifest

    def close(self):
        self.archive.close()


class ArchiveReader:
    def __init__(self, stream, *, limits=DEFAULT_LIMITS, check=lambda: None, schema=SCHEMA):
        self.stream, self.limits, self.check = stream, limits, check
        stream.seek(0, 2)
        if stream.tell() > limits.compressed:
            raise ValueError("experiment compressed-byte budget exceeded")
        stream.seek(0)
        self.archive = zipfile.ZipFile(stream)
        try:
            entries = self.archive.infolist()
            if len(entries) > limits.chunks + 1 or len({e.filename for e in entries}) != len(entries):
                raise ValueError("duplicate or excessive ZIP members")
            physical_bytes = 0
            for info in entries:
                if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError("unsupported encrypted/compressed ZIP member")
                if info.filename == "manifest.json":
                    if info.file_size > MANIFEST_LIMIT:
                        raise ValueError("experiment manifest too large")
                elif (
                    not info.filename.startswith("chunks/")
                    or not SHA.fullmatch(info.filename[7:])
                    or not 0 < info.file_size <= CHUNK
                ):
                    raise ValueError("unexpected or oversized ZIP member")
                physical_bytes += info.file_size
            if physical_bytes > limits.expanded + MANIFEST_LIMIT:
                raise ValueError("experiment expanded-byte budget exceeded")
            self.manifest = strict_json(self.archive.read("manifest.json"))
            if not isinstance(self.manifest, dict) or self.manifest.get("schema") != schema:
                raise ValueError("unsupported experiment archive schema")
            files = self.manifest.get("files")
            if not isinstance(files, dict) or len(files) > limits.files:
                raise ValueError("invalid experiment entries")
            expanded, used = 0, set()
            for name, item in files.items():
                safe_name(name)
                if not isinstance(item, dict) or type(item.get("bytes")) is not int or item["bytes"] < 0:
                    raise ValueError("invalid entry byte count")
                if not isinstance(item.get("sha256"), str) or not SHA.fullmatch(item["sha256"]):
                    raise ValueError("invalid entry digest")
                chunks = item.get("chunks")
                if not isinstance(chunks, list) or len(chunks) > limits.chunks:
                    raise ValueError("invalid entry chunks")
                lengths = []
                for chunk in chunks:
                    if not isinstance(chunk, str) or not SHA.fullmatch(chunk):
                        raise ValueError("invalid chunk digest")
                    lengths.append(self.archive.getinfo(f"chunks/{chunk}").file_size)
                    used.add(chunk)
                if sum(lengths) != item["bytes"] or any(n != CHUNK for n in lengths[:-1]):
                    raise ValueError("entry/chunk sizes disagree")
                expanded += item["bytes"]
            if expanded > limits.expanded or expanded != self.manifest.get("expanded_bytes"):
                raise ValueError("experiment expanded-byte budget mismatch")
            if {e.filename for e in entries} != {"manifest.json", *(f"chunks/{c}" for c in used)}:
                raise ValueError("unreferenced archive members")
        except Exception:
            self.archive.close()
            raise

    def iter_bytes(self, name):
        item = self.manifest["files"][name]
        digest, size = hashlib.sha256(), 0
        for chunk in item["chunks"]:
            self.check()
            raw = self.archive.read(f"chunks/{chunk}")
            if hashlib.sha256(raw).hexdigest() != chunk:
                raise ValueError("experiment chunk checksum mismatch")
            digest.update(raw)
            size += len(raw)
            yield raw
        if size != item["bytes"] or digest.hexdigest() != item["sha256"]:
            raise ValueError("experiment entry checksum mismatch")

    def read(self, name, *, maximum=MANIFEST_LIMIT):
        if self.manifest["files"][name]["bytes"] > maximum:
            raise ValueError("entry exceeds bounded read size")
        return b"".join(self.iter_bytes(name))

    def json(self, name, *, maximum=MANIFEST_LIMIT):
        return strict_json(self.read(name, maximum=maximum))

    def rows(self, name, *, max_row_bytes=16 * 1024**2):
        pending = bytearray()
        for chunk in self.iter_bytes(name):
            pending.extend(chunk)
            while b"\n" in pending:
                line, _, tail = pending.partition(b"\n")
                pending = bytearray(tail)
                if len(line) > max_row_bytes:
                    raise ValueError("archive evidence row too large")
                yield strict_json(line)
            if len(pending) > max_row_bytes:
                raise ValueError("archive evidence row too large")
        if pending:
            raise ValueError("truncated archive JSONL entry")

    def verify(self):
        for name in self.manifest["files"]:
            for _ in self.iter_bytes(name):
                pass
        return self.manifest

    def close(self):
        self.archive.close()
