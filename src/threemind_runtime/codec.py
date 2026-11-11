from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile
from dataclasses import fields

from threemind_core import StateImage
from threemind_core.engine import Edge, Node
from threemind_kernels.registry import kernel_catalog, state_kernel

from .profile import profile_fields, read_profile

FORMAT = "threemind.artifact/2"
UNIFIED_PAYLOAD = "threemind.unified-state-json/1"
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


def split_local_objects(state):
    if state.get("dynamics") not in (
        "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3", "threemind.experimental-weight-decay/1"
    ):
        return
    state["local_object_columns"] = {
        "schema": "threemind.local-object-columns/1",
        **{
            name: [{k: v for k, v in row.items() if k not in {f.name for f in fields(kind)}} for row in state[name]]
            for name, kind in (("nodes", Node), ("edges", Edge))
        },
    }


def join_local_objects(state):
    if state.get("dynamics") not in (
        "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3", "threemind.experimental-weight-decay/1"
    ):
        return
    from threemind_kernels.local import LocalEdge, LocalNode

    if state["dynamics"] == "threemind.continuous-memory/5":
        from threemind_kernels.local5 import Local5Edge as LocalEdge
        from threemind_kernels.local5 import Local5Node as LocalNode
    elif state["dynamics"] == "threemind.continuous-memory/5.1":
        from threemind_kernels.local51 import Local51Edge as LocalEdge
        from threemind_kernels.local51 import Local51Node as LocalNode

    elif state["dynamics"] == "threemind.continuous-memory/5.2":
        from threemind_kernels.local52 import Local52Edge as LocalEdge
        from threemind_kernels.local52 import Local52Node as LocalNode

    elif state["dynamics"] in ("threemind.continuous-memory/5.3", "threemind.experimental-weight-decay/1"):
        from threemind_kernels.local53 import Local53Edge as LocalEdge
        from threemind_kernels.local53 import Local53Node as LocalNode

    extra = state.pop("local_object_columns", None)
    if (
        not isinstance(extra, dict)
        or set(extra) != {"schema", "nodes", "edges"}
        or extra["schema"] != "threemind.local-object-columns/1"
    ):
        raise ValueError("missing local object columns")
    for name, base, local in (("nodes", Node, LocalNode), ("edges", Edge, LocalEdge)):
        expected = {f.name for f in fields(local)} - {f.name for f in fields(base)}
        if len(extra[name]) != len(state[name]) or any(set(row) != expected for row in extra[name]):
            raise ValueError("invalid local object columns")
        state[name] = [row | values for row, values in zip(state[name], extra[name])]


def state_fields(row_type, dynamics):
    # Historic artifacts remain byte/hash faithful, without synthesizing fields absent from their original version.
    added = (
        {"birth_us", "local_plasticity", "pending_inhibition", "generated_inhibition"}
        if row_type is Node and dynamics in tuple(f"threemind.causal/{n}" for n in range(1, 8))
        else set()
    )
    return [f for f in fields(row_type) if f.name not in added]


def validate_archive(state):
    versions = {
        f"threemind.causal/{n}": f"threemind.state/{v}"
        for n, v in ((1, 2), (2, 2), (3, 3), (4, 4), (5, 5), (6, 5), (7, 5), (8, 6))
    }
    if state.get("schema") != versions.get(state.get("dynamics")):
        raise ValueError("unsupported archived dynamics")
    from threemind_core.spec import timestamp

    timestamp(state["time_us"])
    ids = {n["id"] for n in state["nodes"]}
    if len(ids) != len(state["nodes"]) or any(e["source"] not in ids or e["target"] not in ids for e in state["edges"]):
        raise ValueError("invalid archived graph")


def _preflight_ipc(raw: bytes, max_bytes: int) -> int:
    """Inspect Arrow's official FlatBuffer footer/record metadata before Zstd allocation.

    Table indices follow Arrow format/File.fbs and Message.fbs. No payload is
    executed; all offsets and declared uncompressed buffer lengths are bounded.
    """

    def scalar(data, fmt, pos):
        if pos < 0 or pos + struct.calcsize(fmt) > len(data):
            raise ValueError("invalid Arrow metadata offset")
        return struct.unpack_from(fmt, data, pos)[0]

    def field(data, table, index):
        vtable = table - scalar(data, "<i", table)
        size = scalar(data, "<H", vtable)
        if 4 + index * 2 >= size:
            return None
        offset = scalar(data, "<H", vtable + 4 + index * 2)
        return table + offset if offset else None

    def indirect(data, pos):
        if pos is None:
            return None
        return pos + scalar(data, "<I", pos)

    def vector(data, table, index, width):
        pos = indirect(data, field(data, table, index))
        if pos is None:
            return []
        count = scalar(data, "<I", pos)
        if pos + 4 + count * width > len(data):
            raise ValueError("invalid Arrow metadata vector")
        return range(pos + 4, pos + 4 + count * width, width)

    if len(raw) < 10 or raw[:6] != b"ARROW1" or raw[-6:] != b"ARROW1":
        raise ValueError("invalid Arrow file")
    footer_size = scalar(raw, "<I", len(raw) - 10)
    if footer_size > len(raw) - 10:
        raise ValueError("invalid Arrow footer")
    footer = memoryview(raw)[len(raw) - 10 - footer_size : len(raw) - 10]
    root = scalar(footer, "<I", 0)
    if list(vector(footer, root, 2, 24)):
        raise ValueError("dictionary encoded models are not supported")
    expanded = 0
    for block in vector(footer, root, 3, 24):
        offset = scalar(footer, "<q", block)
        metadata_size = scalar(footer, "<i", block + 8)
        body_size = scalar(footer, "<q", block + 16)
        if offset < 0 or metadata_size < 8 or body_size < 0 or offset + metadata_size + body_size > len(raw):
            raise ValueError("invalid Arrow block bounds")
        prefix = 8 if raw[offset : offset + 4] == b"\xff\xff\xff\xff" else 4
        metadata = memoryview(raw)[offset + prefix : offset + metadata_size]
        message = scalar(metadata, "<I", 0)
        kind = field(metadata, message, 1)
        if kind is None or scalar(metadata, "<B", kind) != 3:
            raise ValueError("unexpected Arrow message")
        batch = indirect(metadata, field(metadata, message, 2))
        if batch is None:
            raise ValueError("missing Arrow record batch")
        length = field(metadata, batch, 0)
        if length is not None and not 0 <= scalar(metadata, "<q", length) <= 10_000_000:
            raise ValueError("Arrow batch exceeds row budget")
        compressed = field(metadata, batch, 3) is not None
        for buffer in vector(metadata, batch, 2, 16):
            start = scalar(metadata, "<q", buffer)
            size = scalar(metadata, "<q", buffer + 8)
            if start < 0 or size < 0 or start + size > body_size:
                raise ValueError("invalid Arrow buffer bounds")
            if compressed and size:
                if size < 8:
                    raise ValueError("invalid compressed Arrow buffer")
                declared = scalar(raw, "<q", offset + metadata_size + start)
                if declared < -1:
                    raise ValueError("invalid expanded Arrow length")
                size = size - 8 if declared == -1 else declared
            expanded += size
            if expanded > max_bytes:
                raise ValueError("expanded Arrow data exceeds import budget")
    return expanded


def _json(raw: bytes) -> dict:
    def pairs(items: list) -> dict:
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("duplicate JSON key")
            result[k] = v
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON value {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


class ArtifactCodec:
    """Explicit interchange only. No codec method writes to the filesystem."""

    @staticmethod
    def encode(image: StateImage, format: str = "tmind", *, profile=None) -> bytes:
        if format == "json":
            return json.dumps(
                {"format": FORMAT, "state_hash": image.digest, "state": image.to_dict(), **profile_fields(profile)},
                indent=2,
                allow_nan=False,
            ).encode()
        if format != "tmind":
            raise ValueError("model format must be tmind or json")
        return ArtifactCodec._encode_binary(image.to_dict(), image.digest, profile=profile)

    @staticmethod
    def _encode_binary(captured: dict, state_hash: str, *, profile=None) -> bytes:
        """Internal encoding of one already captured state; never mutate its tables."""
        if captured.get("dynamics") == "unified-associative":
            return ArtifactCodec._encode_unified(captured, state_hash, profile=profile)
        import pyarrow as pa

        state = dict(captured)
        split_local_objects(state)
        parts: dict[str, bytes] = {}
        for name, row_type in (("nodes", Node), ("edges", Edge)):
            schema = pa.schema(
                [
                    (
                        f.name,
                        pa.string()
                        if f.name.endswith("_us")
                        else pa.int64()
                        if f.name in ("id", "channel", "source", "target", "touches")
                        else pa.float64(),
                    )
                    for f in state_fields(row_type, state.get("dynamics"))
                ]
            )
            table = pa.Table.from_pylist(state.pop(name), schema=schema)
            sink = pa.BufferOutputStream()
            with pa.ipc.new_file(sink, schema, options=pa.ipc.IpcWriteOptions(compression="zstd")) as writer:
                writer.write_table(table, max_chunksize=65536)
            parts[f"{name}.arrow"] = sink.getvalue().to_pybytes()
        parts["state.json"] = json.dumps(state, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
        manifest = {
            "format": FORMAT,
            "state_hash": state_hash,
            **profile_fields(profile),
            "files": {
                name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in parts.items()
            },
        }
        parts["manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, raw in sorted(parts.items()):
                archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), raw)
        return output.getvalue()

    @staticmethod
    def _encode_unified(captured: dict, state_hash: str, *, profile=None) -> bytes:
        """Original graph/package fields and unsigned channels never enter Arrow."""
        if captured.get("schema") != "threemind.unified-state/1":
            raise ValueError("unsupported historical runtime state schema")
        raw = json.dumps(captured, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
        manifest = {
            "format": FORMAT, "payload_format": UNIFIED_PAYLOAD,
            "kernel_id": "unified-associative", "state_schema": "threemind.unified-state/1",
            "state_hash": state_hash, **profile_fields(profile),
            "files": {"state.json": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}},
        }
        parts = {"state.json": raw, "manifest.json": json.dumps(manifest, sort_keys=True).encode()}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            for name, part in sorted(parts.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, part, compresslevel=3)
        return output.getvalue()

    @staticmethod
    def decode(raw: bytes, *, max_bytes: int = MAX_ARTIFACT_BYTES, with_profile=False):
        if len(raw) > max_bytes:
            raise ValueError("model exceeds configured import size")
        if raw.lstrip().startswith(b"{"):
            document = _json(raw)
            if document.get("format") != FORMAT:
                raise ValueError("unsupported model format; legacy test data is not migrated")
            image = StateImage.from_dict(document["state"])
            expected = document["state_hash"]
            profile = read_profile(document)
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    names = archive.namelist()
                    if "manifest.json" not in names or len(names) != len(set(names)):
                        raise ValueError("unexpected or duplicate model members")
                    if sum(i.file_size for i in archive.infolist()) > max_bytes:
                        raise ValueError("expanded model exceeds import size")
                    manifest = _json(archive.read("manifest.json"))
                    unified = manifest.get("payload_format") == UNIFIED_PAYLOAD
                    if manifest.get("payload_format") not in (None, UNIFIED_PAYLOAD):
                        raise ValueError("unsupported model payload format")
                    required = {"manifest.json", "state.json"} if unified else {
                        "manifest.json", "state.json", "nodes.arrow", "edges.arrow"}
                    if len(names) != len(required) or set(names) != required:
                        raise ValueError("unexpected or duplicate model members")
                    profile = read_profile(manifest)
                    if manifest.get("format") != FORMAT or set(manifest["files"]) != required - {"manifest.json"}:
                        raise ValueError("unsupported model manifest")
                    parts = {}
                    for name, check in manifest["files"].items():
                        part = archive.read(name)
                        if len(part) != check["bytes"] or hashlib.sha256(part).hexdigest() != check["sha256"]:
                            raise ValueError(f"checksum failed: {name}")
                        parts[name] = part
                    state = _json(parts["state.json"])
                    if unified:
                        if (manifest.get("kernel_id") != "unified-associative"
                                or state.get("dynamics") != "unified-associative"
                                or manifest.get("state_schema") != "threemind.unified-state/1"
                                or state.get("schema") != manifest["state_schema"]):
                            raise ValueError("historical model identity differs from its manifest")
                    else:
                        import pyarrow as pa

                        if state.get("dynamics") == "unified-associative":
                            raise ValueError("historical runtime requires its original JSON payload")
                        if (
                            sum(_preflight_ipc(parts[f"{name}.arrow"], max_bytes) for name in ("nodes", "edges"))
                            > max_bytes
                        ):
                            raise ValueError("expanded model exceeds import budget")
                        for name in ("nodes", "edges"):
                            with pa.ipc.open_file(pa.BufferReader(parts[f"{name}.arrow"])) as reader:
                                row_type = Node if name == "nodes" else Edge
                                schema = pa.schema(
                                    [
                                        (
                                            f.name,
                                            pa.string()
                                            if f.name.endswith("_us")
                                            else pa.int64()
                                            if f.name in ("id", "channel", "source", "target", "touches")
                                            else pa.float64(),
                                        )
                                        for f in state_fields(row_type, state.get("dynamics"))
                                    ]
                                )
                                if not reader.schema.equals(schema, check_metadata=False):
                                    raise ValueError("unexpected model column schema")
                                table = reader.read_all()
                                if any(column.null_count for column in table.columns):
                                    raise ValueError("null values are not valid model state")
                                state[name] = table.to_pylist()
                        join_local_objects(state)
                    image = StateImage.from_dict(state)
                    expected = manifest["state_hash"]
            except (zipfile.BadZipFile, KeyError, TypeError) as exc:
                raise ValueError("invalid model container") from exc
        if image.digest != expected:
            raise ValueError("logical state checksum failed")
        try:
            if image.to_dict().get("dynamics") in {k["kernel_id"] for k in kernel_catalog()}:
                state_kernel(image).create(state=image, backend="reference")
            else:
                validate_archive(image.to_dict())  # Read-only decode; engines refuse continuation.
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError("invalid model state") from exc
        return (image, profile) if with_profile else image
