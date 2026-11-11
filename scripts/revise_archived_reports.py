"""Append location revisions to original study reports; never edit originals."""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from threemind_lab.report_revisions import ReportRevisions
from threemind_lab.storage_files import under_root


def revise(root, manifest_path, *, date, write=False):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["schema"] != "threemind.research-artifact-relocations/1":
        raise ValueError("unsupported relocation manifest")
    entries = {r["legacy_path"]: r for r in manifest["entries"]}
    writer = ReportRevisions(root)
    groups = defaultdict(list)
    for row in entries.values():
        if row["state"] != "verified":
            raise ValueError("unverified archive cannot produce a completed location revision")
        # Validate every declared archived original before claiming relocation.
        archived = under_root(root, row["archive_path"])
        if not archived.is_relative_to(root / "data/experiments") or archived.stat().st_size != row["bytes"]:
            raise ValueError("archived evidence is outside its root or changed size")
        digest = hashlib.sha256()
        with archived.open("rb") as stream:
            while chunk := stream.read(1024**2):
                digest.update(chunk)
        if digest.hexdigest() != row["sha256"]:
            raise ValueError("archived original failed its content hash")
        parts = Path(row["legacy_path"]).parts
        if parts[:2] == ("lab", "explorations"):
            groups["/".join(parts[:3])].append(row)
    changed = []
    for directory, rows in sorted(groups.items()):
        for doc in sorted((root / directory).glob("*.md")):
            if re.search(r"\.r\d+(?:\.[a-z]+)?$", doc.stem):
                continue
            if (
                doc.stem.lower() not in ("readme", "readme_cn", "validation", "results", "analysis", "summary")
                and "report" not in doc.stem.lower()
            ):
                continue
            name, raw = doc.relative_to(root).as_posix(), doc.read_bytes()
            en = (
                (doc.name == "README.md" and (doc.parent / "README_CN.md").exists())
                or ".en." in doc.name
                or "-en." in doc.name
            )
            body = raw.decode("utf-8-sig")

            def remap(match, doc=doc):
                href = match.group(1)
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    return match.group(0)
                path = (doc.parent / unquote(url.path)).resolve()
                item = entries.get(path.relative_to(root).as_posix()) if path.is_relative_to(root) else None
                return (
                    match.group(0).replace(href, f"/api/v2/storage/research-artifacts/{item['resource_id']}/content", 1)
                    if item
                    else match.group(0)
                )

            body = re.sub(r"\[[^\]]*\]\(([^)\s]+)\)", remap, body)
            if en:
                notice = "\n\n## Data location revision\n\nSelected generated evidence has been archived and verified byte for byte. Original reports, criteria, conclusions and embedded source_commit values are preserved. The logical downloads below require the current host administrator. The data directory is not public.\n\n"
                reason = "Relocate generated evidence out of Git; preserve original bytes and conclusions."
            else:
                notice = "\n\n## 数据位置修订\n\n选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。\n\n"
                reason = "生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。"
            index_link = Path(manifest_path).relative_to(root)
            import os

            index_relative = Path(os.path.relpath(root / index_link, doc.parent)).as_posix()
            notice += f"`data/experiments/{Path(directory).name}/`\n\n[Location and hash index / 位置及哈希登记]({index_relative})\n\n"
            for row in rows:
                if Path(row["legacy_path"]).suffix in (".json", ".csv", ".html", ".zip"):
                    relative = Path(row["legacy_path"]).relative_to(Path(directory)).as_posix()
                    notice += f"- [{relative}](/api/v2/storage/research-artifacts/{row['resource_id']}/content) — {row['bytes']} B; SHA-256 `{row['sha256']}`.\n"
            if write:
                result = writer.revise(
                    name,
                    body + notice,
                    reason=reason,
                    date=date,
                    operation_id=uuid5(UUID("878d7cc9-2b4c-4f11-ad49-c91b0d5e99b5"), name),
                    expected_edition=1,
                    expected_parent_hash=hashlib.sha256(raw).hexdigest(),
                    series=doc.stem,
                    language="en" if en else "zh",
                )
                changed.append(result["path"])
            else:
                changed.append(name)
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", default="lab/artifact-index/2026-10-09-relocations.json")
    parser.add_argument("--date", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "write": args.write,
                "reports": revise(args.root, args.root / args.manifest, date=args.date, write=args.write),
            },
            ensure_ascii=False,
        )
    )
