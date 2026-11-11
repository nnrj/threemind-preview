"""Apply reversible performance candidates ONLY to a prepared .work Rust copy.

The copy must have been created by profile_kernel_locality.py prepare from the
current source. This tool neither builds nor installs anything. Apply cache
first, then weight-view; retain each manifest as engineering evidence. No
production optimization or dynamics change is authorized by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("crates/threemind-core/src/local.rs")
MANIFEST_PREFIX = "memory5-perf-"

CACHE_PATCHES = [
    (
        "    consolidate: bool,\n    novelty: String,\n}",
        ("    consolidate: bool,\n    novelty: String,\n    eligibility_period_retention: f64,\n}"),
    ),
    (
        (
            "        Ok(Self {\n            value,\n            c,\n            o,\n"
            "            r,\n            depletion,\n            consolidate,\n"
            "            novelty,\n        })"
        ),
        (
            "        let eligibility_period_retention = if c.eligibility_decay_enabled {\n"
            "            let dt = c.propagation_interval_us as f64 / 1e6;\n"
            "            (-dt / c.eligibility_tau).exp()\n"
            "        } else {\n            1.0\n        };\n"
            "        Ok(Self {\n            value,\n            c,\n            o,\n"
            "            r,\n            depletion,\n            consolidate,\n"
            "            novelty,\n            eligibility_period_retention,\n        })"
        ),
    ),
    (
        (
            "        let retention = if c.eligibility_decay_enabled {\n"
            "            (-dt / c.eligibility_tau).exp()\n"
            "        } else {\n            1.0\n        };\n"
            "        let factor = retention.powf(n);"
        ),
        ("        let retention = self.s.eligibility_period_retention;\n        let factor = retention.powf(n);"),
    ),
]

WEIGHT_PATCHES = [
    (
        (
            "                let e = self.settle_edge(key);\n"
            "                let target = if e.source == id { e.target } else { e.source };\n"
            "                let w = weights.entry(target).or_insert(0.0);\n"
            "                *w = w.max(e.weight);"
        ),
        (
            "                let (source, target, weight) = if V5\n"
            "                    && at(&self.edges[&key].state_us) == self.time\n"
            "                    && at(self.edges[&key].completed_period_us.as_deref().unwrap())\n"
            "                        == self.completed_period(self.time)\n"
            "                {\n"
            "                    // Same settled state and counter; avoid cloning its strings.\n"
            '                    *self.audit.get_mut("edge_visits").unwrap() += 1;\n'
            "                    let e = &self.edges[&key];\n"
            "                    (e.source, e.target, e.weight)\n"
            "                } else {\n"
            "                    let e = self.settle_edge(key);\n"
            "                    (e.source, e.target, e.weight)\n"
            "                };\n"
            "                let target = if source == id { target } else { source };\n"
            "                let w = weights.entry(target).or_insert(0.0);\n"
            "                *w = w.max(weight);"
        ),
    ),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def confined(path: Path, directory: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(directory) or resolved == directory:
        raise ValueError(f"Path escapes the permitted copy: {path}")
    return resolved


def replace_once(text: str, patches: list[tuple[str, str]]) -> str:
    for before, after in patches:
        if text.count(before) != 1:
            raise ValueError("Expected exactly one source fragment: " + before[:100])
        text = text.replace(before, after, 1)
    return text


def without_probe(text: str) -> str:
    # These are the only changes allowed from prepare in local.rs. Other
    # instrumentation or any old candidate must be audited separately.
    text = re.sub(
        r'\n        #\[cfg\(feature="kernel-probe"\)\] let _probe_scope = '
        r"crate::probe::enter\(\d+\);",
        "",
        text,
    )
    return text.replace(
        '        #[cfg(feature="kernel-probe")] crate::probe::add_pairs(contacts.len());\n',
        "",
    )


def atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + ".memory5-perf-tmp")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def manifest_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def apply(work: Path, action: str, check_only: bool = False) -> dict:
    work_root = (ROOT / ".work").resolve(strict=True)
    if not work_root.is_relative_to(ROOT):
        raise ValueError("Repository .work must not resolve outside the repository")
    work = confined(work, work_root)
    if not work.is_dir():
        raise ValueError("Use an existing prepared workspace")
    path = confined(work / SOURCE, work)
    original = ROOT / SOURCE
    if path.samefile(original) or path.stat().st_nlink != 1:
        raise ValueError("The candidate must be an independent copy, not a hard link")
    hashes_path = confined(work / "source-hashes.json", work)
    hashes = json_read(hashes_path)
    original_bytes = original.read_bytes()
    if hashes.get(SOURCE.as_posix()) != digest(original_bytes):
        raise ValueError("Prepared source hash does not match current production local.rs")
    for required in ("Cargo.toml", "configs.json", "driver/src/main.rs"):
        confined(work / required, work)
    if (work / "candidate-changes.json").exists():
        raise ValueError("Do not mix the old locality candidate with these candidates")

    phase = action.removeprefix("apply-")
    manifest_path = work / f"{MANIFEST_PREFIX}{phase}.json"
    if manifest_path.exists():
        raise ValueError("Phase manifest already exists; inspect it instead of reapplying")
    if manifest_path.is_symlink():
        raise ValueError("Phase manifest must not be a symbolic link")
    data = path.read_bytes()
    text = data.decode("utf-8").replace("\r\n", "\n")
    expected = original_bytes.decode("utf-8").replace("\r\n", "\n")
    if action == "apply-weight-view":
        previous_path = confined(work / f"{MANIFEST_PREFIX}cache.json", work)
        previous = json_read(previous_path)
        if (
            previous.get("status") != "applied"
            or previous.get("phase") != "cache"
            or previous.get("source_sha256_after") != digest(data)
            or previous.get("original_sha256") != digest(original_bytes)
        ):
            raise ValueError("Weight-view requires the unchanged, completed cache candidate")
        expected = replace_once(expected, CACHE_PATCHES)
        patches = WEIGHT_PATCHES
    elif action == "apply-cache":
        patches = CACHE_PATCHES
    else:
        raise ValueError("Unknown candidate action")
    if without_probe(text) != expected:
        raise ValueError("Copy differs from the audited source beyond permitted preparation")
    changed = replace_once(text, patches).encode("utf-8")
    receipt = {
        "schema": "threemind.memory5-performance-candidate/1",
        "phase": phase,
        "scope": "Isolated engineering copy only; never installed or used by formal subjects",
        "status": "validated" if check_only else "prepared",
        "created_utc": datetime.now(UTC).isoformat(),
        "work": str(work),
        "source": SOURCE.as_posix(),
        "original_sha256": digest(original_bytes),
        "source_manifest_sha256": digest(hashes_path.read_bytes()),
        "source_sha256_before": digest(data),
        "source_sha256_after": digest(changed),
        "patches": [{"before": before, "after": after} for before, after in patches],
        "equivalence_obligation": (
            "Keep all state, audit counters, event IDs/order, configuration and simulated time; "
            "compare complete state hashes and checkpoint continuation before judging speed. "
            "The cache is reconstructed on creation, restore and reconfigure. "
            "Weight-view bypasses only the exact V5 unchanged settlement branch."
        ),
    }
    if not check_only:
        # A pre-write receipt makes an interruption reviewable. A prepared
        # receipt must never be blindly retried or treated as completed.
        with manifest_path.open("xb") as stream:
            stream.write(manifest_bytes(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != data or original.read_bytes() != original_bytes:
            raise ValueError("Source changed during validation; prepared receipt retained")
        atomic_write(path, changed)
        receipt["status"] = "applied"
        atomic_write(manifest_path, manifest_bytes(receipt))
    return {key: receipt[key] for key in ("phase", "status", "work", "source_sha256_before", "source_sha256_after")} | {
        "manifest": None if check_only else str(manifest_path)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply-cache", "apply-weight-view"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true", help="Validate without writing")
    args = parser.parse_args()
    print(json.dumps(apply(args.work, args.action, args.check_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
