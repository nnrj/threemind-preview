# ThreeMind Experiment and Debug Workbench

[中文](../zh/experiment-debugger.md) | [English](experiment-debugger.md)

## Purpose

The Experiment and Debug Workbench is a host-side research layer shared by a
human operator and an optional AI planner. It is not a new cognitive mechanism
and is not part of the associative Core. Its job is to make a test protocol,
its command trace, its outputs, and its interpretation inspectable.

The workbench is exposed in the React UI as **Experiments**. Its API contract
is `threemind-experiment/1`.

## Boundary

```text
researcher or external AI
  -> proposed experiment plan (JSON only)
  -> host-side validator and explicit command registry
  -> ordinary InputBus / OutputBus / archive APIs
  -> associative Core
```

An AI provider never receives arbitrary HTTP, filesystem, credential,
persistence, network-configuration, deletion, or direct graph-mutation
authority. It can propose only registered steps. The host validates every
argument, applies the run's explicit bounds, records execution, and rejects
everything outside the registry.

This also means that the AI debug bridge is a **duplex host adapter**, not an
internal sensory organ and not a source of automatic self-feedback. Its
submitted carriers use the normal `ai-debug` source policy and Text Sensor;
its observations come from OutputBus projections.

## Live observation transport

The workbench watches its selected target (including a non-active sandbox)
through `GET`-independent WebSocket endpoint
`/api/ws/consciousnesses/{consciousness_id}`. It uses the same acknowledged,
chunked graph snapshot protocol as the main observatory. A slow browser may
receive a fresh snapshot after a dropped visual delta, but it never blocks
Core ticks, changes the target, or silently removes graph elements.

## Visible creation and AI-planning lifecycle

Creating an isolated run and asking an external provider to draft a plan are
host-side operations that can take longer than an ordinary UI request. The
workbench therefore exposes them as one-way Server-Sent Event (SSE) streams:

- `POST /api/experiments/stream` reports validation, target resolution,
  sandbox cloning, initialization, history checkpointing, and the resulting
  experiment record.
- `POST /api/experiments/{run_id}/ai-plan/stream` reports planning stages and
  forwards the provider's raw text deltas to the UI while it is generated.

The streamed planner transcript is explicitly **untrusted and not executed**.
Only after the full response arrives does the host parse it, validate every
step against the registered command vocabulary and run-specific bounds, and
then save the normalized plan. Streaming is a visibility mechanism only; it
does not grant the provider any new command authority.

An experiment can select a saved provider during creation. The UI also has a
manual provider-list refresh, so a provider saved in Settings can be selected
without a browser reload.

## Registered commands

The current registry intentionally remains small:

- `observe.summary`, `observe.output`, `observe.graph`, and `history.tail`
  are read-only observations.
- `stimulus.send` submits a carrier as source `ai-debug` through the ordinary
  Text Sensor and InputBus.
- `runtime.wait` waits for actual runtime ticks; it does not synthesize a
  graph-wide transition.
- `snapshot.capture`, `runtime.pause`, `runtime.resume`, and
  `experiment.note` are narrowly scoped, auditable operations.

No command can delete packages, overwrite the selected consciousness, change
credentials, switch persistence, alter adapter topology, or invoke arbitrary
Core routes.

## Runs and isolation

By default, a new experiment creates a named clone of the selected
consciousness. The clone is an independent running instance and records its
source consciousness as provenance. Its ambient background can be preserved
or paused explicitly; pausing it is useful for controlled carrier tests.

Three execution modes are available:

- **Manual steps**: the researcher adds and runs each validated step.
- **Approval**: a plan may be proposed, but whole-plan execution requires an
  explicit confirmation.
- **Bounded auto**: only for a cloned sandbox; after an AI-proposed plan has
  passed registry validation, it runs with visible limits for total steps,
  submitted carriers, carrier length, and wait ticks.

The defaults are configuration, not hidden Core limits. The
`ai-debug-duplex` adapter exposes them through the normal adapter registry.
An individual run may only lower those limits; it cannot expand them through
the workbench or its HTTP request.
The manual command composer exposes every registered command with typed
controls; it is not a generic JSON or shell executor.

## Evidence, persistence, and reports

Experiment run records are stored through ThreeMind's selected persistence
backend (file, SQLite, MySQL, or D1), alongside an experiment index. The record
contains the target identity, initial observation, validated plan, executed
steps, arguments, results, timing, errors, artifacts, and external analysis.

An optional external AI analysis is an interpretation of recorded evidence,
not Core output and not a conclusion that consciousness is present. A
researcher may add a scoped analysis focus; that instruction is persisted with
the analysis entry. Exported Markdown reports are placed under `lab/ai-debug/`
and are marked **generated, unreviewed**. The persistent experiment record
remains the canonical audit trail.

## Initial templates

The first release includes repeatability, association/transfer,
forgetting/consolidation, input-order, and free-form templates. They are
starting protocols rather than claims. A meaningful result needs explicit
controls, independently cloned repetitions, comparison against alternate
encodings or source policies where relevant, and recorded negative results.

## Why this is separate from AI environmental stimulation

The AI Environment Scheduler creates open-ended external stimuli. The
workbench instead is designed to control variables and retain a trace. They
may share provider configuration and the same Text Sensor, but must retain
separate scheduling, prompts, source IDs, records, and authority boundaries.
