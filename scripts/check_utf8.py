"""Fail when a maintained ThreeMind text source is not UTF-8 without a BOM."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOTS = ("core", "adapters", "threemind-ui", "docs", "lab", "scripts")
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".css", ".md", ".json", ".toml", ".yml", ".yaml"}
IGNORED_PARTS = {"node_modules", "dist", "__pycache__"}


def main() -> int:
    failures: list[str] = []
    root_files = (ROOT / "README.md", ROOT / "README_CN.md", ROOT / "pyproject.toml", ROOT / ".editorconfig")
    for path in root_files:
        if not path.exists():
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            failures.append(f"{path.relative_to(ROOT)}: UTF-8 BOM is not allowed")
        else:
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as error:
                failures.append(f"{path.relative_to(ROOT)}: {error}")
    for root_name in ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if any(part in IGNORED_PARTS for part in path.parts):
                continue
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                failures.append(f"{path.relative_to(ROOT)}: UTF-8 BOM is not allowed")
                continue
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as error:
                failures.append(f"{path.relative_to(ROOT)}: {error}")
    if failures:
        print("UTF-8 verification failed:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print("All maintained text sources are UTF-8 without a BOM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
