"""Explicit, pinned Playground assets. Task loading is always offline."""

import argparse
import hashlib
import importlib.util
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def manifest():
    return json.loads(Path(__file__).with_name("playground_assets.json").read_text(encoding="utf-8"))


def root():
    return (
        Path(os.environ.get("THREEMIND_PLAYGROUND_ASSETS", ".work/playground-assets")).resolve()
        / manifest()["menagerie_revision"]
    )


def checked_path(folder, name):
    path = (folder / name).resolve()
    if not path.is_relative_to(folder.resolve()) or Path(name).is_absolute() or ":" in name:
        raise ValueError("Playground asset path leaves its cache")
    return path


def valid(path, record):
    if not path.is_file() or path.stat().st_size != record["bytes"]:
        return False
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() == record["git_blob"]


def installed():
    return all(valid(checked_path(root(), r["path"]), r) for r in manifest()["asset_files"])


def install():
    package = manifest()
    if sum(r["bytes"] for r in package["asset_files"]) > 128 * 2**20:
        raise ValueError("Playground asset package exceeds 128 MiB")

    def download(record):
        path = checked_path(root(), record["path"])
        if valid(path, record):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{package['menagerie_revision']}/{record['path']}"
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read(record["bytes"] + 1)
        if (
            len(data) != record["bytes"]
            or hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != record["git_blob"]
        ):
            raise ValueError("Playground asset differs from pinned source")
        temporary = path.with_name(path.name + ".partial")
        temporary.write_bytes(data)
        temporary.replace(path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(download, package["asset_files"]))
    return {
        "installed": installed(),
        "revision": package["menagerie_revision"],
        "bytes": sum(r["bytes"] for r in package["asset_files"]),
    }


def verify_source():
    spec = importlib.util.find_spec("mujoco_playground")
    if spec is None or not spec.origin:
        raise ValueError("Pinned Playground is not installed; use the optional Playground worker image")
    folder = Path(spec.origin).resolve().parent.parent
    for record in manifest()["source_files"]:
        if record["path"] == "LICENSE":
            continue  # Installed under wheel license metadata, not as importable source.
        if not valid(checked_path(folder, record["path"]), record):
            raise ValueError("Playground source changed: " + record["path"])
    if not installed():
        raise ValueError("Pinned Panda assets missing; run python -m threemind_runtime.playground_assets install")
    return {"revision": manifest()["revision"], "assets": manifest()["menagerie_revision"]}


def probe(implementation, device):
    result = verify_source()
    import jax

    selected = jax.devices("gpu" if device == "cuda" else "cpu")
    if not selected:
        raise ValueError("selected JAX device is unavailable")
    if implementation == "warp":
        import mujoco_warp  # noqa: F401
    return result | {
        "devices": [str(d) for d in selected],
        "check": "pinned sources, assets, imports and device; compilation occurs when a task starts",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("install", "verify"))
    args = parser.parse_args()
    print(json.dumps(install() if args.operation == "install" else verify_source()))
