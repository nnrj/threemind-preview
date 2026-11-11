# M2 sampling calibration and interpretive correction: unread is not never active

Around04:25 on16 October2026;post-hoc instrument calibration;[prospective calibration scope](sampling-calibration.en.md),commit`1d46af8`.This supplements interpretation without changing M2's original primary endpoint,scores,originals or first report.

**All65 instrument-replay copies exactly matched their original final whole-state hashes.All64 lives with zero original50ms response but nonzero associative fields showed brief activation on a1ms grid.** One additional positive instrument reference also matched.No independent learning origins were added,and originally unread answers did not receive credit.

M2's initial statement that60s S retained connections/associative input but had zero fixed output therefore applies to **the original50ms observation/readout grid**.It cannot mean activation was zero throughout the entire test,or independently prove evocation without any activation.The original0.5–1.5s primary negative and0.5s first response remain unchanged.

## Why the grid missed the signal

Native`local_shared.rs`adds arrivals to activation and associative fields.Activation then decays and is zeroed below its floor;associative persists until cleared at the next emission.The fields have different temporal support.Here floor=0.004,tau=0.3044102343s.An isolated peak a reaches the floor after`tau×ln(a/floor)`.

A representative60s S peak arrived110ms after the cue,a=0.004052929762.The formula gives approximately4.00167ms to the floor.The original100ms observation preceded arrival;150ms followed disappearance,while associative could still persist.Another teaching-order peak was only0.004003203113,about0.244ms to the floor;the1ms grid captured one point.Source-derived timing agrees with replay.This is not a newly fitted universal forgetting law.

![Dense readings and original grid](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-sampling-calibration-v1/figure-v1.png)

| Selected original condition | Copies | Absolute dense peak | Nonzero grid interval,ms after cue |
| --- | ---: | ---: | --- |
| 1s H weak X | 16 | 0.004072102–0.004262994 | 110–115 or110–129 |
| 1s H equal-per-channel joint | 16 | Same | Same |
| 1s S weak X,original-zero subset | 8 | 0.004343347 | 110–135 |
| 1s S equal-per-channel joint,original-zero subset | 8 | 0.004343347 | 110–135 |
| 60s S strong X | 16 | 0.004003203–0.004052930 | Only110 or110–114 |
| 1s H strong X positive instrument reference | 1 | 0.008525988 | 110–340 |

Grid intervals are not confidence intervals for exact continuous lifetimes;sub-millisecond peaks still require event-time/formula interpretation.The64 cases are all eligible items selected post-hoc from original measurements,not dense recertification of every other life among640.They are neither new independent N nor a new accuracy denominator.

## What is and is not resolved

- All65 final whole hashes match,including original50ms recent activity,actuator,Core,learning state,RNG and input order;extra readings are separate.This supports nonperturbation of these trajectories without dropping disagreeing fields.
- All original M2 configurations had`energy_simulation_enabled=false`;actual energy scarcity cannot explain this batch.Ecological energy research remains possible,but cannot retrospectively explain these negatives.
- This establishes sampling omission and field timing,not a complete explanation of retention/retrieval differences or independent contributions of inhibition,short-term synaptic state,retention rules or cue composition.
- Failure of the fixed reader to sustain expression at registered times remains a real functional limitation.Future protocols should separate event-locked peaks,duration/integrals and behavioral endpoints.Post-hoc maxima must not replace original test scores.

## Integrity,cost and evidence

Copies came from preserved whole pre-cue states and replayed only the original2s in separate paths.Original individuals were not rewound;E69 was untouched.65 copies total130s of explicitly declared instrument replay,not new learning scores.There are2,000 extra readings per copy,130,000 total.All65 whole finals match;no STOP/orphaned in-flight unit,pending0.

Host elapsed35.90s includes persistence/API;peak private memory67.01MiB.Pure Core timing was not isolated.Prepublication inventory:416 files/unique files,logical and deduplicated logical5,207,801bytes,file-stream allocation5,992,704bytes,no duplicate links.Subsequent archives/downloads and directory/MFT/database overhead are excluded.

[Original work](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-sampling-calibration-v1).Project`114f4f75-980b-4d79-a60e-228ea3409ecf`,record`201e43f1-1101-5605-aa64-47e58a16a9df`.Source pre/final states,dense final states,extra trajectories,source hashes,lineage,software fingerprint,analysis and figure remain preserved.API archive-readback closure is established by`publication/final-verification.json`.Assistant review is not external replication.

Recompute with`sampling_calibration.py analyze --work <originals>`:it only reads saved states/trajectories,retains identical analysis-v1 and rejects changed overwrites.Do not rerun`run/register`.New scientific materials and remaining M3 criteria proceed under separate protocols;the larger M1/M2/M3 questions remain open.
