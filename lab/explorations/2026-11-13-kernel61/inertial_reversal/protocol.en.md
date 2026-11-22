# R51m: why the reverse response to inertial input disappeared in 6.1

Preregistered design, 13 November 2026. The author requested this study after complete R51k delivery, provided its stopping rules permit continuation, and before R51l. It retains the four historical material blocks, seeds 930101–930104, and ordinary/facilitation configurations. It is a bounded causal investigation, not a new 48-source confirmation.

## Questions and expected outcomes

Historical E18 used continuous-memory/2. Its 144 bodily probes involving inertial information produced reverse process responses. Corresponding R51h probes on 6.1 all produced the taught direction. The author proposed that slow decay prevents transient connections from disappearing promptly. This study tests that account and examines input scheduling, signal thresholds, fatigue, inhibitory learning and context-dependent reception.

The targets are to reproduce the difference under aligned measurement, determine whether connection deletion is necessary for the historical reversal, test whether changing decay or raising the deletion threshold restores it, identify other causal influences on direction, and assess implications for subsequent revalidation. Taught, reverse and unmeasurable responses remain separate outcomes.

## Subjects and inputs

Reuse E18's exported bodily recordings and delivered input frames read-only. Each new subject receives the original 32 episodes of 0.6 s: 12 of one posture, 12 of the opposite posture, and 8 alternating episodes. Seed parity determines the original initial posture. Physical intensity is 0.3; paired anonymous A/B marker value is 0.5; an independent maintenance input has intensity 0.2 every 0.5 s. Teaching lasts 19.2 s, followed continuously by 1 s of retention. Values, arrival times, grouping and order are compared against historical exports. Historical subjects and evidence remain intact.

From each complete retention state, register two physical-probe copies and a matched blank copy. Each physical probe contains 0.4 s of actual sensory measurements without A/B, followed by observation through 5.6 s. Inputs are fixed physical replays and outputs are passive marker measurements. There is no trainable peripheral or claim of closed-loop adaptation.

The primary schedule reconstructs when each historical frame was queued from `source_policy.resolved_at_us`, using historical event IDs for same-time insertion order. Separate /2 and 6.1 controls prequeue all physical frames at the stage's start, followed by maintenance inputs, as in R51f/h. Both schedules have identical external arrival times and values, but may differ in the order of simultaneous external and internal events. Observation must not change either schedule.

## Registered comparisons

Use genuine /2, /3.1, /5.1, /5.3 and /6.1 implementations and saved identities. Comparisons between complete versions locate a transition; they do not isolate one operator. All within-version interventions use existing configuration, without modifying Core.

In addition to those five versions and two prequeue controls, use these ten conditions:

| Condition | Declared change | Question |
|---|---|---|
| /2 without edge deletion | `prune_weight=0` | Is deletion necessary for reversal? |
| 6.1 exponential decay | `decay_curve=exponential` | Contribution of the decay curve |
| 6.1 higher deletion threshold | Independent calibration below | Does faster deletion restore reversal? |
| 6.1 exponential plus higher threshold | Explicit two-factor combination | Curve–deletion interaction |
| 6.1 without strong-stimulus fatigue | `strong_fatigue_enabled=false` | Contribution of fatigue |
| /3.1 without strong-stimulus fatigue | Same switch | Candidate difference after /2 |
| 6.1 higher transmission threshold | `signal_threshold=0.004` | Weak transmitted signals; not an exact recreation of every historical gate |
| 6.1 without inhibitory learning | `inhibitory_learning_enabled=false` | Reinforcement caused by inhibitory transmission |
| 6.1 without sender thresholds | Both sender thresholds 0 | Contribution of terminating weak emission |
| 6.1 without reception matching | `context_mix=0` | Contribution of reception based on recent activity |

Each of the 17 configurations has four blocks, two facilitation settings, and full-sensory/joint-only conditions: 272 trained subjects. Primary /2 and 6.1 additionally retain dose-matched, shuffled-inertial and untrained groups, adding 48 subjects. Total: 320 subjects and 1600 teaching, retention and probe stages.

From primary /2 and 6.1 full-sensory/joint-only parents, separately disable inhibition or fast enhancement immediately before testing. These are 192 further stages: 32 parents × 2 interventions × 3 probes. Save complete pre/post intervention states and changed fields. Teaching references remain intact; test-time effects are not described as teaching effects. Overall, 1792 stages have 3584 initial/final states, plus explicit intervention-state records. Copies do not increase independent N.

Unless specified, 6.1 uses current defaults: inverse-logarithmic decay, deletion threshold 0.008, local deletion, and excitation/inhibition sender thresholds 0.004/0.002.

## Independent deletion calibration

Use seed 930198 and two anonymous task channels, without posture or A/B answers. Deliver a single paired stimulus of intensity 0.03, 0.1 or 0.3, then maintenance input on a separate channel. Observe for 1200 internal seconds, recording edge presence, weight and nodes each second. Use three subjects per version, /2 and 6.1. At each historical first disappearance time, obtain the corresponding 6.1 directed weights. Their median, multiplied by 1.0001 and bounded above 0.008 and below 0.25, defines one higher threshold for the entire study. Validate that single value once; formal response outcomes never select it.

If deletion times for at least two doses are within 0.5–2 times the historical times, call the condition approximately deletion-time matched. Otherwise report it as higher-threshold sensitivity, with matching errors. If no usable historical deletion or corresponding 6.1 weight occurs, use the preregistered 0.018 sensitivity value and explicitly report that matching failed. An inverse-logarithmic curve has no abrupt tail boundary, so empirical disappearance time defines the comparison.

Also derive the historical minimum weight bound over the 25.8 s experiment and inspect observed edge sets. Similar edge counts do not imply equal weights, fast enhancement, synaptic resources or inhibition. Deleting task channels or producing silence is not reversal recovery.

## Measurements and decisions

Record activation, inhibition, direct and associative activity, and read-only graph state every 100 ms. The primary process window is 0.6–5.6 s; 0–0.6 s is separate. Subtract the same-parent blank. A marker has a measurable direction when its excess activation peak exceeds 1e−5 and its integral exceeds the other marker by more than 1e−6. Otherwise classify the response as unmeasurable. Also report unsubtracted activity and the historical common window to expose sensitivity to measurement. This is the R51h rule; no peak time is selected after observing answers.

Each block has four full-sensory probes: two facilitation settings × two postures. A block reproduces the historical direction relation if at least three full-sensory probes are reverse and at least three joint-only probes retain the taught direction. A configuration restores that relation if at least three of four blocks qualify.

First complete /2 and 6.1 under both queue schedules. Historical-stream /2 must reproduce the old relation, and prequeued 6.1 must reproduce R51h's taught direction. Otherwise preserve the evidence and stop for a reproduction-apparatus problem. Streamed 6.1 and prequeued /2 are unconstrained experimental outcomes of the scheduling comparison.

If /2 retains reversal when deletion is disabled, reject the claim that timely connection deletion is necessary for the historical reversal. Recovery requires a real change relative to the same-version, same-schedule reference: at least three of four blocks must change from the taught to the reverse direction while retaining joint-only responses. A reversal already present in the reference is not a recovery. If a deletion-time-matched higher threshold meets that rule, support a causal contribution of deletion speed. If only the combined curve/threshold condition restores reversal, attribute it to that combination and report both individual contrasts. Changes from reverse to taught direction use the same three-of-four-block rule. Several effective conditions are reported separately rather than declared a unique cause. Loss of both response classes is nonspecific damage.

The independent units are four material blocks. Postures, facilitation settings and copies are nested observations. Report block-level integral differences, directions and structural changes; repeated probes are not independent significance tests. Negative results complete the corresponding target. Further separation requiring new Core rules becomes an explicit pending decision, not an automatic kernel change.

## Integrity, budget and delivery

Register and run only after R51k. Scientific hosts remain serial. Independent apparatus checks verify observation, complete save/restore and host pauses for each genuine version, as well as agreement with historical input exports. Formal sources do not tune measurement. Complete the four baseline schedule/version cells before further interventions.

Allow 2 GiB each for originals, archive and API readback, 128 MiB for analysis, plus 25 GiB free reserve; at most 2 h and 1 GiB private memory. Check commit/RAM/C/E reserves 5/4/5/25 GiB each second and pause at complete stages. Each stage has a 300 s host limit and 2000-node/20000-edge bounds. Preserve and report dead-host in-flight markers, inconsistent originals or observation effects; do not rerun, lower thresholds or erase evidence.

Deliver read-only recomputation, independent high-precision integral checks, explicit bilingual conclusions and complete API readback with pending = 0. Update R51 and the histories, separating original hypotheses, implementation facts, results and interpretation. A result that changes a key mechanism judgement is reported after safe completion under the standing authorization; otherwise the original campaign continues. Production Core, defaults, historical data and manuscripts remain unchanged.
