# Restoring persistent activity with inhibition retained and locating prefix-discrimination failure

14 November 2026 · R51t2 · 110 scientific stages in two exchanged curriculum blocks.

## Scientific conclusions

**Low-amplitude persistent activity can be restored in 6.1 while retaining inhibition.** After identical completed teaching, shortening the inhibition time constant from 0.2321 to 0.05803 seconds preserved activity for 300 seconds in both blocks and throughout the following 15-second observation. The maximum task-node activation in this final window ranged from 0.0604 to 0.0812, far below the activation ceiling. This rejects the explanation that recovery necessarily requires disabling inhibition or widespread saturation.

**Prefix discrimination was not restored.** None of the 11 bounded configurations correctly distinguished both A-B and D-B. Process recordings show that the A/D activity difference still existed before B arrived, but did not produce the corresponding change in the relative strength of the two endings. The question is therefore how retained prefix information influences the subsequent choice, rather than whether all prefix activity has disappeared.

## Purpose, expectations and methods

R51t1 found shorter persistent activity in 6.1 than in early kernels. Disabling inhibition after teaching preserved activity for 300 seconds, but at high activation. This batch tested whether milder existing configurations could restore activity and further localized prefix failure. Kernel formulas, production defaults and historical experiments were unchanged.

The persistence comparison reused two complete R51t1 teaching states at 81.2 internal seconds. Each research copy inherited Core, random state, input bus and observer history. Declared configuration changes occurred after teaching, followed by 300 seconds with the original fixed background and no new task cue. The apparatus retained the historical resource condition: depletion disabled and facilitation enabled. Shortening the inhibition time constant makes existing inhibition dissipate faster under the unchanged rule.

Activation, inhibition, direct and associative activity were recorded every 10 ms. A block passed if the maximum activation among the five task nodes exceeded 1e-6 at every sample in the 15-second window after 300 seconds. Both blocks had to pass. Task-node observations reaching activation 0.95 were counted separately as saturation. The completed default-6.1 reference, whose last positive sample was at 28.2 seconds, was reused without rerunning it.

Prefix experiments used two curricula that exchanged C/E endings: A-B-C and D-B-E, or their exchanged counterparts. Each configuration applied from birth during 212.2 seconds of teaching. Separate registered diagnostic copies then received A-B or D-B after a one-second wait, with B one second after the prefix. Both taught-ending minus alternative peak differences had to exceed 1e-6. These were paired causal diagnostics, not ordinary examinations with per-question restoration.

## Persistence results

| Inhibition gain | Time constant relative to reference | Persistence at 300 s | Final-window maximum task activation |
| ---: | ---: | ---: | ---: |
| 0.24 | 1/2 | 0/2 | 0; last positive sample 47.5 s |
| 0.24 | 1/4 | 2/2 | 0.0604–0.0812 |
| 0.06 | 1 | 2/2 | 0.0795–0.1069 |
| 0.06 | 1/2 | 2/2 | 0.1434–0.1927 |
| 0.06 | 1/4 | 2/2 | 0.2416–0.3248 |
| 0.015 | 1 | 2/2 | 0.3181–0.4275 |
| 0.015 | 1/2 | 2/2 | 0.5736–0.7709 |
| 0.015 | 1/4 | 2/2 | 0.7440–1.0000 |

All recovered conditions except the last had no task-node observations reaching 0.95. In the last condition, about 9.99% reached that level. The denominator is five task nodes multiplied by observation times, not the fraction of time during which the entire network was saturated.

With inhibition gain 0.06 and half the original time constant, enabling depletion, disabling facilitation, or doing both prevented recovery. Last positive samples occurred at 1.9, 3.7 and 1.9 seconds, respectively. These results agree with the preceding interventions: propagation, inhibition and short-term resources jointly determine persistence; preserved connections alone do not fix activity duration.

**Recovery amplitude can be adjusted without pushing activity to its ceiling.** The subsequent functional test selects the quarter-time-constant condition under the frozen rule: original inhibition gain retained, few changed fields, and minimal saturation. Selection was frozen before new formal material was run.

## Prefix results and process localization

The 11 configurations covered a finite combination of novelty timing, transmission thresholds 0.0004/0.004 and receptive context mixing, plus immediate-novelty variants disabling inhibitory learning, reducing inhibition gain, shortening its time constant or disabling the fast weight trace. All scored 0/2 on bidirectional recovery. Some changed the preferred ending, but the choice did not switch appropriately with A/D.

Immediate novelty with inhibitory learning disabled had the smallest worst-direction deficit. In block 0, its correct-direction peak margins were approximately −2.163e-5 for A-B and +2.163e-5 for D-B. One correct direction and one incorrect direction do not constitute recovery.

Ten milliseconds before B, the A-over-D activation advantage after A was 0.017738, and the D-over-A advantage after D was 0.017748. At 100 ms after B, C-minus-E was −1.14929e-5 and −1.14953e-5, respectively: both favored E. Exchanging the curriculum made both favor C. All 11 configurations showed the same qualitative feature: the prefixes remained distinguishable, but ending preference did not change with the prefix.

This excludes complete disappearance of prefix activity before B as the explanation for failure in this material. Immediate novelty, the tested thresholds and weaker inhibition did not restore the appropriate bidirectional ending choice. R51t4 uses new encodings, continuous review and bounded correction to test the candidates; configuration selection on old material is not independent confirmation.

## Meaning for ThreeMind and the next decision

The experiment provides a way to restore persistent activity while retaining inhibition, enabling a direct comparison of duration, selectivity and decision benefit. Its positive conclusion is recovery of low-amplitude persistence; prefix recovery is a clear negative. The registered delayed-choice experiment determines whether the recovered activity is useful.

Rao and colleagues found that GABA_A blockade disrupted existing spatial tuning in many monkey prefrontal neurons, while creating tuning in some previously untuned neurons. This motivated measuring selectivity alongside activity strength and duration. [Rao, Williams and Goldman-Rakic, 2000](https://pmc.ncbi.nlm.nih.gov/articles/PMC6774140/). Compte and colleagues studied the organization of excitation and inhibition in a spatial working-memory model. [Compte et al., 2000](https://www.cns.nyu.edu/wanglab/publications/pdf/compte2000.pdf). These papers informed design; the numerical ThreeMind conclusions come from this experiment.

## Verification and delivery

Read-only checks verified 110 stages, 770 complete states and 16,940 inputs. Apparatus comparisons of observation, complete restoration and host pauses preserved identical Core end states. Independent arithmetic differed by at most 4.44e-16. Scientific computation took about 17.33 minutes, with peak private memory about 693.18 MiB. All resource reserves were maintained. Actual allocation and hard-link accounting are recorded in `storage-before-publication.json`.

Originals reside at `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/dynamics-function61-v1`. Frozen protocols, curriculum, intervention differences, states, trajectories, analysis sources and bilingual reports are delivered through the research API. Full readback and zero pending requests in `publication/completion.json` close the batch. All research copies are retained; the main replication campaign remains paused.

Figure: `figures/persistence-and-prefix.png`, `.svg`, and `.pdf` in the evidence package, drawn read-only from recorded trajectories.

Before publication: logical files 244.08 MiB; unique allocated space 247.30 MiB; no additional hard-link paths. Later archive and readback copies are excluded.
