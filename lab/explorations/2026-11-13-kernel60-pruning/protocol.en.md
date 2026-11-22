# R50: A paired quick validation of the 6.0 deletion threshold

Preregistered on 13 November 2026. The author authorized testing 0.018 and adopting it as the 6.0 deletion default if suitable. Historical kernels, saved individuals and the global kernel choice remain unchanged.

## Question and decision

Can raising prune_weight from 0.008 to 0.018 remove weak, one-off traces without damaging responses learned through repetition, spaced review, strong stimulation or novelty? The candidate was selected retrospectively from R47b; its 48 origins are not new validation observations. This study uses eight new independent origins to make a bounded default-parameter decision.

Both arms use genuine 6.0 fixed-function addressing, inverse-logarithmic decay, a 30-internal-second scale, continuing reinforcement age, disabled retention growth/relaxation and dormancy, enabled signal threshold 0.0004, disabled weight gate, and address-based in-flight delivery. Only prune_weight differs.

## Subject and procedure

Reuse the R47 anonymous stimulus adapter and passive temporal instrument. This local preparation has no trained reader, body or optimizer. Preserve the complete Core, random state, channel codes, stimulus log, background schedule and phase. It measures connections and responses rather than training an action or language adapter.

Freeze seeds 261113100–261113107, random anonymous codes, dose multiplier 0.85–1.15 and stimulus phase. Both arms use identical materials. Each history, delay and cue-omission condition develops continuously from birth in its own cohort; no per-question restoration. All observations sharing one origin are paired, not additional independent samples.

R47 courses remain unchanged: weak stimulation 0.08 once; eight 0.4 pairings at seconds 120–127; eight spaced pairings at 16, 17, 19, 23, 31, 47, 79 and 127 seconds; strong stimulation 0.4 with intensity parameter 2. These courses end at second 128. The novelty course pairs the cue with the other output, then with the target after 50 or 75 milliseconds; it ends at second 1. Apply the origin's dose multiplier. Opposite histories pair the cue with output 0 or 1. An independent background channel receives 0.2 every 0.5 seconds.

Use independent first probes at 1 second and at 30 seconds for weak stimulation, or 300 seconds for the other courses. The cue arm receives a 0.8 cue; the matched omission arm receives none. Record a one-second baseline and response, each with twenty frames of activation, inhibition, direct activation and associative activation. Subtract baseline, cue omission and opposite histories to obtain a 160-dimensional experience-specific response. Total: 8 origins × 2 thresholds × 5 courses × 2 delays × 2 histories × 2 cue conditions = 640 continuous sequences. Novelty is analyzed separately.

This fixed paired-stimulation assay has no answer-based error correction. The final results cannot change its curriculum. Spaced review is an explicit course, and every endpoint is an independent first test.

## Frozen acceptance rules

1. Valid apparatus: engineering-source Python/Rust agreement; observation and complete restoration preserve state; formal file hashes, continuous chains, schedules, identities and the single configuration difference all verify. Invalid measurement blocks a default change.
2. Weak-trace removal: both thresholds retain the two target directed connections at 1 second in at least 6/8 origins. At 30 seconds, the candidate has no target connections in either history in at least 6/8 origins, exceeding the baseline count. Its response RMS is at most max(0.0001, 10% of the same origin's baseline-arm 1-second RMS) in at least 6/8 origins.
3. Retention: for each of massed, spaced and strong courses, at least 6/8 candidate origins retain both target connections and a response RMS above 0.0001 at 300 seconds.
4. Preserve baseline expression: for each of these courses and novelty, compare arms separately at 1 and 300 seconds. Every origin must have difference RMS at most max(0.00001, 10% of baseline RMS). When baseline RMS exceeds 0.0001, cosine must be at least 0.98 and candidate RMS at least 90% of baseline. The candidate must retain at least as many target connections as baseline in each history. Novelty is tested for added harm, without imposing an absolute retention level not established by earlier evidence.
5. Describe cost: alternate arm order by origin; report wall time, memory, complete-state size and connection counts. No whole-system speed claim follows from this small preparation. Resource exhaustion causes a complete-boundary pause.

Adopt 0.018 only if every rule passes. Otherwise retain 0.008 and identify the affected course. No post-result threshold revision or extra origins. Report denominators, paired differences and Wilson intervals; eight origins do not establish a universal optimum. Historical R47 expression criteria are auxiliary, not replacements for these goals.

## Resources and delivery

Serial native host; originals at most 1 GiB, private memory 1 GiB, wall budget two hours. Check each second and pause only at complete boundaries; reserve commit/RAM/C/E = 5/4/5/25 GiB. Startup requires commit ≥8 GiB and E ≥34 GiB. Preserve death or orphan in-flight evidence without replay. Use the existing research API for registration and full archive readback, without starting old queue workers. Store originals in E:/ThreeMindData/experiments/2026-11-13-kernel60-pruning/quick-v1.

Deliver bilingual conclusions, independent arithmetic/continuity checks, manifests and verified API readback before any conditional default change. If adopted, verify Python/Rust/API defaults, historical implementations and saved-state compatibility. Local commit only; no push.
