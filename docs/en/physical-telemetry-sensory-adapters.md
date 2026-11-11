# Physical Telemetry Sensory Adapters

[中文](../zh/physical-telemetry-sensory-adapters.md) | [English](physical-telemetry-sensory-adapters.md)

## Role and boundary

ThreeMind treats measured computer state as part of the environment occupied by a consciousness. The implementation stays entirely in the application host and sensory-adapter layer:

```text
read-only operating-system counters
  -> shared HostTelemetryCollector
  -> per-consciousness anonymous sensory mapping
  -> SensoryFrame / InputBus
  -> Core

real thread CPU time and wall-clock timing around one Core instance
  -> read-only application wrapper _HostObservedRuntime
  -> runtime-telemetry-field anonymous sensory mapping
  -> SensoryFrame / InputBus in the next sampling cycle
  -> Core
```

The collector cannot read nodes, edges, or readable carriers. The adapters cannot change Core forgetting, consolidation, association, inhibition, propagation, attention, or energy rules. Physical telemetry is sensory input, not an energy source, and never enables energy simulation automatically. Instance feedback never directly echoes OutputBus, node activation, or readable content.

## Three sensory devices

- `host-telemetry-field` represents the host-computer environment and is on by default. It observes CPU, memory, disk, aggregate network counters, and battery/AC state.
- `process-telemetry-field` represents the whole ThreeMind service process and is off by default, preventing unselected feedback. With several consciousnesses it must never be interpreted as per-consciousness resource use.
- `runtime-telemetry-field` represents the real execution cost of one consciousness instance and is off by default. It independently measures thread CPU time, busy ratio, average epoch duration, and scheduling latency, then encodes a delayed anonymous input for that same consciousness.
- The stochastic `ambient-field` remains available but is off by default.
- “All background input” is an outer permission; each device still has an independent host-device switch and model-instance binding.

An explicit package `enabled: false` wins. A package without a host-telemetry declaration resolves it on and writes the complete resolved configuration on its next save, snapshot, normalized import, or rename. The model-package schema is now `3.0.0`; this unpublished project deliberately does not migrate old experiment packages.

## Measurements and availability

Initial host measurements cover:

- total CPU utilisation and frequency;
- physical-memory, commit, and swap pressure, plus page rates where the platform exposes them;
- disk read/write throughput and IOPS;
- aggregate network byte, packet, error, and drop rates—never addresses, connections, or content;
- battery level, AC presence, and charging state when reliably available.

Process measurements cover CPU, RSS, private memory, page-fault changes, read/write throughput, thread count, handle count, application telemetry-scheduler latency, and a read-only runtime epoch-duration measurement supplied by the application host. This group describes the complete ThreeMind service and must not be interpreted as one consciousness's exclusive resource use.

Instance measurements are:

- `thread_cpu_load`: real thread CPU time consumed while that instance executes epochs, divided by the sampling interval;
- `epoch_busy_ratio`: real epoch wall time divided by the sampling interval;
- `epoch_execution_time_ms`: mean epoch wall-clock duration inside the sampling window;
- `scheduler_latency_ms`: mean delay between the expected tick time and the runtime thread actually beginning work.

The application wrapper measures these quantities around calls into Core. Every consciousness owns an independent measurement window. Operating-system contention from other consciousnesses may naturally affect real latency, but is never relabelled as exclusive CPU or memory use by this instance.

`TelemetryPlugin` reserves a boundary for temperature, fans, GPU, SMART, and measured power. A plugin may enable a quantity only when it has a reliable measured value. Missing values retain reasons; zero is never fabricated, and CPU load is never relabelled as temperature or power.

`psutil` is optional:

```powershell
python -m pip install -e ".[telemetry]"
```

Without it, the service still starts and uses native CPU/memory fallbacks on Windows and Linux. Disk, network, battery, and process counters remain explicitly unavailable.

## Wall time, encoding, and normalisation

Host/process quantities use one shared monotonic-time collector; each runtime independently closes its own monotonic measurement window. Both default to `1000 ms` and remain independent of Core tick speed. Multiple consciousnesses share host raw samples while mapping them through different sensory seeds; runtime raw samples belong to their respective consciousnesses.

Every continuous quantity may produce:

- `metric.level`: smoothed present level;
- `metric.rise`: increase since the preceding level;
- `metric.fall`: decrease since the preceding level.

Fall is a separate non-negative channel because Core clamps negative input. The first sample establishes the change baseline. Pause, disable, resume, and service restart reset that baseline, so no paused experience accumulates into a spike. Disk and network cumulative counters become rates using the actual elapsed time; reset or wrap establishes a fresh baseline.

Runtime feedback is encoded only after a measurement window has closed and is queued for a later input epoch. It therefore cannot recurse synchronously into the epoch currently being measured. Real work caused by that feedback frame may be observed in the next window, forming an explicit and auditable physical loop.

CPU, memory, and battery use physical ratios, while CPU frequency uses its reported maximum. Aggregate network throughput prefers the combined speed of active non-loopback interfaces. Unbounded disk and similar rates use explicit, audited references. Every reference can be manually overridden in advanced settings; an unchecked manual switch cannot override a physical scale supplied by the probe.

## Configuration and runtime management

Adapter Management presents grouped availability, level, change, and gain columns. Level and change each have a master switch plus per-signal switches; disabling a master preserves child settings. A disabled model binding can still be prepared, but creates no mounted encoder and receives no frame.

Public endpoints include:

- `GET /api/adapters` for backend, dependency completeness, availability, last sample, plugins, and recent errors;
- `GET /api/consciousnesses/{id}/adapters` and `PATCH /api/consciousnesses/{id}/adapters/{adapter_id}` for instance bindings;
- `PATCH /api/background-input` for the outer background permission;
- `GET /api/telemetry/samples` for deduplicated global raw samples;
- `GET /api/telemetry/history` for consciousness/adapter delivery links;
- `GET /api/telemetry/export?records=deliveries|samples&format=csv|jsonl` to export delivery audit or raw samples; `adapter_id=runtime-telemetry-field&consciousness_id=...` queries and exports one consciousness's runtime feedback.

## Audit data

SQLite `data/telemetry-audit.sqlite3` stores one shared raw sample plus per-consciousness delivery links. Instance samples are stored separately with `scope=runtime` and their owner consciousness ID. Records include UTC and monotonic time, backend, raw value/unit, availability reason, normalised and smoothed levels, rise/fall, scale source, gain, smoothing, the exact anonymous input frame, consciousness ID, adapter ID, and delivery `envelope_id`. Instance records additionally contain the tick range, epoch count, accumulated thread CPU/wall time, and non-semantic links to input envelopes processed in that window. They remain pageable and exportable after restart; raw samples that produced no positive channel remain present in raw exports.

These rows are external experimental-instrument records. They are never written into nodes or edges and never form a hidden feedback path beyond the explicit sensory frames.
