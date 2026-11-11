"""Verify exact source copies, marked public editions and generated provenance."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root.resolve()
    manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    counts = {}
    seen = set()
    for category in ("source_files", "public_editions", "generated_files", "packaging_edits"):
        entries = manifest.get(category, [])
        for entry in entries:
            name = entry["path"]
            assert name not in seen, f"Duplicate manifest path: {name}"
            seen.add(name)
            file = (root / name).resolve()
            assert file.is_relative_to(root), name
            assert file.is_file() and file.stat().st_size == entry["bytes"], name
            assert hashlib.sha256(file.read_bytes()).hexdigest() == entry["sha256"], name
        counts[category] = len(entries)
    print(json.dumps({"source_commit": manifest["source_commit"], "verified": counts}))


if __name__ == "__main__":
    main()
