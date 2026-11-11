"""Bounded observer-only scene transport; independent of physics dependencies."""

import base64
import hashlib
import json
import zlib

MAX_SCENE_BYTES = 64 * 2**20


def pack_scene(scene):
    raw = json.dumps(scene, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_SCENE_BYTES:
        raise ValueError("scene exceeds observer budget")
    return {
        "schema": "threemind.robot-scene/1",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "zlib": base64.b64encode(zlib.compress(raw)).decode(),
    }


def unpack_scene(archive):
    if archive.get("schema") != "threemind.robot-scene/1" or not 0 < archive["bytes"] <= MAX_SCENE_BYTES:
        raise ValueError("unsupported scene archive or byte budget")
    if len(archive["zlib"]) > 2 * MAX_SCENE_BYTES:
        raise ValueError("scene archive exceeds encoded budget")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(base64.b64decode(archive["zlib"], validate=True), MAX_SCENE_BYTES + 1)
    if not decoder.eof or decoder.unused_data or len(raw) != archive["bytes"]:
        raise ValueError("scene archive is incomplete or exceeds budget")
    if hashlib.sha256(raw).hexdigest() != archive["sha256"]:
        raise ValueError("scene checksum differs")
    return json.loads(raw)
