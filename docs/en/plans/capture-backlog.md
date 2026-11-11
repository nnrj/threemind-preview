# Continuous capture backlog repair (2026-09-09)

## Cause and implementation

The previous worker forced a synchronous whole-model checkpoint for every live packet, in addition to durable packet admission. Default 200 ms audio packets therefore triggered frequent model serialization and graph projection writes. Both checkpoint writes and packet admission requested an exclusive run-row lock. At thousands of nodes and tens of thousands of edges, a single wait could fill the default 16-packet browser queue.

Live packets now use the regular `checkpoint_us` cadence, including the existing wall-time, buffered-memory and stop boundaries. Original bytes, encoder state, sequence and input commands still commit atomically before acknowledgement. Scheduling/delivery evidence, the command cursor and Core state still commit in one checkpoint transaction. Recovery processes commands after the committed cursor. Ordinary manual text, explicit saves and organ controls retain immediate checkpoint requests.

Checkpoint writers now use `FOR NO KEY UPDATE`; capture admission uses compatible `FOR KEY SHARE`. Deletion and identity changes remain blocked. Ordinary input producers retain `FOR UPDATE`, which excludes capture admission. Concurrent live packets additionally serialize budget and sequence checks through a per-run transaction advisory lock. Every path acquires the run row first. Synchronous capture authorization and SQL queries execute outside the async receive loop.

Core dynamics, sampling, encoding, frame timestamps and default queue limits are unchanged. No samples are silently dropped. Admission checks the committed run state visible at that point. A packet admitted concurrently with pause, closure or death is not guaranteed to be delivered: committed input evidence reports the outcome.

## Interface and validation

The chat sidebar shows acknowledged packets, pending packets/capacity and latest acknowledgement latency for the ear and eye. Overflow errors include those values and the parameter location. The limit remains configurable from 1 to 256, default 16, under Parameters → Advanced → Continuous device capture. Sustained overload still stops capture explicitly.

Backend tests cover admission during an open checkpoint transaction, concurrent duplicate requests, periodic checkpoints with complete delivery evidence, async loop isolation, pause/recovery and original-byte export. Browser tests use synthetic devices in manual, default physical-world and 1,024-node/64,512-initial-edge workloads with simultaneous ear and mouth operation.

Reducing checkpoint frequency alone still overflowed in the large-network test; the final concurrent-admission repair passed that workload. Latencies are local engineering observations affected by other processes, not precise speedup estimates. This validation makes no consciousness claim and does not guarantee realtime operation at arbitrary scale. Subsequent scientific experiments retain `threemind.causal/9`.
