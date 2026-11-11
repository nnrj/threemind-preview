# R47a: retention, expression and forgetting with four /5.3 curves

11 November 2026; prospective exploratory mechanism study under the approved [5.3 plan](../../../docs/en/plans/kernel53.md). The question is which single-age decay curve preserves repeated and strong experiences, expresses a history-specific temporal response after delay, and forgets weak transient input. Personal Transformer joint development, correction, reversal and relearning are a separate second layer that must precede a task-default decision. This instrument does not substitute for that layer.

## Subjects and comparisons

Eight independent birth origins use seeds 261111100–261111107. Each origin has a frozen anonymous channel mapping, amplitude multiplier drawn from 0.85–1.15, and timing offset. The four curves are exponential, power law, inverse logarithmic, and power law followed by an exponential tail. H=30 internal seconds, A=10, age is retained after reinforcement, and timescale growth/relaxation are disabled. Other options use the initial /5.3 configuration. Every condition and delay cohort develops continuously from its own birth. Matched histories and cue-omission conditions share an origin and do not increase independent N.

Eight origins × four curves × nine courses × four delays × two histories × cue present/absent gives 4,608 sequences. Six courses use channel amplitudes 0.08 once (weak), 0.4 once (ordinary), 0.8 once (high dose), 0.4 once with overall intensity 2 (strong), 0.4 eight massed presentations, or 0.4 eight spaced presentations. All amplitudes receive the origin multiplier. Massed times are 120–127 s; spaced times are 16, 17, 19, 23, 31, 47, 79 and 127 s; single presentations occur at 127 s. Strong and high-dose courses have equal actual input drive. A seventh course retains the strong input while setting intensity_gain=0 at birth. These courses end at 128 s.

The remaining two courses use the previously checked R46b connection-arrival novelty arrangement: cue and alternative output first, then cue and target output 50 or 75 ms later. Default arrival gain is compared with local_novelty_gain=0; teaching ends at 1 s. This specifically tests connection-arrival novelty gain.

History 0 pairs the cue with out0; history 1 pairs it with out1. Core receives only anonymous numerical channel stimuli. The scoring history, file names and trial identities never enter Core. An isolated background channel receives 0.2 every 0.5 s, separately from task packets. Every graph measurement verifies absence of background-to-task connections.

## Measurements and decisions

First cue tests occur 1, 30, 60 or 300 internal seconds after teaching, in separate continuous cohorts. Each test records a one-second baseline and a one-second response at 50-ms intervals: 20 frames of activation, inhibition, direct activation and associative activation. Complete states and all frames are saved. The instrument is fixed; there is no fitted reader, brightest-node selection or retrospective window selection.

Flatten the two outputs × four fields × 20 frames. Within each history, subtract baseline from response and subtract the corresponding cue-omission contrast. Subtract the history-0 vector from history-1. A root-mean-square magnitude above 1e-4 is detectable. Expression is retained at 300 s when its cosine similarity to the 1-s vector is at least 0.8 and its RMS is at least 10% of the early value. An undetectable early response fails this target and does not remove an origin from the denominator. Each target requires at least six of eight origins.

| Target | Preregistered expectation | Scientific answer |
| --- | --- | --- |
| S | Both directed cue–target connections survive at 300 s, separately for massed, spaced and strong courses; at least 6/8 for each | Does the curve preserve these learned connections? |
| E | Each of those three courses meets the temporal-expression criterion in at least 6/8 | Can the retained experience still be expressed? |
| W | Both weak-course target connections are absent at 30 s in at least 6/8 | Does the curve forget weak transient input as intended? |
| G | Immediate mean target-edge weight increases by >1e-8 with strong gain versus identical input with gain off, and with arrival novelty gain versus gain off; each at least 6/8 | Are the two declared gain mechanisms effective in /5.3? |
| F | For target edges remaining at 300 s, the declared curve and current age predict weight below deletion threshold after another 30 days without reinforcement, in at least 6/8 for each retention course | Does the conditional tail meet this finite-retention target? |

Judge S/E/W/G/F separately. Only curves satisfying S/E/W/F become candidates for the combined instrument goal; none may qualify. Do not rank curves by a post hoc sum of targets. F is an analytic prediction conditional on no further reinforcement, not an actual 30-day cultivation. Thirty days is this study's operational goal, not a human-memory constant. Report all denominators, effects and binomial intervals. Exploratory findings are not confirmatory significance claims.

Valid negative results complete normally. Answer leakage, background/task connections, inconsistent restoration, observation-induced advancement or unverifiable originals invalidate measurement and halt the batch after preservation. New death or orphaned in-flight states must not be replayed. A subsequent confirmation uses 48 fresh origins and separate material after power planning and protocol freeze; exploratory data stay separate.

## Evidence and host limits

Use the isolated genuine Rust /5.3 release module, checked against Python. Teaching and first testing form separate complete boundaries storing Core, mappings, inputs, windows and cursor. No trained peripheral is hidden in this local apparatus. Check host resources every second: retain 5/4/5/25 GiB of commit/RAM/C/E capacity, private memory ≤1 GiB, host time ≤2 h, originals ≤3 GiB. Startup requires ≥8 GiB commit headroom and disk allowance for three evidence copies plus reserve. Pause only at complete boundaries. Observation and saving do not advance time. Old experiments remain untouched.

After instrument validation, register and read back both protocols verbatim before a single launch. Freeze source, configuration, cases and binary hashes. Delivery requires independent arithmetic review, explicit bilingual scientific conclusions, complete archive download through the research API and pending=0. Preserve failed attempts and dated revisions.
