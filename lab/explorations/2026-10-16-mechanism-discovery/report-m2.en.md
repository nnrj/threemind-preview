# Dated correction, 16 October 2026, 04:30: missed transients verified

The first report and its scores remain below. All 65 instrument copies exactly matched their original final whole states. Every one of the 64 trajectories with zero original 50 ms readings but nonzero associative fields showed brief activation on a 1 ms grid. Statements below about zero output and 80 early responses therefore describe the original 50 ms readout grid, not absence of activation throughout other trajectories. The registered 0.5–1.5 s primary and first 0.5 s responses remain zero; no scores were increased. Energy simulation was disabled in every M2 configuration, so actual energy scarcity does not explain these negatives.

Original evidence and first API reports remain intact. See the [calibration and correction](report-sampling-calibration.en.md), separate record `201e43f1-1101-5605-aa64-47e58a16a9df`. Its archive was downloaded and verified through the API before pending-zero closure; SHA256 `3d95e5e16a9ff60038f5641943144c421a287e6b6eff9c7d4d93ff7a24aaa4f4`. Calibration adds no learning or independent origins and does not establish all retention/retrieval mechanisms.

---

# M2 pilot: retained connections, evoked activity and fixed expression

16 October 2026. `m2-pilot-v1`, native `threemind.continuous-memory/5.1`. This is an apparatus and mechanism pilot, not all of M2 or a confirmatory study. The registered protocol and primary endpoints remain unchanged.

## Findings and denominators

**The registered late expression endpoint was negative: all 640 lives had zero mean A−B response at 0.5–1.5 s, and zero first expression at 0.5 s.** There were 512 task-cued lives and 128 no-task-cue controls; the latter are not accuracy trials. Observing an earlier peak did not change the primary endpoint.

Post-hoc trajectory inspection found transient expression at `0<t<0.5 s` in 80/640 lives. Strong single-channel cues elicited history-aligned short responses after 1 and 30 s of retention. At 60 s, S retained taught connections and showed associative input without fixed output. At 300 s, the predefined taught edges no longer survived. The apparatus distinguishes structure, internal evocation and expression; **it does not establish intact memory content from surviving structure or identify a unique cause of expression failure**.

There were 32 independent origins, eight per retention cohort. Mode, history and cue copies are nested observations: 640 is not independent N. No origin was removed for its score; there were no deaths, rollbacks or orphaned in-flight units.

## Design and observation integrity

The [registered protocol](pilot-m2.en.md) specifies opposite co-stimulation histories XY/A with ZW/B, versus XY/B with ZW/A, for 16 rounds ending at 17 s. Separate cohorts then continuously retained for 1, 30, 60 or 300 simulated seconds and were tested once. Earlier tests therefore did not rehearse later tests. A declared K maintenance stimulus continued throughout; retention was not input-free.

Each origin had a frozen, independently randomized anonymous channel map. The fixed, non-learning reader receives only A and B activity and returns A−B. Current cues contain neither A/B nor history labels, question IDs or file metadata. H uses default adaptive-half-life with gain 0.2; S uses legacy-stability. This compares packages of retention rules, not an isolated mechanism ablation.

Five conditions were separate: no task cue, weak X (0.4), strong X (0.8), joint XY with equal total dose (0.4 total), and joint XY with equal per-channel dose (0.8 total). Observations occur every 50 ms; the primary window has 21 frames. Absolute expression at or below 1e-9 means no measurable expression, not chance-correct output.

Apparatus origin 716001 was excluded from scientific N. Plain execution, frequent observation, save/restore and wall-clock pause produced the same whole-state hash at 20 s. Read-only analysis verified all 8,960 committed snapshots and current-state hashes. Core, RNG, channel maps, input cursor, recent activity and actuator were preserved together; absent body, fixed peripheral and absent optimizer were declared. Observation and storage did not advance simulation.

## Results

Each strong-X row contains 16 history lives nested in eight origins. Response is the mean origin-level opposite-history difference divided by two. Weight is the pre-cue, same-time effective-weight sum over the predefined 12 taught edges, missing edges counted as zero. All late primary responses were zero.

| Delay s | Mode | Taught-edge weight sum | Early expressive lives | Early history contrast/2, post-hoc |
| --- | --- | ---: | ---: | ---: |
| 1 | H | 1.039589 | 16/16 | 0.002581996 |
| 1 | S | 1.112912 | 16/16 | 0.003002402 |
| 30 | H | 0.531944 | 16/16 | 0.000469090 |
| 30 | S | 0.719179 | 16/16 | 0.001632731 |
| 60 | H | 0.265972 | 0/16 | 0 |
| 60 | S | 0.444011 | 0/16 | 0 |
| 300 | H | 0 | 0/16 | 0 |
| 300 | S | 0 | 0/16 | 0 |

At 1 s in S, weak X and equal-per-channel XY each produced transient expression in 8/16 lives, with history contrast/2 of 0.000224041. All other weak/joint conditions had no expression. All no-task-cue controls and all equal-total joint conditions had no expression. Dose and cue composition must remain distinct; these observations do not establish input competition as their cause.

At 60 s, S strong X produced maximum associative input 0.004052930 with all 12 taught edges surviving, yet zero output. H at this delay showed neither associative input nor expression. At 300 s both modes had zero taught edges. Associative input is an actual kernel field, not a substitute for behavioral evidence of recovered content.

Origin bootstrap 95% intervals describe exploratory uncertainty: e.g. 1 s H strong X [0.002537646, 0.002626346] and 30 s S strong X [0.001626528, 0.001638934]. There was no confirmatory multiplicity-controlled inference; a degenerate zero interval does not prove a population null. New materials, mechanistic variation and independent confirmation remain necessary.

![Registered late and post-hoc early windows](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-pilot-v1/figure-v2.png)

## Limits and next decision

Storage/expression separation is not a new concept introduced here. [Ryan et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5583719/) distinguished biological storage and normal retrieval, while [Miconi et al.](https://proceedings.mlr.press/v80/miconi18a.html) studied learning in plastic networks. This pilot adds reproducible observations for this /5.1 apparatus under stated doses, delays and windows, not a general memory law or subjective-consciousness claim.

The original late-window negative remains. A separately registered M1 pilot uses new origins and a prospective early window to test dependence on taught connections; see its [report](report-m1.en.md). M2 still needs threshold, inhibition, energy and fast-state interventions, recovery/relearning costs and predictions for unseen delays/intensities. Gains 2/4, rule reversal, relearning and long-term behavioral benefits were not executed. Negative results did not trigger extra teaching or unbounded tuning.

## Resources, originals and recomputation

Total advancement was 74,720 simulated seconds. Host elapsed time was 1,584.80 s (26.41 min, including persistence and API); peak private memory was 117.01 MiB. This is not pure Core timing and cannot estimate large E69 performance. Snapshot size ranged from 0–8 nodes and 0–12 edges; final compressed whole states were 8,708–9,483 bytes, mean 9,103.55.

Prepublication storage inventory v2 counted 12,197 files/unique files: logical and hard-link-deduplicated logical size 81,906,016 bytes, file allocation 107,129,656 bytes, no duplicate hard links. Final publication/download copies were not yet included; directory/MFT/database overhead is excluded. V1 incorrectly labelled ordinary-file GetCompressedFileSizeW values as allocation. It remains preserved with an explicit v2 correction. V2 uses FileStandardInfo.AllocationSize and file-identity deduplication.

[Original work](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-pilot-v1): `analysis-v1.json`, `resource-summary.json`, `storage-inventory-v2.json`. Research project `e1c67df5-4425-41f9-9269-2cc0a38ea150`, record `9c3fa55f-5c9c-5afc-a20c-a809afd16b38`. Publication creates a per-file manifest, complete archive and API download proof; actual closure is established by `publication/final-verification.json`.

Recompute read-only with the project Python: `analyze_m2.py --work <originals> --output <new analysis path>`; use `plot_pilots.py` for figures. Preserve analysis-v1. Source, software fingerprint, inputs, lineage, whole states, analysis and review receipt accompany originals. Reports and figures were checked by the assistant; this is neither external replication nor independent human review.
