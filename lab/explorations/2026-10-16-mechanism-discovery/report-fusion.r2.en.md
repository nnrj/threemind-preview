# M2 receiver fusion and transmission thresholds: prospective results — r2

> **Revision r2 · 2026-10-16**
> Revision reason: Add purpose, existing expectations, interpretation and explicit scientific conclusions; preserve criteria, results and historical editions.
> Original: [report-fusion.en.md](report-fusion.en.md); parent r1: [report-fusion.en.md](report-fusion.en.md)


Revision r2, 16 October 2026. [Preserved prior report and addenda](report-fusion.en.md) · [中文](report-fusion.r2.zh.md) · [Revision register](report-revisions-20261016.en.md)

This revision adds the scientific purpose, pre-run expectations, interpretation and conclusions. No experiment, criterion, denominator or score is changed. The preceding report is retained below as the evidence layer; its next-step and not-yet statements describe that historical stage. The opening analysis and closing conclusion provide the present editorial synthesis. Prior-file SHA256: `f1043239e71b366fa801c0b4af5cc9930c51fe0d02daafd971dbf54b56f569bb`.

## Purpose, expectation and conclusion

For symmetric simultaneous anonymous cues, the experiment compared total-dose prediction with per-route sending thresholds followed by the reception rule. Both predictions were saved before cues. A declared reception-configuration intervention tested selective effects on joint versus single inputs. There were eight origins and a fixed110ms endpoint.

**Per-route thresholds and reception normalization jointly determine expression; total dose alone is insufficient.** Mechanistic prediction classifies all224 nested zero/nonzero observations correctly and has lower error in every origin. In the six measurable origins the joint/single ratio changes from1 to2 under summation while single-route output stays unchanged; restoration and sham agree. The two sending failures stay zero, rejecting universal rescue by removing reception normalization.

This favors mechanistic interpretability in ThreeMind: unexpectedly weak joint responses have specific local conditions. Splitting a dose changes route thresholds, so equal total input is not equal elicitation. Greater summed amplitude is not itself a reason to change production dynamics.

## Preserved prior evidence and methods

2026-10-16. [Frozen protocol](pilot-m2-fusion-v2.en.md), commit `0b992d1`; genuine `continuous-memory/5.1`, S/legacy-stability. All 448 declared causal copies from 16 complete parents and 8 new independent origins completed. The original M2 endpoint and evidence remain unchanged; E69 remains paused.

**Combined-cue effects depend on per-route thresholds and subsequent reception, not total input dose alone.** For the 6/8 origins with measurable single-route responses, normalized joint reception equaled the single-route mean, whereas summed reception doubled it. The other 2/8 origins remained zero: removing receiver normalization cannot recover signals already discarded before arrival. This conclusion is bounded to the symmetric, simultaneous, rested anonymous task.

### Prespecified endpoint and causal comparison

Origins 917100–917107 cover four teaching intensities and two orders each. Complete parents reached 32 seconds, including 15 seconds of retention. Each declared copy received one probe and continued to 34 seconds. Existing reconfigure compared context_mix=1, 0, 1→1 double sham and 0→1 immediate reversal. Same-time settlement side effects were recorded; production Core and defaults were unchanged. Parents stayed intact and the personal A−B projection was never retrained.

The primary endpoint is response at 110ms. Subtract the same-history no-cue baseline before taking half the opposite-history difference. All eight origins, including zeros, enter the primary comparison. These means are neither accuracies nor consciousness scores.

| Cue / total raw dose | Normalized mean | Summed mean |
| --- | ---: | ---: |
| None / 0 | 0 | 0 |
| X .25 / .25 | .001109146 | .001109146 |
| X .5 / .5 | .004834049 | .004834049 |
| Y .5 / .5 | .004834049 | .004834049 |
| XY .25 each / .5 | .001109146 | .002218292 |
| XY .5 each / 1 | .004834049 | .009668098 |
| X 1 / 1 | .011085360 | .011085360 |

The prespecified interaction, `[summed joint−summed single mean]−[normalized joint−normalized single mean]`, is .004834049, with an eight-origin, pointwise bootstrap 95% interval [.002676779, .007050785]. This exploratory interval is not a multiplicity-controlled confirmation or external replication. Conditional joint/single ratios are exactly 1 and 2 in the six eligible origins; their denominator is six, while both zero origins remain in the main analysis.

Single-cue differences across reception arms and endpoint differences between reversal/double-sham are zero. All 112 reversal/double-sham pairs have identical complete initial and final states except branch metadata. Immediate reversal is a zero-time reversibility control, not recovery after damaged experience.

![Prespecified response and prospective prediction error](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v2/figure-v1.png)

### Prediction and limits

Both unfitted approximations were saved before any child probe, using only the same-time parental graph and configuration. The dose model sums arrivals before clipping; the receiver model clips routes first and then applies declared reception. Errors are averaged within origin before inference. The 224 nested forecasts are not 224 independent observations.

| Predictor | Mean origin-level absolute error | Pointwise origin-bootstrap 95% interval | Zero/nonzero classification |
| --- | ---: | --- | ---: |
| Total-dose approximation | .001000660533 | [.000875933012, .001152204306] | 200/224 |
| Route thresholds plus receiver fusion | .000000001570 | [.000000000506, .000000002769] | 224/224 |

The mechanistic approximation has lower error in all eight origins. Its accuracy supports first-arrival prediction at the new delay, teaching intensities and origins. The formula follows implementation ordering; it is not a newly discovered universal memory law. Assumptions include long rest, recovered short-term resources, symmetric arrival keys, and negligible slow-weight change during the first 100ms. Asynchrony, asymmetric competition, H mode and complex behavior remain untested. No production normalization change is recommended from this result.

The original .5–1.5s late window is also retained in this new batch: 36/448 copies have nonzero means, comprising 4/16 summed XY-per copies and 8/16 X-total copies in each of four arms. These are different teaching/probe conditions and cannot rescore the original M2 batch's 640 late-window zeros. Nonzero means are not task success: there is no behavioral success threshold, naming task or closed-loop benefit here. Maximum absolute late mean is .0009602483.

### Apparatus failure and integrity

The preceding v1 apparatus failed its frozen whitelist because definition configuration and its hash were omitted. Its scientific origins were never created. Code, states and the marker remain intact; the record closed failed/verified/pending0. See the [failure report](report-fusion-apparatus-v1.en.md). Separately registered v2 validates configuration, definition and canonical identity explicitly, rather than deleting identity fields. Its 16 apparatus paths passed whole-state equality across ordinary observation, frequent observation, restoration and wall-clock pause before scientific execution.

Read-only analysis verified 16 parents, 896 initial/final copy snapshots, 448 saved predictions, all 2,000-frame endpoints, past input prefixes, identical current cues across histories, definition identity, and unchanged fixed peripherals/body/RNG. There was no new death, STOP, residual in-flight, rollback or student rerun. Pending requests are zero. Reports and figures received assistant review; closure follows full original-package API readback, not external human review.

### Cost, storage and reproduction

Parent development totaled 512 internal seconds and declared copies 896 seconds; these do not form one student's age. Scientific-host wall time was 460.03s including I/O/API, peak private memory 101.77MiB. Pure Core compute speed was not separately measured. Minimum headroom was 15.26GiB commit, 13.55GiB RAM, 9.96GiB system drive and 60.95GiB data drive. The 5/4/5/25 guard never triggered.

Pre-publication inventory: 2,429 files and unique identities; logical and de-duplicated logical size 33,621,687 bytes; file-stream allocation 37,270,880 bytes; no duplicate hard links. This excludes later archives/readback, directory/MFT and database overhead. Final compressed complete individuals occupy 55,001–64,326 bytes, including Core, mapping, fixed peripherals/empty optimizer and body, RNG, recent activity, actuators and environment cursor. This is not Core-only RAM usage.

Originals: [m2-fusion-v2](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v2). Project `ed78f70f-91d8-4836-be8f-39dd0a37e3f3`, record `8a3333df-b46e-5fec-b142-bb06f7d19036`. See `analysis-v1.json`, `resource-summary.json`, `storage-inventory-v2.json` and `publication/final-verification.json` for analysis, resource, allocation and closure evidence.

`analyze_fusion.py --work <originals>` does not load or advance subjects and refuses to replace a differing analysis-v1. Never repeat run/register/apparatus. Next priority is new asynchronous or asymmetric material capable of testing the prediction's boundary before expanding confirmation. Transplantation, the remaining M3 criteria and M4–M7 remain open.

## Final conclusion of this revision

Cue effects are jointly constrained by per-route transmission and reception. The mechanistic model outperforms total dose; joint cues do not automatically strengthen expression. This is a definite local mechanism and new-material prediction result.
