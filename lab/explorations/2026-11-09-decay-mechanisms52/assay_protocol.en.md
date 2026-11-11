# R46a: local retention under three decay laws and two relaxation settings

Prerun protocol v1, 9 November 2026. Registration and execution require completed R45 delivery, genuine /5.2 integration and version regression. This is the first layer of R46, separate from the full personal-adapter task.

## Question and conditions

The author's selection principle is that repeated teaching and strong stimuli should leave persistent connections, weak incidental connections should fade promptly, and persistent connections should eventually fade without reinforcement. Compare exponential, inverse-logarithmic and power-law decay, each with the original linear timescale relaxation enabled or disabled. Equations, contribution ages and immutable birth curve selection are defined in `design-notes.zh.md`. All other parameters retain the /5.1 defaults inherited by /5.2. No extended survival grace period is introduced, no production default changes, and no old subject is upgraded.

## Subjects, experiences and measurement

Eight new birth origins use seeds 261109200–261109207. Anonymous channel mappings, energy and initial random conditions are paired across the six conditions. Courses, opposite teaching histories and delays are nested observations. Each condition teaches either output 0 or output 1 in association with the same cue; the test presents only that cue. Each sequence develops continuously from birth, with no per-question restoration. The measurement and probe do not receive the correct answer.

This is a connection-mechanism assay. Its peripherals are a fixed stimulus adapter and a fixed temporal measurement instrument, without a trainable output adapter. The instrument records 20 frames over one second, retaining activation, inhibition, direct and associative activity at both declared output channels. Instrument discriminability is not scored as successful whole-system task performance. Personal Transformer adapters, the original sound–vision–action task, correction and rule reversal require the separately registered second layer.

A separate background channel receives a 0.2 stimulus every 0.5 internal seconds to preserve the original survival rule. Background and task stimuli are separate events; the instrument checks that background-to-task edges have not formed. Teaching co-presents a cue and its designated output:

|Course|Per-channel intensity|Internal times, seconds|Count|
|---|---:|---|---:|
|Single weak|0.12|127|1|
|Single ordinary|0.4|127|1|
|Single strong|1.0|127|1|
|Massed repetition|0.4|120,121,122,123,124,125,126,127|8|
|Spaced repetition|0.4|16,17,19,23,31,47,79,127|8|

Repetition conditions match count, per-channel dose, birth-to-end duration and last presentation. Actual accepted increments and saturation are preserved; supplied dose is not called an accepted weight increment. All sequences receive the same 12 unrelated single-channel 0.4 stimuli from 0.1 to 11.1 seconds. Teaching ends at 128 seconds. First exposure is part of the actual history; novelty is not disabled, so its separate causal contribution is not isolated here.

The delays are 1 and 300 seconds after teaching. Independent continuous sequences prevent an early test from rehearsing a later test. Each history and delay has matched cue-present and cue-omission sequences, which follow the same schedule from birth and differ only in the final cue. There are 8 origins × 6 conditions × 5 courses × 2 histories × 2 delays × 2 cue conditions = **1920 sequences**, with 3840 complete teaching/test boundaries. Birth, post-teaching and post-test states are preserved. The preceding one-second window has background input only. The cue-present arm receives a 0.8 cue; both arms then undergo a one-second observation. Missing task nodes remain recorded as missing, with zero activity, rather than excluding failed samples.

## Preregistered decisions

These rules select candidates for the later whole-system experiment. The 300-second interval addresses the observed limitations around the current 30-second minimum scale. Thirty internal days is a finite-fading analytical horizon, not a human-memory constant.

1. **Instrument validity:** curriculum, background, dose and complete-state chains match registration; observation does not alter state; channel and edge identities are verifiable. An edge never formed is reported separately from an edge formed and subsequently forgotten.
2. **Selective structural retention:** both original target-directed connections survive to 300 seconds for strong and spaced teaching, while no target connection survives single weak teaching. Both histories must satisfy a condition for an origin to pass. Each of the three conditions requires at least 6/8 origins. Passing all three constitutes meeting the registered structural selection principle. Both directions, current weights and current timescales are reported separately.
3. **Retention of the experience-dependent process:** retain two output channels × 20 frames × four fields, and subtract the corresponding preceding window to form a 160-dimensional vector. For each history and delay, subtract the cue-omission vector from the cue-present vector to obtain the cue's effect. Then subtract these effects between opposite histories at each delay. This separates the cue effect from spontaneous changes in preceding activity. Both resulting vectors must have RMS greater than 1e-4; the 300-second vector must have cosine similarity at least 0.8 to the one-second vector and retain at least one tenth of its RMS. Strong and spaced courses must each pass in at least 6/8 origins. All four activity fields enter this primary measure. Passing establishes a retained cue-evoked, experience-dependent process, not a personal adapter's correct answer.
4. **Finite fading:** from the complete post-teaching connection state, analytically predict weights after 30 internal days, explicitly assuming no further reinforcement or structural damage and applying the actual curve and relaxation rule. Both target connections must fall below the original pruning threshold for strong and spaced courses, each in at least 6/8 origins. This conditional prediction is separate from actual cultivation to 300 seconds.
5. **Spacing and cost:** report paired massed-versus-spaced differences in connection survival, weight and the temporal response at 300 seconds; spacing is not assumed to win. Report wall time, peak private memory, originals size, nodes, edges and contribution counts. If no condition passes targets 2–4 together, state that no tested candidate met the complete registered requirement and identify each benefit and cost.

The independent N is eight birth origins. Frames, edges, courses, histories and delays are not extra independent samples. Report individual-origin results and 95% source-bootstrap intervals for paired differences. This is exploration, not independent confirmation or a claim of universal optimality.

## Engineering, resources and delivery

Complete-state, next-event and full-window checks have passed for all six settings. One excluded inverse-logarithmic/no-relaxation engineering fixture took 16.28 wall seconds for 128 seconds of teaching, 300 seconds of retention and the probe; its state was about 52 KiB with 904 contribution entries, and private memory about 19.3 MiB. The whole-batch budget is six wall hours, 3 GiB host private memory and 3 GiB originals. Startup requires 8 GiB commit and 34 GiB data-disk headroom; runtime reserves are 5/4/5/25 GiB for commit/RAM/C/E. A one-second guard requests pauses at complete boundaries. New death or incomplete state is preserved without blind replay.

Delivery requires independent saved-data arithmetic and state-chain verification, bilingual purpose–result–analysis–conclusion reports, and complete original-package readback through the unified research API. Selection of the second-layer experiment follows the actual outcomes of targets 2–4 and cost. Historical criteria, originals and the author's manuscript remain intact.

Preregistration design addition, 20:05 on 9 November: matched cue-omission controls increase the draft's 960 sequences to 1920. Subtracting only a preceding window could otherwise confound natural activity changes with cue effects. No formal registration, subjects or scientific results existed at this revision. Resource limits are unchanged; the independent N remains eight.
