import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .report_revisions import MANIFEST, ReportRevisions

CATEGORIES = [
    ("index", "索引"),
    ("history", "史书"),
    ("plans", "实施计划与待议机制"),
    ("v2", "第二代使用与架构"),
    ("principles", "核心假设与原理"),
    ("research", "实验与统计"),
    ("reference", "历史设计参考"),
    ("notebooks", "历史研究记录"),
]


class Documents:
    def __init__(self, root: Path, *, resource_resolver=None):
        self.root = root.resolve()
        self.report_revisions = ReportRevisions(self.root)
        # The host resolver verifies an explicitly registered relocation. It is
        # invoked only after the existing public-resource boundary accepts name.
        if resource_resolver is None:
            from .research_storage import ResearchStorage

            storage = ResearchStorage(repository_root=self.root)

            def registered_resource(name):
                try:
                    return storage.resolve_legacy(name)
                except ValueError as error:
                    if str(error).startswith("historical location is not registered:"):
                        return None
                    raise

            resource_resolver = registered_resource
        self.resource_resolver = resource_resolver
        self.items = {}
        for folder in ("docs", "lab"):
            base = (self.root / folder).resolve()
            for path in base.rglob("*.md"):
                resolved = path.resolve()
                if not resolved.is_relative_to(base) or path.stat().st_size > 2_000_000:
                    continue
                name = path.relative_to(self.root).as_posix()
                if "/en/" in name or path.name == "README.md" and (path.parent / "README_CN.md").exists():
                    continue
                text = path.read_text(encoding="utf-8-sig")
                title = next((line.lstrip("# ") for line in text.splitlines() if line.startswith("# ")), path.stem)
                category = (
                    "history"
                    if "/history/" in name
                    else "plans"
                    if "/plans/" in name
                    else "notebooks"
                    if folder == "lab"
                    else "v2"
                    if path.stem.startswith("v2-") or "second-generation" in path.stem
                    else "principles"
                    if path.stem
                    in (
                        "consciousness-hypothesis",
                        "training-protocol",
                        "plasticity-environment-and-language-models",
                        "kernel-evolution-principles",
                        "research-notes",
                        "terminology",
                        "embodied-functional-differentiation",
                    )
                    else "research"
                    if any(w in path.stem for w in ("statistics", "ablation", "research-assessment"))
                    else "reference"
                )
                self.items[name] = {"id": name, "title": title, "category": category, "legacy": category == "reference"}
        # Older bilingual lab notes translated their filenames too. An explicit
        # link from a published document can designate that English counterpart.
        self.published_peers = {}
        self.report_images = set()
        for name in self.items:
            doc = self._markdown_path(name)
            text = doc.read_text(encoding="utf-8-sig")
            for href in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text):
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                target = (doc.parent / unquote(url.path)).resolve()
                if not target.is_relative_to(self.root):
                    continue
                relative = target.relative_to(self.root).as_posix()
                if (
                    "/en/" in relative
                    and relative.startswith(("docs/", "lab/"))
                    and target.suffix == ".md"
                    and target.is_file()
                ):
                    self.published_peers[relative] = name
            for href in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text):
                url = urlsplit(href)
                if not url.scheme and not url.netloc:
                    target = (doc.parent / unquote(url.path)).resolve()
                    if target.is_relative_to(self.root / "lab"):
                        self.report_images.add(target)

    def index(self):
        entries = {key: dict(value) for key, value in self.items.items()}
        seen = set()
        # Only original documents already in the published index authorize an
        # edition. A manifest cannot expose otherwise-private English files.
        for name in self.items:
            if not (self.root / name).parent.joinpath(MANIFEST).exists():
                continue
            history = self.report_revisions.history(name, verify=False)
            if history is None or history["original"] in seen:
                continue
            original = self._read_document(history["original"])
            seen.add(history["original"])
            for row in history["revisions"]:
                edition = self._read_edition(row["path"], original)
                entries[row["path"]] = {
                    key: value for key, value in edition.items() if key != "markdown"
                } | {"report_revision": self._revision_metadata(history, row)}
        return {
            "categories": [{"id": id, "title": title} for id, title in CATEGORIES],
            "documents": list(entries.values()),
        }

    def _read_document(self, name):
        if name not in self.items:
            # A listed Chinese document may link to its published English peer.
            # Do not expand the document boundary to arbitrary local Markdown.
            peer = name.replace("/en/", "/zh/", 1)
            if peer not in self.items:
                peer = self.published_peers.get(name, peer)
            if Path(name).name == "README.md":
                peer = str(Path(name).with_name("README_CN.md")).replace("\\", "/")
            if peer != name and peer in self.items:
                path = self._markdown_path(name)
                if path.is_file() and path.stat().st_size <= 2_000_000:
                    text = path.read_text(encoding="utf-8-sig")
                    title = next((line.lstrip("# ") for line in text.splitlines() if line.startswith("# ")), path.stem)
                    return {
                        **self.items[peer],
                        "id": name,
                        "title": title,
                        "markdown": text,
                    }
            raise KeyError(name)
        return {**self.items[name], "markdown": self._markdown_path(name).read_text(encoding="utf-8-sig")}

    @staticmethod
    def _revision_metadata(history, row):
        return {
            "series": history["series"], "language": history["language"],
            "edition": row["edition"], "parent": row["parent"], "sha256": row["sha256"],
            "canonical_sha256": row.get("canonical_sha256"), "canonicalization": row.get("canonicalization"),
            "read_sha256": row.get("read_sha256"), "byte_identity_matches": row.get("byte_identity_matches"),
            "integrity": row.get("integrity"),
            "date": row["date"], "reason": row["reason"],
            "original": history["original"], "latest": history["latest"],
        }

    def _read_edition(self, name, original):
        path = self._markdown_path(name)
        text = path.read_text(encoding="utf-8-sig")
        title = next((line.lstrip("# ") for line in text.splitlines() if line.startswith("# ")), path.stem)
        for href in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text):
            url = urlsplit(href)
            if not url.scheme and not url.netloc:
                target = (path.parent / unquote(url.path)).resolve()
                if target.is_relative_to(self.root / "lab"):
                    self.report_images.add(target)
        return {**original, "id": name, "title": title, "markdown": text}

    def read(self, name, *, revision=None, latest=False):
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValueError("report revision must be a positive integer")
        if revision is not None and latest:
            raise ValueError("select a fixed report revision or latest, not both")
        try:
            history = self.report_revisions.history(name)
        except (FileNotFoundError, OSError) as error:
            raise KeyError(name) from error
        except ValueError:
            # Existing containment and public-language checks remain the first
            # authority when a caller supplies a non-document path.
            self._read_document(name)
            raise
        if history is None:
            if revision not in (None, 1):
                raise KeyError(name)
            return self._read_document(name)
        original = self._read_document(history["original"])
        selected = next(
            (row for row in history["revisions"] if row["edition"] == revision), None
        ) if revision is not None else next(
            row for row in history["revisions"] if row["path"] == (history["latest"] if latest else name)
        )
        if selected is None:
            raise KeyError(name)
        return self._read_edition(selected["path"], original) | {
            "report_revision": self._revision_metadata(history, selected),
            "report_revisions": history["revisions"],
        }

    def versions(self, name):
        # read() also checks that the manifest's original is published.
        value = self.read(name)
        history = self.report_revisions.history(name)
        if history is None or "report_revision" not in value:
            raise KeyError(name)
        return history

    def _markdown_path(self, name):
        relative = Path(name)
        path = (self.root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] not in ("docs", "lab")
            or not path.is_relative_to(self.root / relative.parts[0])
            or path.suffix.lower() != ".md"
            or not path.is_file()
            or path.stat().st_size > 2_000_000
        ):
            raise KeyError(name)
        return path

    def history(self):
        """A read-only catalogue over published Markdown, independent of Lab data."""
        path = (self.root / "docs/history/catalog.json").resolve()
        if not path.is_relative_to(self.root / "docs/history") or not path.is_file():
            raise KeyError("history catalogue unavailable")
        if path.stat().st_size > 2_000_000:
            raise ValueError("history catalogue too large")
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("schema") != "threemind.history/1":
            raise ValueError("unsupported history catalogue")
        works = catalog.get("works", [])
        chapters = catalog.get("chapters", [])
        work_ids = {w["id"] for w in works}
        if not works or len(work_ids) != len(works):
            raise ValueError("invalid history editions")
        ids, paths = set(), set()
        for chapter in chapters:
            name = chapter["path"]
            if (
                chapter["id"] in ids
                or name in paths
                or chapter["work"] not in work_ids
                or not name.startswith(("docs/zh/history/", "docs/en/history/"))
            ):
                raise ValueError("invalid history chapter")
            self.read(name)  # Also validates published-language peers and containment.
            ids.add(chapter["id"])
            paths.add(name)
        if any(not any(c["work"] == w for c in chapters) for w in work_ids):
            raise ValueError("empty history edition")
        return catalog

    def resource(self, name):
        relative = Path(name)
        if relative.parts[:2] not in (("docs", "benchmarks"), ("docs", "images")):
            # Published reports keep figures beside their Markdown. Only exact,
            # referenced image paths are public; this does not expose Lab JSON/data.
            path = (self.root / relative).resolve()
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not path.is_relative_to(self.root / "lab")
                or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
            ):
                raise KeyError(name)
            if path in self.report_images:
                return self._resource_path(name, path)
            raise KeyError(name)
        path = (self.root / relative).resolve()
        public_root = (self.root / "docs" / relative.parts[1]).resolve()
        if (
            not public_root.is_relative_to(self.root / "docs")
            or not path.is_relative_to(public_root)
            or path.suffix.lower() not in (".json", ".csv", ".png", ".jpg", ".webp", ".pdf")
        ):
            raise KeyError(name)
        return self._resource_path(name, path)

    def _resource_path(self, name, original):
        # A trusted, registered resolver can return an archived public resource
        # outside lab/. Arbitrary caller paths never reach this callback.
        resolved = self.resource_resolver(name) if self.resource_resolver else None
        path = Path(resolved) if resolved is not None else original
        if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
            raise KeyError(name)
        return path
