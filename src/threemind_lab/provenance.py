"""Scientific implementation identity, captured once when a worker starts."""

import hashlib
import importlib.util
import platform
from importlib.metadata import PackageNotFoundError, version

from threemind_core.spec import DYNAMICS, SCHEMA, STATE_SCHEMAS
from threemind_kernels.registry import kernel_catalog

from .config import ROOT


def capture_implementation(backend: str) -> dict:
    dependencies = {}
    for name in (
        "threemind-lab",
        "threemind-native",
        "mujoco",
        "numpy",
        "scipy",
        "pyarrow",
        "psycopg",
        "av",
        "Pillow",
        "psutil",
    ):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    sources = {}
    # Only executable project source and dependency manifests; never data, env or user files.
    for folder, pattern in (("src", "*.py"), ("crates", "*.rs"), ("crates", "Cargo.toml")):
        for path in sorted((ROOT / folder).rglob(pattern)):
            sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in (
        "Cargo.toml",
        "Cargo.lock",
        "crates/threemind-core/src/local-defaults.json",
        "crates/threemind-core/src/local52-defaults.json",
        "crates/threemind-core/src/local53-defaults.json",
        "crates/threemind-core/src/weight-decay-defaults.json",
        "pyproject.toml",
        "crates/threemind-runtime/src/media-profile-contract.json",
        "crates/threemind-runtime/src/media-profile-contract-v3.json",
        "crates/threemind-runtime/src/telemetry-profile-contract.json",
    ):
        path = ROOT / name
        if path.is_file():
            sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    aggregate = hashlib.sha256()
    for name, digest in sorted(sources.items()):
        aggregate.update(f"{name}\0{digest}\n".encode())
    native_hash = None
    if backend == "native":
        try:
            spec = importlib.util.find_spec("_threemind_native._threemind_native")
        except ModuleNotFoundError:
            spec = None
        if spec and spec.origin:
            with open(spec.origin, "rb") as binary:
                native_hash = hashlib.file_digest(binary, "sha256").hexdigest()
    return {
        "schema": "threemind.implementation/1",
        "backend": backend,
        "dynamics": DYNAMICS,
        "supported_dynamics": list(STATE_SCHEMAS),
        "kernels": [item for item in kernel_catalog() if backend in item["backends"]],
        "state_schema": SCHEMA,
        "supported_state_schemas": list(dict.fromkeys(STATE_SCHEMAS.values())),
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "packages": dependencies,
        "source_sha256": aggregate.hexdigest(),
        "source_files": sources,
        "native_binary_sha256": native_hash,
    }
