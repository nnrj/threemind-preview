"""Fixed migration selections separated from frequently saved host progress."""

import hashlib
import json
from collections import OrderedDict
from copy import deepcopy
from uuid import UUID

from .storage_files import StorageConflict, atomic_json, read_json, under_root


class SelectionJournal:
    def __init__(self, control, namespace, fields):
        self.control, self.namespace, self.fields = control, namespace, tuple(fields)
        self.cache = OrderedDict()
        self.cache_bytes = 0

    @staticmethod
    def _hash(value):
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    def _selection(self, row):
        reference = row["selection_ref"]
        path = under_root(self.control, reference["path"])
        expected = self.control / self.namespace / "selections"
        if not path.is_relative_to(expected):
            raise StorageConflict("migration selection leaves its registered control directory")
        stat = path.stat()
        signature = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            reference["sha256"],
            reference["bytes"],
            row["id"],
        )
        key = str(path)
        item = self.cache.get(key)
        if item and item[0] == signature:
            self.cache.move_to_end(key)
            return item[1]
        data = read_json(path, maximum=128 * 1024**2)
        if (
            stat.st_size != reference["bytes"]
            or self._hash(data) != reference["sha256"]
            or data.get("id") != row["id"]
            or data.get("schema") != "threemind.storage-selection/1"
            or set(data.get("fields", {})) != set(self.fields)
        ):
            raise StorageConflict("migration selection failed its identity/hash check")
        if item:
            self.cache_bytes -= item[2]
            del self.cache[key]
        if stat.st_size <= 32 * 1024**2:
            self.cache[key] = (signature, data["fields"], stat.st_size)
            self.cache_bytes += stat.st_size
            while self.cache_bytes > 64 * 1024**2 or len(self.cache) > 8:
                _, evicted = self.cache.popitem(last=False)
                self.cache_bytes -= evicted[2]
        return data["fields"]

    def read(self, path):
        row = read_json(path, maximum=128 * 1024**2)
        if row.get("selection_ref"):
            fixed = self._selection(row)
            if any(field in row and row[field] != fixed[field] for field in self.fields):
                raise StorageConflict("migration selection has conflicting inline and external values")
            row.update(deepcopy(fixed))
        return row

    def write(self, path, row):
        if not row.get("selection_ref"):
            data = {
                "schema": "threemind.storage-selection/1",
                "id": str(UUID(row["id"])),
                "fields": {field: row[field] for field in self.fields},
            }
            sha = self._hash(data)
            key = f"{self.namespace}/selections/{row['id']}.{sha}.json"
            selection = under_root(self.control, key)
            if selection.exists():
                if self._hash(read_json(selection, maximum=128 * 1024**2)) != sha:
                    raise StorageConflict("existing fixed migration selection is corrupt")
            else:
                atomic_json(selection, data)
            row["selection_ref"] = {"path": key, "sha256": sha, "bytes": selection.stat().st_size}
        self._selection(row)  # Cached hash validation, invalidated by replacement.
        progress = {key: value for key, value in row.items() if key not in self.fields}
        atomic_json(path, progress)
