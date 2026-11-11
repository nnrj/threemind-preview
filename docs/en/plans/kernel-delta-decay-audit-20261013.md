# Audit of /4 versus /2: mechanism differences, authorization, and decay costs

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


[中文](../../zh/plans/kernel-delta-decay-audit-20261013.md)

2026-10-13, following the [performance audit](kernel-performance-audit-20261013.md). The user denied having requested connections among the recipients of an internal transmission packet, and requested an investigation of the implementation's basis, similar changes, all mechanism differences, retention and forgetting without decay, and avoidable computational work.

This audit only read source code, original dialogue, Git, and existing evidence. It did not create or restore research individuals, or modify Core, formal originals, parameters, the native extension, or services. The recommendations below are not implementation authorization.

## 1. Authorization audit: the direction was supported; recipient pairing was not a user requirement

In the original dialogue, the assistant's response before authorization (2026-10-08 15:05:01.719 UTC, 23:05 Beijing time) proposed first implementing the original reception semantics equivalently through local events. It also listed differences between external and internal signals in impulses, context, edge birth, and novelty, and recommended replacing source-dependent branches individually. The following day, the user approved the work as `/4`, then clarified that `/3` must remain creatable and executable.

**This authorized local execution, a direction toward unified reception, and separate versions. It does not establish that the user requested connections among one source's downstream recipients.** The user explicitly denied that requirement again in this round. A common source is not evidence of actual contact between B and C.

Git commit `728cde9a93574acad880f5423405cab6a582104f` (2026-10-09 11:37 +0800) committed the `/4` implementation, plan, contract, and tests together. The current contract [in its packet-contact paragraph](../local-events-v4.md:19) describes a local multi-target packet from one node, with contacts established or strengthened among the nodes it actually reaches. This is an explanation written after the assistant selected the implementation, not an independent statement by the user. Calling these “actual contact notifications” in the plan did not resolve the absence of actual transmission between those recipients.

The actual path is `local.rs::emit → receive → associate`, with a corresponding Python implementation: each source generates a multi-target packet, reception groups targets by packet identity, and the code then iterates over ordered target pairs. Old `/2` already paired objects receiving a common external stimulus. The addition was extending this to every internal transmission packet; pairing itself was not entirely new. `reception_mode=legacy-source` excludes internal packets from this pairing and can serve as a single-factor control. Other differences, including scoring and windows, remain, so it is not a switch that restores complete `/2` behavior.


> **Public-edition edit (2026-11-11; source lines 19-19):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



Source verification: lines 6243 and 6253 of the original conversation file `private conversation record (locator omitted)` contain the proposal before approval and the user's approval respectively. Line 6306 contains another implementation-stage promise to preserve established reception semantics; line 7440 is the delivery. No separate explanation or confirmation of internal downstream pairing was found in the user-facing messages between approval and delivery. `tests_v2/test_local_candidate.py:122–135` deliberately requires external and internal two-recipient packets to produce identical `induced_edges`, showing that this was a design interpretation rather than an accidental indexing error. The old default path paired only objects touched by the current external stimulus; it did not require a global search over recently active nodes. That search belonged to the optional temporal policy. Removing global search therefore did not require adding internal pairing.

**Conclusion: this should be recorded as the assistant's semantic expansion of “unified reception,” not as an explicit user requirement or an equivalent optimization that changed scheduling alone.** Beyond recipient pairing, the table below distinguishes approved directions, implementation details, and semantic differences requiring renewed confirmation. It does not classify every `/4` difference indiscriminately as unauthorized.

## 2. Scope of the complete change inventory

The audit covers the current `/2` and `/4` configuration dataclasses, operators, ordinary execution paths, research switches, restoration, and observation boundaries. `NoveltyConfig` has 85 actual fields and `LocalConfig` has 112: **all 85 shared fields have the same default values, and 27 fields were added**. This does not mean that the roles, conditions, and timing of the 85 shared fields are identical.

The comparison uses `dataclasses.asdict`, not the number of keys in `to_dict()`: old configuration serialization omits some defaults, so comparing serialized key sets directly would falsely identify additional new parameters. This inventory covers the configurations, operators, and execution paths identified in this audit; it does not claim that every machine instruction has been proven equivalent. No new experiment covering every parameter combination was run.

| Category | /2 | /4 | Assessment and default status |
|---|---|---|---|
| Identity and implementation | NoveltyDynamics layered on the old continuous engine | Independent LocalEngine/LocalCore, sharing pure functions | Separate version approved; no upgrade of an existing individual |
| Advancement | Whole-node processing on the 10 ms solver clock and event boundaries | Local message/deadline delivery, without a 10 ms whole-graph solver | Explicitly approved direction |
| Propagation | Global 100 ms traversal cycle | Nodes schedule their own events; still aligned to 100 ms by default, with an asynchronous option | Explicitly approved direction; asynchronous operation changes timing |
| Scan control | Old execution itself contains whole-graph loops | `scan-control` enumerates nodes but still executes `/4` rules | Not a complete `/2` control |
| Activation/trace/inhibition decay | Written back at solver/event times | Projected and written back using elapsed time on object access/expiry | Direction approved; floor cutoffs and ordering require verification |
| Same-time reception | External stimuli handled individually; internal traffic combined into a periodic packet and processed by target | Integrated per receiver at the same time by default; sequential message handling is optional | Control options approved; not automatically numerically equivalent |
| Inhibition diffusion saturation | Contributions from sources are summed by target, then softened before delivery | Each source queues its raw share; the target accumulates pending inhibition and softens it when it emits | Changes the location of nonlinear saturation, not just packet boundaries; no specific decision for this change was found |
| Internal/external source | Direct input and internal association follow different dynamics branches | Unified by default; `legacy-source` retains some source branches | Unified direction approved; not every concrete replacement was thereby reviewed |
| Added internal pairing | Default co-stimulus internal arrivals do not invoke the same pairing | Accepted recipients of each internal packet are paired in both ordered directions | No independent user requirement; a central item to correct |
| Pairing score | Product of the endpoints' current activations | Product of the amounts accepted from this packet | Substantive rule change, not a necessary consequence of localization |
| Reinforcement's internal coefficient | Membership in the preceding propagation's `traversed` set selects 1 or 0.45 | `last_pass_us == current time` selects 1 or 0.45 for that edge | Conditions differ for delayed arrivals; requires confirmation |
| Novelty eligibility | Snapshot of already connected nodes before pairing | Immediate incident adjacency read during pairing | Earlier edge births in the packet can make later births eligible, creating an ordering effect |
| Novelty window | Next aligned propagation time plus delay; initialized with existing associative activity | Birth time plus a full propagation period plus delay; initialized to zero | Changes the window and initial experience, not just an implementation of the old reward formula |
| Novelty reward versus emission order | Settle novelty reward after reception, then emit | Receive and emit, then handle due novelty rewards | Changes whether a new reward at that time can affect the current emission |
| Source counted for novelty | Actual internal re-arrivals accumulated within the window | Actual internal and external re-arrivals counted in unified mode | Documented elaboration of the unified direction, not a concrete criterion specified by the user |
| Stimulus amplitude and strong input | Direct stimulus channel amplitude has the old cap; strength uses stimulus intensity | Unified mode uses the received raw amount, identifying strong input at raw > 1; merging can also cross the threshold | Changed criterion; retaining fatigue did not specify this particular source of threshold information |
| Touch with zero effective amount | Corresponding touch/pairing updates require a positive effective amount | Some inputs reduced to zero by energy handling still increment touches, update timestamps, and change node stability | Conditional semantic issue; conflicts with the intuition of counting only effective experience |
| Impulse under insufficient energy | Ordinary impulse is scaled by the actual energy-supply fraction | `/4` uses raw input before energy acceptance; partial supply may not proportionally reduce the impulse | Conditional semantic difference; current energy-disabled experiments are not evidence of this case |
| Inhibition transmission under insufficient energy | Rechecks the sending threshold after payment | Queues directly after payment, potentially below the threshold | Conditional difference; localization does not require removing the second gate |
| Weight retention | Periodic forgetting protected by stability | Default experience-dependent H, which falls during inactivity; stability is optional | H and the two schemes were explicitly approved earlier; numerical values have not been shown optimal |
| Stability/eligibility | Old discrete periodic updates | Analytic settlement in H mode; per-edge periodic events in legacy stability mode | Stability integration in H mode is a numerical change previously disclosed in the contract |
| Ordinary reinforcement | Common stimuli, actual emission, and novelty rewards | All three remain, with different opportunities, scores, and ordering as above | Learning is neither wholly unchanged nor rewritten entirely from scratch |
| Node support | Original additive support learning and decay protected by stability | Dose-driven S and its own H by default; manual mode retains the old policy | The user explicitly selected the unified automatic support mode |
| Strong-input fatigue/salience | No added retention-fatigue state | Inherits `/3` local fatigue/salience | Retaining this direction was approved; it is not the same quantity as short-term synaptic resources |
| Structural reclamation | Old whole-graph pruning with its original conditions | Local deadlines; reclaim only without activity/active connections; node retention and manual waiting options | Approved; expiry rounding and timing are not a point-by-point equivalent of old whole-graph pruning |
| Dormancy/awakening | No residual dormancy or awakening operator | Residual contacts, contributions from both ends, and node/edge thresholds | Approved research options; both off by default |
| Energy model | Global ledger and old maintenance/starvation process | Local regional pools are the default model, with a global-ledger control | Model direction approved; master switch still off; control is not the complete old ledger dynamics |
| Regional allocation | No regions | 16 fixed regions, uptake proportional to capacity deficits, independent reproducible randomness | Local fields and proportional uptake were approved recommendations; 16 regions and the particular random algorithms are implementation details, not user-specified choices |
| Energy capacity semantics | Capacity of one system-wide pool | Capacity per regional pool plus capacity per node | Total capacity differs; equal capacity values do not establish a balanced comparison |
| Input ranking/modulation | Optional global attention competition, budget, and modulation entry point | Global competition and modulation rejected; an explicit peripheral is required | Removing global arbitration was approved; available interfaces changed |
| Global homeostasis/spatial competition | Optional | Enabling them with nonzero settings is rejected | These `/2` options are no longer retained in `/4` |
| Time-window edge birth | Optional temporal-association | Only co-stimulus supported; alternatives rejected | Removes global search; the same policy name does not establish identical edge-birth behavior |
| Propagation/learning quotas | Configurable global quotas | Non-null values rejected | Explicit user request; node/edge capacities remain, unlimited by default |
| STP/fast trace/local context | Already present and enabled by default | Formulas and defaults retained, but call timing and reception grouping change | Not inventions of `/4`; disabling their cost is not an equivalent speed optimization |
| Space and channels | Stable channel mapping; spatial transmission attenuation requires both embedding and neighborhood enabled | Transmission attenuation checks embedding alone, while edge birth still checks both; energy regions use a separate seed/node ID rule | Gating difference in a nondefault spatial combination, possibly an omitted gate; not an equivalent refactor |
| Saving/observation/restoration | Original schema, runtime statistics, and complete state | Independent schema and extensions for object clocks, deadlines, messages, and local reserves | Necessary engineering differences; observation can still traverse the graph without becoming dynamics arbitration |
| Observation counting | pending_events primarily counts queued messages; sequence includes the old observation cadence | pending_events counts messages and deadlines; there are no 10 ms solver events; some old resource/attention views are null | Cross-version count differences cannot directly be treated as transmission counts or performance |
| Inheritance and continuity | Explicit inheritance creates a new individual; restoration resumes the original | Inheritance projects structure/H and resets dynamic state; restoration saves the complete state | Inheritance is not continuous restoration; a new state cannot be disguised under an old identity |
| Birth-fixed settings/parameter changes | Original constraints | Model/formula/region/period fixed; permitted numeric changes use paused, audited boundaries | Preserves version/whole-individual boundaries; no live kernel switching |

Main source entry points: [Python /4](../../../src/threemind_kernels/local.py), [Rust /4](../../../crates/threemind-core/src/local.rs), [old reception/propagation](../../../crates/threemind-core/src/continuous.rs), [old learning/touch](../../../crates/threemind-core/src/restoration.rs), [old pairing](../../../crates/threemind-core/src/lib.rs), [/2 novelty](../../../src/threemind_kernels/novelty.py), and [retention configuration/formulas](../../../src/threemind_kernels/retention.py).

Key locations: pairing gate at Rust local.rs:1023 and nested loops at 850–865; old/new scoring at lib.rs:1389 and local.rs:865; old/new reinforcement coefficient at restoration.rs:218–224 and local.rs:942–946; novelty eligibility at lib.rs:1360–1367 and local.rs:905–907, initial values at novelty.rs:162–163 and local.rs:902–903, and deadlines at restoration.rs:264 and local.rs:912–914. Old aggregated inhibition saturation is at continuous.rs:516–521; new emission at local.rs:1176–1195. Python's same-time novelty settlement/emission ordering is at engine.py:384–391 and local.py:900–911. Zero effective amounts and impulses are at local.py:406–454; spatial attenuation is around continuous.py:235 and at local.py:617–624. After later source changes, locate the functions again rather than treating these line numbers as permanent identities.

## 3. What would be removed: three distinct questions

### 3.1 Removing adaptive H does not mean removing forgetting

Half-life is simply one representation of decay speed. The actual added mechanism is **maintaining a learnable H for each object that can also fall**, and integrating decay and predicting expiry from it. Removing only this adaptive layer would still allow ordinary weight reinforcement followed by a fixed decay rate or another explicit local forgetting rule. Old `/2` demonstrates reinforcement and forgetting without H, although it has a separate stability protection mechanism.

Currently, `legacy-stability` replaces only connection forgetting: automatic node support still uses H. `memory_half_life_decay_rate=0` only stops H from decreasing; weight still decays at that fixed H. `forgetting_rate=0` affects only the old stability-based connection path and does not disable default H forgetting. `plasticity=false` also disables learning. There is no clean existing switch to retain all learning while disabling all structural decay.

### 3.2 Without any structural weakening, ordinary reinforcement does not automatically produce forgetting

With energy and optional spatial competition off by default, and without explicit intervention, ordinary common-stimulus reinforcement, actual-emission reinforcement, and novelty rewards are all nonnegative increments. If weight decay is also removed, connections already above the pruning threshold can only gain weight until they reach the cap. Activation, inhibition, fast traces, and synaptic resources may fluctuate, but that does not establish that the long-term connection structure has forgotten.

Even if node support falls, an active connection prevents automatic node deletion. Capacity is unlimited by default; finite capacity settings mainly reject new births rather than naturally replacing old memories. Energy-starvation damage and explicit deletion can weaken or remove structure, but the former is another mechanism that is off by default, and the latter is an intervention. Neither is ordinary forgetting through disuse.

Therefore, **reinforcement can preserve memory, but reinforcement alone is insufficient for eventual forgetting after long disuse**. Changes in expresser learning, inhibited readout, or temporary resource depletion may prevent an answer and must be distinguished from Core structural forgetting. Disabling all decay of activation, inhibition, and resources would additionally alter oscillation, responsiveness, and refractory behavior; these different forms of decay cannot be removed as one undifferentiated feature.

### 3.3 Natural decay can have low computational cost, but software values do not disappear spontaneously

A biological analogy does not directly determine host CPU costs. In a digital simulation, a floating-point value in memory does not shrink automatically as external time passes. The implementation can save a value and its time anchor, calculate the current value only when actually accessed, and avoid incremental refreshes during inactivity. If exact deletion timing is required, it can schedule a local expiry. This needs neither a whole-graph observer nor idle polling.

`/4` already follows that direction. Its problems are repeated calculations on the same object in hot paths and the added complexity of updating and predicting expiry with variable H. A minimal candidate is ordinary reinforcement plus fixed local decay and on-demand settlement, rather than removing every form of decay. Under fixed exponential decay, the time for w to fall to threshold θ is `ln(w/θ)/λ`; strengthening w naturally increases its reachable lifetime. With a cap on w, however, the extension is limited. Very broad retention levels would still require accumulated protection, a variable rate, or structural redundancy. Removing all historical state while retaining arbitrarily broad retention levels is not a simultaneous option.

Keeping only an expiry date with no reduction in weight before expiry, or adopting linear decay, might simplify computation. But transmission strength before the threshold would differ. These are candidate dynamics changes, not transparent implementation optimizations. No candidate was selected or enabled in this round.

## 4. Inventory of avoidable overhead

“Avoidable” distinguishes implementation waste that can be removed while preserving behavior, work reducible only after changing rules, and necessary costs that cannot honestly be called waste. The table does not promise speedups that have not been measured.

| ID | Cost | Recommendation | Boundary |
|---|---|---|---|
| W01 | Removing and reinserting both indexes when the old and new deadlines are identical | Return immediately for an unchanged deadline | Preserve event order and audit semantics |
| W02 | Scheduling an H change, then overwriting that schedule after ordinary reinforcement in the same operation | Schedule once at the end | Verify no intervening deadline could execute |
| W03 | Repeated same-time settlement and calculations when dt=0 | Reuse the current-time result | Do not skip floor cutoffs or merging of pending quantities |
| W04 | Repeated node/edge cloning and writeback | Controlled in-place mutation/borrowing | Preserve Rust borrowing safety and restoration state |
| W05 | Constructing, cloning, and parsing JSON for internal messages | Typed internal events; serialize only at external boundaries | Preserve message ordering and save compatibility |
| W06 | Parsing and formatting string timestamps in memory | Integer time internally; convert to strings at boundaries | Preserve cross-backend safe-integer and large-time requirements |
| W07 | Repeated logs of parameter constants and exponentials with identical dt/tau | Precompute constants and cache pure coefficients | Do not unknowingly change floating-point or rounding order |
| W08 | Rebuilding the same source features for every outgoing edge | Generate once and reuse | Preserve the original feature sampling instant |
| W09 | Scanning incident edges and settling weights before determining whether inhibition diffusion is needed | Move decidable gates earlier | Preserve actual expenditure, transmission, and settlement semantics |
| W10 | Scanning every incident edge on touch to find active novelty windows | Index only edges with pending novelty settlement | `/2` already offers an indexing precedent; do not change reward windows |
| W11 | Clearing isolation/deletion deadlines at both endpoints after every reinforcement | Maintain these only when connection status changes | Still handle reclamation-time changes caused by learning |
| W12 | Repeated lookups across graph tables, retention side tables, and adjacency | Retain locations within an operation and consolidate local storage | Lookup maps are tools, not dynamics arbitration, and may remain |
| W13 | Repeated copying/sorting of ordered collections into temporary lists | Stable ordered iteration or compact adjacency | Do not change floating-point accumulation order by casually switching to hash iteration |
| W14 | Recomputing spatial coordinates/distances per edge | Cache birth-fixed positions and invalidate cached distances when necessary | Relevant gains occur only when spatial features are enabled |
| W15 | Checking traversed before discovering that legacy forgetting does not apply in the default H path | Check the mode first | The preceding isolated candidate demonstrated limited final-state equivalence |
| W16 | Exponential recovery for zero fatigue/salience; intermediate construction for disabled mechanisms | Fast paths for proven zero/disabled states | Do not skip nonzero residual state |
| W17 | Native API receipt and boundary-encoding costs that remain to be measured | Reduce explicitly unused receipts and boundary copies | A potential opportunity, not evidence that every advance returns complete graph statistics; do not omit data needed for persistence or readout |
| W18 | Repeated whole-graph projection, copying, and encoding of the same state for observation/saving | Reuse read-only results at the same version; incremental/chunked tools | Observation caches must not write back to dynamics or change research sampling |
| W19 | Optional diagnostic and counting overhead | Optional diagnostics with explicit counting definitions | The formal implementation has per-event counters, but no added heavy whole-graph probe was found; the preceding profiling probe ran only in an isolated copy. Counters have not been established as a principal cause; do not remove evidence arbitrarily |
| W20 | `/3.1` combines the old whole-graph framework with local retention | Remove duplicate work first, then separately verify equivalent event execution | Do not replace the old model with unverified `/4` semantics |
| W21 | Collecting energy_regions while the energy master switch is off | Check the switch before maintaining an unused collection | Preserve behavior when energy is enabled |
| W22 | Parsing/updating energy_us in maintenance while energy is off | Remove unnecessary hot-path work while retaining the boundary time-anchor contract | Do not silently change state hashes or restoration formats |
| W23 | Fast-trace efficacy and transmit separately project the same old state | Project once and reuse | Preserve pre-transmission weight versus post-transmission learning order |
| W24 | Revalidating unchanged STP configuration on every edge emission | Strict validation at configuration/restoration boundaries; validated types internally | Do not weaken external-input or corrupt-state validation |
| W25 | Building score/exponential/normalization arrays for single-message context | A single-message coefficient-of-1 fast path | Preserve range validation and the calculation result |
| W26 | Frequent audit/transport tree lookups using string keys | Internal structs/fixed fields, retaining original keys externally | Preserve recorded values and observable counting semantics |
| M01 | k² pairing of internal packet recipients | Redefine actual contact and learning opportunities according to the user's principles | Changes dynamics; not just a data-structure optimization |
| M02 | 100 ms stability events for every edge | Exact lazy settlement/combination if provable; otherwise simplify rules in a separate version | Do not replace eligibility-first decay, discrete stability updates, and clamps with an integral silently |
| M03 | H growth, fallback, integration, and inverse threshold calculation | Evaluate fixed local forgetting, or retain H while removing repetition | Removing H changes retention and requires a new decision and comparison |
| M04 | Maintaining edge eligibility/stability in H mode when they do not participate in that Core weight decision | Evaluate delayed exact projection or retirement of the auxiliary path | Stability enters Runtime readout fingerprints, observation, and inheritance; absence of Core use does not establish no effect on the complete artificial consciousness |
| M05 | Forced edge limits, dropped messages, reduced sampling, or new global quotas | Do not adopt as performance shortcuts | Changes experience/learning; not approved by the user |

Actual signal delivery, necessary gates, ordinary learning, actual contact, and precise expiry checks cannot all be removed. A dense local graph inherently has many real outgoing edges to visit. The optimization target is repeated work per actual interaction and unconfirmed additional interactions, not a guarantee that every local implementation outperforms sequential scanning.

The preceding isolated candidate covered only a small subset such as W01/W15. Short tests improved `/4` stability-mode time by roughly 12%–18%, without a stable improvement for H. Other costs and potential gains are source-level findings and recommendations, not measured speedup claims.

## 5. Added configuration fields and applicability restrictions

There are 18 added retention/reclamation fields and 9 local-execution/energy fields. Defaults of all 85 shared fields are unchanged:

| New field | /4 default |
|---|---|
| consolidation_mode | adaptive-half-life |
| memory_growth_formula | log-saturating |
| node_retention_mode | automatic |
| retain_nodes | false |
| dead_node_retention_us | 80000000 |
| dormant_traces_enabled / revival_enabled | false / false |
| node_wake_threshold / edge_wake_threshold | unset / unset |
| memory_half_life_min_s / memory_half_life_max_s | 30 / 2592000 |
| memory_half_life_decay_rate | 0.125 |
| memory_learning_gain / memory_weight_learning_rate | 0.2 / 0.55 |
| strong_fatigue_enabled / strong_fatigue_tau_s / strong_fatigue_gain | true / 5 / 1 |
| dormant_prune_weight | 1e-8 |
| propagation_mode / propagation_phase | local-events / aligned |
| arrival_mode / reception_mode | coincident / unified |
| energy_model / energy_distribution | local-field / counter-random |
| energy_seed / energy_region_count / energy_node_capacity | 20261009 / 16 / 1 |

Shared fields with restricted or changed applicability in `/4`: `step_us`, `association_window_us`, `attention_budget`, and `target_total_activation` retain only default metadata values, with nondefault values rejected. Homeostasis, positive spatial competition, global attention ranking, non-co-stimulus edge birth, and non-null propagation/learning quotas are rejected. `energy_capacity` changes from a system-wide pool capacity to a regional-pool capacity. `forgetting_rate` does not control decay in the H weight path. `edge_consolidation_enabled` gates both ordinary connection reinforcement and connection H growth; it cannot serve as an independent switch that disables only H.

`stability_decay_enabled=false` also does not disable all forgetting: in the old mode, weights still weaken if stability has not reached 1. `edge_consolidation_enabled=false` does not stop forgetting, edge birth, eligibility, or node-support learning. H/D themselves have explicit support in the later `/3` repair plan fully approved by the user. The earlier discussion of connections not retaining independently by default does not override that later decision for object-owned H. This reassessment does not rewrite the approval record. The current `/4.1` designation is a saved-state format, not an already introduced `/4.1` kernel.

## 6. Recommendations and matters not authorized

First preserve the original `/2`, `/3.1`, and `/4` identities and evidence, and withdraw the interpretation that unified reception necessarily requires connections among downstream recipients of a common source. Prioritize provable implementation optimizations. Separately propose simple local learning rules: a node responds to the actual amount it accepts, and an edge is reinforced by actual transmission through itself. How first contact occurs when no edge exists must be specified explicitly, rather than introducing connections implicitly through internal packet membership.

For forgetting, separate three questions: whether H is learnable, whether passive structural decay exists, and whether computation is performed on demand. Ordinary reinforcement with simple local decay can be discussed as a new baseline. This round does not authorize removing H, removing all decay, changing strong-input/novelty criteria, releasing `/4.1`, or restarting experiments. Every mechanism change requires an explicit new identity and Python/Rust consistency; acceptance must cover Core state, complete-individual readout, and time continuity together.
