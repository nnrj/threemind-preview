"""Bounded in-memory readers for small scientific artifacts, across backends."""

from .blob_store import object_chunks


def object_bytes(database, project, kind, identity, *, maximum):
    if not isinstance(maximum, int) or maximum <= 0:
        raise ValueError("binary read requires a positive byte budget")
    raw = bytearray()
    chunks = object_chunks(database, project, kind, identity)
    try:
        for chunk in chunks:
            if len(raw) + len(chunk) > maximum:
                raise ValueError("binary resource exceeds its read budget")
            raw.extend(chunk)
    finally:
        chunks.close()
    return bytes(raw)
