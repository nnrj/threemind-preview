#!/usr/bin/env python3
"""Archive an explicitly reviewed Git artifact selection without deleting sources.

The small tracked selection freezes scope. The full inventory, original Git blob
versions, and verified location receipt live in ignored data storage. No command
changes the index, refs, reports, scientific payloads, or embedded source_commit.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

SELECTION_SCHEMA = "threemind.research-artifact-selection/1"
INVENTORY_SCHEMA = "threemind.research-artifact-inventory/1"
CHUNK_BYTES = 1024 * 1024
DEFAULT_SELECTION = "lab/artifact-index/2026-10-09-git-data-selection.json"
HEX_OID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class ArchiveError(ValueError):
    """An unsafe path, changed source, or inconsistent archive was rejected."""


def canonical_json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _relative(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArchiveError("A nonempty relative path is required")
    if any(c in value for c in ("\\", ":", "\0", "\r", "\n")):
        raise ArchiveError(f"Invalid relative path: {value!r}")
    if any(part in ("", ".", "..", ".git") for part in value.split("/")):
        raise ArchiveError(f"Unsafe relative path: {value!r}")
    if PurePosixPath(value).is_absolute():
        raise ArchiveError(f"Absolute path is forbidden: {value!r}")
    return value


def safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = root.joinpath(*_relative(relative).split("/"))
    node = path
    while node != root:
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ArchiveError(f"Symlink/junction is forbidden: {node}")
        node = node.parent
    if not path.resolve().is_relative_to(root):
        raise ArchiveError(f"Path escapes its root: {relative}")
    return path


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode:
        raise ArchiveError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").decode("ascii").strip()


def _refs(repo: Path) -> list[str]:
    return sorted(_git(repo, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines())


class GitBlobs:
    """One Git process streams selected blob bytes with bounded memory."""

    def __init__(self, repo: Path):
        self.process = subprocess.Popen(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.process.stdin.close()
        if exc_type:
            self.process.terminate()
        self.process.wait(timeout=10)
        self.process.stdout.close()
        self.process.stderr.close()

    def blocks(self, oid: str) -> Iterator[bytes]:
        if not HEX_OID.fullmatch(oid):
            raise ArchiveError("Invalid Git object identity")
        self.process.stdin.write((oid + "\n").encode("ascii"))
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode("ascii").strip().split()
        if len(header) != 3 or header[0] != oid or header[1] != "blob":
            raise ArchiveError(f"Git blob is unavailable: {oid}")
        remaining = int(header[2])
        while remaining:
            block = self.process.stdout.read(min(remaining, CHUNK_BYTES))
            if not block:
                raise ArchiveError(f"Incomplete Git blob: {oid}")
            remaining -= len(block)
            yield block
        if self.process.stdout.read(1) != b"\n":
            raise ArchiveError("Invalid Git batch framing")


def load_selection(path: Path) -> dict:
    selection = json.loads(path.read_bytes())
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ArchiveError("Unsupported selection schema")
    _relative(selection["batch"])
    if "/" in selection["batch"]:
        raise ArchiveError("Batch must be a single path component")
    if selection.get("destination_root") != "data/experiments":
        raise ArchiveError("Artifact destination must be data/experiments")
    if not HEX_OID.fullmatch(selection["base_commit"]):
        raise ArchiveError("Invalid base commit")
    ids = set()
    for group in selection["groups"]:
        if group["id"] in ids:
            raise ArchiveError("Duplicate selection group")
        ids.add(group["id"])
        if group.get("prefix"):
            _relative(group["prefix"].rstrip("/"))
            if not group["prefix"].endswith("/"):
                raise ArchiveError("Group prefixes must end with a slash")
        for name in group.get("paths", []):
            _relative(name)
    for mapping in selection["path_mapping"]:
        _relative(mapping["prefix"].rstrip("/"))
        if mapping["replace_with"]:
            _relative(mapping["replace_with"].rstrip("/"))
    return selection


def selected_group(selection: dict, name: str) -> dict | None:
    matched = []
    for group in selection["groups"]:
        prefix = group.get("prefix", "")
        if name in group.get("paths", []) or (
            prefix and name.startswith(prefix)
            and any(fnmatch.fnmatchcase(name[len(prefix):], pattern) for pattern in group.get("patterns", []))
        ):
            matched.append(group)
    if len(matched) > 1:
        raise ArchiveError(f"Overlapping selection for {name}")
    return matched[0] if matched else None


def archive_key(selection: dict, name: str) -> str:
    _relative(name)
    for mapping in selection["path_mapping"]:
        if name.startswith(mapping["prefix"]):
            return _relative(mapping["replace_with"] + name[len(mapping["prefix"]):])
    raise ArchiveError(f"No approved destination mapping for {name}")


def _tree(repo: Path, commit: str) -> dict[str, tuple[str, str]]:
    rows = {}
    for row in _git(repo, "ls-tree", "-rz", commit).split(b"\0"):
        if not row:
            continue
        metadata, path = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if kind == "blob":
            rows[path.decode("utf-8")] = mode, oid
    return rows


def _historical_versions(repo: Path, selection: dict) -> dict[str, dict[str, set[str]]]:
    versions: dict[str, dict[str, set[str]]] = {}
    tokens = _git(repo, "log", "--all", "--full-history", "--raw", "-z", "--format=%H", "--no-abbrev", "--no-renames").split(b"\0")
    commit = ""
    index = 0
    while index < len(tokens):
        token = tokens[index].strip(b"\n")
        index += 1
        if not token:
            continue
        text = token.decode("utf-8")
        if HEX_OID.fullmatch(text):
            commit = text
            continue
        if not text.startswith(":"):
            raise ArchiveError("Unexpected Git raw history format")
        fields = text[1:].split()
        if len(fields) != 5 or index >= len(tokens):
            raise ArchiveError("Incomplete Git raw history record")
        name = tokens[index].decode("utf-8")
        index += 1
        if not selected_group(selection, name):
            continue
        _relative(name)
        for mode, oid in zip(fields[:2], fields[2:4]):
            if set(oid) == {"0"}:
                continue
            if mode not in ("100644", "100755"):
                raise ArchiveError(f"Selected history is not a regular file: {name}")
            versions.setdefault(name, {}).setdefault(oid, set()).add(commit)
    return versions


def build_inventory(repo: Path, selection: dict) -> dict:
    repo = repo.resolve()
    base = selection["base_commit"]
    if _head(repo) != base:
        raise ArchiveError("HEAD changed since the reviewed selection")
    refs = _refs(repo)
    tree = _tree(repo, base)
    selected = {name: row for name, row in tree.items() if selected_group(selection, name)}
    history = _historical_versions(repo, selection)
    for name, (mode, oid) in selected.items():
        if mode not in ("100644", "100755"):
            raise ArchiveError(f"Selected source is not a regular file: {name}")
        history.setdefault(name, {}).setdefault(oid, set()).add(base)
    experiment_roots = {"/".join(name.split("/")[:3]) + "/" for name in history if name.startswith("lab/explorations/")}
    companions = {name: row for name, row in tree.items() if name not in history and any(name.startswith(root) for root in experiment_roots)}
    affected = set(selected) | set(companions)
    dirty = set(_git(repo, "diff", "--no-ext-diff", "--name-only", "-z", base).decode("utf-8").split("\0"))
    if dirty & affected:
        raise ArchiveError("Original files differ from reviewed Git checkout: " + next(iter(dirty & affected)))
    working_metadata = {}
    for name in sorted(affected):
        source = safe_path(repo, name)
        if not source.is_file():
            raise ArchiveError(f"Original source is missing: {name}")
        size, digest = file_digest(source)
        working_metadata[name] = {"bytes": size, "sha256": digest}
    oids = {oid for values in history.values() for oid in values} | {oid for _, oid in companions.values()}
    metadata = {}
    with GitBlobs(repo) as blobs:
        for oid in sorted(oids):
            digest, size = hashlib.sha256(), 0
            for block in blobs.blocks(oid):
                digest.update(block)
                size += len(block)
            metadata[oid] = {"bytes": size, "sha256": digest.hexdigest()}
    entries = []
    for name in sorted(history):
        current = tree.get(name)
        key = archive_key(selection, name)
        group = selected_group(selection, name)
        current_record = {"git_blob": current[1], **working_metadata[name], "archive_key": key, "byte_origin": "working-tree"} if current else None
        versions = []
        for oid, commits in sorted(history[name].items()):
            identical_current = current and current[1] == oid and metadata[oid] == working_metadata[name]
            historical_key = key if identical_current else f".history/{selection['batch']}/{key}/{oid}"
            versions.append({"git_blob": oid, **metadata[oid], "change_commits": sorted(commits), "archive_key": historical_key, "byte_origin": "git-blob"})
        entries.append({"source_path": name, "legacy_path": name, "resource_id": "research-artifact:" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:24], "archive_key": key, "group_id": group["id"], "current_blob": current[1] if current else None, "current": current_record, "latest_blob": current[1] if current else next(iter(history[name])), "versions": versions})
    companion_entries = []
    for name, (mode, oid) in sorted(companions.items()):
        if mode not in ("100644", "100755"):
            raise ArchiveError(f"Companion is not a regular file: {name}")
        companion_entries.append({"source_path": name, "archive_key": archive_key(selection, name), "git_blob": oid, **working_metadata[name], "git_bytes": metadata[oid]["bytes"], "git_sha256": metadata[oid]["sha256"], "byte_origin": "working-tree"})
    summaries = []
    for group in selection["groups"]:
        paths = sorted(name for name in selected if selected_group(selection, name)["id"] == group["id"])
        summary = {"files": len(paths), "bytes": sum(working_metadata[name]["bytes"] for name in paths), "paths_sha256": hashlib.sha256(("\n".join(paths) + "\n").encode()).hexdigest()}
        if group.get("expected_current") != summary:
            raise ArchiveError(f"Reviewed scope changed: {group['id']}")
        summaries.append({"id": group["id"], **summary})
    dirty_after = set(_git(repo, "diff", "--no-ext-diff", "--name-only", "-z", base).decode("utf-8").split("\0"))
    if dirty_after & affected:
        raise ArchiveError("Original files changed during inventory")
    if _head(repo) != base or _refs(repo) != refs:
        raise ArchiveError("Git refs changed during inventory; retry after coordination")
    result = {"schema": INVENTORY_SCHEMA, "batch": selection["batch"], "base_commit": base, "refs": refs, "selection_sha256": hashlib.sha256(canonical_json(selection)).hexdigest(), "destination_root": selection["destination_root"], "groups": summaries, "entries": entries, "companions": companion_entries, "history_note": "change_commits identify commits that introduced/changed/removed a version; they are not claims that every listed commit contains that version."}
    result["inventory_sha256"] = hashlib.sha256(canonical_json(result)).hexdigest()
    return result


def load_inventory(path: Path) -> dict:
    inventory = json.loads(path.read_bytes())
    if inventory.get("schema") != INVENTORY_SCHEMA:
        raise ArchiveError("Unsupported inventory schema")
    recorded = inventory.get("inventory_sha256")
    unsigned = {key: value for key, value in inventory.items() if key != "inventory_sha256"}
    if hashlib.sha256(canonical_json(unsigned)).hexdigest() != recorded:
        raise ArchiveError("Inventory integrity mismatch")
    if inventory.get("destination_root") != "data/experiments":
        raise ArchiveError("Invalid archive destination")
    return inventory


def _publish(root: Path, relative: str, blocks: Iterator[bytes], expected: tuple[int, str]) -> bool:
    destination = safe_path(root, relative)
    if destination.exists():
        if not destination.is_file() or file_digest(destination) != expected:
            raise ArchiveError(f"Destination contains different bytes: {relative}")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = safe_path(root, relative)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".artifact-copy-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        size, digest = 0, hashlib.sha256()
        with os.fdopen(descriptor, "wb") as stream:
            for block in blocks:
                stream.write(block)
                size += len(block)
                digest.update(block)
            stream.flush()
            os.fsync(stream.fileno())
        if (size, digest.hexdigest()) != expected:
            raise ArchiveError(f"Source bytes changed or are corrupt: {relative}")
        safe_path(root, relative)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if file_digest(destination) != expected:
                raise ArchiveError(f"Concurrent destination collision: {relative}")
            return False
        return True
    finally:
        temporary.unlink(missing_ok=True)


def publish_inventory(repo: Path, relative: str, inventory: dict) -> Path:
    if not relative.startswith("data/storage-control/"):
        raise ArchiveError("Full inventory belongs in ignored data/storage-control")
    payload = canonical_json(inventory)
    _publish(repo, relative, iter([payload]), (len(payload), hashlib.sha256(payload).hexdigest()))
    return safe_path(repo, relative)


@contextmanager
def _source_blocks(repo: Path, relative: str) -> Iterator[Iterator[bytes]]:
    source = safe_path(repo, relative)
    if not source.is_file():
        raise ArchiveError(f"Original source is missing: {relative}")
    with source.open("rb") as stream:
        yield iter(lambda: stream.read(CHUNK_BYTES), b"")


def _records(inventory: dict):
    for entry in inventory["entries"]:
        current = entry["current"]
        if current:
            yield entry["source_path"], current, True
        for version in entry["versions"]:
            if not current or version["archive_key"] != current["archive_key"]:
                yield entry["source_path"], version, False
    for companion in inventory["companions"]:
        yield companion["source_path"], companion, True


def archive_inventory(repo: Path, inventory: dict) -> dict:
    repo = repo.resolve()
    if _head(repo) != inventory["base_commit"] or _refs(repo) != inventory["refs"]:
        raise ArchiveError("HEAD/refs changed since inventory; archive before Git rewrite")
    copied, reused = 0, 0
    with GitBlobs(repo) as blobs:
        for source_name, record, current in _records(inventory):
            relative = inventory["destination_root"] + "/" + record["archive_key"]
            expected = record["bytes"], record["sha256"]
            if current:
                source = safe_path(repo, source_name)
                if not source.is_file() or file_digest(source) != expected:
                    raise ArchiveError(f"Original source differs from reviewed Git bytes: {source_name}")
                with _source_blocks(repo, source_name) as blocks:
                    created = _publish(repo, relative, blocks, expected)
                if file_digest(safe_path(repo, source_name)) != expected:
                    raise ArchiveError(f"Original source changed during archive: {source_name}")
            else:
                # Always consume a requested batch object, including a reused target.
                destination = safe_path(repo, relative)
                if destination.exists():
                    if file_digest(destination) != expected:
                        raise ArchiveError(f"Historical destination collision: {relative}")
                    created = False
                else:
                    created = _publish(repo, relative, blobs.blocks(record["git_blob"]), expected)
            copied += int(created)
            reused += int(not created)
    if _head(repo) != inventory["base_commit"] or _refs(repo) != inventory["refs"]:
        raise ArchiveError("Git refs changed while archiving; no completion receipt issued")
    verified = verify_inventory(repo, inventory, sources=True)
    receipt = {"schema": "threemind.research-artifact-archive-receipt/1", "inventory_sha256": inventory["inventory_sha256"], "base_commit": inventory["base_commit"], "verified_files": verified["files"], "verified_bytes": verified["bytes"], "source_deleted": False, "scientific_payloads_modified": False}
    payload = canonical_json(receipt)
    relative = f"data/storage-control/research-artifact-archive/{inventory['batch']}/receipt.json"
    _publish(repo, relative, iter([payload]), (len(payload), hashlib.sha256(payload).hexdigest()))
    return {**verified, "copied": copied, "reused": reused, "receipt": relative}


def verify_inventory(repo: Path, inventory: dict, *, sources: bool = False) -> dict:
    count, size = 0, 0
    for name, record, current in _records(inventory):
        expected = record["bytes"], record["sha256"]
        destination = safe_path(repo, inventory["destination_root"] + "/" + record["archive_key"])
        if not destination.is_file() or file_digest(destination) != expected:
            raise ArchiveError(f"Archive missing or corrupt: {name} / {record['git_blob']}")
        if sources and current:
            source = safe_path(repo, name)
            if not source.is_file() or file_digest(source) != expected:
                raise ArchiveError(f"Source missing or changed: {name}")
        count += 1
        size += record["bytes"]
    return {"files": count, "bytes": size, "selected_paths": len(inventory["entries"]), "companions": len(inventory["companions"])}


def resolve_archived_path(repo: Path, inventory: dict, source_path: str, *, git_blob: str | None = None) -> Path:
    _relative(source_path)
    candidates = []
    for entry in inventory["entries"]:
        if entry["source_path"] == source_path:
            candidates.extend(version for version in entry["versions"] if git_blob and version["git_blob"] == git_blob)
            if not git_blob and entry["current"]:
                candidates.append(entry["current"])
    candidates.extend(companion for companion in inventory["companions"] if companion["source_path"] == source_path and (not git_blob or git_blob == companion["git_blob"]))
    for record in candidates:
        result = safe_path(repo, inventory["destination_root"] + "/" + record["archive_key"])
        if not result.is_file() or file_digest(result) != (record["bytes"], record["sha256"]):
            raise ArchiveError(f"Mapped evidence missing or corrupt: {source_path}")
        return result
    raise ArchiveError(f"No archived version is registered: {source_path}")


def build_relocations(repo: Path, inventory: dict) -> dict:
    """A verified, tracked location index; full history remains in the inventory."""
    verify_inventory(repo, inventory)
    entries = []
    for entry in inventory["entries"]:
        record = entry["current"] or next(version for version in entry["versions"] if version["git_blob"] == entry["latest_blob"])
        entries.append({"resource_id": entry["resource_id"], "legacy_path": entry["legacy_path"], "archive_path": inventory["destination_root"] + "/" + record["archive_key"], "bytes": record["bytes"], "sha256": record["sha256"], "git_blob": record["git_blob"], "state": "verified", **({"historical_only": True} if not entry["current_blob"] else {})})
    return {"schema": "threemind.research-artifact-relocations/1", "batch": inventory["batch"], "snapshot_commit": inventory["base_commit"], "inventory_sha256": inventory["inventory_sha256"], "entries": entries}


def publish_relocations(repo: Path, relative: str, inventory: dict, *, replace_expected_sha256: str | None = None) -> Path:
    if not relative.startswith("lab/artifact-index/"):
        raise ArchiveError("Tracked location index belongs in lab/artifact-index")
    manifest = build_relocations(repo, inventory)
    header = {key: value for key, value in manifest.items() if key != "entries"}
    # One row per resource keeps this tracked index small and reviewable.
    payload = json.dumps(header, ensure_ascii=False, indent=2)[:-2] + ',\n  "entries": [\n'
    payload += ",\n".join("    " + json.dumps(entry, ensure_ascii=False, separators=(",", ":")) for entry in manifest["entries"])
    encoded = (payload + "\n  ]\n}\n").encode("utf-8")
    destination = safe_path(repo, relative)
    expected = len(encoded), hashlib.sha256(encoded).hexdigest()
    if not destination.exists() or file_digest(destination) == expected:
        _publish(repo, relative, iter([encoded]), expected)
        return destination
    if not replace_expected_sha256 or file_digest(destination)[1] != replace_expected_sha256:
        raise ArchiveError("Location index changed; explicit expected prior hash is required")
    previous = destination.read_bytes()
    previous_key = f"data/storage-control/research-artifact-archive/{inventory['batch']}/prior-relocations/{replace_expected_sha256}.json"
    _publish(repo, previous_key, iter([previous]), (len(previous), replace_expected_sha256))
    descriptor, name = tempfile.mkstemp(prefix=".artifact-manifest-", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(repo, relative)
        if file_digest(destination)[1] != replace_expected_sha256:
            raise ArchiveError("Location index changed before publication")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main(argv: list[str] | None = None) -> int:
    # Git path lists are UTF-8, including when Windows defaults to a legacy code page.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "archive", "verify", "paths", "resolve", "manifest"))
    parser.add_argument("source_path", nargs="?")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--selection", default=DEFAULT_SELECTION)
    parser.add_argument("--inventory", help="Defaults to the currently reviewed selection batch")
    parser.add_argument("--sources", action="store_true", help="Also verify original files; use before Git cleanup")
    parser.add_argument("--git-blob", help="Resolve a specific historical Git blob")
    parser.add_argument("--output", default="lab/artifact-index/2026-10-09-relocations.json")
    parser.add_argument("--replace-expected-sha256", help="Atomically revise a location index only if its prior hash still matches")
    args = parser.parse_args(argv)
    try:
        selection = load_selection(safe_path(args.repo, args.selection))
        inventory_relative = args.inventory or f"data/storage-control/research-artifact-archive/{selection['batch']}/inventory.json"
        if args.command == "inventory":
            inventory = build_inventory(args.repo, selection)
            path = publish_inventory(args.repo, inventory_relative, inventory)
            print(json.dumps({"inventory": str(path), "inventory_sha256": inventory["inventory_sha256"], "selected_paths": len(inventory["entries"]), "companions": len(inventory["companions"])}))
        else:
            inventory = load_inventory(safe_path(args.repo, inventory_relative))
            if args.command == "archive":
                print(json.dumps(archive_inventory(args.repo, inventory)))
            elif args.command == "verify":
                print(json.dumps(verify_inventory(args.repo, inventory, sources=args.sources)))
            elif args.command == "paths":
                for entry in inventory["entries"]:
                    print(entry["source_path"])
            elif args.command == "resolve":
                if not args.source_path:
                    raise ArchiveError("resolve requires an original source path")
                print(resolve_archived_path(args.repo, inventory, args.source_path, git_blob=args.git_blob))
            elif args.command == "manifest":
                print(publish_relocations(args.repo, args.output, inventory, replace_expected_sha256=args.replace_expected_sha256))
    except (ArchiveError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Archive rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
