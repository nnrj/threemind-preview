"""Host-scoped receipt journal. A pending result is never auto-reexecuted."""

import hashlib
import json
import time
from uuid import UUID

from .storage_files import StorageConflict, atomic_json, file_lock, read_json


def _path(storage, actor, request_id):
    return storage.control_dir / "operation-receipts" / str(UUID(str(actor))) / (str(UUID(str(request_id))) + ".json")


def reserve(storage, actor, request_id, method, path, body):
    destination = _path(storage, actor, request_id)
    fingerprint = hashlib.sha256(
        json.dumps([method, path, body], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    with file_lock(destination.with_suffix(".lock")):
        if destination.exists():
            row = read_json(destination)
            if row["fingerprint"] != fingerprint:
                raise StorageConflict("host request identity belongs to another operation")
            return row
        atomic_json(
            destination,
            {
                "schema": "threemind.host-operation-receipt/1",
                "scope": "host",
                "host_id": storage.initialize()["host_id"],
                "actor_id": str(actor),
                "request_id": str(request_id),
                "method": method,
                "path": path,
                "fingerprint": fingerprint,
                "status": "pending",
                "created_at": time.time(),
            },
        )
    return None


def finish(storage, actor, request_id, content=None, code=None):
    destination = _path(storage, actor, request_id)
    with file_lock(destination.with_suffix(".lock")):
        row = read_json(destination)
        row.update(
            status="completed" if content is not None else "unknown",
            response=content,
            response_status=code,
            updated_at=time.time(),
        )
        atomic_json(destination, row)


def inspect(storage, actor, request_id):
    destination = _path(storage, actor, request_id)
    if not destination.exists():
        from .database import NotFound

        raise NotFound("host operation receipt")
    return read_json(destination)
