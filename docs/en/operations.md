# ThreeMind Operating Guide

[中文](../zh/operations.md) | [English](operations.md)

**October 11, 2026 current Lab workflow:** use the [workbench guide](platform-workbench.md) and [platform access guide](platform-access.md). The real local database is explicitly upgraded to schema 67, the default home is the workbench and the first browser visit sets credentials for the existing local superadministrator. The older Core/UI instructions below are retained as historical operating documentation; they do not describe the current Lab default kernel or navigation.

## Local startup

Install the editable Python project before starting Core:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m threemind serve
```

Start the UI in a separate terminal:

```powershell
cd threemind-ui
npm install
npm run dev
```

Core listens on port `8877`; Vite normally listens on `3001`. If Core reports
that its port is occupied, inspect the holder with:

```powershell
Get-NetTCPConnection -LocalPort 8877 -State Listen | Select-Object OwningProcess
Get-Process -Id <PID>
```

Stop that specific process only after confirming it is an obsolete ThreeMind
server:

```powershell
Stop-Process -Id <PID>
```

## Create an instance

Use **意识图像 → 开启新意识**. The dialog supplies defaults and exposes an
advanced section:

- V3 anonymous spatial is the default; spatial embedding is enabled.
- V1 is a labeled compatibility baseline. Readable labels remain in an external
  adapter dictionary, not in Core nodes.
- V2 is anonymous sensory without spatial embedding.
- Advanced values are written into the new package manifest, including
  attention budget, association window, propagation, learning, forgetting,
  consolidation, and maximum node count.

An active instance can later adjust supported model parameters from
**设置 → 模型与空间**. Some manifest capabilities, such as enabling a spatial
embedding for a package created without one, require a new package.

## Stimuli, body, and lifecycle

The right sidebar separates observation, lifecycle control, and stimulation.

- Manual text is encoded by a text adapter before reaching Core.
- AI-generated text is also external input and follows the same input boundary.
- Measured host telemetry is the default background input. It is sampled in
  wall time outside Core and mapped to anonymous sensory channels.
- Stochastic ambient input remains available but is off by default. The body
  adapter can optionally sample, threshold, adapt, and add noise to that field.
- Whole-process telemetry and per-consciousness runtime telemetry are off by
  default because enabling either creates an explicit self-state feedback path.
- Disabling the final enabled stimulus source requires confirmation because it
  ends the running instance.

Use **设置 → 运行环境** to enable/disable sources or intentionally bypass the
attention budget for a source, and **躯体与注意门** to configure body filtering.
Use **Adapter management** for the outer background-input permission, physical
device switches, instance bindings, level/change channels, gains, and advanced
normalisation. Finite metabolic supply is independently off by default.
Physical telemetry emits ordinary anonymous frames and never supplies energy.
See [Physical Telemetry Sensory Adapters](physical-telemetry-sensory-adapters.md).

**设置 → 模型与空间** can independently control topology-local inhibition or
experimental energy accounting. Local inhibition is on by default and energy
accounting is off by default. Energy accounting has
no internal recovery; attaching its external supply adapter is a separate
experimental decision. See [Local Inhibition, Optional Energy Accounting, and
Dynamics Tracing](local-inhibition-energy-and-dynamics.md).

## Observation and interpretation

- **Single-tick snapshot readout** preserves the original structural output
  adapter: it observes one anonymous `OutputFrame` and records touched activity
  or repeatable structures.
- **Temporal-window convergence readout** is a parallel reader anchored to one
  input envelope. Across multiple ticks it measures persistence, activation
  integral, inhibition, and candidate-set stability. It is also read-only and
  writes results to passive-readout history. See [Temporal-window Convergence
  Readout](temporal-window-readout.md) for metrics and interpretation limits.
- **意识解读** is an optional external AI observer. It reads output-derived
  snapshots and stores interpretation text; it never becomes a Core stimulus
  automatically.
- The chat-like stimulation panel is presentation/logging UI. Hiding a message
  there does not stop the stimulus or erase history.
- After **Start detailed trace**, the consciousness detail page exposes a
  per-tick **Dynamics trace** of sparse activation, inhibition, touch, and
  optional energy changes. Stopping the trace stops generating this dense log.

Treat repeated structure, phrases, or visual clusters as experimental signals,
not a conclusion about consciousness. Compare controls and repeat runs.

## Snapshots, portraits, instances, and history

- A snapshot saves a named package state.
- A portrait is the exported state associated with a stopped/dead instance.
- Resume replaces the active instance; clone creates a new identity from a
  package state.
- The management pages provide instance lists, package actions, and paginated
  stimuli/observation/event/interpretation records.

Data is stored under `data/` by default. Do not commit `data/.threemind.key`,
encrypted provider credentials, encrypted network tokens, or experiment `.tmind`
packages unless you deliberately intend to share them.

If `data/ui-settings.json` is absent, the backend creates it once from the
canonical defaults. Startup never replaces an existing file, including a
manually prepared one. Use the tracked `data/ui-settings.example.json` as the
complete public configuration reference; it intentionally contains no secret
values.

## Optional AI providers

Configure providers in **设置 → AI 环境与解读**. API keys are sent to local
Core for encrypted storage and are not returned to the browser after saving.
Use the provider test button before enabling an environment generator or AI
interpreter.

## Optional network transport

In **设置 → 网络适配器**:

1. Set a shared token of at least 16 characters.
2. Enable the transport.
3. Optionally enable restricted remote modulation.

The Core remains bound to loopback by default. Only use `--host 0.0.0.0` when
you deliberately need remote access, and place it behind TLS/reverse-proxy
protection. See [architecture boundaries](architecture-boundaries.md) for the
protocol and limits.

## Persistence backends

The settings panel can select file, SQLite, MySQL, or Cloudflare D1 persistence
for catalog/management data. The in-memory runtime remains model-package based.
Before switching a backend in a meaningful experiment, export/snapshot the
current state and confirm the migration result in the package and history views.

Independent of that optional application-level backend, the local archive
catalogue is always indexed in `data/archive-index.sqlite3`. It makes package,
snapshot, and consciousness listings fast without placing archive scans on the
Core path; `.tmind` remains the complete portable record. Existing packages are
catalogued progressively after startup. See
[Archive Catalogue and Non-blocking Persistence](archive-catalog.md) for the
rebuild API and backup guidance.
