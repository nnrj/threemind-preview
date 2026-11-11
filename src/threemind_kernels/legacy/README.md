# Preserved historical kernels

These files are scientific implementation source, not generated experiment data.
The registry routes a birth-fixed kernel identity to this provider. Modern
`causal/9`, continuous-memory and LIF dynamics do not execute these modules.

## Source provenance

[`sources.json`](sources.json) records the full original Git revision, original
path and SHA-256 of every extracted source file. No old report, fixture,
individual or original experiment has been rewritten.

| Kernel identity | Original configuration revision | Execution source |
| --- | --- | --- |
| `threemind.causal/1` | `425f1a3` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/2` | `309b077` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/3` | `78f911b` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/4` | `14de159` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/5` | `33e3496` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/6` | `54e859a` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/7` | `0bdb5e1` | Compatible causal family at `0bdb5e1` |
| `threemind.causal/8` | `304ef25` | Separate restored-V3 family at `304ef25` |
| `unified-associative` | `97d8592` | Original Python frame/epoch runtime at `97d8592` |

Each causal identity exposes only fields belonging to its original config.
Compatible versions share the proven historical implementation; they do not
share a mutable modern-kernel profile. Python and Rust constructors receive the
identity **before** initialization. Unsupported mechanism fields, backend
choices and identity changes are rejected, rather than silently promoting an
individual to another kernel.

The only edits inside vendored execution sources are the birth-identity
constructor bridge in Python `causal_compat/engine.py` and Rust
`threemind-causal-legacy/src/lib.rs`, and the local `SensoryFrame` import in
`unified/sensors.py`. Source formatting and historical formulas are retained.
All other adaptation lives in `causal.py`, `unified_adapter.py`, the registry,
and the Rust/native dispatch boundary.

The preserved birth providers also change imports to their local historical
modules; their reset rules and fields are otherwise unchanged.

The original V1/V2/V3 UI choices are **templates of `unified-associative`**,
not three invented kernel versions. `unified_adapter.presets()` preserves their
original preset IDs, payload/encoding/spatial settings and source revision
`0c5e64a114fa33ca18c7106724388a8b3d0e352d`.

## Backends and contracts

- `causal/1..8`: independent Python `reference` and Rust `native` execution.
  The native facade is `_threemind_native.NativeLegacy`; standalone Rust
  `KernelEngine` also routes these identities.
- `unified-associative`: original Python `reference` only. Selecting `native`
  fails explicitly; this work does not introduce a new Rust reimplementation.
- Native `causal/8` retains the original lack of an intervention port.
  Reference `causal/8` exposes its original intervention operation. This is
  an explicit backend capability difference, not an automatic fallback.
- Unified energy accepts the original immediate supply port; causal scheduling
  and attention-modulation events are not fabricated for it. External Python
  attention plugins need a named checkpoint adapter before saving is allowed.

## Original unified time and input

`UnifiedConfig.tick_seconds` controls **environmental input epochs**, not a
new numerical solver step. An epoch with two due frames performs two separate
original Core ticks; an idle epoch performs the original idle transition.
Partial microsecond advancement never invents a Core tick.

`LegacyStimulus` is a transport dataclass compatible with host `InputBus`:
it preserves unsigned 64-bit receptor IDs, source/external flags and the
original `delay_epochs` scheduler argument. It does not use causal's uint32
channel codec. `unified/sensors.py` retains the original text encoding and
labels. The convenience `enqueue_text()` sends the original stream with
explicit epoch delays, preserving one-epoch spacing even at time boundaries.

At the requested host time, `kind=stimulus` means the frame was put into the
**original input queue**, and carries `delivery_stage=legacy_input_queue`,
the due epoch and envelope identity. It does not assert that a Core tick has
already happened. Original `stimulus_frame_delivered` records remain in the
package; the `legacy_epoch` observer reports the resulting epoch and tick.

New transport envelope UUIDs are replaced with deterministic opaque envelope
IDs. These IDs are provenance only: the original graph algorithm does not read
them. The original channel, node and edge identities are not remapped.
Optional new `consciousness_id` is applied to the empty package **before** the
first original runtime construction, so original sensory-seed derivation is
unchanged. Restoring never accepts an identity override.

## Recovery and observations

The unified state wrapper saves the complete original package/manifest,
environmental epoch phase, host pending inputs, original input queue, RNG,
attention adjustment, maintenance deficit and explicit silence policy.
Opaque original top-level state fields are retained. Original snapshots,
portraits, logs, sensory seed, receptor map, display labels, recent activity,
observations and readout histories remain in the package.

`life`, `queue`, `nodes` and `edges` are read-only host projections. Restore
checks them against the authoritative package and pending transport data.
Changing a projection is not a supported way to edit historical dynamics.
Modern observation aliases come from actual historical fields and the saved
receptor map; an unavailable channel is `None`, not a made-up measurement.
Raw scientific state continues to use the original field names and IDs.

## Historical structural birth

Structural inheritance routes to the original `threemind.birth/1` rule before
any modern reset. `causal/1..7` use the rule introduced at
`5a5f0dd58c254e56b290676287d17568e78ae9f0`, when `causal/7` was current. That
rule had no identity restriction, and its compatible executor explicitly
accepted states from `causal/1..7`. `causal/8` uses its separately preserved
rule at `304ef25dd8cafaec3cffd374cf9a7f06b77d5388`, including its version
check. Their original development tests and source hashes are indexed in
`sources.json`.

The earlier rule does not add the later propagation clock, transport counters,
node birth time or pending/generated inhibition fields. Original node/edge
identity, support, stability, touches and weights remain inherited. The
parent is unchanged; transient activity and input queues reset according to
the selected historical rule. These are new individuals, not continuations.
The host applies the same immutable birth transform before either backend;
the child then executes its original Python or Rust kernel independently.

The original unified package `clone()` is an exact state copy with archive
metadata reset; it is not a defined structural birth rule. Structural birth
therefore fails explicitly for `unified-associative`. Blank creation and exact
checkpoint fork/restore remain available, without inventing inheritance laws.

## Engineering evidence

`tests_v2/test_legacy_kernel_execution.py` checks frozen `causal/1..6`
continuations, all eight identities through host `Runtime` and `InputBus`,
same-backend exact restore/next-input continuation, cross-backend structural
decisions and existing float tolerances (`rel=1e-12`, `abs=1e-14`), original
unified text encoding/epoch transitions, 64-bit channels, partial-epoch
restore, dead-state evidence retention, and read-only observation.

Native frozen witnesses reproduce their original state hashes exactly. Python
comparison uses the established cross-platform libm tolerance; it does not
claim every Python/Rust floating-point bit must be identical.

`tests_v2/fixtures/legacy-birth.json` freezes small source-derived birth witnesses
for all eight causal identities. The tests also cover idempotence, original
state field sets, immutable parents, same-version child restore and subsequent
inputs on both backends. This does not add a modern rule to an old kernel.

These are bounded engineering fixtures and tests, not consciousness teaching,
formal experimental results or evidence that an unsupported historical host
plugin can be restored. Build outputs and temporary test data stay in ignored
`.work`/`target` directories. Tests do not access the workstation research DB,
operate user services or move original experiment files.
