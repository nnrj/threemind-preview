# Kernel selection, configuration templates and creation hierarchy delivery

[简体中文](../../zh/plans/kernel-creation-hierarchy-delivery.md) · [Original plan and implementation addendum](platform-hierarchy-navigation-workbench.md) · [Workbench guide](../platform-workbench.md) · [Earlier platform delivery](platform-hierarchy-delivery.md)

October 11, 2026. The user identified hidden kernel versions, missing historical kernels and `/4`, and configuration sources placed above kernel identity. The repair restores the actual catalogue and organizes one page as kernel → matching template → parameters. Implementation, isolated engineering acceptance and real-database migration are recorded separately; temporary engineering checks are not formal research experiments.

## Implementation scope

| Actual kernel identity | Count | Available backends |
|---|---:|---|
| `threemind.causal/1` through `threemind.causal/9` | 9 | Python reference, Rust native |
| `threemind.continuous/1` | 1 | Python reference, Rust native |
| `threemind.continuous-memory/1` through `threemind.continuous-memory/4` | 4 | Python reference, Rust native |
| `threemind.lif/1` | 1 | Python reference, Rust native |
| `unified-associative` | 1 | Python reference |

There are 16 actual identities. The default remains `threemind.continuous-memory/3`. Display names include versions, with descriptions and backend capabilities shown separately. All preserved kernels permit creation; research presets are not kernels. Following the subsequent approved discussion, this phase does not split the continuous family's shared Rust implementation solely by version. Compatible code remains shared; incompatible historical paths are isolated.

System defaults and templates are queried for the selected kernel. One kernel supports multiple revisioned templates. Current parameters or an instance's saved parameters can become a template. Users may edit same-kernel parameters after adopting it. Source provenance records the starting configuration rather than replacing the final actual spec. Future revisions cannot change a template's kernel; existing historical cross-kernel revisions remain intact. Copying an instance configuration reads its metadata revision, clears `study_id`, `condition` and `block_seed`, and leaves checkpoints, jobs and simulated state unchanged.

Backend selection is host metadata, `execution.backend`, outside scientific `spec`. Unsupported explicit choices are rejected; default selection follows host configuration and the kernel's declared capabilities. Empty execution metadata on existing records remains empty rather than inventing historical backend provenance. Scheduling matches kernel and backend; a Python historical worker can run independently.

## Historical implementation and complete original packages

`unified-associative` restores the original Python implementation at `97d8592`, preserving environmental input epochs, Core ticks and original senses. Its V1/V2/V3 built-in templates come from historical UI `0c5e64a114fa33ca18c7106724388a8b3d0e352d`: labelled features, anonymous senses and anonymous spatial configuration. They belong to one kernel. `legacy-labeled` is never silently converted into modern anonymous or literal encoding.

The full package retains the original package, random state and pending host input. Checkpoints use an explicitly marked `threemind.unified-state-json/1` complete `state.json` container, without conversion through modern Node/Arrow fields or modern delta patches. Separate JSON node/edge query projections preserve the original 64-bit receptor channels and unknown historical fields. Modern container and restoration paths are not rewritten.

Historical causal `/1` through `/7` structural birth follows the original `birth/1` at `5a5f0dd`; `/8` follows its original rule at `304ef25`, rather than modern rules. Unified structural birth is explicitly rejected where no corresponding original rule is established. Blank creation, complete restoration and exact forks remain available; this is not a restriction on creating a historical kernel.

## Shared interfaces

| Operation | Interface/entry |
|---|---|
| Kernel catalogue | Existing catalogue with actual identity, description, backends and version-owned fields |
| Selected kernel's creation defaults | `GET /api/v2/configuration/defaults?kernel_id=...` |
| Matching saved/built-in templates | `GET /api/v2/configuration/templates?kernel_id=...`, returning `items` and `builtins` |
| Save parameter template | `POST /api/v2/configuration/templates` |
| Template from instance parameters | `POST /api/v2/projects/{project}/runs/{run_id}/configuration-template`, accepting a name and optional `expected_metadata_revision` |
| Agent/CLI operation catalogue | `configuration.template_from_run`, sharing the saving service and receipts |

Creation and template sources must match the actual kernel. Stale revisions, conflicts and unsupported backends return explicit errors, while same-kernel parameter edits remain permitted. Copying an instance requires `system.write` and source `runs.read`, without additional pause/configure/stimulate permission. Receipt retries still check current authorization.

## Explicit migration and real-database witnesses

After confirming this deployment had no running service or task, small schema and affected-configuration snapshots were saved and schema 67 → 68 was explicitly executed. The migration adds host execution metadata, template provenance and a separate historical graph projection without changing scientific state. Snapshots are in ignored `.work/kernel-hierarchy-20261011/`: 906,353 bytes for schema and 7,518 bytes for configuration, without another full original-data copy.

| Scientific object | Before/after count | Before/after hash |
|---|---:|---|
| Consciousness/runs | 20,581 | Identical |
| Checkpoints | 24,821 | Identical |
| Formal experiment index | 84 | Identical |
| Report revisions | 629 | Identical |
| Note revisions | 719 | Identical |
| Notification-policy revisions | 23 | Identical |
| Notifications | 16 | Identical |
| AI calls | 41 | Identical |

New `legacy_graph_rows` has zero rows and existing `runs.execution` values are all `{}`. The application account's new-table CRUD grants were verified. `doctor` passes after migration. Earlier 65 → 67 evidence remains separate and intact.

Other deployments must migrate explicitly; application startup never silently upgrades an old schema:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

For a separately deployed Python historical worker, use `python -m threemind_lab.cli worker --backend reference --task-family kernel-reference`. These are host operations and do not alter kernel clocks or dynamics.

## Validation evidence and limits

These are separate measured batches with different scopes, not repeated runs added into one total:

| Scope | Result |
|---|---|
| Historical Lab full path on both backends plus unified package codec | 17 passed, 109.9 seconds |
| Historical and modern kernel regressions | 270 passed |
| Complete historical birth regressions | 60 passed, including 16 new birth checks and 1 missing-rule rejection; 2 additional modern birth checks passed |
| Rust regressions | 4 passed |
| Scheduling and operation authorization | 14 and 3 checks passed |
| UI regressions | 40/40 passed; 3 string/execution rechecks passed; build succeeded |
| Observation and actual export/fork | 3 observation checks passed; 1 actual three-format export/exact-fork check passed; 5 additional UI checks passed and rebuild succeeded |
| Modern artifact/checkpoint/inheritance/Runtime interoperability | 36 passed |
| Template service focused checks | 5 passed; operation catalogue focused checks 3 passed |
| Unified codec, checkpoint pipeline and artifact validation focused checks | 15 passed |

The everyday virtual environment has the offline release wheel installed. Capture identity checks pass for all 15 native kernels and unified reference. These checks establish routing, parameter provenance, authorization, saving/restoration and compatibility; they do not establish a scientific advantage for a newer kernel or replace full shape/colour teaching. No new formal training or tuning was conducted. Unestablished historical rules are explicitly rejected rather than approximated with modern behavior.

Closeout: two study backend-provenance checks pass. Parents and children save the actual execution backend, preventing continuation from falling back to host defaults. This change records host provenance without changing paired-study inputs or dynamics.
## Same-day correction, October 11, 2026: /4 live startup and observation contract

The user started `意识测试_2026101101` and received `KeyError: 'parameters'`, then authorized repair of that test subject. It remained at simulation time0 and scientific revision0 with no checkpoint. Lab energy endpoints assumed decorated observations, whereas /4 returned its raw energy ledger. Earlier blank-creation/capture acceptance did not cover this live Lab startup path and must not be interpreted as proof that it passed.

The repair changes read-only observations: both Python and Rust /4 metrics include actual configuration and settlement time; checkpoint-boundary observations aggregate regional and node reserves while preserving raw checkpoint fields. Energy receipts report each actual accepted amount rather than subtracting accumulated counters. Historical observations with unknown enablement remain missing measurements. Spatial observations use the existing /4 time field. Current/historical node pagination and spatial tables include valid nodeID0 while preserving explicit subsequent cursors. The panel distinguishes total local reserve from capacity per region.

Learning, forgetting, resource allocation, clocks, identities and defaults are unchanged. No schema migration was needed; schema remains68. Only the authorized test subject's host status was returned to paused/revision0 (UI: not started), preserving its failed job and a recovery audit event without initializing Core or delivering input. Initial rows, receipt and engineering evidence remain ignored under `.work/startup-local4-20261011/`.

Twenty added cases cover both backends, energy models and switches, the user's realtime MuJoCo configuration, startup/pause/full-host resume, unchanged original bytes, CSV, spatial observation and nodeID0 pagination. The final native extension and frontend build are installed and checked. An expanded batch had89 passes and one failure: an existing /3 recovery gap when an already-born node receives zero response after energy exhaustion and lacks an expiry. Pure-memory reproduction fails on both backends; relevant /3 source matches the pre-repair commit. It remains inT12; validation was not weakened and old states were not rewritten. Engineering checks establish no new formal research experiment or learning benefit.

The complete UI batch has39 passing cases, including spatial nodeID0, read-only switching and existing workbench/configuration/authorization checks; frontend build succeeds. Changed Python files pass Ruff and the Rust file passes formatting. Workspace-wide formatting still reports prior historical-file differences; this repair does not reformat unrelated historical code.
