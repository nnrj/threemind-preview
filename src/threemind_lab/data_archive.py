"""Formal data archives: verified bounded volumes and a dependency manifest.

Logical members are never extracted to user-controlled paths. Unknown object
schemas retain their exact bytes, while unknown outer schemas are rejected.
"""

from __future__ import annotations

import hashlib
import zipfile
from contextlib import ExitStack
from dataclasses import dataclass, field
from uuid import UUID

from .data_catalog import NATIVE, SCHEMAS
from .experiment_archive import SHA, ArchiveLimits, ArchiveReader, safe_name, strict_json

SCHEMA = "threemind.data-bundle/1"
SET_SCHEMA = "threemind.data-bundle-set/1"
RECOVERY_SCHEMA = "threemind.data-recovery-manifest/1"


@dataclass(frozen=True)
class DataLimits:
    volume: ArchiveLimits = field(default_factory=ArchiveLimits)
    volumes: int = 32
    compressed: int = 64 * 1024**3
    expanded: int = 160 * 1024**3
    objects: int = 10000
    json_bytes: int = 64 * 1024**2


def stream_hash(stream, *, maximum=None, check=lambda: None):
    checksum, size = hashlib.sha256(), 0
    stream.seek(0)
    while chunk := stream.read(4 * 1024**2):
        check()
        checksum.update(chunk)
        size += len(chunk)
        if maximum is not None and size > maximum:
            raise ValueError("data volume exceeds compressed-byte budget")
    stream.seek(0)
    return size, checksum.hexdigest()


class DataReader:
    def __init__(self, source, *, limits=None, check=lambda: None):
        self.limits, self.check, self._stack = limits or DataLimits(), check, ExitStack()
        limits = self.limits
        try:
            if isinstance(source, dict):
                master, streams = source.get("manifest"), source.get("volumes", [])
            elif isinstance(source, (list, tuple)):
                master, streams = (source[0], source[1:]) if len(source) > 1 else (None, source)
            else:
                master, streams = None, [source]
            if not 1 <= len(streams) <= limits.volumes:
                raise ValueError("all bounded data volumes must be supplied together")
            if master is not None and not isinstance(master, dict):
                master.seek(0)
                raw = master.read(4 * 1024**2 + 1)
                if len(raw) > 4 * 1024**2:
                    raise ValueError("data volume index exceeds manifest budget")
                master = strict_json(raw)
            if master is not None and (not isinstance(master, dict) or master.get("schema") != SET_SCHEMA):
                raise ValueError("unsupported outer data volume index schema")
            self.readers, self.volumes = [], []
            compressed = expanded = 0
            recovery = None
            bundle_id = None
            for ordinal, stream in enumerate(streams):
                self.check()
                size, sha = stream_hash(stream, maximum=limits.volume.compressed, check=check)
                compressed += size
                if compressed > limits.compressed:
                    raise ValueError("data package total compressed-byte budget exceeded")
                reader = ArchiveReader(stream, limits=limits.volume, check=check, schema=SCHEMA)
                self._stack.callback(reader.close)
                reader.verify()
                metadata = reader.manifest.get("metadata", {})
                if not isinstance(metadata, dict):
                    raise ValueError("invalid data archive metadata")  # noqa: TRY004 - Invalid archive data uses the public validation error contract.
                if metadata.get("volume") != ordinal or metadata.get("volume_count") != len(streams):
                    raise ValueError("data volumes are missing, out of order, or from different sets")
                if ordinal == 0:
                    recovery, bundle_id = metadata.get("recovery"), metadata.get("bundle_id")
                    if str(UUID(str(bundle_id))) != bundle_id:
                        raise ValueError("invalid data bundle identity")
                elif metadata.get("bundle_id") != bundle_id or metadata.get("recovery") != recovery:
                    raise ValueError("data volume recovery identities do not agree")
                expanded += reader.manifest["expanded_bytes"]
                if expanded > limits.expanded:
                    raise ValueError("data package total expanded-byte budget exceeded")
                self.readers.append(reader)
                self.volumes.append({"ordinal": ordinal, "bytes": size, "sha256": sha,
                                     "filename": f"{bundle_id}.v{ordinal + 1:03d}.tmdata"})
            if len(streams) > 1 and master is None:
                raise ValueError("a multivolume data package requires its total manifest and volume hashes")
            if master is not None:
                if master.get("bundle_id") != bundle_id or master.get("recovery") != recovery:
                    raise ValueError("total manifest does not match its data volumes")
                declared = master.get("volumes", [])
                if len(declared) != len(self.volumes) or any(
                    any(a.get(k) != b[k] for k in ("ordinal", "bytes", "sha256"))
                    for a, b in zip(declared, self.volumes)
                ):
                    raise ValueError("data volume size/hash differs from its total manifest")
            self.manifest = {"schema": SET_SCHEMA, "bundle_id": bundle_id, "recovery": recovery, "volumes": self.volumes}
            self._validate_recovery()
        except (zipfile.BadZipFile, KeyError, TypeError, AttributeError) as error:
            self.close()
            raise ValueError("invalid formal data archive") from error
        except BaseException:
            self.close()
            raise

    def _validate_recovery(self):
        recovery = self.manifest["recovery"]
        if not isinstance(recovery, dict) or recovery.get("schema") != RECOVERY_SCHEMA:
            raise ValueError("formal data packages require a supported recovery manifest")
        if recovery.get("source_scope") == "host-research-resource":
            if recovery.get("source_project") is not None:
                raise ValueError("a host research archive cannot claim an invented project")
            UUID(str(recovery.get("source_host_id")))
        else:
            UUID(str(recovery.get("source_project")))
        objects, files = recovery.get("objects"), recovery.get("files")
        if not isinstance(objects, list) or not 1 <= len(objects) <= self.limits.objects or not isinstance(files, list):
            raise ValueError("invalid or unbounded logical data manifest")
        self.objects, self.files, used = {}, {}, set()
        for item in files:
            name = safe_name(item["name"])
            if name in self.files or type(item.get("bytes")) is not int or item["bytes"] < 0:
                raise ValueError("duplicate or invalid virtual data file")
            if not isinstance(item.get("sha256"), str) or not SHA.fullmatch(item["sha256"]):
                raise ValueError("invalid virtual data file checksum")
            parts = item.get("parts")
            if not isinstance(parts, list) or len(parts) > self.limits.volume.chunks * self.limits.volumes:
                raise ValueError("invalid virtual data file parts")
            for part in parts:
                if type(part.get("volume")) is not int or not 0 <= part["volume"] < len(self.readers):
                    raise ValueError("data part refers to an unavailable volume")
                safe_name(part["name"])
                key = (part["volume"], part["name"])
                if key in used or part["name"] not in self.readers[part["volume"]].manifest["files"]:
                    raise ValueError("duplicate or missing virtual data file member")
                used.add(key)
            self.files[name] = item
        physical = {(i, name) for i, reader in enumerate(self.readers) for name in reader.manifest["files"]}
        if used != physical:
            raise ValueError("data archive contains bytes outside its recovery manifest")
        for item in objects:
            if not isinstance(item, dict) or not isinstance(item.get("object_id"), str) or len(item["object_id"]) > 300:
                raise ValueError("invalid data object identity")
            if item["object_id"] in self.objects or not isinstance(item.get("schema"), str) or not isinstance(item.get("kind"), str):
                raise ValueError("duplicate data object or missing object schema")
            if not isinstance(item.get("dependencies"), list) or len(item["dependencies"]) > self.limits.objects:
                raise ValueError("invalid data dependency list")
            self.objects[item["object_id"]] = item
        # Verify virtual concatenations too, rather than treating ZIP chunk
        # checksums as proof of the logical object's original identity.
        for name in self.files:
            for _ in self.chunks(name):
                pass

    def chunks(self, name):
        if name not in self.files:
            raise ValueError("required logical data file is unavailable")
        file = self.files[name]
        checksum, size = hashlib.sha256(), 0
        for part in file["parts"]:
            for chunk in self.readers[part["volume"]].iter_bytes(part["name"]):
                self.check()
                size += len(chunk)
                if size > file["bytes"]:
                    raise ValueError("logical data file exceeds declared length")
                checksum.update(chunk)
                yield chunk
        if size != file["bytes"] or checksum.hexdigest() != file["sha256"]:
            raise ValueError("logical data file size/hash mismatch")

    def json(self, name):
        if name not in self.files or self.files[name]["bytes"] > self.limits.json_bytes:
            raise ValueError("data object exceeds bounded JSON read budget")
        return strict_json(b"".join(self.chunks(name)))

    def rows(self, name):
        pending = bytearray()
        for chunk in self.chunks(name):
            pending.extend(chunk)
            while b"\n" in pending:
                line, _, tail = pending.partition(b"\n")
                pending = bytearray(tail)
                if len(line) > 16 * 1024**2:
                    raise ValueError("data row exceeds bounded JSON read budget")
                yield strict_json(line)
            if len(pending) > 16 * 1024**2:
                raise ValueError("data row exceeds bounded JSON read budget")
        if pending:
            raise ValueError("truncated data JSONL file")

    def preflight(self):
        missing_required, missing_optional, unknown, unsupported_required = [], [], [], []
        known = []
        for object_id, item in self.objects.items():
            if item.get("payload") not in self.files:
                missing_required.append(object_id + ":payload")
            for dependency in item["dependencies"]:
                if not isinstance(dependency, dict) or not isinstance(dependency.get("object_id"), str):
                    raise ValueError("invalid data dependency identity")  # noqa: TRY004 - Invalid archive data uses the public validation error contract.
                if dependency["object_id"] not in self.objects:
                    (missing_required if dependency.get("required", True) else missing_optional).append(dependency["object_id"])
                elif item["kind"] in NATIVE and SCHEMAS.get(item["kind"]) == item["schema"] and dependency.get("required", True) and dependency.get("mode") != "read_only_origin":
                    target = self.objects[dependency["object_id"]]
                    if target["kind"] not in NATIVE or SCHEMAS.get(target["kind"]) != target["schema"]:
                        unsupported_required.append(dependency["object_id"])
            if SCHEMAS.get(item["kind"]) != item["schema"]:
                unknown.append(object_id)
            else:
                if item["kind"] in NATIVE:
                    known.append(object_id)
        return {"schema": SCHEMA, "bundle_id": self.manifest["bundle_id"], "volumes": self.volumes,
                "objects": list(self.objects.values()), "missing_required": sorted(set(missing_required)),
                "missing_optional": sorted(set(missing_optional)), "readonly_unknown": unknown,
                "unsupported_required": sorted(set(unsupported_required)),
                "can_restore": bool(known) and not missing_required and not unsupported_required,
                "can_resume": False, "limitations": self.manifest["recovery"].get("limitations", [])
                + (["optional dependencies are missing"] if missing_optional else [])
                + (["native recovery requires unsupported dependencies; originals remain read-only"] if unsupported_required else [])
                + (["unknown objects are retained read-only and cannot continue"] if unknown else [])}

    def close(self):
        self._stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
