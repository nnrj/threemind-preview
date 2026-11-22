# Chapter 18: one weight and one decay age

[中文](../../../zh/history/chronicles/18-kernel53.md) · [Approved plan](../../plans/kernel53.md)

## Recorded 11 November 2026: replacing contribution histories

R46 compared three decay curves and exposed the cost of the /5.2 representation: each reinforcement created a separate contribution whose age remained in later sums. The author requested equal treatment of the connection's current weight, retaining its accumulated age on reinforcement, and explicitly authorized implementation of the discussed ThreeMind 5.3 plan. These decisions came from the current conversation; this chapter's date records implementation, not an invented timestamp for earlier messages.

Version 5.3 stores one current weight and one cumulative normalized decay age. Reinforcement increases the current weight; age normally continues, with reset after actual positive reinforcement as an alternative. Timescale growth and the original linear relaxation remain independently selectable and default off. Weight strengthening remains enabled. Four curves are available: exponential, power law, inverse logarithmic and power law followed by an exponential tail. The initial power-law selection and 30-second scale are engineering starting values pending scientific comparison.

Structural deletion now compares current values on a fixed internal-clock grid, every 100 ms. Same-time stimulation and reinforcement precede deletion. This removes per-connection expiration inversion but incurs scans proportional to extant structure. The cost is measured rather than assuming that simpler rules are faster on every workload.

## Separating node emission from directed transmission

Nodes offer excitation and inhibition according to their own state and pay energy for attempted emission. Connections calculate delivered quantities from effective weight, offered signal, synaptic resources and enabled spatial factors. Both signal types share one resource release on an edge's emission and use the same joint threshold. Transmission is evaluated before reinforcement. Inhibition contributes to learning by default; an explicit switch removes that learning contribution. Opposite directions retain separate states. An incoming edge no longer automatically supplies an inhibitory reverse route.

These are authorized new dynamics, not an equivalent optimization of the historical kernels. Historical /5.1 and /5.2 code and evidence remain intact, and the global creation default remains /3. A faithful /5.2 Rust implementation is separate pending work; /5.3 cannot be relabelled /5.2. Author-edited manuscripts are outside this implementation task.

## Engineering evidence and scientific questions

Independent Python and genuine Rust /5.3 implementations now have version routing, parameter catalogues and persistence. Eighty /5.3 engineering checks and fourteen local-instrument checks passed. Historical fixed witnesses and independent file/database interoperability were also checked. Engineering validation found and fixed omission of the new age field from binary persistence, then verified complete readback through the standalone runtime. Static checking also exposed a missing import on the local-energy supply path; four explicit delivery comparisons passed after correction. No scientific subject was started with either faulty apparatus.

For a small active fixture of 64 nodes and 64 directed edges, median advancement of ten internal seconds took about 0.0246–0.0285 wall seconds in Rust and 0.632–0.642 in Python. This supports using Rust for the new batch. Passive scans, serialization and a short input course were measured separately; the numbers do not estimate full adapter training or large-graph throughput.

R47a next compares four curves across eight fresh origins and independent delay cohorts, asking about structural retention, temporal expression and forgetting of weak input. Strong-input and connection-arrival novelty gains have identical-input gain-disabled controls. Measurement retains complete activation, inhibition, direct and associative time courses. Confirmation with 48 fresh origins and personal Transformer joint development remain separate required work. Current execution facts are in the [handoff](../../../../lab/explorations/2026-11-11-kernel53/HANDOFF.md).

## 11 November 2026, continued: first complete comparison after simplification

R47a completed 4,608 continuous sequences; independent arithmetic verified 9,216 complete boundaries. Inverse logarithmic decay retained 300-second structure and temporal expression in all eight origins for massed, spaced and strong-input courses, winning this retention comparison. Exponential scored 0/8 in all three; power-law and power-exponential curves retained some structure without consistently preserving response trajectories. All four scored 0/8 for weak-memory forgetting at 30 seconds, so no combined default candidate was selected. Both specific gain mechanisms operated in 8/8 origins for every curve.

The result establishes retention beyond the initial 30-second scale using one weight and one age, and identifies weak-connection removal versus long tails as the remaining design trade-off. Retrospective field decomposition found the late differences mainly in associative and inhibitory processes; primary criteria were retained. Fresh 48-origin confirmation and personal Transformer joint development remain required. The 85,537,475-byte, 32,703-member archive was read back completely through the research API; the record is completed/verified/pending0. [Report](../../../../lab/explorations/2026-11-11-kernel53/report.en.md)

## 11 November 2026, continued: confirmation with 48 new origins

R47b completed 5,376 continuous sequences and 10,752 complete boundaries at the preregistered fixed sample size of 48 origins. Inverse logarithmic decay produced greater 300-second history-dependent expression than exponential, power-law and power-exponential decay. All 48 paired differences had the predicted direction in each comparison, and all three passed the prespecified multiplicity threshold. Its expression targets passed in 48/48 massed, 37/48 spaced and 48/48 strong-input cases. The other eleven spaced cases failed the original early-signal validity threshold and remain failures; retrospective diagnosis does not replace the criteria.

This confirms the local retention advantage and independently confirms the weak-memory forgetting failure: every curve scored 0/48 for deleting weak-experience connections at 30 seconds. Inverse logarithmic decay passed the conditional 30-day tail target in only 16/48 spaced and 14/48 strong-input cases. No curve meets all registered goals, so the engineering and global defaults remain unchanged. The 100,395,432-byte, 38,083-member archive passed complete API and member readback; the record is completed/verified/pending0.

R47c was then registered and started with eight origins and four curves, comprising 32 complete individuals. Personal temporal Transformers, spaced reviews, correction, reversal and return courses preserve each individual's whole state. Their task results will be judged separately from local-instrument retention.

[Confirmation report](../../../../lab/explorations/2026-11-11-kernel53/confirmation/report.en.md) · [Joint-development protocol](../../../../lab/explorations/2026-11-11-kernel53/joint/protocol.en.md)

## 11 November 2026, continued: whole-system results and version delivery

R47c completed 32 whole subjects from eight independent origins. Independent arithmetic checked 1,084 complete boundaries, 453 adapter dependencies and all scores. Inverse logarithmic decay passed initial retention, new learning with old retention, and relearning at 8/8 each; reversal scored 4/8 and failed the preregistered 6/8 criterion. Power law also passed relearning at 8/8. Protected relations under inverse-logarithmic reversal scored 128/128 both immediately and after delay, locating failure in the changed relation. Local retention gains therefore extend to continuous joint development, with conflicting-rule acquisition and retention remaining a specific target. Whole-system eight-origin exploration is reported separately from R47b's 48-origin local confirmation.

Every preregistered objective is explicitly closed. No curve meets retention, weak forgetting, tail and all learning goals together, so the engineering power-law and global /3 defaults remain. Retrospective mathematics notes that F(1)=1/2 for all four curves: a new weight near 0.035 remains above the 0.008 deletion threshold after the 30-second scale even without further reinforcement. The assistant recommends separating scale, initial learned weight and later associative reinforcement before considering a fifth weight-dependent decay candidate. That candidate is discussion only, not implemented or validated.

A faithful /5.2 Rust backend was then integrated, preserving its contribution histories and old transmission rather than substituting /5.3. Final verification passed 441 targeted regressions, twenty Rust checks and 88 historical /5.2 reference checks. Historical identities and fixed witnesses remain intact. Scale measurements reached 8,192 nodes and directed edges, with saving timed separately. All three archives and bilingual texts passed full API readback, pending0. R47c's archive contains 125,341,032 bytes and 4,186 members, SHA256 `0bf75ad8a9ded5aaa1651232c79bd944e4a426dced779124d8bd5c0af6c4bc9f`. Scientific hosts have exited. Author manuscripts, historical originals and current services were preserved; compiled standalone products are available for explicit use.

[Whole-system report](../../../../lab/explorations/2026-11-11-kernel53/joint/report.en.md) · [Engineering verification](../../../../lab/explorations/2026-11-11-kernel53/engineering-report.en.md) · [Implementation and recommendations](../../v2-kernel53.md)

## 2026-11-11: Weight-dependent decay authorized for testing

The user authorized testing slower fractional forgetting at stronger weights. R48 fixes five arms: inverse-logarithmic, fast/slow weight-dependent rules and their matched exponentials. Only edge decay changes; node support and other /5.3 mechanisms are controlled. R48a uses eight local origins; R48b uses eight new origins and forty whole learners. Protocols and engineering checks are ready; no formal scientific results yet and no production default change.

[Contemporary protocol](../../../../lab/explorations/2026-11-11-weight-dependent-decay/protocol.en.md)

## 11 November 2026, continued: the first weight-dependent result

R48a completed eight origins and 1,280 continuous sequences. Separate arithmetic checked 2,560 boundaries, 5,120 file hashes and every score. Fast decay passed weak forgetting at 30 seconds in 8/8 origins. Both weight-dependent settings lost target connections and responses at 300 seconds after review, strong input and novel experience, scoring 0/8 throughout and matching the exponential controls in pass counts. Inverse logarithmic retained structure in all three conditions and retained temporal expression after review and strong input in 7/8 and 8/8 origins. Novel experience separated structural retention from preservation of response shape; the latter failed the original criterion. No arm won the combined goal and defaults remained unchanged.

Retrospective inspection found teaching weights mainly around 0.02–0.12, where the additional-rate multiplier 1−w stays near one. Mathematically slower fractional forgetting of stronger weights thus produced insufficient retention separation in this range. This explanation was recorded after results, without changing scores. The 24,292,846-byte archive and bilingual text passed complete unified-API readback, pending0. R48b then started forty whole learners serially under the original curriculum.

The author explicitly reminded the assistant to include the Rust runtime without interrupting current work. The assistant prepared the same rule in an isolated source copy, including the native kernel, binding and standalone runtime. The scientific host continued to use frozen Python. The local negative result did not trigger parameter changes or cancellation of whole-system cultivation.

[Local report](../../../../lab/explorations/2026-11-11-weight-dependent-decay/report.en.md) · [Whole-system protocol](../../../../lab/explorations/2026-11-11-weight-dependent-decay/joint/protocol.en.md)

## 11 November 2026, continued: immediate learning benefit and delayed retention failure

R48b completed forty whole learners from eight new origins. Weight slow scored 128/128 on the immediate initial test versus 111/128 for matched slow exponential decay: seven origins improved and one tied. It passed development questions throughout without additional correction, requiring 38,400 personal-adapter updates versus 57,600, one-third fewer. The assistant explicitly retained this immediate benefit rather than allowing combined failure to erase it.

Every slow-group delayed stage nevertheless scored 50%; weight fast scored 50% immediately and after delay. Both candidates passed 0/8 on all four complete goals. Inverse log passed initial learning, new learning and return at 8/8, but reversal at 4/8. It remained the retention winner without an all-goals winner. Original criteria required both immediate and 300-second tests and both target and protected relations; pooled scores did not replace them. Independent arithmetic verified 1,820 boundaries, 939 peripheral dependencies and all 18,620 queries; 7,040 formal questions remained distinct from independent N=8.

A retrospective read-only check found eight surviving connections in every slow-group individual before the initial delayed test, at weights 0.013421–0.015323, despite only 64/128 correct answers. Deletion therefore did not explain every failure; decayed activity and the existing reader failed to preserve correct expression. In both fast groups, correct delayed answers occurred only at an already-correct starting position; all new-position choices failed. A local-review appendix confirmed two deletion/recreation episodes per fast teaching history. The original A report and archive were preserved; later interpretations were attached to B.

The 220,490,039-byte archive with 6,907 members passed complete unified-API archive/member readback and exact bilingual protocol/report comparison, completed/verified/pending0. Only after both scientific batches closed was the same rule integrated into a separate Rust kernel, Python binding and standalone runtime. Direct products passed 406 targeted checks, the actual wheel passed 54 overlapping checks, and Rust passed 20 fixed tests; all 63 Rust files matched the compiled copy byte for byte. At 1024 active nodes Rust advanced 20.8–22.6 times faster than Python, with similar costs among the five rules. The separate 11,377,690-byte engineering package was verified member by member.

The bounded comparison ended with its immediate benefit, negatives and independent candidate preserved. Defaults remain; no unbounded tuning follows. Installed products, running services, author manuscripts, historical individuals and originals were retained.

[Whole-learner conclusions](../../../../lab/explorations/2026-11-11-weight-dependent-decay/joint/report.en.md) · [Rust verification](../../../../lab/explorations/2026-11-11-weight-dependent-decay/engineering-report.en.md) · [Usage](../../v2-weight-decay.md)

## 11 November 2026, later: inverse-logarithmic creation default

After comparing power-law and inverse-logarithmic retention, learning and performance, the author explicitly selected inverse logarithmic decay for /5.3 and /5.3 for new individuals, with both /5.2 and /5.3 visible in the interface and API. This paraphrases the contemporary message in context without reconstructing a quotation from its typing errors. The decision prioritizes demonstrated retention: 48-origin local confirmation and 8/8 initial, new and return learning in whole-individual exploration. Earlier weak-forgetting and reversal failures retain their original scores and conclusions.

The implementation synchronizes the Python registry, /5.3 configuration, Rust constructor, standalone runtime and workbench. The language dialog obtains its default from the API. All historical versions and the other three curves remain available. Restoration uses saved identity and configuration, so existing power-law /5.3 individuals retain their curve. Formulas, the 30-second base scale, continued age and disabled retention growth/relaxation are unchanged. Long-run structural memory use remains for larger-scale measurement.

[Decision and engineering checks](../../plans/kernel53-default-selection.md)
