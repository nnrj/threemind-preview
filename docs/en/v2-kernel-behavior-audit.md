# Audit of legacy and current kernel dynamics and behavior

This is the historical pre-restoration audit. Its findings remain unchanged; current causal/8 decisions, evidence and remaining work are in the [V3 restoration record](plans/v3-restoration.md).

2026-09-08 · [中文](../zh/v2-kernel-behavior-audit.md)

## Conclusion and scope of this change

**The current kernel is not a behaviorally equivalent acceleration of the legacy kernel. Beyond the accepted time architecture change, learning, consolidation, forgetting, inhibition, structural lesions, lifecycle rules, and the default environment changed materially. The earlier inference that mapping all 55 legacy fields meant restoration was complete was invalid.** Field coverage, passing tests, mechanism preservation, and usability are separate acceptance conditions.

This change fixes only the compulsory duration of an ordinary consciousness: `duration_s` defaults to `null`; leaving the graphical field empty means continuous operation. A positive value explicitly selects a simulation-time endpoint. Pause, continuation, research stepping, checkpoint forks, configuration edits, and the ecology worker can persist and handle a missing endpoint. No large numeric sentinel represents infinity; a wall-clock deadline does not declare consciousness death. Existing explicit durations and saved project defaults are not rewritten retrospectively. A paused consciousness can have its duration cleared. A finite task already marked `completed` still cannot be edited/resumed directly and requires a checkpoint fork; this pre-existing management restriction is recorded, not additionally changed here.

Paired comparisons, stages of generational selection, endpoint assessments, and explicit phase protocols still require finite observation windows to define their comparison or selection endpoints. These do not reinstate a default lifetime for an ordinary consciousness. Standalone development now defaults to continuous operation. Ecology accepts a null duration, but its form still explicitly starts with 30 seconds. The independent `threemind-runtime` CLI still defaults `--until-us` to one second: it is a finite batch entry point, not yet a continuous device-service entry point. These two entry-point defaults remain subjects for review.

**No other kernel difference or UI issue below is repaired in this change.** An explainable choice is not automatically a user-approved choice or a demonstrated improvement. No `data/` scan, migration, model training, or new AGI efficacy experiment was performed.

## Baselines, evidence, and limits

- Legacy baseline: the preserved `core/threemind/runtime.py`, `model.py`, `frames.py`, and `attention.py` at repository commit `95a6db5`, with adapters, the legacy API, and `legacy/ui/src/`. This is the final locally preserved unified implementation, not an exhaustive history of every commit. Its V1/V2/V3 UI choices are model, encoding, and spatial presets over the same `ConsciousnessRuntime`; `kernel_id` does not dispatch to three different dynamics engines.
- Current baseline: the Python reference in `src/threemind_core/`, the Rust implementation in `crates/threemind-core/src/`, and their Runtime/Lab integration. New states use `state/5` and `causal/7`. Causal versions 1–7 belong to the **new event-kernel family**; they are not seven preserved legacy frame-kernel controls.
- Design sources: [consciousness hypothesis](consciousness-hypothesis.md), [inhibition and energy](local-inhibition-energy-and-dynamics.md), [architecture boundaries](architecture-boundaries.md), [temporal transport](temporal-frame-transport.md), [spatial decision](spatial-embedding-decision.md), [terminology](terminology.md), and the user's requirements for continuous consciousness, stimulus-shaped structure, and faithful passive observation. Implementation behavior is checked against documentation; completion statements are not treated as evidence.
- Reproducible evidence: [script](../../scripts/audit-kernel-behaviors.py) and [source hashes, complete defaults, and eight small probes](../benchmarks/2026-09-08-kernel-behavior-audit.json). Run `.venv/Scripts/python.exe -X utf8 scripts/audit-kernel-behaviors.py`. It only creates in-memory models and writes this small evidence file, without database or environment connections.
- Coverage: all **55 legacy RuntimeConfig fields** and **60 current Config fields**, plus formulas, hardcoded constants, Manifest choices, source policies, observation, and host behavior outside those classes. Each identifier below names a behavior item; the complete parameter inventory follows. Eight probes reveal differences; they do **not** establish equivalence over all states, calibrate time scales, or determine research value.

“Retained” means a mechanism exists, not numerical equivalence. “Time change” refers to the accepted simulation-time direction. “Material change” requires its own review. “Missing/regression” denotes a capability or agreement without equivalent coverage. “New tool” does not establish kernel correctness.

Legacy documentation also conflicts with legacy implementation: the [spatial decision](spatial-embedding-decision.md) requires causal space to be off for the main baseline, while the preserved creation UI defaults to V3 with space enabled. The current off default follows that document, yet its difference from actual old UI behavior must still be recorded; it is not automatically a regression. Legacy Manifest accepts weighted_edges, but the preserved Runtime never reads that switch and always executes weighted-edge formulas. The declarative field is not evidence of an implemented unweighted branch. package_schema_version identifies the artifact format, not a kernel selection.

## Time, input, and node state

| ID | Legacy behavior | Current behavior | Assessment, effect, and source |
| --- | --- | --- | --- |
| K01 | `tick_seconds=.1` controls host waiting; every due frame causes a complete `_advance`; an empty epoch also advances once | Fixed `step_us=10000` numerical lattice plus independent event timestamps; Runtime controls realtime/scaled/unbounded pacing | Accepted time change. Simulation seconds no longer increase with the number of frames received in a host epoch; more than renaming tick. Legacy `_advance_input_epoch/_run_loop`; current `advance_to` |
| K02 | Two frames in one epoch each execute full decay, propagation, and learning | Two events at the same timestamp are delivered sequentially without additional elapsed time or co-stimulus merging | Better time consistency, changed results. Saturation, budgets, and learning can still make order matter; simultaneous events are not guaranteed to commute |
| K03 | Direct input can propagate through existing edges immediately in that tick; newly born edges wait for another transition | Excitation and inhibition have positive `delay_us=10000`; emission occurs at lattice boundaries and delivery at event times; edges created before a boundary emission can participate immediately in that emission | Time and phase change. Effective latency also includes waiting for the next lattice boundary. Legacy `_advance/_propagate`; current `_emit` |
| K04 | `step(ticks=n)` performs n epochs; reads show current discrete state | `advance_to(t)` preserves observation horizon, settled horizon, and lattice phase; segmented reads do not create solver steps | Added capability. Exact continuation needs queues and phase, not weights alone. Horizon projections do not mean every quantity has been reintegrated. Current `capture_state/metrics` |
| K05 | Arbitrary Python integer channels and dictionary order; receptors numbered in arrival order | Unique u32 channels, amplitudes in `[0,1]`, finite nonnegative intensity; sorted channel IDs determine allocation; u128 time serialized as decimal strings | Protocol change. Ordering changes node IDs, finite-budget priorities, and causal spatial coordinates. Arbitrary legacy channel adapters cannot be used unchanged. Current `Stimulus/_stimulate` |
| K06 | Affordable response is computed before allocation; zero response creates no receptor | `_stimulate` allocates before `_touch` charges energy; zero reserve can create a zero-activity/support/touch receptor | **Confirmed regression**, reproduced in both backends. This is not a labeling issue. The special case does not apply with default energy simulation disabled |
| K07 | Requested direct touch is computed before activation saturation; support, trace, and energy can count the part blocked by saturation | Remaining activation capacity limits the increment before charging and support/touch updates | Explainable material change: less ineffective charging, but saturated learning and counters change too. Legacy `_apply_direct`; current `_touch` |
| K08 | direct/associative touch reset each tick; trace multiplies by .82; repeated direct touch uses a within-transition maximum | direct/associative decay with activation tau and accumulate actual responses; trace uses `trace_tau=.504` | Material change in quantities used by novelty/readouts; equal numbers are no longer equal measurements. Legacy `_decay_nodes`; current `_relax/_touch` |
| K09 | Node stability increases by `.5*stability_gain*a` for a touched node, normally without its own decay | Increases by `stability_gain*Δa` per response and decays exponentially | Material change: the first identical stimulus can already produce twice the node stability. Current `Node/_touch/_relax` |
| K10 | Per-node `plasticity=max(.12,1-.72*stability)` modulates direct consolidation | This local state and modulation disappear; only global `Config.plasticity` remains | **Removed mechanism with no equivalent replacement**. A global learning switch cannot replace experience-dependent local plasticity |
| K11 | Support decreases linearly by `support_decay*(1-node_stability)` | Support decays exponentially with support_tau, independently of node stability | Material change, not a conversion of units. Legacy `_decay_nodes`; current `_relax` |
| K12 | Activation below .004 becomes zero; threshold zero is allowed | Default is .00001 and must be strictly positive; also participates in inhibition extinction/emission thresholds | Default lowered 400-fold, plus a new nonzero constraint. Weak activity, extinction time, and propagation work change; this is not a display threshold |

## Edge formation, learning, consolidation, and forgetting

| ID | Legacy behavior | Current behavior | Assessment, effect, and source |
| --- | --- | --- | --- |
| K13 | Default local-coactivation creates directed edges among direct touches in one sensory frame, with no invented semantic nodes | Default co-stimulus pairs actually touched nodes in one event; source semantics do not select edges | Principle retained. Both explicitly depend on how adapters define frames; event grouping shapes topology and is not just storage formatting |
| K14 | Optional temporal mode takes source nodes from direct/associated sets in the previous five `_advance` calls, targeting current touches | Sources are still-active, previously touched nodes within .5 simulated seconds; incoming excitation can also trigger association | Material change. Event density, trace continuation, and inclusion boundaries differ. Legacy `_recent/_adapt_edges`; current `_associate` |
| K15 | Birth weight includes `birth_weight*(.5+score)`, .18 times the capped combined consolidation, and novelty; newborns skip the existing-edge update branch | Birth uses `birth_weight*score`, full endpoint impulses, and novelty, then immediately performs another learning/stability update | **Default birth formula replaced**. Identical first co-stimulation already yields different weights; see formulas/probes |
| K16 | Existing-edge learning includes `(1-weight)`, a traversed/non-traversed factor of 1/.45, and `.08*consolidation` | External events use `weight += learning_rate*score`, with final clipping; those factors disappear | **Learning law replaced**. Default .055 becomes .0055, although both include per-event impulses; a tenfold smaller solver step does not explain this alone |
| K17 | Direct consolidation uses unclipped effective drive, affordable fraction, local plasticity, and first/repeat/extra-intensity terms; combined endpoint impulses are capped | Uses clipped drive, drops local plasticity and energy fraction, sums individually capped endpoint impulses | Strong, nearly saturated, energy-limited, and repeated stimulation behave differently. Only a positive actual touch participates in current pairing |
| K18 | Propagation records traversal; associative consolidation using eligibility occurs only if that edge also enters the current adaptation candidate set | Every positive emission can increase edge weight and stability, subject to the optional shared adaptation budget | Added direct associative reinforcement without renewed direct co-stimulation of both endpoints. Counters/strengthening depend on emission count/step and require separate review |
| K19 | Stability growth includes `1+log1p(touch_count)`, direct impulses, and traversed `associative_gain*eligibility` | Logarithmic history gain and eligibility modulation disappear; current score, impulses, or emitted amount replace them | Removed/replaced causal roles. Saving touches and eligibility does not preserve their legacy function; current eligibility is primarily a recorded quantity |
| K20 | Eligibility multiplies by .78 each transition and by .7 before a traversal addition; stability decreases by `stability_decay*(1-eligibility)` | Eligibility decays with trace_tau; stability with stability_tau, independently | **Forgetting protection changes**. 666.667 seconds is not equivalent calibration of the old conditional linear decay |
| K21 | Traversed edges avoid weight forgetting for that tick; others decay with stability protection, which can fully protect stability=1 | All edges undergo integrated `dw/dt=-forgetting_rate*w/(1+4s(t))`, then receive learning; no traversal exemption | Default forgetting law replaced. Even highly stable edges decay; equal prune thresholds do not imply equal memory lifetimes |
| K22 | New-edge novelty bonus defaults to .018, requiring an existing neighborhood and weak nonzero associative re-entry within the tick | Mechanism remains optional but defaults to **0**; reference activity is now continuously decaying associative state | **An existing default mechanism was disabled**. This is not automatically accepted as restoration. Current local_novelty_gain/novelty_touch_reference |
| K23 | `edge_birth_activation_product_min` filters the entire candidate set, including existing-edge adaptation | Filters only absent edges; existing edges can update below it | Explainable correction consistent with the name, but different ablation behavior. No difference from this gate when disabled |
| K24 | Low-weight edges are removed; isolated nodes need no activation, low support, and more than 800 untouched ticks | Low-weight removal remains; isolated nodes need no activation/inhibition and support below .00001; **no age guard** | **Joint deletion rule replaced**. Legacy was not age-only deletion. Old support threshold .006 is 600 times higher. Some nodes last longer; extremely weak ones may disappear sooner |
| K25 | No single global plasticity switch; local plasticity participates normally and experimental interventions are separate | `plasticity=false` freezes ordinary slow-state learning/forgetting/pruning, but external input can still allocate receptors; explicit energy damage can still change structure | Added ablation tool with exceptions. “Plasticity off” does not mean completely frozen topology |

## Propagation, inhibition, energy, space, and lifecycle

| ID | Legacy behavior | Current behavior | Assessment, effect, and source |
| --- | --- | --- | --- |
| K26 | Edge propagation multiplies source/target inhibitory responses, target headroom, and gain .42; each small edge contribution is filtered at .004 | Emission uses source response and `1-exp(-4.2*h)`; fan-in is accumulated, delayed, then target response/headroom apply; aggregate threshold is `activation_floor*h` | Material change retains weaker fan-in, but emission, reception, and multi-source saturation are not equivalent. Legacy `_propagate`; current `_emit/_touch` |
| K27 | Local inhibition enabled by default; either directed edge creates physical adjacency, maximum reciprocal weight gives conductance; finite potential splits without duplication | These principles remain, inhibition=true; still no negative-weight edges, preset semantic regions, or semantic inhibitory rules | **Local inhibition was not lost**, but K28–K30 change its equations/intervention behavior; no claim of full equivalence |
| K28 | Net activation rise relative to the decayed baseline produces self-inhibition, with pending delivery in the next tick | Each actual touch schedules self-inhibition at `t+delay`; event kinds arrive sequentially | Timing and amount change. Legacy uses net rise after spatial/global suppression; current later suppression does not retract already scheduled inhibition |
| K29 | Repeated `cap*tanh(q/cap)`, including another saturation during response; .35 transfer per tick and .002 threshold | Hard `min(cap,q)` state cap, no response-time tanh; transfer `1-exp(-3.5*h)` and flux threshold times h | **Nonlinearity and default gate changed**. New configured threshold defaults to zero but activation_floor still contributes |
| K30 | Legacy inhibitory diffusion through incident adjacency does not consult edge-silencing policy | Current diffusion excludes silenced_edges and silenced sources stop emitting; receiving inhibition is still not complete physical neuron removal | Intervention scope changed; old lesion interpretation cannot simply be transferred |
| K31 | Optional global activation clamp defaults off, target 12; scales activation only | Still off, target 4; runs at causal/numerical boundaries and also scales direct/associative | Optional rule and default target changed. An explicit global clamp is not emergent local competition |
| K32 | Optional causal space; old UI defaults to V3 with 3D enabled; BLAKE2b(sensory_seed,node,axis); neighborhoods operate on existing edges | New Core defaults to no space; enabling uses SHA256(Core seed,node,axis), 3D, radius 2.5 | **Default experimental model changed**. Bare legacy Manifest also defaulted off: distinguish constructor and UI defaults. Hash, seed source, and precision differ. Neither creates edges merely from proximity |
| K33 | Spatial competition mutates weak endpoints while traversing edges with `.12*spatial_competition`; order can matter; vectors rounded to eight decimals | Freeze boundary comparisons, then scale weak endpoints by `exp(-rate*h*count)`; no old vector rounding | Explainable numerical redesign, but a different optional spatial law. Both competition coefficients default to zero |
| K34 | Energy ledger defaults off; supplies act immediately; legacy requested quantities are charged; enabling after disabling can restore initial reserve | Still off; supplies are timestamped; categorized acceptance/refusal/discard ledgers; existing ledger toggles do not issue another initial reserve; supply does not create activation | Energy boundary retained with accounting/time changes. Charges differ under K06/K07/K26; equal resource budgets do not imply equal behavior |
| K35 | Irreversible starvation off by default; maintenance per tick; linear support/stability damage, multiplicative weight damage; 900-tick deadline | Still off; maintenance integrates actual node/edge existence time; exponential support/stability/weight damage; 90,000,000 μs deadline; clears activity/queue and closes sources | Optional damage law changed. Initial state, capacity, supply ordering, deadlines, and recovery are experimental conditions, not a default consciousness lifetime |
| K36 | Starts active; ongoing external drive with inadequate change can become unresponsive and then dead; capacity saturation marks unstable | waiting/active/dead; removes unresponsive death and capacity-unstable state; death requires not-waiting, explicitly closed sources, no activation/in-flight excitation, or explicit energy death | **Lifecycle replaced**. Avoiding unresponsiveness-based death has a rationale, but an open interface with no actual stimulus/activity can remain active forever; a never-activated closed model stays waiting. Both need hypothesis review |
| K37 | Pause freezes; stop/die marks life dead; normal thread has no total duration limit. Disabling all source flags also does not itself cause death | Pause resumable; administrative cancel generally preserves Core life; this change removes ordinary consciousness's default 60-second task endpoint | Duration regression fixed here. Legacy also had a no-input/no-activity-yet-active gap; not every issue originated in this rewrite |
| K38 | Temporary host intervention policy is not stored in the model and can be detached; structural lesion removes nodes, receptor mappings, and incident edges | Silenced sets persist in the model; `lesion=true` removes incident edges but **retains nodes/receptor mappings**; no direct unsilence API, requiring restore/birth or another path | **Structural lesions and reversible interventions are not equivalent**. Node counts, maintenance, renewed stimulation, and experimental effects change; the lesion probe verifies this |
| K39 | Optional capacity/propagation/adaptation budgets default unlimited; reset each `_advance`; some priorities depend on set traversal | Still unlimited by default, zero allowed; shared adaptation ledger per numerical interval, propagation budget per emission step; deterministic ID ordering and rejection counters | Resource mechanism retained with different time scope/boundaries/priorities. Display tiers must not silently set these scientific budgets. Current resources.py |
| K40 | Attention transparent by default, optional competition budget 28; plugins return score/strength/budget multipliers per frame and per channel; budget at least one, plugin errors ignored, plugin state not restored with the package | Still transparent by default and budget 28; timestamped global scalar modulation with TTL replaces per-channel score plugins; aggregate multipliers capped at 8, individual values `[0,2]`, at most 64 active sources; zero budget allowed; modulation/counters recoverable | **Narrower interface, stronger recovery**. Global modulation is not equivalent to legacy per-channel plugins. Opt-in selection does not evaluate semantics; selected input and raw evidence must remain distinct. Both attention.py implementations |
| K41 | With inhibition disabled, the next `_prepare_inhibition` clears all inhibition and pending_inhibition | Disabling stops generation/diffusion/shunting and ignores incoming inhibitory events, but existing inhibition decays instead of immediately clearing | Toggle/resumption semantics change. Re-enabling before decay completes can make residual inhibition effective again; nonzero q does not prove the switch is currently on. Checking the Boolean alone cannot validate this ablation |

## Formulas that cannot be explained by renaming fields

Let `c=a_i*a_j`, `B` be combined consolidation, and `N` novelty. Omitting `[0,1]` clipping:

| Quantity | Legacy | Current |
| --- | --- | --- |
| New edge | `w0=β(.5+c)+.18B+N`; `s0=B+N`; `e0=B`, then same-tick forgetting | `w0=βc+Bi+Bj+N`, immediately followed by `w+=ηc`, `s+=gs*c+Bi+Bj`, `e+=c` |
| Existing co-stimulus edge | `Δw=ηc*k*(1-w)+.08B`, k=1 if traversed, otherwise .45 | `Δw=ηc`; separate associative emission adds `associative_gain*amount` |
| Node-local plasticity | `p=max(.12,1-.72*s)` enters consolidation | No p |
| Edge stability decay | `s←max(0,s-δs*(1-e))` | `s←s*exp(-dt/τs)` |
| Weight forgetting | Untraversed only: `w←w*(1-.0025*(1-(.08+.92*s)))` | Analytic interval integral of `dw/dt=-.025*w/(1+4*s(t))` |
| Inhibition saturation | Repeated `q←cap*tanh(q/cap)` | `q←min(cap,q)` with explicit delayed events |

The time constant `-.1/log(.72)≈.3044` approximately aligns **isolated activation decay**. It does not align learning, edge stability, protection against forgetting, or inhibitory nonlinearity. Dividing legacy propagation gain by .1 to get 4.2 is only a candidate rate, not proof of delayed-network equivalence. The tenfold reduction of direct learning rate particularly needs a rationale: external sensory event counts do not automatically multiply by ten when the solver step shrinks.

A default isolated legacy node also has approximately 80 seconds of untouched-age protection. Current exponential support and the lower threshold can extend this particular retention example to roughly 85 minutes. This is an order-of-magnitude estimate for an isolated node without further touches, not a general memory lifetime or performance benchmark.

## Reproducible behavioral witnesses

All probes use fixed anonymous channels 11/22, without text transduction, a world, AI, or a database. The legacy first frame executes one full transition; the new first event arrives at t=0 without an artificially inserted solver step. These compare **actual entry-point behavior**, not already calibrated identical physical timelines.

| Probe | Legacy result | Current result | What it establishes |
| --- | --- | --- | --- |
| First same-frame .7/.5 input | Activations .63/.45, edge weight about .06439827 | Same direct activations, weight .08802675 | Birth/consolidation already differ despite equal direct responses |
| Three repetitions over .2 simulated seconds, one legacy transition per repetition | Directed weights about .12209977/.10282601 | About .09695469/.09686080 | Repetition continues accumulating differences; the new kernel is not simply always stronger |
| Energy enabled, initial reserve zero, positive input | No node | One zero-response node | K06 allocation-order regression |
| Isolated node silent to about ten seconds, interfaces open | Zero activation, active | Zero activation, active | Active status alone does not establish ongoing consciousness activity in either version |
| Explicit source closure after the previous silence | Active | Dead | Lifecycle predicates replaced; old source flags and new close_inputs differ |
| Close a never-activated new instance | No direct old mapping asserted | Waiting; time can still advance | New waiting exception requires review |
| Two frames in one epoch/timestamp, touching different nodes | First activation decays to .4536 during the second transition | Both .63 | Legacy frame count changed dynamical elapsed time; the new mechanism addresses that problem |
| Lesion one node of a two-node graph | One node, zero edges remain | Two nodes, zero edges, one silenced | K38 physical node removal is not preserved |

Both the Python reference and Rust native backends ran all eight probes; full-precision outputs are stored separately in JSON. They are not exhaustive cross-backend proofs over concurrency, extreme parameters, or long trajectories. None of the exposed kernel formulas was changed in this task.

## Changes outside Core that affect the research object or its use

| ID | Finding | Status and decision needed |
| --- | --- | --- |
| R01 Presets and marking | Old creation defaults to anonymous-spatial-v3, with anonymous-sensory-v2 and labeled-feature-v1 alternatives; V3 also offers anonymous/observation labels/literal characters. Current creation fixes the event kernel and puts three text modes in advanced settings; the old word/word-pair-enhanced legacy-labeled encoding is absent | Three marking modes are not all missing, but the entry point regressed and the old labeled baseline is missing. Python/Rust backend selection is not a substitute for model-version presets |
| R02 Sensory identity | Legacy derives default sensory_seed from consciousness UUID, mixing it with random_seed; RunSpec.seed now defaults to fixed 20260724, while Core/environment seeds are separate | Default new consciousnesses can have identical sensory wiring. This changes individuality controls and spatial identity without assigning semantics |
| R03 Text transduction | Anonymous byte/pair/position/length pulses remain; observation labels add no pulses. Channels move to a reusable u32 bijective domain; literal characters use codepoint wiring instead of 64-bit hashes; old 24-character frames default to one-epoch intervals, now 20ms | Timing, identities, and collisions differ. New normalization/gain/bounds are configurable. Identical raw text does not necessarily mean identical delivered stimuli |
| R04 Validation and backpressure | Old text may be empty, intensity is usually clamped to `[0,2]`, and the queue lacks the current aggregate bounds. New text is nonempty, defaults to at most 100,000 characters, intensity up to 100; queue defaults to 8192 frames/524288 channel entries, rejecting/waiting for whole carriers instead of truncating | Engineering benefits and added restrictions coexist. Long text can still exceed queue capacity; this is not unlimited input. Record rejections and actual deliveries |
| R05 Source policies and envelopes | Legacy already has envelope IDs, frame numbers, and output provenance. Current links live in Runtime/DB; Core receives anonymous frames. Source enablement and attention bypass are separately declared input policies | **Correlation IDs are not read by dynamics and do not predefine private associations.** Changing actual source policy changes input; distinguish it from read-only IDs. Admitted frames retain their admission policy |
| R06 Default environment | Legacy Manifest enables host telemetry by default and disables synthetic ambient input. Ordinary creation now defaults to a MuJoCo planar body with actuator feedback, physical telemetry off unless host is selected | **The default experienced world changed**. Simulated physics is within the accepted design direction, but planar wiring/stimulus distributions are not an equivalent legacy default |
| R07 Body outputs | New planar/world adapters use versioned engineering projections from node identity/activity to actuators; raw output may be broadcast and converted by specialized protocols | Neither predefined good/bad behavior nor demonstrated emergent organ selectivity. A completed interface protocol does not prove trained robot control or emergent brain regions |
| R08 Senses, organs, and networks | Audio, vision, acoustic output, activation images, host/process/runtime telemetry, ambient/body/interoceptive signals, and network adapters have Runtime implementations/configuration. Worlds, ecology, public contracts, stable logical IDs, timestamps, and recovery checks were added | Module existence does not establish parity of every old default/device behavior. Obsolete disk data need not migrate, but useful capabilities must remain. Specialized transports coexist; the common contract is not a universal hardware protocol |
| R09 Raw passive observation | Old OutputFrame contains all nodes, while old interpreted activity still has thresholds/ranking. Current structural readout defaults to saving all sampled nodes separately from candidates; thresholds/recurrence/baselines define derived measurements | No path was found in which envelope association crops Core activations. Complete node samples are not a complete topology history at every microsecond; edges come from selected subgraphs, checkpoints, and change records according to the study |
| R10 Temporal readout | Legacy observes ticks; current reader measures simulation time, baseline, response integrals, tail set/amplitude stability, censored timeouts, overlapping windows, true delivery links, and explicit window budgets | Added instrumentation. Classifications/candidates are neither raw activity itself nor proof of causation. Background-triggered windows off by default do not mean background activity is filtered by Core |
| R11 Chat and plaintext | A conversation backend and separate stimulus/output page still exist, but entries emphasize delivery/classification/counts, without directly projecting readable labels as legacy chat did. The graph-side composer lacks an adjacent live readout stream | **Confirmed usability regression; a backend readout does not compensate.** Anonymous mode cannot invent natural-language output, but available labels/character observations should be conveniently readable |
| R12 Submitted draft | inputs.tsx updates notices/cache after success but never calls `setText("")` | Confirmed interaction defect; recorded here without changing UI, as requested |
| R13 Storage/reuse | Old packages mix nodes, history, labels, logs. Current Core state, runtime profile, Lab continuation context, and evidence are separate; PostgreSQL in Lab, optional SQLite in independent Runtime, computation without DB, on-demand .tmind/JSON exports | Accepted architectural direction. Core-only models do not contain complete physical-world/readout-window state; exact experiment continuation also needs matching Runtime/world context and versions |
| R14 Inheritance/training | Old clone primarily copies current state. Current birth/1 distinguishes birth from continuation: inherit structural slow states, counts, and wiring; clear activity, queues, time, interventions; reset birth energy. Development, generational selection, shared/independent ecology, and independent-birth evaluation added | Agreed tool boundary, not verified genetic evolution. Retained node touch counts affect first-contact consolidation; the precise inherited/reset fields belong in experimental protocols |
| R15 Configuration edits | Old live edits can silently clamp values or ignore unknown parameters. Current validation is strict; Lab requires pause; step/Core seed/initial energy and other identity fields are fixed after creation; study-member protocols are frozen | Validation/audit are valuable, but narrowed live editing and immutable fields are usage constraints, not inherent consciousness laws. Independent forks need understandable entry points |
| R16 Research tools and AI | Current comparisons/ablations/statistics, source-fixed reports, notebooks, narration, warnings, independent assessment, and AI drafts surround Core | Tool development cannot substitute for kernel preservation. AI suggestions/scores must not impersonate evidence or automatically write Core; input-producing AI adapters require separate explicit authorization paths |
| R17 Naming/version/display | The user's established name is consciousness (意识); the UI broadly substituted run (运行). Rendering now uses native Three.js batches, separate processing, and tiers; display coordinates are distinct from causal space | Renaming lacked a supporting user requirement. Rendering optimization was authorized, removal of useful interactions was not. Names, menus, feedback, and graph usability are recorded for the next discussion |
| R18 Trace and metrics | Legacy stores per-tick sparse changes and at most 20,000 trace entries in the package, with many output values rounded to six/eight decimals. Current Lab trace stores recoverable state at advance boundaries, with ordinary metrics sampled separately at sample_us; f64 Core state is separate from window evidence | Trace representation, cadence, and storage cost change. Current metrics add density/saturation fractions; legacy mean_stability, inhibited_nodes, unresponsive/unstable are not identical direct metrics. Do not concatenate old/new curves or expect old sparse-delta presentation over the new format |
| R19 Output subscriptions and observer overhead | Legacy publishes full OutputFrames for external observers. Current metrics, raw node readout, and organs use separate subscriptions; evidence-consumer failures/storage backpressure can pause workers; presentation supports latest-only delivery with skip counts | Given the same delivered input sequence, Core does not read envelope IDs, display selections, or human interpretations. In a real closed loop with explicitly enabled host/process telemetry, observer overhead can change later inputs through measured external quantities. Invariance checks must fix/replay inputs rather than ignore that external path |

These R items cover why the same Core may behave differently under a different host; they do not claim usability acceptance of every peripheral setting. The next UI repair still needs to address the concrete gaps above.

The current application document catalogue excludes docs/en/. The English report is available in the repository or a local Markdown reader, but cannot yet be selected normally in that catalogue; this task does not opportunistically rewrite the document UI.

## Decisions to make after reviewing this audit

1. Decide which old scientific mechanisms to restore: node-local plasticity, learning/consolidation formulas, stability/eligibility coupling, default novelty, node-removal guards, and actual structural node lesions. Give each retention or replacement a reason and acceptance example instead of bundling them into “kernel optimization.”
2. Specify lifecycle separately: physical disconnection versus temporary silence, the waiting exception, and computation stop/task cancellation/consciousness death. Fixing the default duration does not settle these predicates.
3. Decide default research objects and instruments: default causal space, individual identity seeds, frame cadence, labeled baseline, and the role of engineering actuator wiring. Do not select defaults merely because the graph appears livelier.
4. Only after those decisions, repair the kernel with local numerical/behavioral controls and input/output invariance checks, then restore the user's consciousness terminology, creation presets, live graph-side readout, plaintext chat, draft clearing, and shallower navigation.

This audit cannot establish that ThreeMind lacks research value or that its AGI hypothesis is supported. It does establish that “only the technology stack changed and all core behavior was preserved” is not an accurate account of this rewrite.

## Validation of this task

Duration-fix commit: `0d334e7`. **85 distinct backend tests in the affected/related scope passed**: the initial group of 28, a related group of 56, and one added unlimited-ecology case; the final set of four new tests also passed together. **One real-browser configuration test passed.** These are scoped current checks, not a claimed rerun of the historical 559-test full suite.

- Duration checks exercise null/default/finite/invalid values, finite research windows, the actual native worker beyond sixty simulated seconds, pause/resume/cancel, finite-to-unlimited edits, immutable historical checkpoints, unlimited forks, and ecology continuation with a null endpoint.
- Existing configuration, research advance, development, independent assessment, ecology storage/API, research plans, Core, inhibition, and raw-readout tests were also run. They only check the covered paths against this duration change; passing does not establish old/new formula equivalence.
- TypeScript/Vite build, Ruff, and translation checks passed; a real browser checked the default unlimited field, filling/clearing, JSON synchronization, and paused editing. No Docker image was republished. Database schema remains 46; update application server and worker code together before restarting them.

## Complete default-parameter inventory and behavior index

The following table is generated from the script's field inventory. References point to K/R explanations above. `—` means no single replacement field, not that the old capability is valueless. Legacy defaults come from RuntimeConfig; UI spatial presets are distinguished in K32. **Equal defaults still require reading the corresponding formula changes.**

<!-- PARAMETER_AUDIT_TABLE -->

| Legacy field | Legacy default | Current field and default | Behavior IDs |
| --- | --- | --- | --- |
| `tick_seconds` | `0.1` | `step_us=10000`; Runtime.clock / speed (R15) | K01–K04 |
| `activation_decay` | `0.72` | `activation_tau=0.3044` | K01, K12 |
| `propagation_gain` | `0.42` | `propagation_rate=4.2`; `delay_us=10000` | K03, K26 |
| `propagation_activation_min` | `null` | `propagation_activation_min=0.0` | K26 |
| `node_activation_floor` | `0.004` | `activation_floor=1e-05` | K12, K26, K29 |
| `direct_gain` | `0.9` | `direct_gain=0.9` | K07, K17 |
| `learning_rate` | `0.055` | `learning_rate=0.0055` | K16 |
| `edge_decay` | `0.0025` | `forgetting_rate=0.025` | K21 |
| `edge_birth_weight` | `0.065` | `birth_weight=0.065` | K15 |
| `stability_gain` | `0.022` | `stability_gain=0.022` | K09, K19 |
| `stability_decay` | `0.00015` | `stability_tau=666.667` | K20 |
| `consolidation_first_gain` | `0.045` | `first_gain=0.045` | K10, K17 |
| `consolidation_repeat_gain` | `0.018` | `repeat_gain=0.018` | K10, K17 |
| `consolidation_intensity_gain` | `0.075` | `intensity_gain=0.075` | K17 |
| `consolidation_associative_gain` | `0.01` | `associative_gain=0.01` | K18, K19 |
| `consolidation_cap` | `0.42` | `consolidation_cap=0.42` | K15, K17 |
| `prune_threshold` | `0.008` | `prune_weight=0.008` | K24 |
| `node_support_gain` | `0.035` | `support_gain=0.035` | K07, K11 |
| `node_support_decay` | `0.00015` | `support_tau=666.667` | K11 |
| `node_support_prune_threshold` | `0.006` | `prune_support=1e-05` | K24 |
| `node_prune_after` | `800` | — | K24 |
| `association_window` | `5` | `association_window_us=500000` | K14 |
| `edge_birth_policy` | `"local-coactivation"` | `edge_birth_policy="co-stimulus"` | K13, K14 |
| `attention_budget` | `28` | `attention_budget=28` | K40 |
| `attention_competition_enabled` | `false` | `attention_competition_enabled=false` | K40 |
| `edge_adaptation_limit` | `null` | `edge_adaptation_limit=null` | K18, K23, K39 |
| `propagation_limit` | `null` | `propagation_limit=null` | K26, K39 |
| `edge_birth_activation_product_min` | `null` | `edge_birth_activation_product_min=0.0` | K23 |
| `local_novelty_gain` | `0.018` | `local_novelty_gain=0.0` | K22 |
| `novelty_touch_reference` | `0.2` | `novelty_touch_reference=0.2` | K08, K22 |
| `homeostasis_enabled` | `false` | `homeostasis_enabled=false` | K31 |
| `target_total_activation` | `12.0` | `target_total_activation=4.0` | K31 |
| `topology_inhibition_enabled` | `true` | `inhibition=true` | K27–K30, K41 |
| `inhibition_generation_gain` | `0.24` | `inhibition_gain=0.24` | K28 |
| `inhibition_decay` | `0.35` | `inhibition_tau=0.2321` | K29 |
| `inhibition_diffusion` | `0.35` | `inhibition_diffusion_rate=3.5` | K29 |
| `inhibition_response_gain` | `2.0` | `inhibition_response_gain=2.0` | K27, K29 |
| `inhibition_saturation` | `1.0` | `inhibition_saturation=1.0` | K29 |
| `inhibition_propagation_min` | `0.002` | `inhibition_propagation_min=0.0` | K29 |
| `energy_simulation_enabled` | `false` | `energy_simulation_enabled=false` | K06, K34 |
| `energy_initial_reserve` | `1.0` | `energy_initial_reserve=1.0` | K34, R15 |
| `energy_capacity` | `1.0` | `energy_capacity=1.0` | K34 |
| `energy_direct_cost` | `0.035` | `energy_direct_cost=0.035` | K06, K07, K34 |
| `energy_associative_cost` | `0.02` | `energy_associative_cost=0.02` | K26, K34 |
| `energy_inhibition_cost` | `0.01` | `energy_inhibition_cost=0.01` | K29, K34 |
| `irreversible_energy_death_enabled` | `false` | `irreversible_energy_death_enabled=false` | K35 |
| `energy_maintenance_cost_per_node` | `2e-05` | `energy_maintenance_cost_per_node=0.0002` | K35 |
| `energy_maintenance_cost_per_edge` | `4e-06` | `energy_maintenance_cost_per_edge=4e-05` | K35 |
| `energy_starvation_structural_decay` | `0.006` | `energy_starvation_structural_decay=0.06` | K35 |
| `energy_starvation_death_ticks` | `900` | `energy_starvation_death_us=90000000` | K35 |
| `response_epsilon` | `0.0008` | — | K36 |
| `unresponsive_window` | `900` | — | K36 |
| `max_nodes` | `null` | `max_nodes=null` | K06, K39 |
| `max_edges` | `null` | `max_edges=null` | K39 |
| `random_seed` | `20260724` | `seed=20260724`; RunSpec.seed=20260724; environment_seed=null | K32, R02 |

Additional independent fields / fields moved from Manifest into Core:

| Current field | Default | Behavior IDs |
| --- | --- | --- |
| `trace_tau` | `0.504` | K08, K20 |
| `plasticity` | `true` | K10, K25 |
| `spatial_embedding` | `false` | K32 |
| `spatial_dimensions` | `3` | K32 |
| `neighborhood_enabled` | `true` | K32 |
| `spatial_radius` | `2.5` | K32 |
| `spatial_competition_rate` | `0.0` | K33 |
