# ThreeMind kernel: architecture, time and local dynamics

[中文](../zh/v2-kernel.md)

New consciousnesses use **`threemind.causal/9` and `threemind.state/6`**. Local V3 laws are restored from Git `97d8592`, retaining approved timestamp delivery and independent traversal consolidation. The [restoration record](plans/v3-restoration.md) provides all formulas, decisions, source evidence and validation status. The [earlier audit](v2-kernel-behavior-audit.md) remains a historical account. Earlier causal/1–7 artifacts remain readable and exportable with their original identities; they cannot be relabeled, resumed or inherited under new dynamics.

## Architecture

Physical/simulated environment → sensory adapters → timestamped anonymous input → mutable in-memory Core → output adapters → environment. Read-only observers and immutable state captures feed Lab evidence and database checkpoints. Runtime owns pacing and adapter protocols; Lab owns storage, research tools, accounts and UI. Core has no dependency on a database, browser, AI or renderer.

Python reference code is in `src/threemind_core`, Rust in `crates/threemind-core`; restored local laws live in their respective restoration modules. Empty models contain no manually assigned concepts, brain regions or cognitive edges. Admitted channels can leave zero-support receptors, isolated nodes and disconnected subnetworks. Default edges arise from actual co-contact within a stimulus. Independent same-time inputs are not merged. Inherited structure has a recorded parent lineage.

External annotations and envelope references are evidence metadata, not propagation instructions. Passive observation does not crop activity according to human semantic or causal expectations.

## Time responsibilities

| Parameter | Default | Responsibility |
| --- | --- | --- |
| `step_us` | 10,000 μs | Numerical lattice, including flooring and existing optional spatial competition |
| `propagation_interval_us` | 100,000 μs | Physical emission, restored inhibition phases, edge forgetting and pruning |
| `delay_us` | 10,000 μs | Positive in-flight delay |

Time is an unsigned 128-bit integer in microseconds, serialized as decimal strings in JSON. State preserves observation time, last solved time, both next-boundary phases, complete queues and quiescence timing. Arbitrary observation batches do not create extra physical pulses. Same-time arrivals precede the death decision. In-flight signals reset quiescence only when they actually cause activity.

Realtime pacing uses the host monotonic clock, scaled pacing uses an explicit multiplier, and unbounded pacing computes without wall-clock waiting. Ordinary consciousnesses have no default duration limit. Display performance settings cannot change scientific time parameters.

## Local behavior

Soft inhibition is $S(q)=c\tanh(q/c)$; response is $R(q)=1/(1+g_rS(q))$. Arrival/contact and actual activation increment remain separate. Sending depends only on the source, edge and explicitly enabled spatial rules. Saturation at the receiver cannot revoke incurred transmission cost, and reception does not charge it twice.

An edge emits $x_{ij}=a_iR(q_i)w_{ij}g_{prop}\Delta t_{prop}$, default gain `.42` per physical pulse. Each path must pass `.004` before fan-in; individually rejected paths cannot rescue each other. Core activation flooring also defaults to `.004`, independently of rendering thresholds.

Coactivation, combined consolidation and local novelty determine birth. Local plasticity varies with node stability. Existing strong edges have less growth headroom and contact history participates in learning. Default event learning rate is `.055`, local novelty gain `.018`; neither is divided by the solver step nor driven by semantic scoring. Qualified actual emissions independently consolidate traversed edges without duplicating the old candidate-path association term.

Two-stage soft inhibition redistributes a finite pool with source subtraction and positive delay. Activation, node trace and inhibition decay over elapsed simulation time. Eligibility, stability and traversal history govern edge forgetting; node stability affects support loss. Zero activation alone does not delete a node: isolation, low support, zero activity and sufficient untouched time must coincide, default `.006` support and more than 80 simulated seconds. See the [full equations](plans/v3-restoration.md#formulas-and-phases).

## Life, damage and state

Before first activation, a consciousness waits. After birth, continuous zero activity for `quiescence_death_us` causes death, default 1 simulated second. Zero grace means immediate evaluation after same-time arrivals, not disabled death. Connections, residual inhibition, open interfaces and ineffective external stimuli are not evidence of life. Pausing and experimental duration limits are not death.

Death retains structure and evidence and cannot automatically resurrect the same consciousness. On 2026-09-09 the approved implementation removed independent starvation death while retaining optional shortage damage. Empty reserves do not erase activity or reset the inactivity grace period. See [unified activity death](plans/energy-lifecycle.md).

Explicit research damage separates disconnecting edges, deleting nodes, temporary silencing and unsilencing. Disconnecting does not retract emitted packets. Deleted receptors can later be recreated only with new node IDs and blank history; old packets cannot target the new identity. No random/default damage is added.

## Configuration and verification

Creation exposes the node-labeling/sensory mode at the first level. It shares `text_sensor.encoding` with advanced and JSON views. Validation and save enforce immutable fields and frozen experiments. Ordinary scientific changes require a pause and a causal configuration checkpoint. Existing queued signals retain their values and times. Explicit propagation-interval changes start a new phase and reset period-budget usage. Restricted live organ commands cannot alter unrelated Core parameters.

Models mutate in Core memory. Lab writes checkpoints/evidence to PostgreSQL under the recording protocol; `.tmind` and JSON are on-demand exports, not per-contact files. Exact continuation needs history, queues, phase, transport accounting and quiescence state, not just weights. No legacy mass migration occurs.

Optional causal space and interventions retain explicit settings; spatial competition keeps its existing numerical phase, separate from restored topological inhibition. UI coordinates do not enter Core. Same-backend replay checks hashes and phase invariance; Python/Rust comparisons allow stated floating-point tolerances. Frozen old operator witnesses validate local laws, not equality with obsolete whole-frame trajectories. These engineering checks do not establish AGI or subjective experience. See [validation and open questions](plans/index.md).
