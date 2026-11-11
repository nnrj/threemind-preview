# Archive Catalogue and Non-blocking Persistence

[中文](../zh/archive-catalog.md) | [English](archive-catalog.md)

## Why the archive catalogue exists

ThreeMind keeps a model package (`.tmind`) as the portable, complete experimental
artifact. It contains the manifest, runtime state, logs, snapshots, and
portraits needed to reopen or audit that particular package. A package is not
replaced by a database row.

Management views, however, should not deserialize every historic graph merely
to display names, ticks, snapshot counts, or lineage. That behavior makes the
cost of listing archives proportional to the total size of all past
experiments, and can starve stimulation and control requests.

For this reason the Core maintains `data/archive-index.sqlite3` as a local,
derived archive catalogue. It contains small metadata records only: artifact
path, consciousness identity and name, package/kernel declaration, provenance,
time, tick, node/edge counts, lifecycle state, and parent identity.

## Data boundary

```text
associative runtime
  -> immutable package capture
  -> background archive writer
  -> portable .tmind artifact
  -> SQLite archive metadata index

management/package/snapshot APIs
  -> SQLite metadata query
  -> small catalogue response
```

The archive writer performs ZIP compression, file writes, and SQLite updates
outside the runtime tick. Automatic snapshots therefore do not make the Core
wait for archive I/O. A manual snapshot waits only at the HTTP/CLI boundary so
the caller can receive its saved artifact, while the associative runtime has
already released its lock before compression begins.

## New and legacy packages

New `.tmind` files include a compact `metadata.json` ZIP member. The catalogue
can index it without reading the full graph state.

Packages created before that header are supported. At Core startup they are
indexed by a low-priority background worker, one file at a time, with deliberate
yielding between files. During that one-time migration, historical
consciousnesses and snapshots appear progressively in the UI; the live graph,
stimulus, and control APIs remain catalogue-query operations rather than file
scans.

## Operations

- `GET /api/archive-index` reports the local index, migration, and writer
  status.
- `POST /api/archive-index/reindex?force=true` schedules a new background
  catalogue pass after files were copied into `data/` outside ThreeMind.
- Deleting `archive-index.sqlite3` (and its `-wal`/`-shm` companions) does not
  delete consciousness data. The next Core start rebuilds it from `.tmind`
  files.
- Back up/export `.tmind` files for durable research records. The SQLite index is
  disposable operational metadata, not the only copy of an experiment.

The older generic file/SQLite/MySQL/D1 persistence adapter remains a separate
application-level extension point. It does not replace the local archive
catalogue or alter associative dynamics. A future remote catalogue backend
should be implemented as an explicit synchronizer/mirror with its own failure
and migration semantics, not by making live Core execution depend on network
database availability.
