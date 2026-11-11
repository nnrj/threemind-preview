"""On-demand evidence packaging; database history is streamed, never rewritten."""

import csv
import hashlib
import io
import json
import zipfile
from tempfile import SpooledTemporaryFile

from threemind_runtime import ArtifactCodec

from .database_stream import closing_iterator, stream_rows
from .inputs import evidence_rows
from .model_library import annotation_snapshot
from .statistics import figure, phase_evidence, summarize

SPOOL_BYTES = 8 * 1024 * 1024
BLOCK_BYTES = 1024 * 1024


def json_lines(records, *, ensure_ascii=True):
    with closing_iterator(records) as iterator:
        for record in iterator:
            yield (json.dumps(record, ensure_ascii=ensure_ascii, default=str, allow_nan=False) + "\n").encode()


def database_json_lines(records, fields):
    """Copy PostgreSQL's valid JSONB text without parsing/rebuilding its tree.

    The raw values only come from internal SQL `jsonb::text` projections, never
    arbitrary user text. Header fields still use the normal JSON encoder.
    """
    with closing_iterator(records) as iterator:
        for record in iterator:
            raw = {target: record.pop(column) for target, column in fields.items()}
            parts = [json.dumps(record, ensure_ascii=False, default=str, allow_nan=False)[:-1]]
            separator = ", " if record else ""
            for name, value in raw.items():
                parts.extend((separator, json.dumps(name), ": ", "null" if value is None else value))
                separator = ", "
            parts.append("}\n")
            # One record at a time, not a whole JSON object tree or history.
            yield "".join(parts).encode()


def csv_rows(metrics):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=sorted({key for row in metrics for key in row}))
    writer.writeheader()
    yield buffer.getvalue().encode()
    for row in metrics:
        buffer.seek(0)
        buffer.truncate()
        writer.writerow(row)
        yield buffer.getvalue().encode()


class EvidenceArchive:
    def __init__(self, archive):
        self.archive = archive
        self.files = {}
        self.sizes = {}

    def write(self, name, chunks):
        if name in self.files:
            raise ValueError("duplicate evidence member")
        digest, size = hashlib.sha256(), 0
        # A member's size is unknown until consumed. ZIP64 permits a large
        # history without first buffering it to compute the length.
        with closing_iterator(chunks) as iterator, self.archive.open(name, "w", force_zip64=True) as member:
            pending = bytearray()
            for chunk in iterator:
                if pending and len(pending) + len(chunk) > BLOCK_BYTES:
                    member.write(pending)
                    digest.update(pending)
                    pending.clear()
                if len(chunk) >= BLOCK_BYTES:
                    view = memoryview(chunk)
                    for start in range(0, len(view), BLOCK_BYTES):
                        part = view[start : start + BLOCK_BYTES]
                        member.write(part)
                        digest.update(part)
                else:
                    pending.extend(chunk)
                size += len(chunk)
            if pending:
                member.write(pending)
                digest.update(pending)
        self.files[name], self.sizes[name] = digest.hexdigest(), size

    def bytes(self, name, raw):
        view = memoryview(raw)
        self.write(name, (view[i : i + BLOCK_BYTES] for i in range(0, len(view), BLOCK_BYTES)))

    def json(self, name, value):
        self.bytes(name, json.dumps(value, ensure_ascii=False, default=str, indent=2, allow_nan=False).encode())


def export_evidence(database, job, cp, image, protocol, profile, metadata):
    project, run = job["project_id"], job["run_id"]
    boundary = (run, cp["time_us"], cp["revision"])
    # Only a requested export may spill its transient ZIP to disk. The file is
    # removed on success/failure; the committed DB artifact is authoritative.
    with SpooledTemporaryFile(max_size=SPOOL_BYTES, mode="w+b") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            package = EvidenceArchive(archive)
            package.bytes("model.tmind", ArtifactCodec.encode(image, profile=profile))
            with database.tx(project, repeatable=True) as db:
                package.json("annotations.json", annotation_snapshot(db, run, cp["id"]))
                with closing_iterator(
                    stream_rows(
                        db,
                        "SELECT metrics FROM observations WHERE run_id=%s AND time_us<=%s AND commit_revision<=%s ORDER BY time_us",
                        boundary,
                        batch=128,
                    )
                ) as samples:
                    metrics = [row["metrics"] for row in samples]
                package.write("observations.csv", csv_rows(metrics))
                package.write(
                    "input-carriers.jsonl",
                    database_json_lines(
                        stream_rows(
                            db,
                            "SELECT e.id,e.adapter_id,e.adapter_version,e.source,e.payload::text AS payload_json,e.payload_hash,e.configuration::text AS configuration_json,e.configuration_hash,e.created_at FROM input_envelopes e WHERE run_id=%s AND (e.processed_revision<=%s OR EXISTS(SELECT 1 FROM input_frames f WHERE f.envelope_id=e.id AND f.scheduled_revision<=%s)) ORDER BY e.ordinal",
                            (run, cp["revision"], cp["revision"]),
                        ),
                        {"payload": "payload_json", "configuration": "configuration_json"},
                    ),
                )
                package.write(
                    "input-frames.jsonl", json_lines(evidence_rows(db, run, cp["revision"]), ensure_ascii=False)
                )
                event_query = "SELECT time_us,kind,payload::text AS payload_json,commit_revision,provenance::text AS provenance_json FROM events WHERE run_id=%s AND time_us<=%s AND commit_revision<=%s"
                for filename, kind in (
                    ("events.jsonl", None),
                    ("organ-outputs.jsonl", "organ_output"),
                    ("telemetry-samples.jsonl", "telemetry_sample"),
                    ("structural-readouts.jsonl", "structural_readout"),
                    ("temporal-readouts.jsonl", "temporal_readout"),
                ):
                    package.write(
                        filename,
                        database_json_lines(
                            stream_rows(
                                db,
                                event_query + (" AND kind=%s" if kind else "") + " ORDER BY time_us,id",
                                (*boundary, kind) if kind else boundary,
                            ),
                            {"payload": "payload_json", "provenance": "provenance_json"},
                        ),
                    )
                unknown = {}
                for table, fields, ordering, raw_fields in (
                    (
                        "observations",
                        "time_us,sequence,metrics::text AS metrics_json,commit_revision",
                        "time_us",
                        {"metrics": "metrics_json"},
                    ),
                    (
                        "events",
                        "time_us,kind,payload::text AS payload_json,commit_revision,provenance::text AS provenance_json",
                        "time_us,id",
                        {"payload": "payload_json", "provenance": "provenance_json"},
                    ),
                ):
                    unknown[table] = db.execute(
                        f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND time_us<=%s AND commit_revision IS NULL",
                        (run, cp["time_us"]),
                    ).fetchone()["n"]
                    package.write(
                        f"unscoped-{table}.jsonl",
                        database_json_lines(
                            stream_rows(
                                db,
                                f"SELECT {fields} FROM {table} WHERE run_id=%s AND time_us<=%s AND commit_revision IS NULL ORDER BY {ordering}",
                                (run, cp["time_us"]),
                            ),
                            raw_fields,
                        ),
                    )
            package.json("protocol.json", protocol)
            package.json("recovery-context.json", cp["context"])
            # Full numerical time samples are retained for the existing
            # trapezoidal statistics and figures. This remains O(samples),
            # separately from the now-streamed event/carrier history.
            package.json("phase-evidence.json", phase_evidence(metrics, protocol))
            for format in ("svg", "png", "pdf"):
                package.bytes("dynamics." + format, figure(metrics, format=format))
            audit = {
                "revision": cp["revision"],
                "time_us": str(cp["time_us"]),
                "rule": "Scoped observations/events require both time_us <= checkpoint time and known commit_revision <= checkpoint revision.",
                "unscoped_counts": unknown,
                "unscoped_rule": "Unknown commit revisions are preserved in unscoped-*.jsonl, excluded from scoped statistics and figures; their presence at this checkpoint cannot be established.",
            }
            package.json(
                "manifest.json",
                {
                    **metadata,
                    "schema": "threemind.evidence/2",
                    "files": dict(package.files),
                    "file_bytes": dict(package.sizes),
                    "coverage": cp["context"].get("recording"),
                    "summary": summarize(metrics, protocol),
                    "commit_boundary": audit,
                },
            )
        output.seek(0)
        return database.put_artifact_stream(
            job, f"evidence-r{cp['revision']}.zip", "application/zip", output, metadata | {"evidence_boundary": audit}
        )
