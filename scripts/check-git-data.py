"""Check staged bytes (or the full index) against the reviewed data boundary."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# Match GitHub's ordinary Git file limits; these are not research-data exemptions.
WARN_BYTES = 50 * 1024**2
MAX_BYTES = 100 * 1024**2
SELECTION_PATH = "lab/artifact-index/2026-10-09-git-data-selection.json"
POLICY_PATH = "lab/artifact-index/git-data-policy.json"
EVIDENCE = (".tmexperiment", ".tmind", ".bbx", ".tmt", ".parquet", ".arrow", ".sqlite", ".sqlite3", ".db", ".safetensors", ".pt", ".pth")
DATA_BUNDLE = re.compile(r"\.tmdata(?:[.-].*)?$", re.IGNORECASE)
RUN_RESULT = re.compile(r"^lab/explorations/[^/]+/(?:run|trace)-[^/]+/(?:.*/)?(?:results?\.json|result-[^/]+\.json)$")


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)


def _policy_json(repo: Path, path: str, index: dict) -> dict:
    # A staged policy is read from the index, just like every checked payload.
    if path in index:
        return json.loads(_git(repo, "cat-file", "blob", index[path]))
    local = repo / path
    return json.loads(local.read_bytes()) if local.is_file() else {}


def _selected(name: str, selection: dict) -> bool:
    for group in selection.get("groups", []):
        prefix = group.get("prefix", "")
        if name in group.get("paths", []) or (
            prefix and name.startswith(prefix)
            and any(fnmatch.fnmatchcase(name[len(prefix):], pattern) for pattern in group.get("patterns", []))
        ):
            return True
    return False


def classify_path(name: str, size: int, selection: dict, policy: dict) -> list[str]:
    lower = name.lower()
    if size > MAX_BYTES:
        return [f"{size} staged bytes exceeds GitHub's 100 MiB file limit; "
                "use Git LFS or external storage for eligible assets, not ordinary Git blobs"]
    if _selected(name, selection):
        return ["reviewed original research artifact; store it outside Git"]
    allowed = policy.get("allow_paths", {}).get(name)
    if allowed:
        if size <= allowed["max_bytes"]:
            return []
        return [f"{size} staged bytes exceeds this reviewed exception's {allowed['max_bytes']} byte allowance; "
                "review the changed fixture or template before expanding its exception"]
    if name.startswith(("data/", "lab/raw/", "lab/exports/", ".work/")):
        return ["runtime or research storage belongs outside Git"]
    reasons = []
    if lower.endswith(EVIDENCE) or DATA_BUNDLE.search(lower):
        reasons.append("portable research/model/database data belongs outside Git")
    if name.startswith("lab/explorations/"):
        basename = name.rsplit("/", 1)[-1]
        if lower.endswith((".json.gz", ".jsonl", ".jsonl.gz", ".ndjson", ".npy", ".npz", ".zip")):
            reasons.append("original checkpoint, stream or evidence/source archive")
        elif basename in ("inputs.json", "training-traces.json", "time-courses.json", "measurements.json") or basename.startswith("raw-"):
            reasons.append("original input or per-point measurement output")
        elif RUN_RESULT.match(name):
            reasons.append("generated run/trace result; compact provenance and summaries may stay")
    return reasons


def check_index(repo: Path, *, all_tracked: bool = False, warnings: list[str] | None = None) -> list[str]:
    index = {}
    unmerged = []
    for record in _git(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, raw = record.split(b"\t", 1)
        _mode, oid, stage = metadata.decode("ascii").split()
        name = raw.decode("utf-8")
        if stage != "0":
            unmerged.append(name)
        else:
            index[name] = oid
    if unmerged:
        return ["Index contains unresolved merge stages: " + ", ".join(sorted(set(unmerged)))]
    names = sorted(index) if all_tracked else [raw.decode("utf-8") for raw in _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0") if raw]
    selection = _policy_json(repo, SELECTION_PATH, index)
    policy = _policy_json(repo, POLICY_PATH, index)
    if policy and policy.get("schema") != "threemind.git-data-policy/1":
        return ["Unsupported Git data policy schema"]
    if not names:
        return []
    request = ("\n".join(index[name] for name in names) + "\n").encode("ascii")
    result = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch-check=%(objectsize)"], input=request, capture_output=True, check=True)
    sizes = result.stdout.decode("ascii").splitlines()
    if len(sizes) != len(names):
        raise ValueError("Incomplete staged-object size response")
    failures = []
    for name, raw_size in zip(names, sizes):
        size = int(raw_size)
        reasons = classify_path(name, size, selection, policy)
        failures.extend(f"{name}: {reason}" for reason in reasons)
        if not reasons and size > WARN_BYTES and warnings is not None:
            warnings.append(f"{name}: {size} staged bytes exceeds GitHub's 50 MiB warning threshold; "
                            "this warning does not block the commit")
    return failures


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--all-tracked", action="store_true", help="Audit the whole index after history cleanup")
    args = parser.parse_args(argv)
    warnings = []
    failures = check_index(args.repo, all_tracked=args.all_tracked, warnings=warnings)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
    else:
        print("Source/data separation check passed.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
