# R51g: all eight ThreeMind 6.1 sources satisfy the four autonomy criteria

13 November 2026. The eight-group exploratory replication is complete. Confirmation will use 64 new sources. This report follows the preregistered [protocol](protocol.en.md), saved whole-system states and independent arithmetic verification. Historical evidence and criteria remain intact.

## Purpose and expectation

The study tested whether 6.1 exhibits experience dependence, selective internal causality, temporal interaction and feedback adaptation under the same anonymous teaching and ring environment, alongside four existing comparison systems. The expectation was that ThreeMind would meet the original X3 threshold of six out of eight sources on every criterion, while each comparator would miss at least one. The number of sources satisfying all four criteria together was also counted separately.

## Design

Each of eight independent encoding sources supplied a reactive controller, a finite-state controller, a local Hebbian network, a fixed recurrent network with a personal RLS readout, and ThreeMind: 40 system units in total. They received the same public stimuli and teaching materials and retained their declared architectures and learning methods. ThreeMind used explicit 6.1 defaults and a fixed A−B readout. The four comparator implementations were unchanged. The comparison concerns these five implementations.

Each system underwent two opposite pairing histories. Complete references supplied declared sham, target, matched, restored and internal-communication-blocked research copies. Connections were selected using teaching data only. Further comparisons tested sequential stimuli and four continuous closed-loop lives of 90 internal seconds each. Post-stage diagnostics and input replays used registered copies and did not alter the ongoing lives. Models, personal readout learning state, random state, body, actuator, input and recent activity were saved together.

## Results

| System | Experience dependence | Selective causality | Temporal interaction | Feedback adaptation | All four in the same source |
|---|---:|---:|---:|---:|---:|
| Reactive controller | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| Finite-state controller | 8/8 | 8/8 | 0/8 | 0/8 | 0/8 |
| Local Hebbian network | 8/8 | 8/8 | 0/8 | 8/8 | 0/8 |
| Fixed recurrent network with personal readout | 8/8 | 0/8 | 5/8 | 8/8 | 0/8 |
| ThreeMind 6.1 | **8/8** | **8/8** | **8/8** | **8/8** | **8/8** |

ThreeMind was the only implementation to satisfy the conjunction. The recurrent network's temporal-interaction count of 5/8 fell below the preregistered 6/8 threshold. All other criterion verdicts use that same threshold.

Both teaching histories produced detectable response differences in ThreeMind. Blocking target connections changed the corresponding response; matched and sham interventions had zero response effect, and restoration error was zero. Sequential-stimulus interactions in the intact network vanished when internal communication was blocked. Reversing actions in the closed loop changed subsequent sensory input and model state. Replaying identical inputs reproduced the same model state, including when action direction was reversed during replay. Environmental feedback therefore changed internal activity and responses through the inputs the individual subsequently experienced.

## Scientific conclusion and implications

The four preregistered functional claims were supported: 6.1 developed experience-dependent responses, relevant internal connections selectively caused those differences, successive stimuli interacted internally, and action and environmental feedback reshaped subsequent experience. All eight sources exhibited the four properties together. **The study constructed autonomous activity in 6.1 according to the operational definition fixed before execution.**

The comparator results identify the distinction. The finite-state controller retained experience and used internal state to affect responses; the Hebbian network also adapted to feedback; the recurrent network showed temporal interaction in some sources. None met the conjunction. ThreeMind won this comparison on its preregistered joint criterion, reproducing the earlier mechanism finding on the new 6.1 material.

The result supports proceeding to the independent 64-group confirmation. These eight sources will not enter confirmation statistics. No preregistered scientific stopping condition was triggered.

## Verification, cost and evidence

On separate apparatus material, four execution paths for each of five systems—ordinary observation, frequent observation, save/restore and a host pause—produced identical whole-system endpoints. Independent verification passed for all 4,240 formal whole states, 2,560 probes and 160 closed-loop replay groups. Sixteen RNN teaching calculations were independently reproduced. Analysis loaded no Core engine and advanced no scientific individual.

The two Core connection sets each contained two edges with equal node degrees. Weight and teaching-activity residuals met the preregistered 0.02 limits. The maximum standardized RNN matching residual was 0.36473, below its 0.5 limit. Matching and replay measurements were valid for every source.

Formal execution took 419.17 seconds with peak private memory of 564.82 MiB. Before analysis, files occupied 164.91 MiB logically and 175.11 MiB of allocated storage. The once-per-second resource guard recorded minimum available commit, RAM, C-drive and E-drive capacity of 13.42, 12.87, 10.50 and 91.13 GiB, respectively, above the 5/4/5/25 GiB reserves.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria61-v1/`. Research record: `84cc0d63-6ec4-5cb1-a527-5f002881f9b6`. Per-source values are in `analysis.json`; independent verification is in `audit.json`. Final delivery is established by the complete API readback and zero pending requests in `publication/completion.json`. Verification was performed by this study's tools and assistant and is not labeled an external researcher's replication.
