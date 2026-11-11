# Consciousness workbench, system settings and projects

[简体中文](../zh/platform-workbench.md) · [Platform and AI access](platform-access.md) · [Implementation plan](plans/platform-hierarchy-navigation-workbench.md)

October 11, 2026: ThreeMind is a local-first application with a Web interface. Projects organize research and access grants; system settings manage deployment capabilities. Each consciousness retains its own version, configuration and recovery state.

## Entering and opening a consciousness

Start the workstation with the existing command:

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

Open <http://127.0.0.1:8877>. First-time setup assigns login credentials to the existing `local` identity, preserving its ID and all research ownership. Later sessions can remember login. Manage accounts, roles and grants under Users and permissions.

A single-user deployment can use this superadministrator directly without requesting approval for each menu, project or action. AI clients reuse a protected profile after initial login; limited delegation is optional. Deletion/migration confirmations, revision conflicts and managed-experiment controls are operation boundaries rather than permission applications.

The default home is the Consciousness workbench. With no selected consciousness, New and Open are shown; no recent instance is automatically opened or started. Open reads an authorized instance and graph without starting, pausing, restoring or copying it. Graph layout, frozen display and consciousness pause are separate actions. Viewing an already running instance leaves its execution unchanged.

The right panel includes properties, text stimulation and actual readouts, senses and outputs. Opening the page requests no camera or microphone and starts no playback. Cancelling media selection does not change senses. Live capture requires a running instance in realtime mode and an explicit action. Leaving releases this page's devices and playback while background execution follows its existing rules.

Ecological, experimental and frozen-evaluation subjects can be viewed; their owning controllers retain control. Details, recovery, historical branching, import and advanced tools retain distinct entries. A Core-only file is not a complete individual.

## Creation defaults, templates and preparation

System settings require no project selection. Creation defaults, configuration templates, device capabilities, AI, mail, host execution, storage and personal preferences have separate sections. The creation form is organized as **kernel version → a template for that kernel → parameters** on one page, rather than separate required submission steps. Choose an actual identity, such as `continuous-memory/4`; the description below explains its mechanisms and available execution backends.

The selected kernel's system creation defaults are selected initially, or its own factory defaults when no system revision has been saved. Explicitly adopt a matching built-in research template, saved template or project preset, then edit parameters. Resolution remains factory kernel defaults → system creation defaults → one explicitly selected template → current edits. One kernel can have several templates; template names do not stand in for kernel versions. Switching kernels reloads matching templates and asks before discarding unsaved changes. Selecting ownership does not overwrite a draft.

Save current parameters as template saves configuration, not learned weights or a complete individual. Instance details can also create a template from saved parameters. This reads configuration and its metadata revision without starting, pausing, restoring or stimulating the instance. Future template revisions cannot change its kernel; existing historical revisions remain intact.

The catalogue contains 16 actual identities: `causal/1` through `causal/9`, `continuous/1`, `continuous-memory/1` through `continuous-memory/4`, `lif/1`, and `unified-associative`. The original V1, V2 and V3 are three historical parameter templates for `unified-associative`, not three additional kernels. The default remains `continuous-memory/3`. This repair does not split the continuous family's shared Rust implementation solely by version number.

`unified-associative` supports only the Python reference backend, preserving the original `97d8592` input epochs, internal ticks and sensory encoding. Legacy labelled encoding is never silently changed to modern anonymous encoding. Its checkpoints use a separate complete JSON package path, not modern node/edge Arrow schemas. The backend is host metadata, `execution.backend`, outside the scientific `spec`; an explicitly unsupported backend is rejected. Historical causal kernels use their original structural-birth rules. Unified structural birth is rejected where no original rule exists; blank creation and exact forks remain available.

The default creation action is Create and prepare: save configuration and provenance, without a runtime job, checkpoint or simulation advance. Create and start is separate and explicit. Prepared instances can edit permitted fields, with metadata revision checks for saving and first start. Birth-fixed fields remain immutable.

Defaults and templates have independent revisions. Existing individuals keep their actual configuration when templates change. Display preferences apply to this browser, separated by account, and do not alter dynamics. Host speed, queues and concurrency are execution controls, not Core energy.

This deployment explicitly migrated from database schema 67 to 68 on October 11, 2026. Other deployments must migrate after updating code and before starting the new service; application startup does not automatically upgrade an old database:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

Migration uses existing local configuration. The workstation supplies matching backend workers. A separately deployed Python historical-kernel worker can use `python -m threemind_lab.cli worker --backend reference --task-family kernel-reference`. See the [delivery record](plans/kernel-creation-hierarchy-delivery.md) for migration evidence, validation limits and original-package preservation.

## Projects, materials and services

Navigation groups are Consciousness workbench, Research center, Materials center, System settings, and Documentation and help. Research/material lists default to all authorized projects; project selection filters lists. Detail identity, edit drafts and stimulus targets remain stable. Saving a new object requires explicit project ownership, with inline project creation; the first project is never selected automatically.

Project details hold members, presets, research rules and project tools. Legacy links resolve the appropriate object or independent project tool page. Filtering does not replace a materials menu with a different UI.

AI providers use one platform catalogue, with separate read, manage and use permissions. Migration retains provider IDs, revisions, keys and call/cost links. Existing project scope becomes an explicit grant; same-name services are not merged or automatically shared. Provider diagnostics do not require a fabricated project.

Mail transport and project event rules are separate. Platform services own credentials and transport; projects select a granted service and save events/recipients plus a frozen service revision. Editing a service does not change old policies or resend queued notices. The bell aggregates the user's authorized notifications without requiring project selection.

## Logout and continued execution

Explicit logout defaults to Logout and continue running. Users may instead select independently controlled instances for which they have pause permission, wait for confirmed pause, then log out. Failure to confirm preserves login and reports an error; accepting a command is not confirmation of pause. Managed experiments cannot bypass their controller through this dialog.

Session expiry, disconnection, closing the page and ordinary CLI client completion do not automatically pause instances. New actions need valid credentials and current grants. Admitted run provenance remains intact; sessions are not scientific checkpoint state. Stopping the workstation process, power failure and existing host safe-saving mechanisms are separate lifecycle events.

AI, CLI, MCP and Python share backend services and recording standards; see the [access guide](platform-access.md). Independent local Runtime use requires no Lab login.
