# E58: whole-scene vision, movement feedback and memory content

Recorded 2026-10-07. Status: batch delivered; findings and remaining scope are recorded below and in the report. [中文](../../zh/plans/embodied-memory-content.md)

## Clarification

The user proposed that remembering an object–name relation and retaining a teacher-pointing trace may share the same mechanism: experience leaves an internal pattern that becomes a template for later cognition. This is an interpretation, not a newly measured result.

We accept that both can be memory. Short duration or storage in receptor activation does not disqualify a trace. Activation, inhibition, fast connection states and persistent structure can all carry history. The earlier opposition between sensory residue and genuine memory was too strong. This dated clarification supplements, rather than overwrites, E57.

The remaining question concerns content and division of work. Core might retain individual correspondences, or retain teaching context that lets an externally trained reader choose among mappings it already knows. Both are useful memory. Failure to express a new mapping alone does not prove absence of learning; sensitivity to an intervention alone does not locate the entire concept.

## Verified apparatus

The pointer already supplies position, velocity, acceleration, motor power and body/weather feedback. It is not yet visible to the actual eye. Four separate optical origins inspect fixed locations; sharing their decoder does not make one whole-scene eye. A fixed guide-contact measurement is not distributed skin pressure or friction. E50's connection-dependent naming evidence remains valid within its conditions; it does not automatically certify the later differently supervised E57 selector.

## Approved work

1. Add a separately versioned whole-scene eye with a physically rendered self-pointer, without target-conditioned cropping or changes to old worlds/Core. Touch measurements must correspond to simulated contact.
2. Separate movement-to-sensation, sensation-to-activity and activity-to-command causation. Use recorded physical backgrounds and distinguish active/passive motion and feedback removal. Losing movement-linked activity after removing feedback does not prove absence of control.
3. Give opposite histories the same terminal experience and delays. Measure remaining history and what the reader uses; report both frozen old readers and fairly recalibrated readers.
4. Compare fixed and individually adaptable external readers on newly taught correspondences. Labels belong to teaching, never held-out inference. No merged Core is authorized by this experiment.

Keep expanding reviews, bodily background, forgetting and inhibition. Attribute changes separately to optics, organs and readers. The main goal remains pointing, the history that changes choices, and where that contribution resides. Research interventions do not become silent defaults.

[Registration](../../../lab/explorations/2026-10-07-embodied-memory/design.en.md) · [Dialogue source](../history/sources/2026-10-07-memory-content.md)

## In-execution addition, 2026-10-07: visual sampling and attention (R36, next-round discussion)

The user proposed a small sharp central field with coarse peripheral vision, a visual central adapter and possibly a Transformer attention gate, while asking not to interrupt E58. Decision: finish the registered inputs first; inspect and record candidates without enabling a gate or replacing sampling mid-study.

The old /2 fields enter the same observation simultaneously; they are not four temporally experienced saccades. The /3 two-second apparatus sample produced1,038nodes and1,076,404edges. Whether attention is the remedy remains a hypothesis: shared observation rules and correlated background surfaces may also contribute.

The directed non-self maximum is1,038×1,037=1,076,406, so this sample is nearly complete. `restoration.py::_associate` considers co-touched source/target pairs and their activation products under default `co-stimulus`, without enabled spatial restriction. The grey background surface also produces persistent nonzero pixels. Sampling and common-observation granularity therefore deserve joint study; neither absent attention nor meaningless weights follows merely from edge density. This inspection does not authorize changing historical birth rules.

Existing mechanisms differ. `attention_competition_enabled=false`, budget28, optionally selects the largest incoming channels. Continuous Core already has `context_enabled=true/context_mix=1`, which compares local arrival features with recipient state; it does not scan a retina, move gaze or select an object by task. Inhibition and decay also exist. Missing gaze selection must not be described as absence of all filtering. Sources: [input attention](../v2-attention.md), `src/threemind_kernels/continuous.py`, `crates/threemind-core/src/mechanisms.rs`, and the saved E58 configuration.

Suggested sequence: versioned coarse-periphery/sharp-centre optics; compare fixed gaze, answer-independent scanning and uniform sampling with explicit geometry, timing, channel and amplitude budgets. Then add controllable gaze and bodily feedback; only explicit teaching may supply demonstrations. Compare existing local competition, an external visual adapter and a learnable Transformer gate. No answer/object-ID/observer-importance ranking may secretly control inference. Record original and gated signals separately and retain old versions. Count the gate's own scanning cost and learned recognition; similarity weighting is not automatically the intended visual attention mechanism. No candidate was implemented in E58.

The functional category "visual central adapter" is already defined in [central adapters](../reference/central-adapters.md); it needs no privileged Core interface. E58's shared retinal reader selects an output location, rather than implementing visual input filtering. A future versioned, optional input processor can use the same adapter architecture, recording physical measurements, processed incoming quantities and internal responses separately.

## Delivery, 2026-10-07

E58 treats short sensory traces as memory and tests their content and causal role. After identical recent experience and a six-second wait, environment seed 223 scores 16/32 with the old reader and 24/32 after recalibration. Silencing existing connections gives 16/32; restoring communication recovers all original choices and the 24/32 score. Recalibrating the learning-off control gives 16/32. Teacher-activation transfer has no effect; edge/fast-state transfer gives 22/32 without systematic following of donor answers. Environment seed 279 fits 32/32 but tests at 14/32. The six-second reader scores 15/32, 24/32 and 16/32 after waits of 0, 6 and 30 seconds. A causal contribution is established in the first environment; robust decoding remains open. Correction improves the new mapping from 0/16 to 14/16, while old examples fall from 25/32 to 20/32. The direct-input bypass also learns new answers at 16/16. Body and self-vision feedback change activity, without establishing subjective agency. Whole-scene held-out trials: the correct object was nearest the final pointer in 10/24 Core-activity and 13/24 direct-input trials; actual arrival within 0.20 m was 10/24 and 12/24, respectively. Color scores are 6/8 and 8/8; shape scores are 0/8 and 1/8. The new apparatus has a shape bottleneck that cannot be assigned solely to Core or yet identified as an attention failure. New tools add a whole eye, visible self, guide touch, shared retinal reader and CLI without Core/old-data changes. The user proposes sharp-centre/coarse-periphery optics and attention as R36; this batch retains its inputs. Disabled legacy input gating and enabled continuous local competition remain distinct.

[E58 report](../../../lab/explorations/2026-10-07-embodied-memory/report.en.md)
