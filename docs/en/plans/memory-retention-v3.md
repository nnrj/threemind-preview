# continuous-memory/3: local retention repair and validation

> October 8, 2026, revision 5: implementation, engineering checks and bounded mechanism probes completed. The default gain 0.2 still provides insufficient edge retention; improved memory has not been established. Revision 4 below is the original delivery record. Its measurements do not describe the repaired default. Original reports, experiments and frozen witnesses remain intact.

[中文](../../zh/plans/memory-retention-v3.md) · [Repair report and evidence](../../../lab/explorations/2026-10-08-retention-repair/report.en.md) · [Backlog](research-backlog.md) · [User decisions and correction](../history/sources/2026-10-08-adaptive-retention.md)

## 5.1 Purpose, defaults and version boundary

Improving retention and forgetting remains the purpose of /3. Repair `threemind.continuous-memory/3` in place; do not retain its faulty implementation as another kernel. Complete historical kernels remain selectable by their original kernel IDs. The two /3 forgetting choices share ordinary positive learning, novelty rewards and node reclamation:

| Configuration | Current behavior | Role |
| --- | --- | --- |
| `consolidation_mode=adaptive-half-life` | Each edge learns its own H; no additional stability-based forgetting protection | Default, option 1 |
| `consolidation_mode=legacy-stability` | Original stability-based edge forgetting | Option 2, a control, not a complete historical kernel |
| `memory_growth_formula=log-saturating` | Saturating growth in logarithmic H coordinates | Default |
| `memory_growth_formula=linear-saturating` | Linear H growth capped at Hmax | Matched initial-gain control |

Existing 10 ms solver cadence, periodic propagation, old decay/structural scans, short-term resources, external/internal source distinctions and the default-off global energy model remain for later review. The whole executor is not claimed to be a fully local event engine.

## 5.2 Object-owned state and settlement on use

Each node and edge owns H and its materialization time. Nodes credit their own actually accepted input. Edges credit actual emission after gates and resource handling, exactly once, without receiver acknowledgement or queries of endpoint activation, H or salience. Dose uses a fixed 0.1 simulation-second reference, independent of solver steps, with no fixed per-event bonus. Strong-input salience and fatigue are node-local. Learning-off periods accumulate no deferred rewards.

Graph-wide retention updates, post-event synchronization, full-edge maintenance lists/sorting, unconditional Rust pruning reindexing and novelty reward undo/conversion into D are removed. Ordinary weight/stability reinforcement and direct novelty rewards are restored. Node stability is not repeatedly reset, and plasticity is not forced to one. The 0.55 `memory_weight_learning_rate` learns automatic node support only.

Objects settle on their own touch, transmission, structural change or expiry. Each computes its own next expiry, delivered by a sparse deadline queue at the existing post-propagation structural phase. Same-time input precedes expiry checks; idle objects still expire. Python uses an indexed mutable heap; Rust uses an ordered deadline set and object index. Superseded tasks do not accumulate. Indices locate objects; the queue delivers deadlines, without ranking or allocating learning opportunities.

Full construction is limited to loading or explicit configuration interventions. Rust edge deletion updates affected indices. Node deletion preserves the old Vec order and updates moved offsets; this is deletion-time storage cost, not periodic graph synchronization. Graphs, observations and metrics project current values without mutating H, S, weights or timers. Checkpoints preserve anchors and timers for later settlement.

## 5.3 Formulas and provisional values

For edges q is weight; for automatic nodes q is support S. During nonuse:

\[
H(t)=\max(H_{min},H_0-r\Delta t),\qquad
q(t)=q_0\exp\left[-\ln2\int_0^{\Delta t}\frac{du}{H(u)}\right].
\]

Both the integral and threshold crossing use analytic expressions rather than retention polling. On dose D, define \(x=\ln(H/H_{min})\), \(x_{max}=\ln(H_{max}/H_{min})\). Default growth is:

\[
H'=H_{min}\exp\{x_{max}-(x_{max}-x)\exp[-gD/x_{max}]\}.
\]

The linear control is \(H'=\min(H_{max},H+H_{min}gD)\). Passive decay, support learning and fatigue recovery retain their exponential/logarithmic formulas; no wholesale linear replacement was added. Hmin 30 seconds, Hmax 30 simulated days, regression 0.125 and gain 0.2 remain provisional engineering parameters, with no human-time equivalence.

**Measured limit:** after 120 seconds of repetition, default maximum edge H is about 40.33 seconds. Both edges disappear after 300 seconds without input, while the legacy-stability control retains mean weight 0.21256. Registered gain-2/4 calibration controls retain about 0.97053/0.99832. Only repetition was tested for those gains, without long-background or reversal costs; neither becomes the default. Nodes and edges receive different actual doses; a large node H cannot stand in for edge retention.

## 5.4 Reclamation and default-off local awakening

| Control | Current rule |
| --- | --- |
| `retain_nodes=false` | Automatic deletion allowed by default; true blocks automatic reclamation, not explicit deletion |
| `node_retention_mode=automatic` | Default: own S/H; reclaim only if inactive, without live edges and S < 0.006; no semantic importance score |
| Manual `prune_support>0` | Original support threshold and touch-wait condition take priority; fixed isolated wait inactive |
| Manual `prune_support=0` | Positive `dead_node_retention_us`, default 80 simulated seconds, counted from the later of disconnection and last actual touch |
| `dormant_traces_enabled=false` | No residual-contact store by default; disabling forces awakening off, re-enabling does not enable awakening |
| `revival_enabled=false` | API field retained, UI renamed local awakening; default off |
| `node_wake_threshold` / `edge_wake_threshold` | Unset by default; enabling awakening requires two explicitly positive signal-amplitude thresholds |

Touch resets isolation waiting; reconnect cancels it; later disconnection starts a new interval. Restoration never resets elapsed time. Dormancy does not exempt a node from reclamation. Residual contacts continue fading and disappear below `dormant_prune_weight`.

Only residual contacts carry awakening signals. A node evaluates actual arrivals; an edge evaluates actual signals delivered from either end, allowing same-time sums. Two-hop search, ranking, rotation, cross-time charge accumulation and fixed 0.04 weight grants are removed. Waking a node does not restore all edges. Waking an edge preserves its residual weight and normal transmission/learning/pruning. Silence, disconnection and deletion are not undone. Deleted objects cannot reappear through screen proximity or inferred topology. Root-like branching remains deferred under H05.

## 5.5 Interfaces, execution and recovery

API catalogue, CLI definitions/parameters, UI and saved definitions share the configuration contract; inactive controls are shown disabled. `revival_tau_s`, old `revival_threshold`, `revival_weight`, `revival_two_hop_gain` and `revival_candidate_limit` are removed without silent unit conversion. /3 rejects non-null `propagation_limit` and `edge_adaptation_limit`; historical kernels retain their meanings. Node/edge capacity controls still default to unlimited.

Kernel identity, edge-forgetting choice and H-growth formula are fixed at birth. Allowed numerical edits use the existing pause/checkpoint/configuration-intervention flow. Host load is controlled through realtime/scaled/unbounded pacing, waiting or pausing, without changing simulation steps/propagation cadence or dropping internal events.

State schema is `threemind.continuous-memory-state/3.1`; kernel name remains unchanged and operator definitions are updated. Save local anchors, sparse expiry queues, pending arrivals, isolation times and optional dormant state, validating missing/corrupt expiry records. Pre-repair /3 states are rejected rather than silently migrated, cleared or rebuilt; evidence remains in place. Official historical kernels retain their frozen fixtures, serialization and restoration paths. Python and Rust run independently with matching dynamics, without runtime synchronization.

## 5.6 Acceptance and next phase

The approved sequence is complete: documentation/evidence boundary, local retention and ordinary learning, structural/interfaces/state work, then engineering checks and bounded mechanism probes. The [report](../../../lab/explorations/2026-10-08-retention-repair/report.en.md) records backend tolerances, exact restoration, observation/batching/host-speed invariance, recycling/awakening, rejected quotas, historical witnesses and local visit counts, with configurations, separate timing costs and checkpoint hashes. E64/E65/E66 and pre-repair /3 evidence were not overwritten.

Engineering acceptance does not cancel the negative default-gain result. Register parameter versus sustained-background/conflict controls before choosing a new default. Full shape/color teaching belongs to the next stage, from new complete blank individuals following the [training protocol](../training-protocol.md). Each group preserves its own Core, peripheral, optimizer/RNG, body, mappings and readout history. R07/R40/R41, modern bilingual histories and both Classical adaptations receive dated corrections.

## Original revision 4 record (preserved; not the repaired specification)

---

[中文](../../zh/plans/memory-retention-v3.md) · [Research progress](research-backlog.md) · [Dialogue and revisions](../history/sources/2026-10-07-rehearsal-centered.md)

October 8, 2026, revision 4. **The approved unified automatic support mode is implemented. After backend and basic mechanism acceptance, unspecified creation defaults to continuous-memory/3.** Saved individuals/project defaults and explicit historical configurations retain their identities. [Implementation and verification](../../../lab/explorations/2026-10-08-retention-kernel/report.en.md). Earlier proposals remain in history; this current manual is not an account of historical experimental conditions.

## 1. Decisions and version boundaries

Introduce threemind.continuous-memory/3 with independent state and hypothesis identities and equivalent Python reference/Rust native behavior. Preserve executable old versions and frozen witnesses; renaming a snapshot is not an upgrade. After validation, unspecified new creation uses the new version; existing individuals, historical protocols and explicit old configurations do not migrate silently.

Retention scale, activity dose and reversible fatigue are the main changes. Permanent node retention, dormant traces and revival are independent controls. Implemented new-creation defaults:

| Control | Candidate field | Default | Meaning |
| --- | --- | --- | --- |
| Prevent automatic node deletion | retain_nodes | false | Eligible nodes may still be reclaimed; enabling prevents automatic deletion, not explicit interventions |
| Keep dormant connection traces | dormant_traces_enabled | false | Weak edges are normally removed, without a hidden historical-edge store |
| Local revival | revival_enabled | false | Research option requiring dormant traces, not a prerequisite for fixing rapid forgetting |
| Node reclamation mode | node_retention_mode | automatic | Reuse support and its activity-dependent half-life; manual selects threshold/wait controls |
| Consolidation law | consolidation_mode | adaptive-half-life | Use adaptive half-life; retain legacy-stability as a compatibility research option |

Exact historical compatibility means selecting the old kernel_id and configuration. Partially disabling features in the new version is an ablation, not proof of full historical equivalence. Existing edge_consolidation_enabled also gates ordinary positive weight learning; setting it to false does not correctly implement removal of the old stability bonus alone.

### 1.1 Automatic support retention and manual reclamation (revision 4)

After revision 3, the user proposed and explicitly selected unified automatic support retention. Support S is a reserve formed through local use, not semantic importance. Reuse S and store its half-life H_node; accepted direct/associative touches and sustained activation form time-based dose, updating both as in section 2. No separate importance score is introduced.

- Default node_retention_mode=automatic: reclaim only inactive, disconnected nodes with S<0.006. This is a versioned numerical floor, not a third user control. Save S and H_node completely.
- Automatic mode ignores prune_support, node_prune_after_us and dead_node_retention_us; the UI disables them. More effective use generally extends retention after disconnection but does not recognize semantic value in repetitive background input.
- node_retention_mode=manual activates the two experimental policies below. S is state; threshold/wait are mutually exclusive policy parameters, so they are not merged into one quantity.
- retain_nodes=true overrides automatic deletion in either mode. Mode changes settle old elapsed time and clear pending node dose while preserving learned S/H_node.

The retained manual policies follow:

On October 8, 2026 the user replaces the signed encoding with two nonnegative quantities, giving threshold mode priority. The existing node quantity is support, not edge weight. Retain prune_support and label it “node reclamation support threshold”; the independent edge threshold prune_weight remains unchanged.

- Manual prune_support > 0 (default 0.006): preserve threshold mode. Reclaim only inactive, isolated nodes whose support is below the threshold and whose last touch is older than node_prune_after_us. Ignore isolated-node retention time.
- Manual prune_support = 0: use dead_node_retention_us (“isolated-node retention time”), default 80,000,000 microseconds / 80 simulated seconds, strictly positive. Reclaim inactive nodes with no active incoming/outgoing edges after uninterrupted, untouched isolation reaches that duration. Do not require negative support or add the old node_prune_after_us delay.
- retain_nodes=true overrides both automatic deletion modes, without blocking explicit research deletion.
- Start isolation at loss of the last active edge, or birth for never-connected nodes. Reconnection cancels the timer and an actual touch while isolated restarts it. Preserve all timing state across restoration, independently of host time.
- Deletion cleans receptors, dormant traces, charge and rotation indexes. Dormancy does not secretly prevent deletion. Later input on the same channel creates a new identity.
- Old kernels retain their original parameters, equations and execution. This replaces revision 2's signed-second proposal without erasing its historical record.

### 1.2 Dormancy/revival dependency

The configuration invariant is that revival_enabled=true requires dormant_traces_enabled=true.

- Turning dormancy off in the UI also turns revival off and disables its control. API/CLI enforce the same rule and return the effective configuration and dependent changes.
- Re-enabling dormancy does not automatically re-enable revival.
- An explicit paused-state change first preserves a complete checkpoint. Turning dormancy off clears dormant records, indexes, breakthrough charge and pending revival in the working copy, while retaining active edges and historical checkpoints. Re-enabling tracks new dormancy events only.
- Turning only revival off clears its charge/pending work, while retained traces keep decaying normally.
- Restore saved snapshots faithfully; reject inconsistent configurations or missing essential state rather than silently normalizing a restored individual.

## 2. Consolidation through forgetting speed

Each connection stores weight w and its current forgetting half-life H, with no permanently consolidated flag. The candidate engineering target is about 30 simulated seconds for insufficiently repeated weak connections, gradually reaching hours/days with learning, capped initially at 30 simulated days. This is not a conversion to human memory time.

| Parameter | Initial candidate |
| --- | --- |
| Hmin / Hmax | 30 / 2,592,000 seconds |
| Natural half-life decrease | One second of H per eight simulated seconds, floored at Hmin |
| Half-life learning gain | 0.2 per effective-dose second |
| Ordinary weight learning rate | 0.55 per effective-dose second |
| Active-edge pruning threshold | Keep 0.008 |

For x=ln(H_passive/Hmin), xmax=ln(Hmax/Hmin), and effective dose D, settle the passive stage before reinforcement:

    H_passive = max(Hmin, H - 0.125 * dt)
    w_passive = w * exp(-ln(2) * integral(1/H(t), dt))
    x_new = xmax - (xmax - x) * exp(-0.2 * D / xmax)
    H_new = Hmin * exp(x_new)
    w_new = 1 - (1-w_passive) * exp(-0.55 * D)

Each fixed solver interval integrates passive decay exactly, then computes x from H_passive and settles positive dose. This is operator splitting, not an exact solution of simultaneous differential equations. Node S uses the same form. Activity decay is integrated analytically; resources/salience use interval-start values. Positive edge learning obeys edge_adaptation_limit; skipped learning does not accumulate rewards and forgetting continues. Observation/advance batching does not change the solver lattice; step convergence remains separately testable.

D integrates q over simulated time. Local coactivation integrates over time and local available resources; successful associative arrivals use actually accepted amounts normalized to the same dose units. Take the larger overlapping contribution and count a transmission once, rather than rewarding the number of input events. Rejected, subthreshold or undelivered candidates are not successful touches.

Settle half-life decrease separately from activity reinforcement, removing the complete forgetting exemption for an edge traversed during the step. Do not carry the node's permanently accumulated stability gate into the new learning law; use recoverable local states. Preserve physical time and event order independently of observers or advance_to batching.

These implemented values are initial engineering defaults, not established optima. Both backends verify that an initial one-hour H retains about 94.4% of weight after five unreinforced minutes. Repeated two-node exposure retains mean weight 0.99533 at 300 seconds in /3 versus 0.21198 in /2; ordinary and intensity-4 single exposure both disappear by 300 seconds. Strong input helps but does not directly produce long retention in that probe; no permanent protection was added. These are structural measurements, not answer accuracy.

## 3. Two research mechanisms disabled by default

### 3.1 Dormant traces

Only with dormant_traces_enabled=true does a pruned active edge become a nonconducting trace preserving endpoints, residual weight, H and necessary history. Residual weight follows the same decay law and is removed below the candidate floor 1e-8. Earlier node deletion clears associated traces without dangling references.

Dormant storage does not participate in normal propagation or maintain life. Off means no hidden store. max_edges counts the union of live edges and traces; relearning the same contact can replace its trace. Charge is stored separately; the candidate limit bounds work per interval, not total accumulated state globally. Changing pruning thresholds does not automatically revive historical traces; raising the dormant floor clears insufficient traces in the working copy. Large-graph cost and long-term accumulation remain open.

### 3.2 Historical-topology revival

Test only when both controls are enabled. Use historical-topology proximity as the initial candidate definition; unrelated isolated nodes are not found through display coordinates.

- A target has no active incoming/outgoing edge. This does not change the definition of organism death.
- Neighborhoods cover one or two historical hops; a two-hop route contains one active and one dormant contact. Normalize residual contact strength relative to 0.008 and attenuate two-hop effects by 0.5.
- Actual nearby activity accumulates leaky breakthrough charge, initially a two-second recovery constant and 0.2 activation-seconds threshold. Crossing creates a weak edge of weight 0.04. A returning old contact inherits remaining H; a newly formed two-hop edge starts at Hmin.
- Per active source and propagation interval, inspect at most 64 local candidates with deterministic rotation and create at most one edge, respecting existing budgets. Save indexes, rotation and charge.
- Subsequent behavior follows ordinary transmission, learning and forgetting. Do not renew first-contact/novelty bonuses or reset memory age. Background revival must not defeat silencing, disconnection or deletion interventions.

These remain hypotheses. Tests verify actual transmission through a revived weak edge, no creation without historical contact, capacity and restoration boundaries. The bounded 120-second weak-background comparisons produced no revival and all cleared after 300 seconds without input. This does not establish benefit under realistic long-term noise; complete-system and scale tests remain pending and both defaults remain off.

## 4. Strong input, novelty and previously effective mechanisms

Introduce a default-enabled local strong-input fatigue candidate with an initial five-second recovery constant. Actual accepted drive determines extra consumption; larger input causes deeper fatigue and longer recovery. Unreceived input causes neither learning nor fatigue. Record actual costs when whole-system energy accounting is enabled; disabling that optional ledger does not remove local depletion. Strong input affects H through actual activity rather than direct old stability bonuses; regress prior strong-input effects explicitly.

Retain arrival-window local novelty eligibility, describe it as structural novelty and add no semantic first-encounter detector. Modulate current local plasticity without permanent protection. Reviving a contact is not a first encounter.

The audit has not found a wholly omitted major effective mechanism. Retain depletion/recovery, fast traces, local competition, inhibition, ordinary learning and delayed-arrival novelty. One-second facilitation has conditional benefits and stays a research preset. Prior results do not establish universally better defaults for doubled learning, faster recovery or stronger inhibition. Balanced peripheral calibration, process readout, corrective teaching and expanding review belong to the peripheral/protocol, not Core. [E49 audit](../../../lab/explorations/2026-10-05-bus-expression/report.en.md) · [E20 controls](../../../lab/explorations/2026-10-01-priority-memory/report.en.md)

Deliver an evidence/implementation/effective-default/new-version matrix. Restore any supported omission with its conditions. A benefit in one task does not automatically become a general default.

## 5. Channels, multiple connections and branching

A channel is a numbered stimulus entrance from a peripheral into Core. A frame carries channel/amplitude pairs plus delivery time and intensity. Current receptors associate a channel with one receptor node; that node can also receive associative activity through many incoming graph edges. Channel identity, node identity and graph edges are distinct.

An object or sentence generally produces activity across multiple channels rather than a predefined concept node. Repeated inputs normally reuse the receptor; they do not create a node per stimulus. After deletion, the same channel can acquire a new node identity. Default text encoding uses a finite channel bank, but other adapters have different channel domains, so that limit is not universal.

Nodes already support multiple outgoing/incoming edges, such as A→B, A→C and A→D, each with its own weight/history/transmission state. Each current edge has one source and target; it is neither a multi-target hyperedge nor a growing geometric branch.

If branching means influencing multiple nodes, the graph already supports it. Modeling axonal/dendritic extension, shared branch resources, distance-dependent delays, physical contact and retraction needs a separate geometry/morphology version. Existing optional spatial embedding does not implement that growth, and display layout cannot become its coordinates. Record it as a future question only, outside this memory implementation.

## 6. Interfaces, validation and later experiments

Reuse the configuration catalogue, API, CLI, UI and frozen definitions. Share field semantics, effective-state reporting and dependent toggles. Disabled mechanisms allocate no hidden traces or background revival work. Save H, partial dose, isolation clocks, optional dormant/revival states, fatigue, pending events and RNG across backends.

Engineering and basic mechanism acceptance are complete; the list also includes deferred full-system and scale studies. The report distinguishes delivered and pending checks:

- Frozen old behavior, identity and restoration; Python/Rust topology and discrete decisions agree, with existing rel=1e-12/abs=1e-14 float tolerances and strict same-backend restoration.
- Time batching, observer toggles, cross-backend recovery, in-flight signals, reconfiguration and invalid snapshots.
- Weak forgetting, repetition-dependent persistence, accelerated forgetting with disuse, conflicts/reversal, strong-input costs/recovery; splitting input events cannot manufacture extra durable gain.
- All three switch combinations, dormancy-off dependency, no automatic revival re-enable, no hidden default traces; threshold priority and isolation-timer boundaries, touch/reconnection resets, birth/restore and node-linked cleanup.
- Matched node-retention conditions for no dormancy / dormancy only / dormancy plus revival; long random/repeated backgrounds mixed with learning, storage, compute, false links, retention and relearning. Separate fixed-channel from expanding-channel pressure.
- Prior pairing, strong-input, novelty and facilitation witnesses, reporting regressions/zero results rather than accepting increased weights alone.

Switch unspecified new creation only after engineering/basic-mechanism validation; dormancy and revival remain off. Preregister later centered shape/color experiments under the [training protocol](../training-protocol.md): new complete blank individuals, new-kernel main groups and old-kernel references, continuous personal peripheral/optimizer/RNG/body/mapping/recent-history state. Correct errors, reinforce related examples and review prior successes before retesting; isolate calibration from final tests. Report structural retention, actual answers and relearning cost separately.

This phase authorizes implementation and basic-mechanism validation; complete shape/color teaching is deferred to a separately registered next phase. Do not operate running services or deploy, and change no E64/E65/E66 original evidence or gates. Later delivery must continue bilingual documentation, R07/R40/R41 and modern/Classical history updates.

## 7. Revision provenance and scientific boundaries

The first conversational proposal defaulted to retaining nodes, dormant traces and revival. After the user raised background accumulation, the assistant revised its judgment: these are inspired hypotheses, not prerequisites for correcting rapid forgetting; silent memories do not demonstrate topology-triggered reconnection of wholly disconnected nodes. The current user decision disables permanent-retention and revival defaults, makes dormant storage opt-in pending evidence, and couples dormancy-off to revival-off. Preserve that change of recommendation without describing either proposal as an implemented default.

Long-lived neurons do not imply permanently retained connections; silent-memory evidence still involves functional connectivity; synaptic elimination can contribute to forgetting. These sources inspire the model rather than establish its half-life, signed-threshold or two-hop equations: [Spalding 2005](https://pubmed.ncbi.nlm.nih.gov/16009139/), [Roy 2017](https://pubmed.ncbi.nlm.nih.gov/29078397/), [Wang 2020](https://pubmed.ncbi.nlm.nih.gov/32029629/). Branching is closer to axonal/dendritic anatomy, while synapses are contact sites: [Neuronal Dynamics 1.1](https://neuronaldynamics.epfl.ch/online/Ch1.S1.html).

## October 8, 2026: appended text/physical-background and full-/2 validation

This adds results without changing revision-5 parameters or mechanisms. The user authorizes text retention with repetition, then full /2 to check regression. With 57 expanding repetitions per sentence, default /3 loses all text edges at +120s; legacy-stability and full /2 have identical text curves and twelve surviving shared-character edges. Specific cue/color edges disappear in all, baseline cues are unresolved, and 422 replay observations sample text H no higher than 30s. Improved default retention is unproven; preserve the initial single-character-frame formation failure too.

The background is archived real telemetry, not a new live capture; TB is zero, so noise interference is not established. After all input stops /3 clears nodes while /2 retains disconnected ones. No reclamation/default changes follow. Recommend quantifying local post-gate/resource signal versus H growth/regression before choosing parameters and an expressive baseline; no automatic new mechanism implementation is authorized here. Full teaching remains separately registered. [Conditions, curves and evidence](../../../lab/explorations/2026-10-08-retention-telemetry-text/report.en.md)
