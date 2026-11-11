"""Validate the static history catalogue and links without a database or simulations."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    catalog = json.loads((root / "docs/history/catalog.json").read_text(encoding="utf-8"))
    errors = []
    if catalog.get("schema") != "threemind.history/1":
        errors.append("unsupported catalogue schema")
    works = catalog["works"]
    chapters = catalog["chapters"]
    if len({w["id"] for w in works}) != len(works):
        errors.append("duplicate edition ID")
    for field in ("id", "path"):
        for value, count in Counter(c[field] for c in chapters).items():
            if count != 1:
                errors.append(f"duplicate chapter {field}: {value}")
    for work in works:
        if not any(c["work"] == work["id"] for c in chapters):
            errors.append(f"empty edition: {work['id']}")
    zh = {c["key"] for c in chapters if c["work"] == "modern-zh"}
    en = {c["key"] for c in chapters if c["work"] == "modern-en"}
    if zh != en:
        errors.append(f"unpaired modern chapters: {zh ^ en}")
    known_works = {w["id"] for w in works}
    listed = {c["path"] for c in chapters}
    actual = {
        p.relative_to(root).as_posix()
        for lang in ("zh", "en")
        for p in (root / "docs" / lang / "history").rglob("*.md")
    }
    if actual != listed:
        errors.append(f"unindexed or missing history documents: {actual ^ listed}")
    for chapter in chapters:
        name = chapter["path"]
        path = (root / name).resolve()
        if (
            not name.startswith(("docs/zh/history/", "docs/en/history/"))
            or not path.is_relative_to(root.resolve())
            or not path.is_file()
            or chapter["work"] not in known_works
        ):
            errors.append(f"invalid chapter: {name}")
            continue
        text = path.read_text(encoding="utf-8-sig")
        if not text.startswith("# "):
            errors.append(f"missing title: {name}")
        if "[[H:" in text or "[[S:" in text:
            errors.append(f"unresolved drafting reference: {name}")
        fence = ""
        for number, line in enumerate(text.splitlines(), 1):
            boundary = re.match(r"\s*(`{3,}|~{3,})", line)
            if boundary:
                token = boundary[1]
                if not fence:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = ""
                continue
            # Quoted original messages may contain historical links. Do not
            # silently rewrite those sources to make present-day checks pass.
            if fence or line.lstrip().startswith(">"):
                continue
            for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", line):
                href = match[1].strip().strip("<>")
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (path.parent / unquote(url.path)).resolve()
                if not target.is_relative_to(root.resolve()) or not target.exists():
                    errors.append(f"{name}:{number}: missing/local boundary: {href}")
    return errors


if __name__ == "__main__":
    errors = validate()
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    catalog = json.loads((ROOT / "docs/history/catalog.json").read_text(encoding="utf-8"))
    print(
        f"History verified: {len(catalog['works'])} editions, {len(catalog['chapters'])} chapters; bilingual coverage and local links valid."
    )
