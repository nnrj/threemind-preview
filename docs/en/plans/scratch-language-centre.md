# A from-scratch Transformer language centre and spontaneous-activity translation

[中文](../../zh/plans/scratch-language-centre.md) · [Research backlog](research-backlog.md) · [Language devices](../language-adapters.md)

**Current execution order, amended before experiments on 2026-10-04:** the user requests frozen pretrained Qwen feasibility first, then from-scratch companion training only if feasibility is supported. The from-scratch design below remains the final objective, not the first executed E42 condition.

Approved on 2026-10-04. E42 is the first bounded study. Ocean experiments pause; their evidence and species remain intact. The long-term objective is a small Transformer trained from scratch alongside ThreeMind, serving as a language sensory/expressive interface, including observation of internally continuing activity. That objective has not been achieved by wiring the devices or reconstructing calibration words.

## Boundaries and evidence

Use the unchanged `continuous-memory/2` dynamics and explicit saved configuration. Do not alter old instances, input normalization, death criteria or defaults. Transformers remain external devices. The primary experiment uses no pretrained weights/tokenizer, Qwen, paid provider or downloaded model. Train byte-level models on declared material, then freeze them during assessment. Original text, random frozen encoding and independently trained frozen encoding are separate conditions.

[E26](../../../lab/explorations/2026-10-02-robot-language/report.en.md) reconstructed four calibration words but did not reliably express new pairings. Signed time-bin averaging may discard information; single-word calibration did not cover experienced network states. These are hypotheses to investigate, not evidence that Core cannot remember. Existing autonomy criteria and ecological findings remain unchanged.

## Stages

| Stage | Work | Decision |
| --- | --- | --- |
| A / E42 | Add no-input observation; compare complete activity, compressed features and trained output on independent calibration/held-out states | Distinguish projection loss, decoder failure, bias and genuine silence |
| B / E42 | Four-to-eight-word ordinary/reversed pairing and untrained controls; repeated short teaching; freeze converters before new Core experience | Report every seed, raw responses and decoded answers, including failures |
| C / E42 | Observe before/after teaching without new input; real/zero/shuffled/swapped activity controls; early versus later decoder checkpoints | Separate changes in expression from changes in Core activity; retain incoherent output |
| D / later or separately registered extension | Speakers, role direction, changing possession, unseen family composition, then bounded dialogue | Address measurement/expression first; do not replace registered endpoints after seeing results |

## Teaching and splits

Preserve complete short sentences, speaker information and punctuation, including “甲是松子。” and “乙是铃铛。”. Each new sentence is repeated 12 consecutive times, followed by reviews of 6 and 3; balance order using fixed seeds. Teaching intensity 1, probes 0.5. Keep the existing extra strong-stimulus term. Record the legacy 0.5-second response window and subsequent continuous activity rather than assuming the short window contains the whole response. Any timing choice is made in labelled calibration and frozen for formal testing.

Device calibration uses independent words, intensities and recovery states, never formal pairing answers. Probe forks originate from the same teaching checkpoint. Test new combinations of familiar words separately from unfamiliar words. Independently trained input models see words or material excluding test pairings. Preserve existing normalization and anonymous channel wiring and record actual dose; do not adapt channels to answers.

## Spontaneous output / “inner monologue”

This is a name for the activity-to-language interface, not a guarantee that generated prose faithfully reports pre-existing semantic thought. Store original activity, simulation timestamps, input presence, projected features, decoder version, generated text/bytes, empty results and failures.

1. Explicit no-input observation advances the existing simulation and queued events. It sends no empty text, BOS token, hidden query or awakening input to Core. Distinguish no newly submitted input from the end of already queued external deliveries.
2. Emit results window by window through streaming CLI JSONL and the same API/UI operation. Report wall-clock decoding delay. Do not alter Core time or discard activity to meet a display rate.
3. Strict output receives current activity and frozen calibration only. Reset Transformer autoregressive context between windows; do not feed its generated text back into Core. Feedback and persistent external-model memory require separate experiments.
4. Keep incoherent, repetitive and unreadable output. Record genuine zero activity as silence without inventing prose.
5. Replay the same recorded activity through early and later decoder checkpoints. More fluent wording on identical activity is decoder improvement, not improved Core reasoning.
6. Complete absence of input is primary. If activity naturally ends, report it. A separately labelled replayable weak environmental-background condition may be studied; it is not an input-free condition. No live host telemetry in this batch.

## Controls and analysis

Compare text, frozen random Transformer, and independently trained frozen Transformer inputs. Compare ordinary, reversed and absent teaching, then learning-disabled controls as needed. Preserve signed-average readout identity; a non-cancelling/peak-preserving alternative must have its own protocol identity. Retain raw trajectories.

Use actual, zero, feature-shuffled and cross-experience-swapped activity. If a clear relationship appears, use targeted versus matched connection silencing and persistent-state grafts. Global destruction alone is insufficient attribution. Report preregistered transient target responses alongside decoded accuracy; global stability is not required. Peak/integral probes locate information but do not permit picking arbitrary favourable times after testing.

For spontaneous streams report activity duration, readable output, vocabulary distribution, repetition, experience differentiation, training-stage changes and response to feature interventions. Distinguish new internal re-entry from residual decay. New words or coherent strings are observations; relational correctness is tested independently. Locate failures at raw activity, projection or decoding before changing anything; this study does not change Core.

## Resources and delivery

Preflight: CUDA-capable GTX 1650, approximately 10.6 GiB available RAM, E: 62.8 GiB and C: 8.9 GiB free. Existing E: environment, no downloads. One worker, initially four independent seeds, at most 256 Core instances; four hours aggregate training/simulation. Process-tree budget 6 GiB (existing study parent guard remains 4 GiB), GPU 3 GiB. Preserve 2 GiB RAM, 5 GiB C:, 15 GiB E: headroom. Stop expansion at 3 GiB new evidence, hard cap 4 GiB. Account starts at 31% used; +3 percentage points stops expansion, +5 stops new computation, conservatively including other tasks. Save batch checkpoints, never overwrite prior data or repeatedly hash large archives.

Publish independent E42 design, inputs, versions, failures, snapshots, activity, results and bilingual reports under `lab/explorations/2026-10-04-language-centre/` and in Lab. Add reusable library/API/CLI operations. Synchronize backlog, modern histories and both Classical Chinese adaptations. Completion of the bounded study does not imply completion of a general language centre.

## User request (translation; Chinese original in the paired document)

“Generate the plan, put it in the appropriate docs location, and start the experiment. The final goal is to see whether a small Transformer trained from scratch alongside ThreeMind can become its language centre and sensory interface for natural-language communication. ThreeMind may also continue associative activity without stimulation; this activity should be translated and monitored in real time, even if these ‘inner monologues’ are disorganized or illogical. Observe whether training improves them and whether other associative activity, logic, or something approaching a logical inner monologue or thought process appears.”

## Same-day pre-execution amendment

The user additionally authorizes pretrained Qwen first: inputs pass through Qwen and the input bus into ThreeMind; later prompts should yield relevant utterances, possibly logic, through Qwen output. Only then train the from-scratch companion.

Use locally pinned Qwen3-Embedding-0.6B and Qwen3-0.6B, frozen base weights with an external activity-prefix calibration head. Strict decoding sees no question or lessons; acknowledge pretrained linguistic priors. Gate progression on successful held-out word/state conversion, new pairing performance exceeding blank and reversing with experience in at least three of the initial four seeds, and feature-swap/shuffle controls supporting Core contribution. Word conversion alone is instrument feasibility, not passage of the learning gate. If the gate fails, report the bottleneck and do not start large scratch training. Resource limits remain unchanged.

### 2026-10-04 clarification during calibration, before formal teaching tests

The initial machine registration counted every held-out window toward word accuracy. Raw traces show that the last two windows of each word already have zero activity, where silence is correct. Keep the original denominator and results, and separately report active-window translation accuracy (75% gate) and silent-window silence accuracy. Do not discard decay tails. This clarification follows raw activity, not favourable decoded answers. The formal cue metric remains the second 500ms window. Blank controls wait without input for 42 simulated seconds to match the teaching groups' test start; no hidden awakening input is supplied.

### 2026-10-04: E43 spaced review preserves structure; language retrieval remains open

The user requested ordinary intensity, individually expanding reviews, physical telemetry background, and permission for simulated comparisons. E43 starts blank with57 presentations per sentence at intensity1, compared with dose-, elapsed-time- and final-recency-matched massed review. Recorded host/recorder-process telemetry is replayed identically. Both wirings show5.4–5.7times more emission-floor-passing signal under spacing and157 retained language edges300s later versus zero under massing. A stronger, more stable subset is missed by mean weight alone.

Primary texts do not reliably express new pairs; matched reversed success is0/8. Ordinary-spaced texts equal learning-disabled outputs at completion and60/300s later. A prospectively registered40-fork intensity1 cue diagnosis adds no qualified transmission over no-language controls. Background maintains overall life but has no observed cross-basis edges at checkpoints; the old four-word head also translates untaught background into familiar words. Structural retention, unsuccessful retrieval and mixed-background decoder calibration remain separate findings. All500 sources/forks complete without Core changes. Scratch co-training has not started; sensory/retrieval calibration is a recommendation.

[Follow-up](language-spaced-review.md).

### 2026-10-04：后续顺序更新 / Subsequent execution-order revision

[共同发育路线 / Co-development](language-development.md) 已获用户批准。当前Qwen成功不再是新路线的前置条件；上文旧批次门槛与结果保持原义。 / The user approved the independent route; current Qwen success no longer gates it. Earlier criteria and results above retain their original meaning.
