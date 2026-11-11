# M5: a fixed personal peripheral expresses newly learned Core associations — r2

> **Revision r2 · 2026-10-16**
> Revision reason: Add purpose, existing expectations, interpretation and explicit scientific conclusions; preserve criteria, results and historical editions.
> Original: [m5-report.en.md](m5-report.en.md); parent r1: [m5-report.en.md](m5-report.en.md)


Revision r2, 16 October 2026. [Preserved prior report and addenda](m5-report.en.md) · [中文](m5-report.r2.zh.md) · [Revision register](report-revisions-20261016.en.md)

This revision adds the scientific purpose, pre-run expectations, interpretation and conclusions. No experiment, criterion, denominator or score is changed. The preceding report is retained below as the evidence layer; its next-step and not-yet statements describe that historical stage. The opening analysis and closing conclusion provide the present editorial synthesis. Prior-file SHA256: `af750c15c5dd7d0eb7f6f321f288577a3ab663a69d439531d5e2f80940acb180`.

## Purpose, expectations and scope

The experiment distinguished **a new association learned by Core and expressed through an already fixed personal peripheral** from **a reader learning a new cue–label mapping and thereby producing correct answers**. It also tested whether readout scope can block expression of a usable learned association. The preregistered task used native `/5.1`, default H, two familiar answer labels and new anonymous cues, with eight independent birth origins and two opposite histories per origin.

After old-course calibration, both the all-activity and output-port readers were frozen, including their scales. Only Core then received the new teaching. Core-dependent expression predicted improved new answers with old answers retained, selective target-lesion damage, no new-task damage from matched lesions, and restoration. Reader bottlenecks predicted changes with readout scope or further calibration; early/late activity crossed with early/late readers would locate their source. Both readers were scored separately throughout.

## Overall conclusion: a favorable Core result and an identified expression bottleneck

**M5 favors the ThreeMind research approach: Core can learn new associations that are correctly expressed through a personal output-port reader without retraining it. Peripheral relearning is not required for every new association. At the same time, this task rejects the practice of assuming that successful old-course calibration of an all-activity reader guarantees expression of later experience; it identifies a readout-scope bottleneck.**

This is an interpretation of the paired trajectories and interventions, not a sum of four passing and three failing scores. The fixed port reader answers 64/64 new singleton questions; the all-activity reader answers 0/64 and always WAITs, while both answer all 64 old questions. Because one declared, fixed interface expresses the new learning, failure of the other cannot mean that this Core formed no usable new association.

## Supported and rejected explanations

| Proposition or explanation | Scientific judgment | Evidence |
| --- | --- | --- |
| A fixed personal peripheral can express Core's newly learned association | **Established in this task** | Unchanged port weights; zero correct before teaching and 64/64 afterward, with opposite answers after opposite histories under identical cues |
| Port success is only a current-sensory shortcut or new reader training | **Does not explain this success** | Sensory-only new answers 0/64; port weights frozen; disabling the new-course plasticity bundle gives 0/64 |
| New and old associations have selectively separable local connection roles | **Established in this task** | Target lesion changes new 64→0 while old stays64; matched old-route lesion changes old64→0 while new stays64; immediate restoration restores both |
| Old-course success guarantees expression of new experience | **Refuted by this all-activity-reader counterexample** | Old64/64 but new0/64 on the same taught Core |
| High scores after reader recalibration alone establish new learning in Core | **Refuted as a sufficient inference** | The new all-activity reader also answers from pre-teaching activity; the old port reader succeeds only with post-teaching activity |
| Further calibration necessarily improves already perfect port expression | **No gain in this batch; the original gain target fails** | Held-out new128/128 before and after; this is not failure of fixed expression |

The two sufficient-inference statements are logical interpretations of the results, not verbatim preregistered hypotheses. All seven original numerical targets, including three failures, remain below.

## Why the readers diverged

The all-activity reader learned old labels from twelve activity dimensions; the port reader used only the predeclared A/B answer ports, whose label meanings were also learned from old calibration. More available activity did not improve new expression here: old cue representations could dominate the readout. A post hoc arithmetic audit attributes 87.77–96.31% of absolute old-answer contributions to old-cue channels; old weights for new cue dimensions are zero, and new scores fall within WAIT thresholds.

The evidence separates three levels: paired readout scope locates an expression-interface bottleneck; target/matched lesions and restoration establish the relevant Core connection dependence; early/late crossing shows that peripheral recalibration can independently add cue–label mappings. Together they distinguish **Core learning expressed through a fixed interface** from **peripheral learning applied to existing cue representations**.

All-activity recalibration improves untrained-dose answers from 0/128 to 128/128, showing a practical remedy for this expression bottleneck. Its ability to decode pre-teaching activity means that this remedy's score cannot by itself be attributed to Core's new learning. The port reader starts at ceiling; zero additional benefit does not count against the Core mechanism already demonstrated.

## Implications for ThreeMind

**The favorable finding is selective causal evidence for the proposed division of labor: after a personal peripheral learns how to express familiar answers, Core's subsequent experience can create new correspondences without retraining the peripheral for each one.** This directly resolves an important capability question left by earlier fixed-expression failures.

**The unfavorable finding is that expression does not automatically follow Core learning.** An all-activity reader fully competent on old material fails on new associations. Interface scope and calibration materials are therefore substantive experimental variables. Future work should test both Core learning and reader shortcuts explicitly; this recommendation does not replace any historical individual's reader.

The apparatus is a passive answer terminal recording parallel readers on one trajectory. Port answers are actual saved expression outputs, while the saved `actuator` records the all-activity reader and answers do not affect later cues. The resolved question is expression attribution. Joint cues remain separately reported at port16/32, and E69's historical WAIT mechanism retains its own evidential identity.

## Preserved prior evidence and methods

16 October 2026. Scope: native `continuous-memory/5.1`, default H, new anonymous cues associated with two familiar answer labels. Eight independent birth origins each receive two opposite teaching histories. Protocol and scoring were frozen at `1cee65d`. Core, historical individuals, E69 and the author's manuscript are unchanged. [Prospective protocol](m5-protocol.en.md) · [中文](m5-report.zh.md)

**The batch establishes that newly learned Core associations can be expressed through a fixed personal output-port reader and depend on the corresponding local connections. A reader calibrated on the same old course but given all activity fails to express those associations. Readout scope changes the expression of new experience.** The complete test includes opposite histories, old-skill retention, fixed weights, a sensory control, the plasticity bundle, target/matched masks, immediate restoration and early/late crossing. Each goal receives its own verdict.

### Frozen goals and outcomes

Both opposite histories must meet each conjunction within an origin; at least 6/8 origins must pass. Per history, four new and four old singleton cues form the primary denominators. Two new and two old equal-total-dose joint cues are separate. The sole answer endpoint is 110 ms, and ordinary questions are continuous without restoration.

| Goal | Prespecified criterion, abbreviated | Observed result | Verdict |
| --- | --- | --- | --- |
| Fixed all-activity expression | New ≥75%, gain over baseline ≥50 pp; old ≥75%, loss ≤10 pp | 0/8 origins; new 0/64, old 64/64 | **FAIL** |
| Fixed output-port expression | Same, with baseline old ≥75% | 8/8; new 64/64, old 64/64 | **PASS** |
| All-activity Core attribution | Sham exceeds plasticity-off and target by ≥50 pp; matched-new and target-old loss ≤10 pp; restoration error ≤1e-9 | 0/8; sham and all interventions give new 0/64 | **FAIL** |
| Output-port Core attribution | Same | 8/8; target loss 100 pp, matched-new and target-old losses zero, restoration error zero | **PASS** |
| Readout-scope benefit | Ports exceed all-activity new accuracy by ≥25 pp, port old accuracy ≥75% | 8/8; advantage 100 pp, old all correct | **PASS** |
| Continued all-activity calibration | Held-out-dose new gain ≥25 pp, old loss ≤10 pp | 8/8; new 0/128→128/128, old 128/128 unchanged | **PASS** |
| Continued output-port calibration | Same; no ceiling exception | 0/8; new 128/128→128/128, zero gain | **FAIL** |

The 64 answers are nested observations: eight origins × two histories × four cues. The 128 answers additionally contain two held-out doses. Independent N remains eight. Before new teaching there are only four distinct new and four distinct old singleton observations per origin, 32 of each in total. Scoring this shared baseline against both subsequent histories produces the displayed 0/64 and 64/64; it does not create additional baseline trials.

All origins have identical primary contrasts. Origin-bootstrap descriptive 95% intervals are [100,100] pp for port learning, target loss, the plasticity-bundle contrast and all-activity continued-calibration gain, and [0,0] for the designated unrelated losses. These degenerate intervals reflect identical observed contrasts. Descriptive Wilson 95% intervals for source pass proportions are [67.56%,100%] for 8/8 and [0,32.44%] for 0/8. This is the registered exploratory cohort, without post-result significance selection or trial-level pseudoreplication; the frozen 6/8 decisions stand.

### Selective causal expression with fixed peripherals

Readers first learn from 12 calibration questions on U/V→positive and Z/W→negative. The all-activity reader receives 12 raw activation coordinates. The port reader retains only the declared A/B physical answer ports, whose positive/negative meanings are learned from the same old labels. Both use linear ridge regression without an intercept. Their scales and weights are fixed before new teaching. Ports were declared before scientific execution, rather than selected from final performance. Readers receive no case number, phase, history ID, label or scoring answer.

Core then learns X/Y and C/D with opposite assignments in the two histories, while current examination cues remain identical. Ordinary lives are continuous. Declared research copies preserve the complete parent, personal readers and normal equations, all old samples, mappings, random state, body, recent trajectories and actuator.

| Condition | Port new singleton | Port old singleton | All-activity new singleton | All-activity old singleton |
| --- | ---: | ---: | ---: | ---: |
| Intact/sham | 64/64 | 64/64 | 0/64 | 64/64 |
| Plasticity bundle off during new teaching | 0/64 | 64/64 | 0/64 | 64/64 |
| New-association target connections silenced | 0/64 | 64/64 | 0/64 | 64/64 |
| Matched old-association connections silenced | 64/64 | 0/64 | 0/64 | 64/64 |
| Target immediately restored | 64/64 | 64/64 | 0/64 | 64/64 |

**The local connections have selectively separable roles: target masking impairs new answers only, matched masking impairs old answers only, and restoration returns the original performance exactly.** The sensory-only control gives new 0/64 and old 64/64, with every new answer WAIT. Identical current inputs cannot substitute for opposite teaching histories. All new answers from the fixed all-activity reader are also WAIT.

Target XYCD→AB and matched UVZW→AB sets each contain four edges specified from teaching interfaces, without selection from examination answers. Degree distributions match exactly. Maximum contemporaneous mean effective-weight and teaching-activity residuals are 0.00652154 and 0.00020110, below the frozen 0.05 and 0.02 limits. Masking changes only `core.silenced_edges`, and immediate reversal preserves the whole state. The existing plasticity switch also affects retention decay and fast learning. It is explicitly a bundle; both arms use the same-time reconfigure operation, including its settlement of edges, nodes and timers. Its contrast is not attributed to one isolated learning field.

### Crossing identifies two expression routes

After first answers, fixed-reader and continued-reader copies start from the complete current endpoint. Continued calibration appends six new-cue activity/label samples to the original 12 samples and normal equations, retaining the original scales. Doses 0.85 and 0.95 were never used for fitting. Each copy continuously answers 24 questions; their final Core states and input histories are exactly identical.

| Offline new-singleton combination | All-activity reader | Port reader |
| --- | ---: | ---: |
| Old reader × activity before new teaching | 0/64 | 0/64 |
| Old reader × activity after new teaching | 0/64 | 64/64 |
| Continued reader × activity before new teaching | 64/64 | 0/64 |
| Continued reader × activity after new teaching | 64/64 | 64/64 |

This is the registered offline attribution diagnostic and never writes back to an individual. The continued reader was fitted on post-teaching answer material, so relevant cells contain fitting material; these cells are separate from held-out-dose performance.

**Port-reader success depends on activity changes after Core teaching. Continued all-activity calibration can instead attach new labels to cue representations already present before that teaching.** Both learning routes are distinguished in the same study. The all-activity reader can retain old accuracy even when the corresponding old connections are silenced; old accuracy alone therefore cannot replace a fixed-peripheral new-experience test.

A separately labeled post-result arithmetic explanation finds that old-cue channels supply 87.77%–96.31% of the sum of absolute contributions to all-activity old-answer scores. New-cue coefficients are zero in every origin, and new scores range from −0.21917 to 0.13220, entirely inside the ±0.25 WAIT band. This numerical decomposition explains dependence on old-cue activity; it neither replaces frozen scoring nor constitutes another causal intervention.

### Joint cues retain their separate denominator

XY/CD have total dose 0.8, or 0.4 per input. Their separation from singleton primary outcomes was specified before execution, not selected after results.

| Condition | Port new joint | Port old joint | All-activity new joint | All-activity old joint |
| --- | ---: | ---: | ---: | ---: |
| Sham | 16/32 | 24/32 | 0/32 | 32/32 |
| Plasticity bundle off | 4/32 | 0/32 | 0/32 | 32/32 |
| Target silenced | 4/32 | 24/32 | 0/32 | 32/32 |
| Matched silenced | 16/32 | 0/32 | 0/32 | 32/32 |
| Immediately restored | 16/32 | 24/32 | 0/32 | 32/32 |

Joint cues do not request two output labels. Their dose/threshold/reception differences remain within the already registered M2 question, without rescoring M5 singleton expression.

![M5 fixed expression, causal controls and held-out doses](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m5-expression-v1/figure-v1.png)

### Integrity, scale and reproducibility

Five isolated tests passed. Formal apparatus origin 1056002 produced identical complete-state hashes under ordinary execution, frequent observation, save/restore and wall-clock pause. Scientific seeds are 1056100–1056107. Protocol-disclosed apparatus-design sources and transient debugging without retained whole states are excluded from scientific N. The scientific batch ran once, completing all eight origins without STOP, in-flight residue or runtime errors; no failed question was rerun.

The read-only audit passes all snapshot-hash, before/after-state, one-second-continuity, 110 ms-feature, independent-reader-arithmetic, answer-free-input, fixed-weight and lineage checks. It also verifies 64 intervention receipts, their whitelists and matched edge counts/degrees/projected effective weights, and 32 continued-reader statistics pairs. Scientific examinations comprise 1,824 questions, including 1,216 singletons, plus 96 old calibration questions. There are 2,024 scientific whole snapshots and ten apparatus snapshots. Each post-teaching reference has 60 internal seconds, 11 nodes and 24 edges; the longest continuous copy ends at 96 seconds. Branch times cannot be concatenated into one individual's lifetime.

Host time is 901.04 seconds including saving, original-file I/O and API synchronization, not pure Core time. Peak private memory is 718.39 MiB. Minimum system commit/RAM/C/E headroom is 10.62/10.72/8.17/59.32 GiB, above the 5/4/5/25 GiB reserves. Compressed scientific whole snapshots range from 6,304 to 682,738 bytes, median 365,387.5; they include cumulative trajectories and personal peripherals, rather than measuring Core-only RAM. Logical, hard-link-deduplicated logical and actual file-stream allocation are reported separately in `storage-inventory-v1.json`, before publication archives and API readback copies.

That inventory contains 2,081 files/unique files, 876,781,389 logical and deduplicated logical bytes, and 881,047,120 bytes of actual file-stream allocation, with zero multiply linked files. Subsequent report copies, archives, API readback copies, directory/MFT and database overhead are excluded.

Scoring: `m5_analyze.py`; independent file/arithmetic audit: `m5_audit.py`; descriptive intervals/figure: `m5_summary.py`. The reviewer is the executing assistant; this is separately implemented recalculation and code review, not external-researcher replication.

Originals: [m5-expression-v1](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m5-expression-v1). Project `fdde9caa-db45-4231-9735-05a71a6836bd`, record `a5949c51-5916-5f6a-a590-cbf58f44bc91`. Frozen hashes are in `runner-manifest.json`; audit in `audit-v1.json`; scores/statistics in `analysis-v1.json` and `summary-v1.json`; per-member archive and API readback receipts in `originals-manifest-v1.json`, `publication/final-verification.json` and `publication/download-receipt.json`. Closure requires matching full-archive readback and pending=0.

### Research position and next priority

Plastic networks storing new experience have established precedents, including gradient-trained weights and Hebbian plasticity in [Miconi et al., 2018](https://proceedings.mlr.press/v80/miconi18a.html) and temporary past storage through fast weights in [Ba et al., 2016](https://arxiv.org/abs/1610.06258). This study does not benchmark those implementations. Its additional evidence concerns separation within ThreeMind: the same newly taught experience is expressed by a fixed port reader but missed by a fixed all-activity reader, with declared local interventions and early/late crossing identifying their roles.

Historical E50/E52 fixed-new-association failures and E69 hand-WAIT evidence retain their conclusions. This separately frozen anonymous task does not retroactively determine their causes. Next priority is independent new-source/new-material confirmation of this complete mechanism, with readout scope an explicit variable in future training design. E69 and its bounded retraining remain separately paused. M4 specialization, ecological transfer and longer experience expression retain their own prospective questions, rather than becoming additional conditions on this batch's passes.

## Final conclusion of this revision

M5 establishes Core learning expressed through a fixed personal peripheral in this task and locates the corresponding local connections through selective intervention. It also shows that an all-activity reader can conceal a usable new association, while peripheral recalibration can create answer gains from existing cue representations. The overall result supports the Core mechanism and identifies an interface bottleneck: a mechanistic conclusion that guides the next experiments, not merely a list of scores.
