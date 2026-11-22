# Can threshold and resource adjustments restore prefix discrimination while preserving release-first transmission?

15 November 2026 · R51t9 · Research record `72caba0f-6820-5662-8d2b-ff5a693659df`.

## Conclusion

New configurations restoring prefix discrimination: **None**. Thirty-one new configurations completed two exchanged curricula, totaling 186 teaching and diagnostic stages, followed by eight copies observed without further stimuli. Twenty-four stages from four completed reference conditions were reused from verified originals.

**This study found no threshold or resource-supply condition that replaced pre-release screening.** With resource release still preceding the signal-magnitude check, lowering or removing connection thresholds, removing either or both node sending thresholds, accelerating resource recovery, and disabling depletion all failed to restore prefix discrimination. All 24 current-propagation conditions, three conditional historical-inhibition conditions and four high-threshold resource conditions passed 0/2 curricula. The previously successful reference with pre-release screening retained its recorded 2/2 outcome.

**Resource limitations and signal thresholds jointly affect transmission, but removing those restrictions was insufficient to recover the correct prefix relationships.** Faster recovery and disabled depletion markedly increased transmitted signals and connection weights, while the system continued to favor the same ending. The study therefore rejects the tested expectation that lower thresholds or sufficient resource supply alone would restore discrimination. For ThreeMind, the next improvement must preserve experience-dependent differences; increasing overall activity has not provided an effective solution.

## Purpose and expected result

The preceding study restored prefix discrimination in a specified combination by checking signal magnitude before releasing synaptic resources. The author proposed an alternative: resource depletion and signal thresholds may jointly suppress transmission, so lowering thresholds or increasing available resources might recover the same capability without that early check. The author also asked whether node sending thresholds contribute to the failure or prevent excessively long weak activity.

The preregistered criterion remained unchanged. One curriculum teaches A→B→C and D→B→E; the other exchanges C and E. Diagnostic cues are A→B and D→B. After B, the correct ending must have a peak activation more than 10⁻⁶ above the other ending. Both cues must pass for a curriculum to pass, and both curricula must pass for recovery. The question is whether A versus D changes the response following the same B. Increasing a single preferred ending does not meet that target. [Original protocol](protocol.en.md)

## Design

Each new configuration started with a new complete individual and underwent 212.2 internal seconds of continuous teaching with the original stimuli, background, intensities, order and intervals. The complete final teaching state was preserved. Separate AB and DB diagnostic copies were then created from it; each waited one second, received the first cue, received B one second later, and was observed for 15 seconds. Teaching and each diagnostic remained internally continuous. No trainable peripheral was needed: passive instruments recorded the process, and scoring answers did not drive the Core.

Activation, inhibition, direct activation and associative activation were recorded every 10 milliseconds, with peaks, integrals and final values retained. Teaching records captured task nodes, connections and resources every 100 milliseconds. The two exchanged curricula are two material blocks for mechanism localization; configurations, diagnostic copies and recorded points are not additional independent samples. The successful reference came from R51t8 and the other three references from R51t7. Their copied originals were hash-verified rather than rerun.

Two retention configurations were examined separately. `stable` uses stability retention and immediate novelty to connect this study to the previous successful combination. `default` uses the current 6.2 defaults of single-age inverse-logarithmic decay and arrival-window novelty. All new conditions preserve the order **release resources first, then check the connection signal magnitude**.

| Identifier | Meaning |
|---|---|
| g4, g04, g0 | Connection signal thresholds of 0.0004, 0.00004 and zero, applied to both excitation and inhibition in the main matrix |
| r8, r08 | Resource recovery time constants of 0.8 and 0.08 seconds |
| full | Depletion disabled, maintaining available normalized resources; utilization remains 0.5 |
| sources0 | Both node sending thresholds set to zero |
| exc0, inh0 | Only the excitatory or inhibitory node sending threshold set to zero |
| old | The registered research implementation of historical inhibitory propagation |

Unless stated otherwise, the excitatory and inhibitory node thresholds are 0.004 and 0.002. The node activation zeroing floor, `activation_floor=0.004`, was retained throughout. Setting sending thresholds to zero does not remove that floor. Resources are normalized to a total of one, so increased availability was implemented through faster recovery; disabling depletion provides a fully available upper-bound control. The total resource pool was not increased beyond one.

The original protocol specified 24 new conditions. None recovered discrimination, triggering the preregistered three historical-inhibition conditions. While the main study was running, four additional conditions were separately registered before execution: the previous 0.004 excitatory connection threshold combined with faster recovery or disabled depletion, using either current or historical inhibition. The registration preserves which main-study results were already known. This was a prospective supplement, not part of the initial preregistration. [Supplement](supplement-high.en.md)

## Connection thresholds and resource availability

Both blocks' primary margins are shown. A positive value favors the taught ending; opposite signs across AB and DB indicate a fixed preference for one ending. `stable-g4-r8` and `default-g4-r8` are reused controls.

| Configuration | Block 0: AB margin | Block 0: DB margin | Block 1: AB margin | Block 1: DB margin | Curricula passed |
|---|---:|---:|---:|---:|---:|
| stable-g4-r8 | 0.000997287395 | -0.000997331755 | 0.000997287395 | -0.000997331755 | 0/2 |
| stable-g4-r08 | -2.17158814e-05 | 2.17158814e-05 | -2.17158814e-05 | 2.17158814e-05 | 0/2 |
| stable-g4-full | -2.11953204e-05 | 2.11953204e-05 | -2.11953204e-05 | 2.11953204e-05 | 0/2 |
| stable-g04-r8 | 0.000875522492 | -0.000874152152 | 0.000875522492 | -0.000874152152 | 0/2 |
| stable-g04-r08 | -2.17134381e-05 | 2.17134381e-05 | -2.17134381e-05 | 2.17134381e-05 | 0/2 |
| stable-g04-full | -2.11953204e-05 | 2.11953204e-05 | -2.11953204e-05 | 2.11953204e-05 | 0/2 |
| stable-g0-r8 | 0.000879773595 | -0.000878396832 | 0.000879773595 | -0.000878396832 | 0/2 |
| stable-g0-r08 | -2.17134381e-05 | 2.17134381e-05 | -2.17134381e-05 | 2.17134381e-05 | 0/2 |
| stable-g0-full | -2.11953204e-05 | 2.11953204e-05 | -2.11953204e-05 | 2.11953204e-05 | 0/2 |
| default-g4-r8 | -0.000131848083 | 0.000131882899 | -0.000131848083 | 0.000131882899 | 0/2 |
| default-g4-r08 | 0.00874589989 | -0.00874447015 | 0.00874589989 | -0.00874447015 | 0/2 |
| default-g4-full | 0.0127457412 | -0.0127365377 | 0.0127457412 | -0.0127365377 | 0/2 |
| default-g04-r8 | -0.000201352708 | 0.000201366663 | -0.000201352708 | 0.000201366663 | 0/2 |
| default-g04-r08 | 0.0089477544 | -0.00894737245 | 0.0089477544 | -0.00894737245 | 0/2 |
| default-g04-full | 0.0124551951 | -0.0124466127 | 0.0124551951 | -0.0124466127 | 0/2 |
| default-g0-r8 | -0.000197755738 | 0.000197838752 | -0.000197755738 | 0.000197838752 | 0/2 |
| default-g0-r08 | 0.00894772269 | -0.00894734072 | 0.00894772269 | -0.00894734072 | 0/2 |
| default-g0-full | 0.0124551962 | -0.0124466138 | 0.0124551962 | -0.0124466138 | 0/2 |

## Node thresholds and inhibitory propagation

| Configuration | Block 0: AB margin | Block 0: DB margin | Block 1: AB margin | Block 1: DB margin | Curricula passed |
|---|---:|---:|---:|---:|---:|
| stable-g4-r8-sources0 | 0.000964316621 | -0.000964392811 | 0.000964316621 | -0.000964392811 | 0/2 |
| stable-g4-r08-sources0 | -2.17158792e-05 | 2.17158792e-05 | -2.17158792e-05 | 2.17158792e-05 | 0/2 |
| stable-g0-r8-sources0 | 0.000845845044 | -0.000845764978 | 0.000845845044 | -0.000845764978 | 0/2 |
| stable-g0-r08-sources0 | -2.17133384e-05 | 2.17133384e-05 | -2.17133384e-05 | 2.17133384e-05 | 0/2 |
| default-g0-r8-sources0 | -0.000215665648 | 0.000215741336 | -0.000215665648 | 0.000215741336 | 0/2 |
| default-g0-r08-sources0 | 0.00889847806 | -0.00889746931 | 0.00889847806 | -0.00889746931 | 0/2 |
| stable-g0-r8-exc0 | 0.000879692974 | -0.000879749957 | 0.000879692974 | -0.000879749957 | 0/2 |
| stable-g0-r8-inh0 | 0.000845845044 | -0.000845764978 | 0.000845845044 | -0.000845764978 | 0/2 |

| Configuration | Block 0: AB margin | Block 0: DB margin | Block 1: AB margin | Block 1: DB margin | Curricula passed |
|---|---:|---:|---:|---:|---:|
| old-g4-r8 | 0.0005585789 | -0.000558674848 | 0.0005585789 | -0.000558674848 | 0/2 |
| old-g0-r8 | 0.000645785359 | -0.000642123113 | 0.000645785359 | -0.000642123113 | 0/2 |
| old-g4-r08 | 0.00147122807 | -0.00146512201 | 0.00147122808 | -0.00146512202 | 0/2 |
| old-g0-r08 | 0.00114502424 | -0.00114496476 | 0.00114502425 | -0.00114496477 | 0/2 |
| pre-old-high | 0.000978372527 | 0.00273543383 | 0.000978372527 | 0.00273543383 | 2/2 |

Historical inhibition distributes its signal according to adjacent connection weights, uses its existing threshold, and does not consume the resource used by the modern excitatory pathway. Its threshold therefore does not become zero when the common connection threshold is changed. This is a declared propagation-method comparison, not a single-parameter adjustment. `pre-old-high` is the previously successful reference with pre-release screening; none of the new conditions includes that check.

## Separately registered high-threshold resource conditions

| Configuration | Block 0: AB margin | Block 0: DB margin | Block 1: AB margin | Block 1: DB margin | Curricula passed |
|---|---:|---:|---:|---:|---:|
| high-current-fast | 0.0114346328 | -0.0114705779 | 0.0114346328 | -0.0114705779 | 0/2 |
| high-current-full | -2.1252624e-05 | 2.12526243e-05 | -2.1252624e-05 | 2.12526243e-05 | 0/2 |
| high-old-fast | 0.0137035154 | -0.0146204742 | 0.0137035154 | -0.0146204742 | 0/2 |
| high-old-full | 0.018641978 | -0.0184946356 | 0.018641978 | -0.0184946356 | 0/2 |

These conditions use stability retention and immediate novelty with an excitatory connection threshold of 0.004. The current inhibitory connection threshold remains 0.0004. `current` and `old` denote current and historical inhibition; `fast` denotes 0.08-second recovery, and `full` denotes disabled depletion.

## Why more resources need not improve discrimination

Additional resources increased transmission and connection weights. The table describes teaching in block 0. Available resources were projected to each record's internal time, avoiding comparisons of caches updated at different times. The means summarize recorded connections in this apparatus.

| Stability-retention condition | Mean available resource at observation time | Mean recorded weight | Excitation transmitted | Inhibition transmitted | Curricula passed |
|---|---:|---:|---:|---:|---:|
| stable-g4-r8 | 0.136608 | 0.472276 | 38.518870 | 4.513275 | 0/2 |
| stable-g4-r08 | 0.414883 | 0.706054 | 317.929419 | 65.442367 | 0/2 |
| stable-g4-full | 1.000000 | 0.742688 | 434.557381 | 113.151890 | 0/2 |
| stable-g0-r8 | 0.131281 | 0.614454 | 103.655324 | 14.403356 | 0/2 |
| stable-g0-r08 | 0.414808 | 0.734814 | 536.517081 | 115.284326 | 0/2 |
| stable-g0-full | 1.000000 | 0.760258 | 693.969500 | 185.575165 | 0/2 |

Current transmission multiplies the offered node signal, effective connection weight and released resource fraction before applying the connection threshold. Slower recovery therefore makes otherwise identical offers and weights more likely to fall below that threshold. The author's proposed joint restriction has a clear implementation basis. However, increased resources strengthen both excitation and inhibition and alter subsequent learning. More transmission and better preservation of the prefix difference are distinct outcomes.

A calculation using the resource operator illustrates this interaction. With the study's 100-millisecond sending interval and utilization of 0.5, the fraction released after sustained repeated use is approximately 0.10484 with 0.8-second recovery and 0.41370 with 0.08-second recovery. To meet a connection threshold of 0.0004, the corresponding product before resource release must be approximately 0.00382 or 0.000967. This fixed-interval illustration is not an additional trained individual and does not replace the recorded process.

Retrospective read-only analysis also compared the time courses of the two endings' activation differences under AB and DB. The successful reference diverges toward different endings after B. Several unsuccessful conditions produce almost overlapping cue trajectories: more signal is transmitted, but insufficient prefix-specific difference remains. This analysis explains the existing result without changing the original peak criterion. The figure and full measurements are stored as `figures/prefix-process-comparison-v2.png` and `process-contrast-v2.json` in the data directory.

## Node thresholds, activity after stimulus cessation, and cost

| Condition | Teaching and diagnostics, both blocks (wall seconds) | Curricula passed |
|---|---:|---:|
| stable-g0-r8 | 102.763 | 0/2 |
| stable-g0-r8-exc0 | 99.616 | 0/2 |
| stable-g0-r8-inh0 | 130.793 | 0/2 |
| stable-g0-r8-sources0 | 131.452 | 0/2 |

These durations include the same process recording and complete-state saving. The current-propagation conditions use the native backend, allowing comparison of their observed costs. Historical inhibitory research conditions use Python, so their wall times cannot directly rank the propagation mechanisms' intrinsic performance.

| Condition | Curriculum block | Internal seconds observed | First all-zero activation sample (seconds) | Final life label | Maximum final activation | Final connections | Wall seconds |
|---|---:|---:|---:|---|---:|---:|---:|
| stable-g4-r8 | 0 | 33.300000 | 1.0 | dead | 0 | 939 | 0.464 |
| stable-g4-r8 | 1 | 33.300000 | 1.0 | dead | 0 | 939 | 0.465 |
| stable-g0-r08-sources0 | 0 | 2.900000 | 2.9 | dead | 0 | 1466 | 0.316 |
| stable-g0-r08-sources0 | 1 | 2.900000 | 2.9 | dead | 0 | 1466 | 0.284 |
| default-g4-r8 | 0 | 300.000000 | 1.0 | active | 0 | 1268 | 0.366 |
| default-g4-r8 | 1 | 300.000000 | 1.0 | active | 0 | 1268 | 0.335 |
| default-g0-r08-sources0 | 0 | 2.600000 | 2.6 | dead | 0 | 1466 | 0.273 |
| default-g0-r08-sources0 | 1 | 2.600000 | 2.6 | dead | 0 | 1466 | 0.264 |

Each observation copy continued from its complete teaching state with no further external stimuli. The table separates elapsed internal time, the first all-zero activation sample, and the software lifecycle label. The exact cessation time between samples was not measured at higher resolution; the first all-zero sample is not treated as the precise final activity time.

**Removing thresholds did not produce hundreds of seconds of sustained transmission in these comparisons.** Both original retention references had zero node activation at the one-second stimulus-free sample, with no subsequent increase in transmitted-signal totals. The combination of zero connection and node thresholds with 0.08-second recovery still had activation at one second, followed by zero activation at the final samples of 2.9 seconds for stability retention and 2.6 seconds for default retention. This comparison changes both thresholds and recovery, so its conclusion concerns that combination.

**A separate lifecycle-maintenance defect was identified.** The default condition retained the active label at 300 seconds although activation and further transmission had already ceased. Its complete final state retained two entries in the active set, with cached activations of approximately 0.000786 and 0.0000463, both below the 0.004 zeroing floor, and neither activation-expiry nor sending timers. Both Python and Rust permit a small positive input to add a node to the active set while scheduling activation expiry only above the floor. Once sending stops, those entries can remain until an unrelated event settles them. The stability reference changed its life label to dead only at 33.3 seconds, also later than actual transmission cessation.

The software life label is therefore invalid as a measure of actual activity duration in this study. Stimulus-free conclusions use recorded activation and cumulative transmission, while prefix scores continue to use the saved activation processes. Experiments relying on survival duration or input handling after death require this local maintenance gap to be corrected and its effects checked first. Original states and labels were preserved; no kernel was silently repaired and no individual was rerun.

## Biological motivation and the next decision

Neuronal firing thresholds have a biological basis and can depend on membrane-potential history and ion-channel states. ThreeMind's threshold on a continuous activation variable is a specific computational rule whose effect is assessed by the comparisons above. [Platkiewicz and Brette, 2010](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1000850) The role of release and recovery in short-term depression motivated treating recovery speed as a separate experimental factor. [Tsodyks and Markram, 1997](https://pmc.ncbi.nlm.nih.gov/articles/PMC19580/)

These results do not support lowering the 6.2 default thresholds or disabling depletion: neither restored the target capability, and removing the inhibitory node threshold increased observed computation cost. The immediate recommendation is to complete local lifecycle-expiry handling, then investigate whether resource consumption per send should depend on the actual signal amount. The current operator deducts utilization multiplied by available resources; weak signals invoke the same release operation without scaling that fraction by signal amplitude. This is an implementation fact established from source, not a demonstrated cause of prefix failure in this study.

A concrete next candidate would make the released fraction vary continuously with the offered signal: weaker sends consume less and stronger sends more, retaining release-first ordering. It should be compared with the current operator and the successful pre-screening reference. Such a rule need not anticipate whether the later threshold will be passed. This candidate has not been implemented; its formula and recovery target should be fixed before a new study. The present study's negative conclusion is complete. The cited biological papers are retained as sources of motivation for subsequent manuscript revision.

## Verification, resources and evidence

Python and Rust were compared for 24 current-propagation configurations using independent apparatus encodings. The three historical-inhibition conditions use the same isolated Python implementation; they are not three additional Rust comparisons. Observation, saving and restoring, host pauses, and advance partitioning passed their checks. Read-only verification covered 436 complete initial/final states and 140 diagnostic processes. Expected answers were independently derived from the exchanged curricula for 140 checks. The maximum arithmetic discrepancy was 2.78e-17.

New formal computation and stimulus-free observation totaled approximately 74.42 minutes. Peak private memory across the three guarded runs was 592.42 MiB. Minimum available commit/RAM/C-drive/E-drive capacity was 13.82/12.51/8.79/61.63 GiB. Data files occupied 255.90 MiB logically before publication packaging; this is not a measurement of NTFS allocated storage. The delivery receipt records the final compressed archive size. There was no resource pause, simulation rollback or incomplete state left by a dead host. The lifecycle-label problem is separately recorded in `tail-status-audit-v2.json`, with the earlier analysis retained; successful file and arithmetic verification does not erase that measurement defect.

Original states, processes, inputs, frozen files and recomputed analyses are stored outside Git at `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-resources62-v1`. Verification tools are `audit_resources.py` and `audit_supplement.py`, with the combined receipt in `final-audit.json`. Full archive readback and research completion are documented in `publication/completion.json`; a small repository copy is kept as `delivery.json`. Production kernels, defaults, historical subjects and reports, and the manuscript are unchanged. Comprehensive replication remains paused.
