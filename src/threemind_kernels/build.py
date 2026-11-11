"""Build a standalone constructor from trusted versioned operators, never eval JSON."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .definition import KernelDefinition


def build_runtime(definition: KernelDefinition, output: Path, *, root=None, offline=True):
    definition = KernelDefinition.parse(definition.payload)
    root = Path(root or Path(__file__).resolve().parents[2]).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("output directory already exists; choose a new directory")
    if not (root / "Cargo.lock").is_file():
        raise ValueError("standalone build requires the ThreeMind source checkout and Rust toolchain")
    # This fingerprints only the small implementation tree, never data or model files.
    source = hashlib.sha256()
    paths = [root / "Cargo.lock", root / "Cargo.toml"]
    paths += sorted(p for p in (root / "crates").rglob("*") if p.suffix in (".rs", ".json") or p.name == "Cargo.toml")
    for path in paths:
        source.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    work = root / ".work"
    work.mkdir(exist_ok=True)
    cache = work / "kernel-build-cache"
    with tempfile.TemporaryDirectory(prefix="kernel-definition-", dir=work) as temporary:
        source_path = Path(temporary) / "definition.json"
        source_path.write_bytes(definition.payload)
        env = dict(
            os.environ, THREEMIND_KERNEL_DEFINITION=str(source_path), CARGO_TARGET_DIR=str(cache), CARGO_BUILD_JOBS="1"
        )
        command = ["cargo", "build", "-p", "threemind-runtime", "--release", "--locked"]
        if offline:
            command.append("--offline")
        subprocess.run(command, cwd=root, env=env, check=True, timeout=1200)
        binary = cache / "release" / ("threemind-runtime.exe" if sys.platform == "win32" else "threemind-runtime")
        inspected = subprocess.run([str(binary), "--inspect-definition"], capture_output=True, check=True, timeout=15)
        bound = KernelDefinition.parse(inspected.stdout)
        if bound.digest != definition.digest:
            raise ValueError("compiled constructor differs from the requested definition")
        output.mkdir(parents=True, exist_ok=False)
        shutil.copy2(binary, output / binary.name)
    (output / "definition.json").write_bytes(definition.payload)
    manifest = {
        "schema": "threemind.standalone-build/1",
        "kernel_id": definition.to_dict()["kernel_id"],
        "definition_hash": definition.digest,
        "source_hash": source.hexdigest(),
        "binary": binary.name,
        "binary_sha256": hashlib.sha256((output / binary.name).read_bytes()).hexdigest(),
        "platform": sys.platform,
        "architecture": platform.machine(),
        "semantics": "compiled constructor; model weights and physical state remain plastic",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
