"""Append-only repository report editions, independent of scientific state.

The manifest is the publication boundary. A crash before its atomic replacement
can leave an unregistered edition file; retrying the same request verifies and
registers it. Existing report bytes and their URLs are never replaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from datetime import date as CalendarDate
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

SCHEMA = "threemind.report-revisions/1"
MANIFEST = "report-revisions.json"
MAX_BYTES = 2_000_000
MAX_EDITIONS = 1000
SHA = re.compile(r"[0-9a-f]{64}\Z")


class RevisionConflict(ValueError):
    """The parent, operation or edition no longer matches the supplied draft."""


def checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_checksum(raw: bytes) -> str:
    """Git text identity only: UTF-8, CRLF to LF. This is not a byte hash."""
    raw.decode("utf-8")
    return checksum(raw.replace(b"\r\n", b"\n"))


def _integrity(row, raw):
    actual = checksum(raw)
    exact = actual == row["sha256"]
    textual = (row.get("canonicalization") == "utf8-crlf-to-lf/1" and
               row.get("canonical_sha256") == canonical_checksum(raw))
    if row.get("canonical_sha256") and not textual or not exact and not textual:
        raise ValueError("registered report edition failed its content hash")
    return {"read_sha256": actual, "byte_identity_matches": exact,
            "integrity": "exact_bytes" if exact else "git_text_eol"}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _text(value, *, maximum=2000):
    if not isinstance(value, str) or not value.strip() or "\0" in value or len(value.encode()) > maximum:
        raise ValueError("revision text must be nonempty, bounded UTF-8 without NUL characters")
    return value


def _date(value):
    if not isinstance(value, str) or CalendarDate.fromisoformat(value).isoformat() != value:
        raise ValueError("revision date must use YYYY-MM-DD")
    return value


def _read(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("report or revision manifest exceeds 2 MB")
    return raw


def _json(raw):
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate report manifest key")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique_pairs)


def revision_notice(*, edition, parent, date, reason, language, original, previous=None):
    """A dated author statement; it does not claim that any data were migrated."""
    _date(date)
    _text(reason)
    if "\n" in reason or "\r" in reason:
        raise ValueError("revision reason must be one paragraph")
    if language not in ("zh", "en") or type(edition) is not int or edition < 2:
        raise ValueError("invalid report language or edition")
    if type(parent) is not int or parent < 1:
        raise ValueError("a revision must identify its preserved parent edition")
    if language == "zh":
        return f"> **修订 r{edition} · {date}**\n> 修订原因：{reason}\n> 原版：{original}；父版本 r{parent}" + (
            f"：{previous}" if previous else "。"
        )
    return f"> **Revision r{edition} · {date}**\n> Revision reason: {reason}\n> Original: {original}; parent r{parent}" + (
        f": {previous}" if previous else "."
    )


def with_notice(body, notice):
    if not isinstance(body, str) or "\0" in body:
        raise ValueError("report body must be UTF-8 text without NUL characters")
    heading, separator, tail = body.partition("\n")
    if heading.lstrip("\ufeff").startswith("# "):
        return heading.rstrip("\r") + "\n\n" + notice + "\n\n" + (tail if separator else "")
    return notice + "\n\n" + body


@contextmanager
def _locked(directory):
    # Keep this inode: removing a lock file can let waiters lock different files.
    path = directory / ".report-revisions.lock"
    if path.resolve().parent != directory:
        raise ValueError("report lock cannot leave its directory")
    with path.open("a+b") as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RevisionConflict("another author holds this report directory lock") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _publish_file(path, raw, *, replace):
    descriptor, temporary = tempfile.mkstemp(prefix=".report-revision-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)  # Exclusive publication, including Windows.
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class ReportRevisions:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("the report repository root must be a directory")

    def _path(self, name, *, must_exist=True):
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] not in ("docs", "lab")
            or relative.suffix.lower() != ".md"
        ):
            raise ValueError("reports must use repository-relative Markdown paths inside docs/ or lab/")
        path = (self.root / relative).resolve(strict=must_exist)
        if not path.is_relative_to(self.root / relative.parts[0]) or must_exist and not path.is_file():
            raise ValueError("report path leaves the published document root")
        return path

    def _manifest(self, directory):
        path = directory / MANIFEST
        if path.resolve().parent != directory:
            raise ValueError("revision manifest cannot leave its report directory")
        if not path.exists():
            return {"schema": SCHEMA, "series": []}
        value = _json(_read(path))
        if not isinstance(value, dict) or set(value) != {"schema", "series"} or value["schema"] != SCHEMA:
            raise ValueError("unsupported report revision manifest")
        if not isinstance(value["series"], list) or len(value["series"]) > 1000:
            raise ValueError("invalid report series list")
        groups, paths, operations = set(), set(), set()
        for group in value["series"]:
            if not isinstance(group, dict) or set(group) != {"id", "language", "revisions"}:
                raise ValueError("invalid report series")
            _text(group["id"], maximum=200)
            pair = (group["id"], group["language"])
            if group["language"] not in ("zh", "en") or pair in groups:
                raise ValueError("duplicate report series language")
            groups.add(pair)
            revisions = group["revisions"]
            if not isinstance(revisions, list) or not 1 <= len(revisions) <= MAX_EDITIONS:
                raise ValueError("invalid report edition count")
            for edition, row in enumerate(revisions, 1):
                required = {"edition", "parent", "path", "sha256", "date", "reason", "operation_id", "request_hash"}
                optional = {"canonical_sha256", "canonicalization"}
                if not isinstance(row, dict) or not required <= set(row) or set(row) - required - optional:
                    raise ValueError("invalid report edition metadata")
                if set(row) & optional and (not optional <= set(row) or
                                            row["canonicalization"] != "utf8-crlf-to-lf/1" or
                                            not isinstance(row["canonical_sha256"], str) or
                                            not SHA.fullmatch(row["canonical_sha256"])):
                    raise ValueError("invalid explicit report text identity")
                name = row["path"]
                if not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name:
                    raise ValueError("report edition paths must be filenames in the same directory")
                repo_name = (directory / name).relative_to(self.root).as_posix()
                self._path(repo_name, must_exist=False)
                if name in paths or type(row["edition"]) is not int or row["edition"] != edition:
                    raise ValueError("duplicate or nonsequential report edition")
                paths.add(name)
                if row["parent"] != (edition - 1 if edition > 1 else None) or (
                    edition > 1 and type(row["parent"]) is not int
                ):
                    raise ValueError("report edition parent must identify the preceding edition")
                if not isinstance(row["sha256"], str) or not SHA.fullmatch(row["sha256"]):
                    raise ValueError("invalid report content hash")
                _text(row["reason"])
                if row["date"] is not None:
                    _date(row["date"])
                if edition == 1:
                    if row["operation_id"] is not None or row["request_hash"] is not None:
                        raise ValueError("original report is preserved evidence, not a new revision request")
                else:
                    if row["date"] is None:
                        raise ValueError("new editions require a revision date")
                    if not isinstance(row["operation_id"], str):
                        raise ValueError("revision operation ID must be a UUID string")
                    operation = str(UUID(row["operation_id"]))
                    if operation != row["operation_id"] or operation in operations:
                        raise ValueError("duplicate or noncanonical revision operation ID")
                    operations.add(operation)
                    if not isinstance(row["request_hash"], str) or not SHA.fullmatch(row["request_hash"]):
                        raise ValueError("invalid revision request hash")
        return value

    def history(self, name, *, verify=True):
        path = self._path(name)
        value = self._manifest(path.parent)
        group = next((g for g in value["series"] if any(r["path"] == path.name for r in g["revisions"])), None)
        if group is None:
            return None
        rows = []
        for row in group["revisions"]:
            relative = (path.parent / row["path"]).relative_to(self.root).as_posix()
            resolved = self._path(relative)
            identity = _integrity(row, _read(resolved)) if verify else {}
            rows.append(deepcopy(row) | {"path": relative} | identity)
        return {
            "schema": SCHEMA,
            "series": group["id"],
            "language": group["language"],
            "original": rows[0]["path"],
            "latest": rows[-1]["path"],
            "edition": next(r["edition"] for r in rows if r["path"] == path.relative_to(self.root).as_posix()),
            "revisions": rows,
        }

    def revise(
        self, original, body, *, reason, date, operation_id, expected_edition, expected_parent_hash,
        series=None, language=None, original_date=None,
    ):
        path = self._path(original)
        if type(expected_edition) is not int or not 1 <= expected_edition < MAX_EDITIONS:
            raise ValueError("expected report edition must be a positive bounded integer")
        if not isinstance(expected_parent_hash, str) or not SHA.fullmatch(expected_parent_hash):
            raise ValueError("an exact parent SHA-256 is required")
        if not isinstance(body, str) or "\0" in body or len(body.encode()) > MAX_BYTES:
            raise ValueError("report body must be bounded UTF-8 text without NUL characters")
        _date(date)
        _text(reason)
        if original_date is not None:
            _date(original_date)
        language = language or ("en" if path.stem.endswith(".en") else "zh")
        series = series or re.sub(r"\.(zh|en)$", "", path.stem)
        _text(series, maximum=200)
        operation_id = str(UUID(str(operation_id)))
        request_hash = checksum(_canonical({
            "original": path.relative_to(self.root).as_posix(), "body": body, "reason": reason, "date": date,
            "expected_edition": expected_edition, "expected_parent_hash": expected_parent_hash,
            "series": series, "language": language, "original_date": original_date,
        }))
        with _locked(path.parent):
            value = self._manifest(path.parent)
            for existing in value["series"]:
                for row in existing["revisions"]:
                    if row["operation_id"] == operation_id:
                        if row["request_hash"] != request_hash:
                            raise RevisionConflict("revision operation ID reused with different content")
                        result_path = (path.parent / row["path"]).relative_to(self.root).as_posix()
                        self.history(result_path)  # Never report a corrupted edition as a successful replay.
                        return {"series": existing["id"], "language": existing["language"], **row,
                                "path": result_path, "replayed": True}
            group = next((g for g in value["series"] if (g["id"], g["language"]) == (series, language)), None)
            if group is None:
                if any(r["path"] == path.name for g in value["series"] for r in g["revisions"]):
                    raise RevisionConflict("this original already belongs to another report series")
                if expected_edition != 1:
                    raise RevisionConflict("an unregistered original has only edition 1")
                raw = _read(path)
                if checksum(raw) != expected_parent_hash:
                    raise RevisionConflict("original report changed; preserve the draft and reload")
                group = {"id": series, "language": language, "revisions": [{
                    "edition": 1, "parent": None, "path": path.name, "sha256": checksum(raw),
                    "canonical_sha256": canonical_checksum(raw), "canonicalization": "utf8-crlf-to-lf/1",
                    "date": original_date, "reason": "Preserved original report; original date is not inferred.",
                    "operation_id": None, "request_hash": None,
                }]}
                value["series"].append(group)
            elif group["revisions"][0]["path"] != path.name:
                raise RevisionConflict("report series already belongs to a different original")
            else:
                self.history(original)
            parent = group["revisions"][-1]
            if parent["edition"] != expected_edition or parent["sha256"] != expected_parent_hash:
                raise RevisionConflict("report parent changed; preserve the draft and reload")
            edition = expected_edition + 1
            base = path.stem
            suffix = "." + language if base.endswith("." + language) else ""
            if suffix:
                base = base[:-len(suffix)]
            destination = path.with_name(f"{base}.r{edition}{suffix}.md")
            self._path(destination.relative_to(self.root).as_posix(), must_exist=False)
            notice = revision_notice(
                edition=edition, parent=expected_edition, date=date, reason=reason, language=language,
                original=f"[{path.name}]({quote(path.name)})",
                previous=f"[{parent['path']}]({quote(parent['path'])})",
            )
            raw = with_notice(body, notice).encode()
            if len(raw) > MAX_BYTES:
                raise ValueError("revised report exceeds 2 MB")
            if destination.exists():
                if _read(destination) != raw:
                    raise RevisionConflict("edition file already exists with different content; it is preserved")
            else:
                _publish_file(destination, raw, replace=False)
            row = {
                "edition": edition, "parent": expected_edition, "path": destination.name, "sha256": checksum(raw),
                "canonical_sha256": canonical_checksum(raw), "canonicalization": "utf8-crlf-to-lf/1",
                "date": date, "reason": reason, "operation_id": operation_id, "request_hash": request_hash,
            }
            group["revisions"].append(row)
            encoded = _canonical(value)
            if len(encoded) + 1 > MAX_BYTES:
                raise ValueError("revision manifest exceeds 2 MB; the edition remains unregistered")
            for registered in group["revisions"]:
                try:
                    _integrity(registered, _read(path.parent / registered["path"]))
                except ValueError:
                    raise RevisionConflict("a report changed before registration; the draft is preserved") from None
            _publish_file(path.parent / MANIFEST, encoded + b"\n", replace=True)
            return {"series": series, "language": language, **row,
                    "path": destination.relative_to(self.root).as_posix(), "replayed": False}
