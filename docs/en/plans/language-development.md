# Co-developing a language adapter with ThreeMind

[中文](../../zh/plans/language-development.md) · [Research backlog](research-backlog.md) · [Earlier plan and evidence](scratch-language-centre.md)

2026-10-04. Approved for implementation; this document is a plan, not a result.

## Decision and evidence

E26 calibrated a scratch decoder on four words. E42 did not establish reliable new-pair expression through Qwen. E43 ordinary-intensity spaced reviews preserved more structure, but current cues did not produce the corresponding transmission; the old decoder also translated untaught background into familiar words. Learning, retrieval and expression therefore require separate investigation. The existing ocean and internal-activity intervention evidence remains intact.

The user now approves an independent scratch-Transformer co-development route without requiring the current Qwen pipeline to succeed first. This changes future execution order, not E42's criteria or outcomes. Transformers may learn representation, order and expression; Core continues learning from anonymous stimuli through its existing dynamics. Alternate external training and Core experience rather than requiring gradients through Core. Freeze external models for new-experience attribution and exclude test associations from their training.

## Stages

| Stage | Work | Deliverable / progression |
| --- | --- | --- |
| A | Input distinguishability, full experience versus partial cue, trajectories versus projections | Locate sensory, retrieval or observation failure without changing Core thresholds |
| B | Scratch language adapters, expanding reviews, jointly observed teaching material | Compare original text, legacy whole-sentence vectors and independently versioned continuous feature input; train expression on realistic activity |
| C | New and reversed associations after freezing adapters, delays and held-out combinations | Untaught, learning-off, exchanged activity and local-transmission controls; report each capability separately |
| D | Communication under unequal observations | Finite external signalling channels in complete environments, no preassigned food/danger semantics; mute, shuffled and history-swap controls |
| E | Object persistence, delayed consequences, division of information, new skill combinations | Later population/body evolution; replaying Earth's entire history is not a prerequisite for language learning |

E44 is a bounded first batch covering A–C and continuous internal-activity observation. A formal D ecological batch requires distinguishable, measurable language/signal effects and a separately registered environment and budget. Unstarted D/E work is neither negative evidence nor completion. If the limiting issue is Core dynamics, finish the report and discuss it with the user rather than modifying Core.

## Teaching and information boundaries

Objects, bodily observations, actions or measurable speaker features may co-occur with language. Teachers and analysis tools may know names; Core receives versioned sensory measurements/features, not hidden answers, grammatical roles or predetermined semantic paths. Ordinary teaching intensity is 1, cues 0.5/1; initially repeat each intact sentence at least 12 times, then widen the review intervals. Do not substitute strong stimuli for normal teaching.

Keep normalization, forgetting, inhibition, depletion/recovery and death rules. Extra facilitation remains off by default. New sparsity, normalization or sequential delivery choices receive an independent protocol and measured per-frame dose; they are sensory interventions, not mere observation. Preserve existing mappings and instances.

Learning an existing language through interaction and a population inventing a communication system are distinct questions. Teacher interaction can come first. Group experiments need an information difference and consequences of communication. Preserve the complete habitat for ecology; a one-agent/one-food apparatus cannot replace it.

## Internal association and interpreted monologue

Record prompted periods, no-new-language periods with background, and genuinely input-free branches separately. Reuse immutable physical telemetry at its original timestamps where available; label simulated background. A background-supported interval is not absence of external input.

Save timestamps, pending deliveries, complete anonymous active-node trajectories, activation rises/re-entry, actual transmission, adapter identity, raw text/bytes, empty results and failures. Do not remove activity because it looks meaningless or require global stability before inspecting a clear transient response.

Train and compare decoders on temporal activity including background and post-learning states. Supervised silent calibration examples may learn termination; do not hard-code familiar words. Do not infer association merely from an activation rise: distinguish pending arrivals, background, residual decay and internal propagation, with matched-input local interventions and sham controls. Preserve all interpreted outputs, including repetition and gibberish; distinguish experience-supported, background-equivalent and unresolved text. Fluency improvement on an unchanged trajectory is an adapter improvement, not new Core reasoning.

No generated-text feedback to Core and no cross-window decoding cache. Active vocalization and reafference are separate future experiments. Continuous recordings must not be confused with concatenated independent probe branches.

## First-batch limits

Verified locally: GTX 1650 and Torch CUDA; approximately 13.6 GiB available RAM, 60.6 GiB free on E, 8.8 GiB on C at registration. One simulation worker, small local models; use available GPU for actual training with recorded CPU fallback.

At most 1,536 sources/restored branches and four aggregate hours of simulation/model computation. Process-tree limit 6 GiB, GPU 3 GiB; retain 2 GiB system RAM, 5 GiB on C and 15 GiB on E. New evidence soft/hard limits 6/8 GiB including archive copies and database growth. Account starts at 35%; +8 percentage points stops expansion, +12 stops new computation, shared usage included; refresh at least every 30 minutes. Reserve resources for reporting.

Register calibration choices before observing them and keep formal names/assignments/seeds held out. Checkpoints support bounded recovery. Preserve old evidence; no broad data scans or repeated whole-archive hashing. Missing tools may be added outside or inside development-only interfaces provided they do not alter dynamics.

## 2026-10-04 continuation: multisensory experience and early language

While E44 was running, the user emphasized grounding language in an experienced world and continuing beyond text-only training regardless of its outcome. This steers later stages without changing the ongoing E44 comparisons.

Existing implementation includes camera/microphone adapter contracts, image/audio codecs, and MuJoCo RGB, contact-force, joint and inertial ports in `world_ports.py`. Prefer simulated acquisition sources using existing conversion and buses; introduce new protocols only for genuinely different measurements. MuJoCo is not a complete acoustic-field simulator: synthesized PCM must be labelled as such. Smell/chemical concentration requires an explicit diffusion, flow or concentration source, not a hidden food label.

A later complete interaction scene should contain persistent objects, a movable body and a teacher. Vision, contact, proprioception and language accompany distinguishable consequences of approaching, touching, moving and consuming food. Start with objects, colours and small quantities, then speakers and caregivers as persistent roles across interactions. Father/mother cannot be reduced to two picture labels. Text can temporarily express vocal output before using the same audio protocol.

Candidate visual budgets are32×32 or64×64 at5–10Hz, with existing block audio downsampling. These are later calibration candidates, not changes to current sensory defaults or Core propagation. Reduced sampling must preserve relevant distinctions, contacts and action feedback. Compare language alone, visual-language, added contact/proprioception, active interaction and recorded playback; retain the complete environment and record dose, background and duration.

The question is whether joint experience binds words to reproducible world changes within plastic Core. Neither impossibility for text-only systems nor guaranteed understanding from multiple senses is an established ThreeMind result. Continuous internal activity and verbatim translation remain primary evidence.

[Implemented tools](../reference/language-development-tools.md)

## References

- [Riveland & Pouget, 2024](https://www.nature.com/articles/s41593-024-01607-5): language and sensorimotor-network cooperation, with pretrained language and different learning rules.
- [Titans](https://arxiv.org/abs/2501.00663): attention combined with online-updated memory; not permission to replace Core's rules.
- [BabyCL, 2026 preprint](https://arxiv.org/abs/2606.05115): chronological egocentric visual/verbal learning, with explicit contrastive objectives, segmentation and replay.
- [Wieczorek et al., 2024](https://www.nature.com/articles/s41467-024-51887-5): communication and generalization in reinforcement-trained teacher/student agents.

These motivate designs, not claims that ThreeMind has already reproduced them.

## Dialogue source

The [Chinese counterpart](../../zh/plans/language-development.md#原始讨论及本次授权) preserves the original user messages. The following is a translation, not an original English quotation:

The user asks whether ThreeMind and a small randomly initialized Transformer can learn together, given existing evidence of memory, history-dependent responses and order effects; whether social cooperation is necessary; and whether developmental environments or longer body/brain evolution can produce a system that learns language and knowledge through experience while allowing forgetting and errors.

The user then authorizes recording the discussion and proceeding, emphasizes observation and interpretation of unprompted internal associations as monologue, permits necessary interfaces/tools, prohibits damage to Core dynamics, and asks that any actual dynamics gaps be reported after the experiments for discussion. Resource limits may be relaxed appropriately.


## Source and clarification of the continuation

Both additions are recorded in the [dialogue source](../history/sources/2026-10-04-language-grounding.md). Later work tests bidirectional language/sensory associations without semantic labels delivered to Core.

### 2026-10-05：本批结项 / Batch completion

[E44 report](../../../lab/explorations/2026-10-04-language-development/report.en.md)：A–C首批完成；跨感官唤起和局部因果通路已有证据，准确新回答与可信联想独白未接通。后续先分离输入和曝光，再增加物理共同经历，D/E未启动。 / First A–C batch complete: cross-sensory effects and local paths supported; accurate new answers and verified monologue remain open. Separate input/exposure before richer grounding; D/E remain unstarted. 原登记保留，不能把本段回写成事前承诺。 / Original registration remains unchanged.

### 2026-10-05：后续实施

[E45独立校准与组合计划 / Calibration and composition](language-calibration-and-composition.md) 已获准；保留E44结论与原始证据，后续外设/参数选择先校准后验证。 / Approved without rewriting E44; select on calibration before held-out validation.

### 2026-10-05: E45 completed; separate pathways, patterns and expression

E45 completed 2041 sources/branches and recorded 67.91 minutes of simulation, training and decoding. Equal-dose routes and six parameter alternatives did not beat sparse character input with defaults; Core/defaults were unchanged. Visual cues influenced name channels in 24/36 normal and 24/36 reversed cases, versus 0/36 learning-off. Six target-edge interventions removed at least 99.9813%; matched-other-edge silence retained 98.995%–165.205%. These learned reciprocal effects must not be concealed by correct-name retrieval of 0/36. Original object retrieval was 10/72 and two-step name-to-sound 0/48; the first link also lacked reliable retrieval after second teaching, so a composition-specific gap is not isolated. Fifteen 300-second histories contained no registered late sensory replay candidate.

The user emphasized feelings, processes, multiple intentions and inhibition as possible native representations; communication need not reproduce an external visual template. A post-result registered rereading found name/name-plus-is pattern matches of 12/36 normal and 9/36 reversed, with no discriminable learning-off patterns; delay/reversal stability remained weak. Two earlier 3/24 totals involved different cues and do not alone prove a common hidden rule. This supplement does not replace exact-retrieval criteria or exhaust non-activation codes. Recommended next work adapts expression to individual patterns, freezes peripherals for new-experience attribution, retains both component relations and broadens contextual/inhibitory/transmission observations.

[Report](../../../lab/explorations/2026-10-05-language-calibration/report.en.md)
