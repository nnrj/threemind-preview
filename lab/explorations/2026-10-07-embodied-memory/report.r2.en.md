# E58: whole-scene vision, movement feedback and memory content

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-10-07. [中文](report.zh.md) · [Registration](design.en.md) · [Execution decisions](execution-notes.md) · [All measured values](results.json)

**The clearest finding is that prior experience can still affect answers through internal connections after identical recent experience.** In the first environment, recalibration gives 24/32, connection silence reduces this to 16/32, and rescue restores every original choice and the 24/32 score. The second environment does not reproduce the gain. Small-dose external correction learns new mappings with some loss of old examples. Whole-scene results, including errors, are reported below with a direct-input control.

## 1. What the study corrects

Recent teacher-pointing traces are memory: real past experience changes later answers. Their short duration or sensory location does not disqualify them. We investigate content, causal role and the division of work between Core and the external reader. E57's original report/data and E50's previous connection evidence remain intact.

No Core equations, defaults, old instances or text normalization changed. Normal experiments retain continuous-memory/2, ordinary intensity, continuous simulated body/weather input, forgetting, inhibition and expanding reviews. Raw activity is neither baseline-subtracted nor normalized per trial. The external reader receives explicit supervised training; it is not assumed to be a mechanically faithful translator.

## 2. History after identical terminal experience

Retain E57's saved four-field world to isolate memory from optical changes. Two histories teach different name–shape mappings. Both then see the same four grey shapes and the same two-second pointing sequence (0.5 seconds per location, no names), followed by 0,6 or 30 simulated seconds with continuing background.

Each question independently restores its saved state. Current test inputs are exactly identical across histories while answers differ. **A deterministic reader without history can score at most 16/32; this is not four-choice chance.** The 32 answers are 16 paired questions, not 32 independent minds/worlds. Calibration/test layouts are separate; teaching labels never enter test inference.

| Condition | Old reader /32 | Equal recalibration /32 | Recalibration training /32 |
|---|---:|---:|---:|
| Environment source 223, normal learning,6 s | 16 | **24** | 29 |
| Source 223, structural learning off from birth,6 s | 16 | 16 | 16 |
| Environment source 279, normal learning,6 s | 14 | 14 | 32 |

Source 223 answers both histories correctly in 9/16 pairs and changes 11/16 paired choices with history. Source 279 fits calibration but fails to transfer to held-out layouts. The first-source gain is not a stable cross-environment result. Sources refer to the original environmental conditions; questions are not independent experimental replications.

The frozen six-second recalibrated reader scores **15/32,24/32,16/32** at 0/6/30 seconds after the common tail. The original reader scores 16/32 at all three times. At 30 seconds the total absolute activation difference across histories is 0.21114, versus 0.06148 at 6 seconds: states have not become identical. Differences are offline diagnostics only, never decoder inputs. This identifies unstable decoding across time/layout, not erasure of all memory. No separate 0/30-second recalibration was performed.

Six-second recalibration does not modify or reteach Core: it reads previously saved activity. The reader has seen supervised examples from both histories and may identify a historical context, then consult externally learned answer rules. Exceeding 16 shows use of information beyond present input, not that every conceptual association is wholly stored in Core.

## 3. Connection silencing, rescue and transfer

| Source 223 at 6 s, same recalibrated reader | Recipient-history correct /32 | Choices changed from normal |
|---|---:|---:|
| Normal | **24** | 0 |
| All existing edges silent | **16** | 17 |
| Rescue | **24** | 0 |
| Teacher activation swapped | **24** | 0 |
| Opposite-history edges and short connection state | 22 | 6 |

**The 24→16→24 silence/rescue chain is the clearest positive causal finding.** Silencing makes all paired-history choices identical; rescue restores every original choice, not just the total. Derived first servo commands at the same body pose change in 17/32 cases and return after rescue.

Teacher activation transfer changes only 0.00020289 in absolute total and no longer controls the answers as immediately after E57 teaching. Edge transfer changes six choices: four move toward donor answers and two move away, increasing total donor matches from 7/32 to 9/32. These are partial effects, without wholesale conversion to the donor's mapping. Recipient selections contain 107,138/107,066 edges; 107,046 matched donor edges are inserted. Actual short-state counts are retained in results. This supports communication-dependent expression, not successful transplantation of the entire mapping. Source 279 did not meet the preregistered workload gate for these follow-ups.

Silencing affects all existing edges in the copied state, not an answer-selected concept region. Newly formed edges and already emitted signals are not retrospectively removed. Rescue removes the same silence. Teacher-receptor transfer changes only activation on channels identified by the saved world. Those activations already differ very little after the common tail; no choice effect does not mean these nodes can never matter.

Connection transfer aligns channels and replaces recipient-existing pairs with donor edges and their short-resource/fast states. Recipient nodes, activation, inhibition, energy, clock and pending transmissions remain. It is not transplantation of all memory, nor are all donor-only edges inserted. A score decrease alone is not successful transfer; donor-answer following must be examined.

First motor commands can be derived from recorded selections at an explicit common body pose, before movement feedback returns. This separates selection from its later sensory consequences. It is an existing-servo command calculation, **not a new closed-loop autonomous trajectory**, and not evidence that an articulated arm has been learned.

## 4. Movement feedback causes internal activity

The /3 world physically renders the self-pointer. From one two-second warmup Core state, replay six seconds of physical measurements. Movement is driven by explicitly prescribed forces; a reference body is externally held stationary. Simulated weather is shared, without live CPU feedback. Keep vision, body, both, or replace both with reference input. Body replacement includes motor power and body temperature, avoiding hidden movement feedback.

| Feedback retained | Activation integral | Associative-touch integral |
|---|---:|---:|
| Reference only | 3.69518 | 0 |
| Self-motion vision | 4.17645 | 0 |
| Body motion | 21.25023 | 0.295438 |
| Both | 21.73044 | 0.295451 |

**The instance senses movement; body feedback also produces associative touch.** Body effects dominate under this apparatus's scales and early state, not as a general statement about vision. Replacing both modalities reproduces the independent reference process: hidden physical motion has no extra input route. This identifies sensory causation, not a desire to move or subjective authorship.

## 5. Pointing with an actual whole-scene eye

The old four nearby optical fields arrive simultaneously; they are neither a single whole view nor temporally experienced saccades. Version /3 uses one fixed camera and a 16×16 regular retina. Objects, teacher sphere and colored self-pointer appear together. No object boxes, IDs or target-coordinate ports are inputs. The same reader serves each pixel neighborhood; selected pixels are mapped to servo coordinates, while ground-truth targets are used only for scoring.

The 104 lessons cover four shapes and four colors, ten consecutive first presentations per item plus three reviews with continuing background. Calibration has 48 questions; the held-out episode has 24, separating color, shape and combined confusions. Every complete scene asks about all objects, at jittered physical positions. Calibration/test each start from the same taught snapshot but are internally continuous, with fixed independent randomized order and no test-answer feedback; trials are not independent instances.

Extra review-round pauses are 0,6 and 18 seconds; each item's actual revisit interval also includes other scheduled items. This is not an exact item-wise memory-curve schedule. Reader calibration already includes combination questions; held-out performance concerns new physical arrangements, not zero-demonstration relational composition.

| Reader information | Color: nearest / arrived | Shape: nearest / arrived | Combination: nearest / arrived | Total: nearest / arrived |
|---|---:|---:|---:|---:|
| Core activity | 6/8 · 6/8 | 0/8 · 0/8 | 4/8 · 4/8 | 10/24 · 10/24 |
| Direct input | 8/8 · 7/8 | 1/8 · 1/8 | 4/8 · 4/8 | 13/24 · 12/24 |

**Whole-scene color selection is functional in this batch; reliable shape and combination selection remain unresolved.** The activity reader does not outperform direct input. Shape selection is also only 1/8 in the bypass, so the new eye, teaching material or reader contributes to the bottleneck; this cannot be assigned solely to Core. Distinct raw measurements in one optical example do not ensure recognition across layouts. Prioritize sampling and readout checks before attributing the result to attention or graph density alone.

“Nearest” means the correct object is closest to the final pointer. “Arrived” requires a distance at most 0.20 m. Both use the actual endpoint. Training labels specify a centre pixel; exact training-pixel hits for the activity and direct-input readers are 45/48 and 30/48, respectively. Teaching ends at 180 simulated seconds with 1,154 nodes and 1,319,614 edges. All 24 questions and endpoints are retained in each predictions.json. Nearest-object correctness is not precise motor control; the new apparatus does not retrospectively redefine the old four-field result.

Both activity and direct-input conditions use the same supervised selector capacity, labels and optimization budget. Success is system performance, not automatically pure intention translation. The executor is a selected-position servo, not a trained articulated arm. Guide reaction is measured physical contact, without arbitrary skin/object friction.

Before teaching, a tiny teacher cue was found invisible at the two far locations. Its physical radius changed from 0.065 to 0.12 metres; size is saved with state and legacy states restore the old radius. No coordinate side channel was added. A warmup/B had no teacher marker and are unaffected.

## 6. Continuing external learning on a new mapping

| Reader information | Frozen: new /16, old /32 | 4 new feedback +8 old rehearsals | 16 new feedback +8 old rehearsals |
|---|---:|---:|---:|
| Actual Core activity | 0,25 | **14,20** | **14,20** |
| Current incoming signals (explicit bypass) | 0,16 | **16,16** | **16,14** |

**A small amount of correction enables the individual reader to follow the new mapping.** Four new examples reach the same score as 16 in this batch, but five old correct answers are lost in the Core-activity condition. This is useful continued teaching, not cost-free stable updating. Direct-input supervision also reaches 16/16 new answers, so new-task accuracy alone is explainable externally. The activity reader retains more old-history discrimination; interpret alongside C's identical-input controls. Natural conversation and open relational reasoning are not established.

The new permutation is(2,3,0,1), absent pair-by-pair from the old(0,1,2,3) and(1,2,3,0). One experienced Core receives 52 more lessons, the common tail and six-second wait. Evaluate the frozen reader first, then restore it separately for 4 or 16 new supervised examples plus 8 old rehearsals and 600 optimization steps; doses are not cumulative.

This is individualized continued supervised learning of an external adapter, not labels written as Core answers or a merged kernel. Old/new episodes occur at different physical times; direct-input readers can also exploit current context. The test concerns adaptation and old-example retention, not isolated proof that Core learned every new concept. Old examples are saved old-history processes, not contradictory names simultaneously presented to one current instance.

## 7. Tools, failures and resources

New reusable tools provide versioned whole-scene vision, visible self, guide touch, recorded sensory replacement, a shared retinal reader and a CLI, through existing Runtime/output APIs. The production world editor is not wired to the new apparatus. History/docs use the existing UI; designs, reports and evidence belong to a new research project.

The first C refit requested default 6×6 ports for saved 4×4 data. Validation stopped it before fitting. The repaired script restores the saved world's inventory and uses a new case directory, preserving both evidence and failure. No redundant full-content audit of historical data was performed.

Completed 58 stages and 436 Core creations/restores; recorded compute including failed attempts totals 138.02 minutes. Before any A pointing score, a dated amendment increased the 120-minute compute cap to 140 minutes solely to finish the fixed workload; all other limits remain. Local evidence before archiving is 0.650 GiB. Shared account usage changed from 76% to 80%, not wholly attributable to E58. At closing, available RAM is 11.60 GiB and free C/E storage is 8.86/75.49 GiB. Final archive/database growth is separately recorded in delivery.json.

Validation: 19 targeted apparatus, restoration, reader and choice-attribution tests passed in 7.37 seconds. History validation passed for four editions and 61 chapters, including bilingual coverage and local links. No frontend or Core changes were made; their full builds were not repeated.

## 8. Next decisions

Separate whether memory exists, which relations it stores, and how it is expressed. Loss of a fixed reader's accuracy does not imply absence of memory; accuracy after external supervision does not imply all answers originate inside Core.

The user's sharp-centre/coarse-periphery, gaze and attention proposal is R36 for a separate round. The legacy input-amplitude gate is off; continuous local-context competition is on. Neither is a complete visual-gaze loop. Compare sensory sampling and selection separately, accounting for external recognition and costs. E58 does not change to sparse sampling or enable a new gate mid-study. [Plan/source](../../../docs/en/plans/embodied-memory-content.md)

## 2026-10-07: system-continuity scope note

Frozen and newly fitted heads are different conditions. Four- and sixteen-example feedback each starts from the same old weights: independent dose controls, not sequential 4-to-16 development. Fitting resets the optimizer. Fixed-head attribution and measured small-data adaptation remain; continuous whole-system learning requires complete state.

[Continuity audit / 连续性核查](../../../docs/en/plans/system-continuity-audit.md)


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
