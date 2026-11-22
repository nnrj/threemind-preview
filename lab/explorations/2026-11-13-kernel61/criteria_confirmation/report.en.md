# R51i: all 64 ThreeMind 6.1 sources satisfy the four autonomy criteria

13 November 2026. **The registered target was confirmed: all 64 ThreeMind 6.1 sources jointly satisfied experience dependence, selective causality, temporal interaction and feedback adaptation. Each of the four comparators had 0/64 joint passes. ThreeMind won the predefined conjunction among these five implementations.**

This report follows the preregistered [protocol](protocol.en.md), complete originals and independent arithmetic checks. R51g's eight exploratory groups and this batch's 64 groups were registered and counted separately.

## Purpose and expectation

The study tested whether 6.1 consistently develops all four properties in new independent sources and whether four existing comparators jointly satisfy them. ThreeMind was expected to meet the full confirmation target, with each comparator missing at least one criterion. The registered requirements were at least 48/64 ThreeMind passes on each criterion and on their within-source conjunction, a joint-pass advantage of at least 10 percentage points over each comparator, and P<0.05 for all four paired comparisons after Holm correction. Valid matching and replay measurements were also required throughout.

## Experimental organization

The 64 new sources used birth seeds 1096100–1096163. Each group contained a simple reactive controller, a finite-state controller, a local Hebbian plastic network, a fixed recurrent network with a personal readout, and ThreeMind: 320 system units in total. Systems received the same public anonymous stimuli and teaching materials while retaining their predefined structures and learning procedures. ThreeMind used default 6.1 mechanisms and a fixed A−B output difference; the recurrent network's personal readout learned according to its original procedure.

Each system underwent two opposite continuous teaching histories, followed by declared causal diagnostic copies of complete teaching references. Identical cues and blank controls tested experience dependence; target, matched, sham and restored interventions tested selective causality; sequential stimuli and internal-communication blocking tested temporal interaction. Four additional closed-loop lifetimes each lasted 90 internal seconds. Actions changed position and position changed sensory input, while environmental correspondences remained stable or reversed at predefined stages. Identical-input replay and action reversal identified how feedback affected the system.

Ordinary teaching and closed-loop lifetimes were continuous. Stage diagnostics, interventions and replays used registered research copies, preserving their complete references. Core, personal readout and learning state, random state, recent activity, body and actuator were saved together. The statistical unit was one of the 64 paired sources; questions and copies were nested observations.

## Results

| System | Experience dependence | Selective causality | Temporal interaction | Feedback adaptation | Within-source joint passes |
|---|---:|---:|---:|---:|---:|
| Simple reactive controller | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 |
| Finite-state controller | 64/64 | 64/64 | 0/64 | 0/64 | 0/64 |
| Local Hebbian plastic network | 64/64 | 64/64 | 0/64 | 64/64 | 0/64 |
| Fixed recurrent network with personal readout | 64/64 | 0/64 | 49/64 | 64/64 | 0/64 |
| **ThreeMind 6.1** | **64/64** | **64/64** | **64/64** | **64/64** | **64/64** |

The recurrent network's temporal count of 49/64 exceeded the 48/64 batch threshold, so that criterion passed; selective causality failed. The finite-state and Hebbian systems also demonstrated the abilities recorded above. None of the four comparators jointly satisfied all four criteria.

ThreeMind's joint-pass advantage over each comparator was 100 percentage points. All four exact two-sided paired P values were 1.0842×10⁻¹⁹ before correction and 4.3368×10⁻¹⁹ after Holm correction. The exact 95% interval for ThreeMind's joint-pass proportion was 94.40%–100%; each comparator's interval was 0–5.60%. The 20,000-draw paired bootstrap interval on the observed differences was [100,100] percentage points for every comparison. Exact source-proportion intervals are retained alongside it to express sampling uncertainty.

Across ThreeMind's 128 teaching histories, target connection blocking changed the relevant response, matched and sham effects were zero, and restoration error was zero. Internal-communication blocking abolished the detected sequential-stimulus interaction. Reversing actions changed subsequent input and model state in the real closed loop. Replaying identical inputs produced identical model states, including when action direction was reversed during replay. Environmental feedback therefore continued shaping internal activity and responses by changing the experience actually received.

## Scientific conclusion and meaning for ThreeMind

**Version 6.1 constructed and consistently reproduced autonomous activity as defined by the four preregistered criteria.** Experience caused response differences; internal connections selectively supported them; successive stimuli interacted internally; and actions together with environmental feedback shaped later experience. All 64 sources satisfied these properties together, completing the full confirmation target.

This is a favorable confirmation for ThreeMind. Version 6.1, with fixed-function addressing, local deletion and default sender thresholds, retained the four functions and the cross-system distinction investigated in the original research. The result supports continuing the planned studies of local experience structures, bodily associations and readout. No campaign-level scientific stopping condition was triggered.

## Verification, cost and evidence

All 20 independent apparatus paths for observation, save/restore and host pause produced identical complete endpoints. Checks passed for 33,920 scientific whole states, 20,480 probes, 1,280 closed-loop replay groups and 128 numerical reconstructions of RNN teaching. Independent arithmetic recomputed criterion counts, exact paired P values and Holm correction. No Core was loaded or advanced during analysis.

Core target and matched sets each contained two edges with identical endpoint degrees. Maximum base-weight and teaching-activity residuals were 0.000464 and 0.000489, below the 0.02 limit. The maximum standardized RNN residual was 0.39171, below 0.5. Matching was valid for every formal source.

Formal execution took 5,899.94 seconds, or 98.33 minutes, with peak private memory of 654.05 MiB. Pre-analysis files occupied 1,314.45 MiB logically and 1,395.02 MiB in allocated storage. The largest source cost was 1.003 times its estimate. Minimum available commit memory, physical RAM, C drive and E drive were 12.93, 11.99, 10.30 and 89.45 GiB, satisfying the respective 5/4/5/25-GiB reserves.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria-confirmation61-v1/`. Research record: `51a6fe79-aa3c-5b3a-b934-4ae4cd0db085`. `analysis.json` contains source-level scores and statistics; `audit.json` contains verification results. Final archival and complete API readback are recorded in `publication/completion.json`. Originals and historical batches remain intact. This is an independent-source confirmation within the research project and an executing-assistant arithmetic review, not an external-researcher replication.
