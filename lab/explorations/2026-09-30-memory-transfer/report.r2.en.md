# Memory, sequence, transfer and environmental adaptation: 1536 instances

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-09-30. Project `c49b4ad2-3d53-486a-b124-433e5491df36`; baseline `36c1ea7`; kernel `continuous-memory/2`. No Core, Runtime, sensory mapping or default parameter was changed. This study adds experiment tools, controls, passive inspection and analysis.

[中文](report.zh.md) · [Prospective design](design.en.md) · [Commands](README.md) · [Delivery verification](delivery.en.md)

## Main findings

**A learned association remained elicitable after 300 simulation seconds with forgetting still enabled and without rehearsing its cues. Silencing the cue's outgoing connections eliminated the response; restoring those connections restored it.** This is evidence of retained, usable associations, beyond merely finding a saved connection structure.

**Adding inertial sensors produced a reproducible reversed preference.** Joint-only conditions expressed the trained correspondence. Three conditions containing inertial measurements expressed the opposite preference across the original domain, a new angle and a new gravity. The original answer key remains unchanged; the reversed pattern is reported as a finding in its own right.

| Question | Result |
|---|---|
| Retained associations | 192/192 trained cue tests expressed a selective transient response at 1, 60 or 300 seconds; untrained controls: 0/48. |
| Dependence on retained connections | 32/32 targeted silencing cases lost elicitation; restoration and matched other-edge controls preserved the original sampled activation trajectories. |
| Transfer across physical parameters | Joint-only conditions retained the correspondence in 48/48 tests across original, new-angle and new-gravity domains. |
| Uniform benefit from inertial sensing | Not found. The three inertial conditions instead produced opposite integral preferences in 144/144 tests. |
| Learned AB versus BA output selection | Not found. After 0.5 seconds there was no result-channel response; after 5 seconds fixed-correspondence training favoured the same output for both orders. |
| Improving the external centring objective | No consistent improvement or average consolidation benefit in this setup. Individual conditions improved or worsened. |

**The registered primary outcome must remain explicit: all 736 scored memory, sequence and transfer tests reached a convergence decision, but neither task target was elicited at that decision. Primary success was therefore 0/736.** The retained-memory and transfer findings above use the separately preserved sampled trajectories and causal interventions. These transient responses disappear before convergence; they are not the same outcome as a successful final ranking.

## Methods and boundaries

Ordinary defaults were compared with a 1-second facilitation preset. Novelty, forgetting, inhibition and local energy depletion/recovery remained enabled as configured. Core propagation timing and thresholds were unchanged. The closed-loop consolidation control changed only `edge_consolidation_enabled`, retaining node dynamics, edge birth and forgetting; it was not an all-learning-off condition.

Existing MuJoCo pendulum/cart worlds used a 5 ms physical step and 20 ms sensory samples. Routine all-node trajectories were sampled every 100 ms. Eight follow-up replays inspected the existing observation callbacks, at intervals up to 20 ms, without adding advancement boundaries.

Anonymous markers were jointly presented with physical body measurements. Each pose initially appeared 12 times consecutively, followed by interleaved repetitions: 32 episodes, each containing 0.4 seconds of physical measurements and a 0.2-second tail. This was not a repetition of the Chinese-language pairing or family-relation experiments. Semantic marker names never entered Core.

Sixteen calibration cases, using seed 930199, selected physical intensity **0.3** solely from measurability and saturation, not answer correctness. Main coding seeds were 930101–930104. Separate anonymous cue intensity was **0.45**. A distinct **0.2** maintenance input every 0.5 seconds kept the instances active during waiting and testing; it was never grouped with task inputs. This repeatable synthetic control replaced live host telemetry for this comparison, preventing death-frozen snapshots from masquerading as retention.

Sensory conditions were full joints-plus-IMU, joint-only, full sensors attenuated to the joint-only physical dose, and shuffled inertial samples. Closed-loop tests used a causal 200 ms IMU delay rather than shuffling. An additional ordinary-preset condition removed **all proprioceptive measurements**, including joints. Joint-only must not be described as absence of proprioception.

Saved states contained at most 13 nodes and 66 directed edges. The 1536 instances include training parents, waiting forks, controls and calibration, not 1536 independent samples. Coding seeds and two initial teaching orders are not four independent ecological worlds. Counts and effect sizes are descriptive; repeated time samples were not treated as independent observations to manufacture significance.

## Retention and facilitation

Cue and no-cue forks shared the same parent and observation schedule. A secondary directional response required an expected-target increase above 1e-5 and an expected-minus-other activation-integral difference above 1e-6. This secondary scoring detail was registered after inspecting the first seed and is not represented as the original primary endpoint.

All trained sensory configurations and both presets passed both cue directions at all three delays; all untrained controls failed. At 300 seconds the task nodes had zero activation while the isolated maintenance channel kept the instance alive. Subsequent elicitation was therefore not a task response that had simply continued throughout the waiting period.

Mean expected-target activation integral, relative to matched no-cue forks:

| Configuration | After 1 s | After 60 s | After 300 s |
|---|---:|---:|---:|
| Ordinary, full | 0.0095415 | 0.0199928 | 0.0033106 |
| Ordinary, joints only | 0.0113920 | 0.0214713 | 0.0033007 |
| Facilitation, full | 0.0095330 | 0.0214263 | 0.0041213 |
| Facilitation, joints only | 0.0120697 | 0.0230925 | 0.0041060 |

The full-sensor facilitation preset increased 300-second elicitation by approximately **24.5%**, with no equivalent benefit at 1 second. This is a real parameter-specific benefit, not a reason to claim universal superiority or change defaults. Recovery of fast states and slower forgetting may jointly explain the non-monotonic retention curve; their individual contributions were not isolated here. Simulation seconds cannot be translated directly into human years.

The 96 targeted follow-ups covered both presets, full/joint-only sensing, four seeds and two cues:

| Intervention | Cases | Result relative to original cue |
|---|---:|---|
| Silence cue-outgoing edges | 32 | Expected-target cue-increment integral became zero in every case. |
| Silence, then restore before advancing | 32 | Zero all-node activation difference at every recorded time. |
| Silence equal-count, approximately weight/stability-matched other edges | 32 | Zero all-node activation difference at every recorded time. |

These interventions establish a causal role for the retained outgoing connections in this elicitation. They do not by themselves establish subjective experience.

## Transfer and the reversed response

Forks received physical measurements without the training markers. The original angles were ±0.7, unseen angles ±0.45, and gravity changed from −9.81 to −6. Body, mounting, scales and channel identities remained fixed.

| Sensory condition | Original correspondence: original | New angle | New gravity | Reversed preference |
|---|---:|---:|---:|---:|
| Joints only | 16/16 | 16/16 | 16/16 | 0/48 |
| Full | 0/16 | 0/16 | 0/16 | 48/48 |
| Full, matched dose | 0/16 | 0/16 | 0/16 | 48/48 |
| Shuffled IMU | 0/16 | 0/16 | 0/16 | 48/48 |
| Untrained | 0/16 | 0/16 | 0/16 | No target response |

Counts combine two presets; each contributes eight tests per cell. Direction uses activation integral over the original score window, not the final convergence rank. Existing no-cue trajectories provide a matched absolute-time overlap of **4.4 seconds** with the same conclusion; the missing last 0.6 seconds was not filled with zeros.

Joint-only sensing supported limited transfer across physical parameters. Inertial conditions also retained a consistent discriminable pattern, but with the opposite orientation. The answer key was not inverted after observing the results. Dose matching and shuffled inertial timing retained the reversal, so greater total dose or precise inertial sample timing alone does not explain it.

Eight passive replays captured the input phase. Their full final Core hashes matched the original trials in **8/8** cases. Of the four full-sensor examples, two had reversed input-phase means and two retained the original input-phase means; all four had reversed post-input means. These are phase averages, not a claim that the first instantaneous crossover occurred exactly when input stopped: the illustrated trace already crosses during input. The expected target had stronger inhibition. All four joint-only examples kept the trained direction across the three phases.

Shared sensory pathways, inhibition and recent history are concrete candidates for further isolation. The current observations do not identify a unique cause. This repeatable pattern should be investigated, rather than disappearing into a binary failure count. Transfer here does not cover new body layouts, complete channel remapping, unseen word meanings or general reasoning.

## Sequence selection

AB and BA had equal input amounts and the same anonymous context C in each physical frame. Teaching endings were C+X and C+Y; tests omitted X/Y and supplied only C. Shuffled outcome controls balanced X/Y counts.

| Training correspondence | Delay | Secondary direction correct | What occurred |
|---|---:|---:|---|
| Fixed | 0.5 s | 0/64 | Neither outcome channel had measurable activation. |
| Fixed | 5 s | 32/64 | Each parent favoured the same outcome for AB and BA. |
| Shuffled | 0.5 s | 0/64 | Neither outcome channel had measurable activation. |
| Shuffled | 5 s | 0/64 | Neither outcome channel had measurable activation. |

No tested seed/configuration selected both directions correctly. An illustrative 5-second response peaked around 0.00423, close to the propagation threshold, and does not establish robust order computation. This task did not convert order differences into the requested output selection; it does not show that all order-dependent internal state is absent.

## Closed-loop environmental behaviour

The external objective was staying near the cart's track centre, assessed by mean squared position error. It was **an observer score, not a reward, survival constraint or population-selection pressure**. The test asks whether repeated experience spontaneously improves that objective, not whether ecological selection can train an adapted population. Inactivity, repetition and directional preferences were not inherently labelled abnormal.

Each instance experienced three 10-second episodes. Only the physical body reset between episodes; Core continued. Results average four seeds and both force directions:

| Preset / sensors | Episode 1, consolidation on | Episode 3, on | Episode 3, off |
|---|---:|---:|---:|
| Ordinary / full | 0.967373 | 1.026585 | 1.009630 |
| Ordinary / joints | 0.871873 | 0.905887 | 0.880953 |
| Ordinary / delayed IMU | 0.938373 | 0.998403 | 0.970144 |
| Ordinary / no proprioception | 0.900855 | 0.901240 | 0.901240 |
| Facilitation / full | 0.968420 | 1.026058 | 1.006947 |
| Facilitation / joints | 0.873030 | 0.908573 | 0.880953 |
| Facilitation / delayed IMU | 0.940460 | 1.004567 | 0.970302 |

Passive physics without model output scored 0.893579. Across 56 paired conditions, consolidation improved third-episode error in 18, worsened it in 30 and left it unchanged in eight. The unchanged cases were the all-body-feedback-removed condition. There was no average goal benefit. Consolidation-off still retained other plastic and dynamical mechanisms.

Ordinary-preset reversed-force evaluations scored 0.991397 with full sensors, 0.874531 with joints, 1.003534 with delayed IMU and 0.901240 without proprioception. Lower error in some reversals does not independently demonstrate learned compensation: changing force and pre-existing motor bias also changes error. Evaluation retained each condition's consolidation setting, so stored effects and ongoing learning were not completely separated.

For illustration, seed 930101 with ordinary full sensing scored about 0.0457 under positive force but 1.9728 under negative force in episode three. Showing only the favourable direction would give a misleading impression. Sensory coupling has a substantial behavioural effect; alignment with a chosen environmental objective requires both directions and proper controls.

## Priorities

1. Isolate the reversed response with registered interventions on shared sensory paths, target inhibition and local energy recovery. Observe both during-input and post-input phases; retain both response orientations.
2. Display transient process response alongside the final convergence result. Preserve this study's original metric for reproduction, and distinguish a response that occurred from the pattern remaining at the end.
3. Diagnose sequence-outcome pathways, inhibition and energy availability before increasing scale. Separate missing association from failed expression, then test registered intervals and new examples in independent data.
4. Use the existing external selection/lineage tools for actual objective adaptation, then evaluate forces, masses and sensor delays excluded from selection. Keep goals outside Core.
5. Do not globally increase facilitation or reduce forgetting from these results. Facilitation improved this retention measure but not general motor performance; retention existed with forgetting enabled. Strong-stimulus and novelty contributions were not independently ablated.

## Evidence and resources

Coverage: 16 calibration, 520 memory, 320 sequence, 240 transfer, 336 closed-loop, 96 edge interventions and eight passive replay instances. Previous projects were not overwritten. New simulation is stopped.

All 1536 database checkpoints matched their local full states. Thirty-two restoration trajectories matched all sampled node activations; eight dense replays matched full Core hashes. Seven tool tests and Ruff passed. Source inspection confirmed no changes to Core, Runtime or application implementations.

Eight verified process-start source bundles provide authoritative runner provenance. In 22 early cases, the single-file shorthand hash was taken at completion and could reference subsequently edited tool text; their complete frozen launch bundles remain valid. Later tools fix that shorthand at launch. Sixteen calibration cases predate bundle capture: all their shorthand hashes match the CRLF checkout of Git `5c9c3ae`, whose sources are also archived. Original records were retained, with the metadata issue disclosed.

All **427,136 input envelopes and 427,136 delivery records** were exported and verified. Archive validation identified a persistence limitation: PostgreSQL JSONB stores measurement metadata's `-0.0` as `0.0`, so 85,925 exported payloads differed from their pre-storage byte hashes. Unmodified database exports are retained. Separate `inputs-original-payloads.jsonl.gz` sidecars restore signed zeros exclusively from recorded physical samples; every recovered payload exactly matched its original hash. Each recovery lists the changed paths and source records. Recovery rejects any difference beyond a zero sign in measurement metadata, including any change to Core channels, magnitudes or timestamps. No database row or hashing protocol was rewritten. File manifests appear in `inputs-export.json` and delivery verification. A future versioned persistence protocol should specify numeric canonicalization or retain original payload bytes. This is an evidence-engineering issue, not a change in the tested dynamics.

Cumulative per-instance wall time was **2028.25 seconds, approximately 33.8 minutes**, including sampling and database persistence, not a pure kernel-speed benchmark. At simulation completion, local evidence occupied approximately 153.49 MiB and database growth 2464.02 MiB. Subsequent compressed input exports totalled 137.75 MiB. Delivery verification accounts for the final archive, figures, total storage and usage after reporting. The 4 GiB hard evidence limit, memory/disk reserves and single worker remained in force. Shared account usage at simulation completion was **66%→68%**, including concurrent work. No paid AI provider or GPU was used.

The evidence archive includes actual inputs, raw physical measurements, configurations, states, sampled trajectories, readouts, negative results, analyses and versioned tools. See the README for CLI access. In ThreeMind, select this study project and open the experiment notes or records/reports modules.


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
