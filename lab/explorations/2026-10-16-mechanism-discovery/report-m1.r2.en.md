# M1 pilot: selective connection silencing and immediate reversal — r2

> **Revision r2 · 2026-10-16**
> Revision reason: Add purpose, existing expectations, interpretation and explicit scientific conclusions; preserve criteria, results and historical editions.
> Original: [report-m1.en.md](report-m1.en.md); parent r1: [report-m1.en.md](report-m1.en.md)


Revision r2, 16 October 2026. [Preserved prior report and addenda](report-m1.en.md) · [中文](report-m1.r2.zh.md) · [Revision register](report-revisions-20261016.en.md)

This revision adds the scientific purpose, pre-run expectations, interpretation and conclusions. No experiment, criterion, denominator or score is changed. The preceding report is retained below as the evidence layer; its next-step and not-yet statements describe that historical stage. The opening analysis and closing conclusion provide the present editorial synthesis. Prior-file SHA256: `b73a5de74f534141a753ca44c0a78b08608256f1435611e2a97ca1b1de472694`.

## Purpose, expectation and conclusion

This batch asked whether history-dependent short responses require course-related connections rather than current cues or arbitrary network perturbation. Target silencing was expected to remove the history contrast, matched silencing to preserve it, and immediate restoration to recover the reference. Eight origins, the early window and matching limits were fixed in advance. This was an exploratory effect test without a numerical capability pass line; none is invented retrospectively.

**The learned, specific connection pathway causally carries the history-dependent response in this task.** Target silencing eliminates the contrast in every origin; sham, matched and restored conditions preserve it. Identical-current-cue explanations and arbitrary equal-sized silencing do not explain this pattern.

This favors ThreeMind's mechanism: experience changes internal connections that participate in expression without reader relearning. This batch tested pathway necessity. Content transfer and actual gate-choice benefit were subsequently tested in the separate [X1 revision](closure-report.r2.en.md), not retrospectively credited here.

## Preserved prior evidence and methods

16 October 2026. `m1-silence-v1`, native `/5.1`; [registered protocol](pilot-m1-silence.en.md). This tests a selective expression pathway. Transplantation and closed-loop ability transfer were not executed.

### Results

**All eight independent origins met the registered matching criteria. Silencing two target connections eliminated the registered early history contrast; silencing matched connections preserved it; immediately reversing the target mask restored the intact result.** This supports a causal role in expression for this task, not the claim that complete memory content resides in two edges.

The primary metric is each origin's opposite-history A−B response difference divided by two, averaged over five frames at 0.1–0.3 s after the cue. This window was frozen before M1, informed by M2 development data, and uses new origins. It is not confirmation of M2's original late endpoint.

| Declared causal copy | Mean over eight origins | Origin range |
| --- | ---: | ---: |
| Intact | 0.004647593 | 0.004541153–0.004754033 |
| Sham | 0.004647593 | As above |
| Target mask | 0 | 0 |
| Matched mask | 0.004647593 | As intact |
| Immediately restored mask | 0.004647593 | As intact |

The selective effect (matched minus target mask) is 0.004647593, with exploratory origin-bootstrap 95% interval [0.004567763, 0.004727423]. Late 0.5–1.5 s expression remained zero in all 80 copies. Intact, sham and immediately restored final whole states were identical except for the declared copy ID.

### Subjects, matching and boundaries

Eight new origins817100–817107 each had two opposite teaching histories, giving16 continuously cultivated references. Each developed from birth to18 s and was saved whole before the cue. Five registered causal copies then each continuously experienced18–20 s. Eighty copies are nested within eight origins, not80 independent replications. Apparatus origin817001 was separate. There were no deaths, rollbacks or orphaned in-flight units.

The pilot used the M2 curriculum, default H mode,1 s retention,strong X0.8,frozen randomized mapping,maintenance input and fixed non-learning reader. History/answer labels never entered the reader. Absent body/optimizer were declared; Core, peripheral, RNG, input cursor, maps, recent readout, actuator and lineage were preserved. E69 received no intervention or stimulus.

Targets were the curriculum-defined X/Y-to-associated-output edges; matched edges were Z/W-to-other-output. Selection used only curriculum and pre-cue teaching data. Both sets had two edges and matched endpoint degrees. Mean effective-weight and teaching source/target activity residuals were below the registered0.02 limits; per-origin residuals are preserved in `analysis-v1.json` and matching originals. Edges were not reselected using outcomes.

The existing public `intervene` silence/restore operation was used. Apparatus verification showed immediate masking changes only `core.silenced_edges`, not weights,H/S,fast activity,time or queues; immediate restoration recovered the same-time whole state. This is **zero-simulated-time intervention reversal**, not recovery after two seconds of blocked experience. Ordinary teaching/tests were not restored per question.

![Eight-origin causal-copy comparison](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m1-silence-v1/figure-v1.png)

### Interpretation and remaining work

The same current cue produced opposite short responses after opposite histories. Masking taught target connections removed the effect, matched masks preserved it, and immediate reversal returned it. A current-cue shortcut alone cannot explain this response: formed connections participate in expression. Prior plastic-network research means this observation is not automatically a major originality claim. Its contribution here is a reproducible, matched and reversible local causal check of this implementation.

The eight origins produced only two response magnitudes, stratified by teaching order; randomized maps do not provide rich task diversity. Confirmation needs new materials/mechanistic conditions, not merely more copies. Z/W were inactive under this X cue: **this is not an unrelated behavioral task**, so absence of collateral ability damage cannot be claimed. Content transplantation, cross-individual alignment, fast/persistent-state separation, post-experience recovery, closed-loop benefit and external replication remain untested. The full M1 question remains open.

Next decision: retain this positive pilot and prepare M3 criterion-discrimination apparatus. M1 transplantation requires a clean, validated state interface and independent materials; the old /2 transplant tool cannot simply be applied to /5.1. Core will not be modified to obtain a positive result.

### Resources and reproducibility

Scientific advancement was448 simulated seconds (16×18+80×2), plus separate apparatus cultivation excluded from N. Host elapsed time43.59 s includes persistence/API; peak private memory94.97 MiB. Pure Core timing was not isolated, and these costs do not predict complex-subject throughput.

Prepublication v2 storage:754 files/unique files; logical and hard-link-deduplicated logical2,960,051 bytes; file allocation3,820,648 bytes; no duplicate hard links. This excludes subsequent publication/download copies and directory/MFT/database overhead. V1 mislabelled ordinary-file GetCompressedFileSizeW values as allocation and remains preserved; v2 corrects this using deduplicated FileStandardInfo.AllocationSize.

[Original work](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m1-silence-v1) includes `analysis-v1.json`, `resource-summary.json` and `storage-inventory-v2.json`. Project `e5c9bbae-d360-405b-803b-0de332af52c2`, record `11112b5f-8927-5d03-a4ce-fe11e93a1609`. Publication produces per-file manifests, a complete archive and API download verification; actual closure is recorded in `publication/final-verification.json`.

Read-only recomputation: run project Python `analyze_m1.py --work <originals> --output <new path>`, preserving the original analysis. Protocol, execution source, fingerprint, whole states, inputs, lineage, matching, analysis and figures are retained. The assistant checked bilingual reports, denominators and figures; this is not independent human review or external replication.

## Final conclusion of this revision

Experience affects the task response through a local pathway that can be selectively blocked and immediately restored. This causal proposition is supported and favors ThreeMind’s experience mechanism.
