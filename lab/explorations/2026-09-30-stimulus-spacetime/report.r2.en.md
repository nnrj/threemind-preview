# Stimulus intensity, backgrounds and physical references: results

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-09-30. Project **2026-09-30 刺激强度、背景与物理参照**, `36029e2c-2f4c-4f21-9aa5-376b0701c044`.

**Independent random inputs were not forced into the existing graph. Weak connections formed by one joint observation naturally disappeared. Grouping and physical sample order changed learned structures and subsequent responses.** These outcomes use the existing kernel; no dynamical rule was added to obtain them.

260 original-design instances, four retention-extension instances and 31 preserved observer-registration failures: 295 new instances in total. Every database checkpoint was read back and matched local state. Aggregate simulation wall time: **134.68 seconds**, excluding development, database and reporting time. Before publication, local evidence was about 18.83 MiB and database growth 72.41 MiB. Account use increased 64%→65%, including shared work. Old experiments were untouched.

## Primary readout

Descending activation at the activity reader's **pattern-convergence decision** remained primary. Of 100 correctly registered cued probes, 58 detected a converged pattern and 42 did not. Counts by family: background 2/24, intensity/history 28/36, physical references 28/40. This is not accuracy. Some convergence continues prior training activity, so exact no-cue clones and full trajectories are essential. No-cue runs without envelopes do not receive fabricated windows. Legacy stable-convergence outputs remain available.

## Background connectivity and forgetting

Each background condition followed the same two-node trained network. Directed-edge counts after 48 background samples, averaged over two seeds (counts match across presets):

| Source | Total edges, including original two | Cross-links to original network |
|---|---:|---:|
| Fresh single channels | 2 | 0 |
| Fresh two-channel groups | 98 | 0 |
| Twelve random groups repeated four times | 26 | 0 |
| Fixed channels, random amplitudes | 4 | 0 |
| Existing synthetic field | 185 | 0 |
| Real host telemetry replay | 1376 | 0 |

Single independent channels did not create additional edges; joint pairs formed separate connected fragments. No source-tag deletion or learning prohibition was used. Telemetry repeatedly co-observes multiple metrics. Its 0.2 intensity is a multiplier, not a per-frame L1 cap: cumulative dose was about 44.22 versus 9.87 for two-channel random input. Dominant background ranking therefore does not demonstrate forced attachment or clamping. A future comparison should match dose and channel count explicitly.

Without further input, models died before the 80-second pruning grace period and retained their snapshots. Four prospectively registered extension clones received one unused independent channel at 0.2 every 0.5 seconds for 120 seconds. All went from **98 to 2 edges**: 96 once-observed weak edges disappeared approximately **57.6–68.4 seconds after background stopped**, while the two repeatedly reinforced edges persisted. The independent support channel did not attach to them. Only the original two nodes plus that support node remained. This demonstrates differential retention and natural removal; it motivates, but does not separately establish, forgetting-based attention. Structural forgetting occurs much later than activation fading. Deletion resolution was 0.1 s; still-present edges are right-censored and pre-existing edges are not assigned false birth times.

## Intensity and history

After one second, total directed-edge weight was 0 for untrained, about 0.344 after one intensity-4 event, and 0.934 after ten intensity-1 events. Repetition also delivered more dose, so this does not establish better dose efficiency. After repeated history, a 0.2 cue produced converged candidates containing both channels; the same weak cue after no history or one strong event did not. History changes response. No-cue clones also retained activity in the second channel: paired trajectories showed additional indirect differences around 0.004–0.008, rather than justifying attribution of all second-channel activity to recall. Stronger cues did not produce weaker overall responses in this condition.

Equal-drive witnesses confirm the existing formula distinction. Amplitude 1 × intensity 1 and amplitude 0.25 × intensity 4 both produced total received/activated amounts 1.8 across two nodes, but the latter added 0.45 extra consolidation; at 100 ms total weights were about 0.216 versus 0.322. This is an explicit intensity term, not a physically equivalent callus/transduction mechanism. It remains preserved for future comparison with more basic local processes.

## Physical references

Complete, split and shuffled controls matched per-channel dose and timestamps in all eight groups. Removing proprioception intentionally reduced its dose; that contrast alone cannot identify temporal perception.

| Scene and condition | Edges | Pattern convergence, two seeds × two presets |
|---|---:|---:|
| Cart, complete | 6 | 4/4 |
| Cart, no proprioception | 2 | 4/4 |
| Cart, split | 0 | 4/4 |
| Cart, shuffled | 6 | 0/4 |
| Cart, untrained | 0 | 0/4 |
| Pendulum, complete | 60 | 4/4 |
| Pendulum, no proprioception | 8 | 4/4 |
| Pendulum, split | 0 | 4/4 |
| Pendulum, shuffled | 60 | 4/4 |
| Pendulum, untrained | 0 | 0/4 |

Complete versus shuffled ordinary-preset total weights were 39.50 versus 37.91 for the pendulum and 0.514 versus 0.465 for the cart. Identical total input values do not guarantee identical structures or responses. However, split inputs can converge with no edges: local node histories and decay explain part of the outcome. The complete-pendulum cue arrived at an already saturated target, and cued/no-cue sampled activation trajectories matched. Subsequent activity cannot all be assigned to that weak cue; receipt accounting was still retained.

Shuffling also changes final samples and residual state. A dedicated sequence-memory experiment should match final segments and delays before attributing a difference to retained ordering. These passive scenes have no actuators, so no behavioral-adaptation claim is made, nor is subjective time established.

## Facilitation and next steps

The 1-second facilitation preset produced nearly identical edge counts and approximately percent-level pendulum weight differences, without a general convergence gain. In telemetry, ordinary settings converged while facilitation settings did not. Retain facilitation as a research option, not a universal replacement default. Arrival-window novelty stayed unchanged and its counters were recorded separately.

Promising next tests: physical sequence relationships with matched endings; background dominance with matched total drive; a more fundamental local account of strong-input consolidation, preserving today's equal-drive witnesses. Current peripheral tools can distinguish raw measurements, anonymous drive, received touches and network response without first modifying Core.

## Tooling corrections and evidence

31 initial cued probes used `registered-probe`, classified as ambient and therefore not opening default windows. They remain preserved. Separate `manual-registered-probe` clones reproduced **31/31 final Core hashes exactly**. Missing windows are not part of the 42 nonconverged results. Derived analysis corrected undefined saturation for empty graphs and added matched-time no-cue differences; absent nodes in complete sampled states count as zero activation, but unobserved intervals are not filled. Earlier analysis files remain; `analysis-v3.json` and `summary-v3.csv` are final for the original design. Design, amendments, inputs, all 295 states, full trajectories and reports are archived together.


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
