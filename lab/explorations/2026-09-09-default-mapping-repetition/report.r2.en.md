# Default-mapping replication: blocked sentence teaching

> **Revision r2 · 2026-10-10**
> Revision reason: Relocate generated evidence out of Git; preserve original bytes and conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-09-09. Project `a9bd83bb-3d57-4eab-859d-68312f6b2b17`. The complete Chinese report contains every final candidate and stage table.

The previous experiment incorrectly disabled NFKC when interpreting the requirement to preserve source punctuation. This replication uses the complete existing `TextSensorConfig()` and `Config()` defaults, with frozen product-source and native-binary hashes. Literal input payloads preserve speakers, punctuation and sentence components; the unchanged sensor applies its default NFKC and encoding. The four family examples now end with the periods supplied by the user. This is a separate project; no previous data were altered.

Every dialogue sentence is delivered 20 consecutive times before switching, repeated for three sweeps (600 deliveries). Seven family/rule sentences follow with the same blocked repetition (420). Dialogue review then uses five consecutive deliveries per sentence (50); finally four held-out-name parent facts use 20 consecutive deliveries for three sweeps (240). Each complete course has 1,310 deliveries at fixed 0.8-s simulated intervals. The maximum carrier length is 17 characters; all training carriers fit the existing single-frame default. No extra background text is used.

Four fixed encoding seeds are 41701–41704. Each has a counterfactual family branch from exactly the same 1,070-input state. Two additional models with the first two fixed seeds consistently swap the two dialogue objects, preserving every speaker and punctuation mark. All controls were planned before this replication began. This is a small descriptive experiment, not a confirmatory significance claim.

Primary measurements continue the full current state with zero wait. Auxiliary copies use the existing `threemind.birth/1` rule: retain long-term topology and attributes, but clear activation, inhibition, recent traces, eligibility and the in-flight queue, and reset clocks and related runtime state. They are new initial conditions, not a resumption of the same individual. Each cue and no-cue baseline starts from an independent copy, learning remains enabled, and no probe changes are written back to the teaching model. The fixed main summary is sham-corrected mean activity over 0.2–1.0 s. Early activity and full traces are retained. Scoring masks do not remove any raw node activations; unavailable masks remain missing, not zero. The tables below describe observer projections, not generated natural-language answers.

## Final numerical results

| Arm | Route | Measure | Strict target top / scorable | Total | Ties | Mean contrast |
| --- | --- | --- | --- | --- | --- | --- |
| normal | continuation | pair | 0/8 | 8 | 8 | 0 |
| normal | birth | pair | 8/8 | 8 | 0 | 0.0001057436485 |
| normal | continuation | who | 0/16 | 16 | 16 | 0 |
| normal | birth | who | 15/16 | 16 | 1 | 0.0001563656276 |
| normal | continuation | family | 0/6 | 8 | 6 | 0 |
| normal | birth | family | 2/6 | 8 | 1 | -1.346165325e-05 |
| crossed | continuation | family | 0/6 | 8 | 6 | 0 |
| crossed | birth | family | 1/6 | 8 | 0 | -3.29468362e-05 |
| pair_swap | continuation | pair | 0/4 | 4 | 4 | 0 |
| pair_swap | birth | pair | 4/4 | 4 | 0 | 0.0001333653798 |
| pair_swap | continuation | who | 0/8 | 8 | 8 | 0 |
| pair_swap | birth | who | 8/8 | 8 | 0 | 0.0001739960172 |

## Pair-swap controls

| Seed | Route | Measure | Normal correct margin | Swapped correct margin | Following difference |
| --- | --- | --- | --- | --- | --- |
| 41701 | continuation | pair | 0 | 0 | 0 |
| 41701 | continuation | who | 0 | 0 | 0 |
| 41701 | birth | pair | 9.067297571e-05 | 0.0001111094665 | 0.0002017824422 |
| 41701 | birth | who | 0.0001816468579 | 0.0001759209715 | 0.0003575678295 |
| 41702 | continuation | pair | 0 | 0 | 0 |
| 41702 | continuation | who | 0 | 0 | 0 |
| 41702 | birth | pair | 0.0002123879278 | 0.0001556212931 | 0.0003680092209 |
| 41702 | birth | who | 0.0002160760725 | 0.0001720710629 | 0.0003881471354 |

## Crossed-family controls

| Seed | Route | Z difference | W difference | Mean |
| --- | --- | --- | --- | --- |
| 41701 | continuation | 0 | 0 | 0 |
| 41702 | continuation | 0 | 0 | 0 |
| 41703 | continuation | unscorable | unscorable | unscorable |
| 41704 | continuation | 0 | 0 | 0 |
| 41701 | birth | 0 | 0 | 0 |
| 41702 | birth | 0 | 0 | 0 |
| 41703 | birth | unscorable | unscorable | unscorable |
| 41704 | birth | 0 | 0 | 0 |

## Interpretation

The auxiliary structural birth copies show a trainable correspondence bias under the existing default mapping. All 8 original-pair cues favored their taught object, and 15 of 16 question cues favored their taught name (one tie). All four seed means were positive. Both prospectively chosen pair-swap controls followed the reversed teaching: 4/4 pair cues and 8/8 question cues favored their new targets. In both seeds, normal and swapped correct-direction mean margins were positive. This supports a learned correspondence bias in this small design rather than merely a fixed preference for one symbol. These counts are activation rankings, not generated-answer accuracy or proof of general language or speaker-role understanding.

The effect did not grow monotonically. After the first complete dialogue sweep, birth-copy pair and question rankings were 8/8 and 16/16, with mean contrasts about 0.00150 and 0.00176. Final contrasts were about 0.000106 and 0.000156. Around 48–58% of first-sentence edges still had their original birth identity at the end; other edges were lost or recreated. At the 600-input and final checkpoints, all extant edges in the four primary models had weight 1. This demonstrates consolidation as well as loss. Without an ablation, it does not establish that weight saturation caused the readout limitations; topology and other local state still matter.

The primary ongoing-state route yielded zero final word-candidate contrasts in the fixed window. It must not be replaced by the positive birth-copy route. However, zero word projections are not absence of a response. All 16 complete primary family queries initially changed the full activation vector. Twelve queries across three seeds matched their sham activation vector at subsequent 20-ms samples. The four complete queries in seed 41702 retained a difference in another anonymous channel through 1 s (L1 differences about 0.649–0.732). Bare Z/W cues in seed 41703 also retained differences. No semantic label is assigned to these channels. Sampling can miss faster changes, and activation is not the full dynamical state.

Held-out-family birth probes had two strict target-leading cases among six fully scorable queries, with two additional queries unscorable. The original positives were seed 41702/W→U and seed 41704/Z→X. In the latter, the father question also favored Y, an interesting isolated role-sensitive case. Yet the X-versus-U preference did not follow the counterfactual family facts in any of the three fully scorable seeds; every planned per-family following contrast was zero. Some other candidate activations did change, so this is not a claim that the changed training affected nothing. Explicitly taught family queries were also only 2/6 strictly target-leading, limiting attribution specifically to composition rather than fact learning or measurement.

The result supports further work on trainable association while leaving reliable grandfather-rule transfer unestablished in this design. It neither demonstrates general language understanding nor disproves the overall ThreeMind hypothesis. The next useful step would separate persistent-state observation, limitations of exclusive word masks, and reliable retrieval of explicitly taught family facts before expanding composition tests. No additional experiment, mapping change, Core change or parameter search was performed here.


## Resources and provenance

Experiment-process time: 20.72 min; sampled maximum process RSS: 194.74 MiB. 8820 literal deliveries, 10 teaching records, 44 checkpoints, 132 measurement jobs and 588 probe/sham copies. Pre-publication database growth: 365.67 MiB; local evidence: 9.28 MiB. Final post-publication measurements are in `acceptance.json`. Account usage baseline was 66%, stop line 84%; observations are account-wide and can lag.

All recorded source carriers, defaults, normalized hashes, actual stimulus channels/amplitudes and delivery timestamps were verified; all source/checkpoint hashes were checked. Four fixed representative ZIP bundles and their final model hashes and 51-sample raw activation traces were checked. All 1912 prior consciousness heads and associated old document/note heads remained unchanged. Source and native-binary hashes are unchanged. This does not claim a browser UI test or exhaustive unpacking of every ZIP.

The platform stores the plans, three records, linked report, result notebook and Markdown/HTML exports. Raw ZIP links and checkpoints are indexed in `evidence-index.json`. Full source identity is in `implementation.json`.


## Data location revision

Selected generated evidence has been archived and verified byte for byte. Original reports, criteria, conclusions and embedded source_commit values are preserved. The logical downloads below require the current host administrator. The data directory is not public.

`data/experiments/2026-09-09-default-mapping-repetition/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [measurements.json](/api/v2/storage/research-artifacts/research-artifact:dbfff82fe099b76a2bd3de00/content) — 683222 B; SHA-256 `cf7e579516363d0af8efaa2d1050586a51078fc602dd6e0e2c87cca8b1ed568b`.
- [raw-activity-differences.json](/api/v2/storage/research-artifacts/research-artifact:ee9d13d05f5136dd41cac98d/content) — 176450 B; SHA-256 `99ce5441b9563dde3045f63f7b7eb1b65ca0eec5bfbd6692606e5d225e2f4dd2`.
- [time-courses.json](/api/v2/storage/research-artifacts/research-artifact:943f9d7ab9ccc620ab61f098/content) — 967982 B; SHA-256 `8c4d20babadaf773793c4128ebf1dc1bdf024e66b3d3446418c68e1a2b9122b1`.
- [training-traces.json](/api/v2/storage/research-artifacts/research-artifact:181fcc88fa99d7496f49f41e/content) — 1988076 B; SHA-256 `b0c110b1d394729042b1c271c5aca78dd48772dae977d521745bc3ef04babed9`.
