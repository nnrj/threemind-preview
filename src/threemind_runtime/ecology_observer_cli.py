"""Read-only text/JSONL observation of an explicitly selected local population."""

import argparse
import json
import sqlite3
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path

from .codec import _json
from .ecology_observer import VERSION, ObserverConfig, describe_checkpoint, describe_event, evaluate_rules
from .world_schema import digest


class PopulationEvidenceReader:
    """Never instantiate PopulationStore, load model chunks or run an engine."""

    def __init__(self, path, instance, *, maximum_manifest_bytes=128 * 1024**2):
        self.path = Path(path).resolve(strict=True)
        self.instance = instance
        self.maximum_manifest_bytes = maximum_manifest_bytes
        with self.connect() as db:
            if db.execute("SELECT version FROM population_schema").fetchall() != [(1,)]:
                raise ValueError("unsupported population store schema")
            if not db.execute("SELECT 1 FROM population_instances WHERE id=?", (instance,)).fetchone():
                raise ValueError("population instance does not exist")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            db.execute("PRAGMA query_only=ON")
            yield db
        finally:
            db.close()

    def latest(self):
        with self.connect() as db:
            row = db.execute("SELECT revision FROM population_instances WHERE id=?", (self.instance,)).fetchone()
        if row is None:
            raise ValueError("population instance disappeared")
        return row[0]

    def checkpoint(self, revision):
        with self.connect() as db:
            db.execute("BEGIN")
            size = db.execute(
                "SELECT length(CAST(metadata_json AS BLOB)) FROM population_checkpoints WHERE instance=? AND revision=?",
                (self.instance, revision),
            ).fetchone()
            if size is None:
                raise ValueError("checkpoint is missing; observations are not silently skipped")
            if size[0] > self.maximum_manifest_bytes:
                raise ValueError("checkpoint manifest exceeds --maximum-manifest-mib; increase the explicit limit")
            metadata, state_hash = db.execute(
                "SELECT metadata_json,state_hash FROM population_checkpoints WHERE instance=? AND revision=?",
                (self.instance, revision),
            ).fetchone()
            members = dict(
                db.execute(
                    "SELECT individual,state_hash FROM population_members WHERE instance=? AND revision=?",
                    (self.instance, revision),
                )
            )
        value = _json(metadata.encode("utf-8"))
        if value.get("schema") != "threemind.ecology-runtime/1":
            raise ValueError("unsupported population checkpoint")
        if (
            value.get("checkpoint_hash") != state_hash
            or digest({k: v for k, v in value.items() if k != "checkpoint_hash"}) != state_hash
        ):
            raise ValueError("population manifest checksum mismatch")
        if {k: v["state_hash"] for k, v in value["members"].items()} != members:
            raise ValueError("population manifest has incomplete member references")
        return value

    def events(self, revision):
        cursor = 0
        while True:
            # Close each read transaction before handing data to a potentially
            # slow console/pipe. A viewer must not pin SQLite's WAL indefinitely.
            with self.connect() as db:
                rows = db.execute(
                    "SELECT id,event_json FROM population_evidence WHERE instance=? AND revision=? AND id>? ORDER BY id LIMIT 100",
                    (self.instance, revision, cursor),
                ).fetchall()
            if not rows:
                break
            for identity, raw in rows:
                value = _json(raw.encode("utf-8"))
                if value.get("scope") == "ecology":
                    yield identity, value
                cursor = identity


def population_summary(metadata):
    accounts = metadata["ledger"]["accounts"]
    if any(type(a.get("alive")) is not bool for a in accounts):
        raise ValueError("invalid body lifecycle in population manifest")
    # dead_recorded is a notification cursor, not the instantaneous Core life.
    # Do not infer a brain count from that cursor or read every model to fill it.
    return {
        "individuals": len(accounts),
        "living_bodies": sum(a["alive"] for a in accounts),
        "body_failures": sum(not a["alive"] for a in accounts),
        "births": len(accounts) - metadata["ledger"]["founder_count"],
        "maximum_generation": max((a["generation"] for a in accounts), default=None),
        "viable_cores": None,
        "model_time_us": str(metadata["time_us"]),
        "physical_time_us": str(metadata["world"]["time_us"]),
        "pending_delivery_us": str(metadata["pending_end_us"]) if metadata["pending_end_us"] is not None else None,
        "deferred_population": metadata["ledger"]["deferred_population"],
        "deferred_budget": metadata["ledger"]["deferred_budget"],
    }


def observe_checkpoint(reader, revision, configuration, previous):
    """Yield complete entries, then a cursor with the next read-only rule state."""
    if not configuration.enabled:
        return
    metadata = reader.checkpoint(revision)
    source = {
        "population_instance": reader.instance,
        "checkpoint_revision": revision,
        "checkpoint_hash": metadata["checkpoint_hash"],
        "configuration_hash": digest(configuration.model_dump(mode="json")),
        "scope": "standalone-population-manifest-and-ecology-events",
        "missing_metrics": ["viable_cores"],
    }
    if configuration.narration_enabled:
        for identity, value in reader.events(revision):
            yield describe_event(value, source | {"event_id": str(identity)})
    population = population_summary(metadata)
    if configuration.narration_enabled:
        # A standalone store doesn't declare whether its separate writer process
        # is still active. Reaching its latest CP is not a training completion.
        yield describe_checkpoint(population, "writer_status_unknown", source)
    entries, state = evaluate_rules(configuration, population, previous, source)
    yield from entries
    yield {
        "type": "cursor",
        "checkpoint_revision": revision,
        "checkpoint_hash": metadata["checkpoint_hash"],
        "rule_state": state,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, help="Existing standalone population SQLite store; opened read-only")
    parser.add_argument("--instance", default="ecology")
    parser.add_argument("--configuration", type=Path, help="Explicit observer configuration JSON")
    parser.add_argument("--write-example", type=Path, help="Create a disabled configuration example and exit")
    parser.add_argument("--output", type=Path, help="Optional new output file; stdout otherwise")
    parser.add_argument("--format", choices=("text", "jsonl"), default="text")
    parser.add_argument("--language", choices=("zh", "en"), default="zh")
    parser.add_argument("--from-revision", type=int)
    parser.add_argument("--through-revision", type=int)
    parser.add_argument("--follow", action="store_true", help="Wait for new committed checkpoints until interrupted")
    parser.add_argument("--poll-seconds", type=float, default=1)
    parser.add_argument("--maximum-manifest-mib", type=int, default=128)
    args = parser.parse_args()
    if args.write_example:
        with args.write_example.open("x", encoding="utf-8") as stream:
            stream.write(ObserverConfig().model_dump_json(indent=2) + "\n")
        return
    if args.store is None or args.configuration is None:
        parser.error("--store and --configuration are required")
    if not 0.25 <= args.poll_seconds <= 60 or not 1 <= args.maximum_manifest_mib <= 4096:
        parser.error("invalid polling interval or manifest memory limit")
    if any(v is not None and v < 1 for v in (args.from_revision, args.through_revision)):
        parser.error("checkpoint revisions start at 1")
    if args.follow and args.through_revision is not None:
        parser.error("--follow and a fixed --through-revision cannot be combined")
    if args.output and args.output.resolve() in (args.store.resolve(), args.configuration.resolve()):
        parser.error("output must not overwrite a scientific input")
    try:
        if args.configuration.stat().st_size > 128 * 1024:
            raise ValueError("observer configuration exceeds 128 KiB")
        configuration = ObserverConfig.model_validate(_json(args.configuration.read_bytes()))
        reader = PopulationEvidenceReader(
            args.store, args.instance, maximum_manifest_bytes=args.maximum_manifest_mib * 1024**2
        )
        initial_latest = reader.latest()
        current = args.from_revision or (1 if configuration.start_from == "beginning" else initial_latest)
        bound = args.through_revision or initial_latest
        if current > bound or bound > initial_latest:
            raise ValueError("selected checkpoint range is not currently available")
        with args.output.open("x", encoding="utf-8") if args.output else nullcontext(sys.stdout) as stream:

            def emit(value):
                if args.format == "jsonl":
                    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
                elif "text" in value:
                    stream.write(f"[r{value['source']['checkpoint_revision']}] {value['text'][args.language]}\n")
                elif value["type"] == "manifest":
                    stream.write(
                        (
                            "只读观察；内核生命汇总未读取，相关规则会标示证据不足。"
                            if args.language == "zh"
                            else "Read-only observation; Core life counts are not loaded and related rules remain undetermined."
                        )
                        + f" r{current}..{'follow' if args.follow else bound} · {value['configuration_hash']}\n"
                    )
                elif value["type"] == "cursor":
                    return
                else:
                    stream.write(
                        ("观察输出结束：" if args.language == "zh" else "Observation output ended: ")
                        + value["reason"]
                        + "\n"
                    )
                stream.flush()

            emit(
                {
                    "type": "manifest",
                    "version": VERSION,
                    "configuration": configuration.model_dump(mode="json"),
                    "configuration_hash": digest(configuration.model_dump(mode="json")),
                    "first_checkpoint_revision": current,
                    "maximum_checkpoint_revision": None if args.follow else bound,
                    "following": args.follow,
                    "missing_metrics": ["viable_cores"],
                    "scope": "standalone-population-manifest-and-ecology-events",
                }
            )
            if not configuration.enabled:
                emit({"type": "end", "reason": "observer_disabled"})
                return
            state = {}
            while True:
                latest = reader.latest() if args.follow else bound
                if latest < current - 1:
                    raise ValueError("population history moved backwards")
                while current <= latest:
                    for entry in observe_checkpoint(reader, current, configuration, state):
                        emit(entry)
                        if entry.get("type") == "cursor":
                            state = entry["rule_state"]
                    current += 1
                if not args.follow:
                    emit({"type": "end", "reason": "snapshot_complete", "through_revision": current - 1})
                    break
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
