"""Host-side inventory for local ThreeMind storage.

This module deliberately knows nothing about associative dynamics.  It only
classifies direct children of a configured data directory so the API and UI
can present a safe, auditable cleanup plan.  Files are never deleted during a
scan, and unrecognised/configuration items remain protected by default.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .model import READABLE_MODEL_PACKAGE_SUFFIXES


STALE_TEMP_SECONDS = 60.0


def _item(
    *,
    item_id: str,
    name: str,
    category: str,
    size: int,
    modified_at: float,
    selectable: bool,
    action: str,
    note: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "name": name,
        "category": category,
        "bytes": max(0, int(size)),
        "modified_at": float(modified_at),
        "selectable": bool(selectable),
        "action": action,
        "note": note,
    }


def scan_data_directory(data_dir: Path | str, *, active_persistence: str = "sqlite") -> dict[str, Any]:
    """Return a metadata-only inventory of direct data-directory children.

    The catalogue intentionally does not recurse and never opens a package,
    database, encrypted setting, or legacy JSON document.  This matters for
    very large historical files: a maintenance screen must not recreate the
    same eager-load failure it is designed to prevent.
    """

    root = Path(data_dir).resolve()
    now = time.time()
    items: list[dict[str, Any]] = []
    if not root.exists():
        return {"data_dir": str(root), "total_bytes": 0, "items": [], "categories": {}}

    for path in sorted(root.iterdir(), key=lambda entry: entry.name.casefold()):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        name = path.name
        lower = name.casefold()
        size = int(stat.st_size)
        modified_at = float(stat.st_mtime)
        item_id = f"file:{name}"

        if name == "records.json":
            active = active_persistence == "file"
            items.append(_item(
                item_id=item_id,
                name=name,
                category="legacy_history",
                size=size,
                modified_at=modified_at,
                selectable=not active,
                action="delete_file" if not active else "protected",
                note="legacy_file_backend_active" if active else "legacy_file_backend_unused",
            ))
        elif path.suffix.casefold() in READABLE_MODEL_PACKAGE_SUFFIXES:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="model_packages",
                size=size,
                modified_at=modified_at,
                selectable=True,
                action="delete_file",
                note="portable_model_package",
            ))
        elif any(lower.endswith(f"{suffix}.tmp") for suffix in READABLE_MODEL_PACKAGE_SUFFIXES) or lower.endswith(".upload.tmp"):
            stale = (now - modified_at) >= STALE_TEMP_SECONDS
            items.append(_item(
                item_id=item_id,
                name=name,
                category="temporary_files",
                size=size,
                modified_at=modified_at,
                selectable=stale,
                action="delete_file" if stale else "protected",
                note="stale_incomplete_archive" if stale else "recent_write_in_progress",
            ))
        elif name == "threemind.sqlite3":
            items.append(_item(
                item_id=item_id,
                name=name,
                category="history_database",
                size=size,
                modified_at=modified_at,
                selectable=False,
                action="managed_history",
                note="managed_by_current_persistence",
            ))
        elif name in {"threemind.sqlite3-wal", "threemind.sqlite3-shm"}:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="database_sidecars",
                size=size,
                modified_at=modified_at,
                selectable=False,
                action="protected",
                note="active_database_sidecar",
            ))
        elif name == "archive-index.sqlite3" or name in {"archive-index.sqlite3-wal", "archive-index.sqlite3-shm"}:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="archive_index",
                size=size,
                modified_at=modified_at,
                selectable=False,
                action="rebuild_index",
                note="rebuildable_archive_catalogue",
            ))
        elif lower.startswith("qa-") and path.suffix.casefold() in {".out", ".err", ".log"}:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="diagnostic_logs",
                size=size,
                modified_at=modified_at,
                selectable=True,
                action="delete_file",
                note="diagnostic_output",
            ))
        elif name in {"ui-settings.json", "ai-providers.enc", "notifications.enc", "network.enc", "persistence.enc", ".threemind.key"}:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="configuration_and_credentials",
                size=size,
                modified_at=modified_at,
                selectable=False,
                action="protected",
                note="configuration_or_secret",
            ))
        else:
            items.append(_item(
                item_id=item_id,
                name=name,
                category="unclassified",
                size=size,
                modified_at=modified_at,
                selectable=False,
                action="protected",
                note="unclassified_file",
            ))

    categories: dict[str, dict[str, int]] = {}
    for item in items:
        bucket = categories.setdefault(item["category"], {"count": 0, "bytes": 0, "selectable_count": 0})
        bucket["count"] += 1
        bucket["bytes"] += int(item["bytes"])
        bucket["selectable_count"] += int(bool(item["selectable"]))
    return {
        "data_dir": str(root),
        "total_bytes": sum(int(item["bytes"]) for item in items),
        "items": items,
        "categories": categories,
    }


def direct_child(data_dir: Path | str, name: str) -> Path | None:
    """Resolve a scan item into a direct child, rejecting path traversal."""

    if not name or Path(name).name != name:
        return None
    root = Path(data_dir).resolve()
    target = (root / name).resolve()
    return target if target.parent == root else None
