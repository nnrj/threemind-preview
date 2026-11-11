"""Explicit, pinned public models. Inference never downloads or executes repository code."""

import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path


def registry():
    return json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))


def root():
    return Path(os.environ.get("THREEMIND_LANGUAGE_MODELS", ".work/language-models")).resolve()


def folder(identity):
    item = registry()[identity]
    return root() / identity / item["revision"]


def verify_file(path, item):
    if not path.is_file() or path.stat().st_size != item["bytes"]:
        return False
    h = hashlib.sha256() if item["sha256"] else hashlib.sha1(f"blob {item['bytes']}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest() == (item["sha256"] or item["git_blob"])


def available(identity, *, verify=False):
    return all(
        verify_file(folder(identity) / f["path"], f)
        if verify
        else (folder(identity) / f["path"]).is_file() and (folder(identity) / f["path"]).stat().st_size == f["bytes"]
        for f in registry()[identity]["files"]
    )


def install(identity):
    value = registry()[identity]
    target = folder(identity)
    target.mkdir(parents=True, exist_ok=True)
    missing = sum(f["bytes"] for f in value["files"] if not verify_file(target / f["path"], f))
    if missing > 3 * 2**30 or shutil.disk_usage(target).free - missing < 30 * 2**30:
        raise ValueError("model budget exceeds 3 GiB or would leave less than 30 GiB free")
    for item in value["files"]:
        final = target / item["path"]
        if verify_file(final, item):
            continue
        temporary = final.with_suffix(final.suffix + ".partial")
        url = f"https://huggingface.co/{value['repository']}/resolve/{value['revision']}/{item['path']}"
        with urllib.request.urlopen(url, timeout=45) as response, temporary.open("wb") as stream:
            size = 0
            while block := response.read(4 * 1024 * 1024):
                size += len(block)
                if size > item["bytes"]:
                    raise ValueError("public model exceeds pinned size")
                stream.write(block)
        if not verify_file(temporary, item):
            raise ValueError("public model hash differs from pinned manifest")
        temporary.replace(final)
    return {"identity": identity, "revision": value["revision"], "verified": True, "folder": str(target)}


def status():
    return {
        key: {
            "available_here": available(key),
            "repository": row["repository"],
            "revision": row["revision"],
            "bytes": sum(v["bytes"] for v in row["files"]),
        }
        for key, row in registry().items()
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("list", "install", "verify"))
    parser.add_argument("identity", nargs="?", choices=tuple(registry()))
    args = parser.parse_args()
    if args.operation != "list" and not args.identity:
        parser.error("model identity required")
    print(
        json.dumps(
            status()
            if args.operation == "list"
            else install(args.identity)
            if args.operation == "install"
            else {"verified": available(args.identity, verify=True)}
        )
    )
