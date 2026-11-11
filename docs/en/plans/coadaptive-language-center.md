# Individual coadaptive language center: E52

2026-10-05, approved bounded work. [简体中文](../../zh/plans/coadaptive-language-center.md)

E50 demonstrated known-reference naming and partial internal causal contribution, but failed wholly new assignments. E51 did not fit its own supervision reliably. These are different problems; neither complete latent semantics nor a broken Core is assumed.

Add an independent expression adapter that learns from scratch, keeps bounded teaching replay, updates in small batches, and optionally returns its actual utterance through the unchanged text sensor. Teacher feedback likewise travels through ordinary sensory inputs. Preserve Core formulas, defaults, time, input encoding, old models and evidence. The first version adds no cross-window factual cache, hidden intent labels, or gradients into Core.

The user's “multiple angles” means intersecting linguistic descriptions and relations, not just camera viewpoints: two colors crossed with two shapes, red/blue spheres/boxes; names, properties and same-color references, with unseen wording and contrary assignments. Within-reference agreement and between-reference distinction are both required; intervention remains necessary to exclude direct sensory guessing.

## Stages

1. Deliver Python/CLI, bounded continual fitting, checkpoints/replay recovery, and explicit output-feedback routing.
2. Start blank. Teach two objects, add two, correct the first two names while checking retention of the latter. First ten consecutive presentations of each statement, then two increasingly spaced reviews; intensity1,20ms language frames, unchanged physical telemetry replay.
3. Compare adaptive feedback, adaptive no-self-feedback, and adaptive expression with Core plasticity disabled. Evaluate the earlier frozen head on the same new observations. Self-feedback introduces real extra input; benefits cannot automatically be assigned solely to closed-loop agency.
4. Test learned and held-out descriptions, relational wording, visual cues and unprompted windows. External labels are teaching-only; inference excludes answers, stage/object/history IDs.
5. Use related-edge silencing, matched silencing, rescue and exchanged same-origin experience with a fixed expression adapter. Report system learning separately from Core contribution.

Start with one source. Below7/8 baseline fit, preserve failure and allow only one preregistered numerical diagnostic before expansion. Second source and larger causal checks depend on that gate. No Core change to force success. Complex logic, hours/yesterday, and emitted-signal-vs-state-bus comparison remain separate.

Budget:640new sources/probes, single worker,3h cumulative simulation/training,4GiB RSS/3GiB GPU, free RAM2/C5/E15GiB.3GiB local evidence soft stop,8GiB including archive/database hard cap. Shared account52% start,+6points stop expansion,+10stop new compute. Local commits, no push.

## User statement, translated

The user approves exploring an individual, plastic language-center adapter shaped jointly with ThreeMind and receiving feedback. They correct “multiple angles”: different sentences referring to the same entity should support the same translation. Pointing at the moon while saying “moon” or “月亮” initially leaves ambiguity between the moon and moonlight; further descriptions such as drawing a circle and calling the moon round can disambiguate the referent. This is offered as a hypothesis, not an established proof. The exact Chinese original is retained in the linked Chinese plan.

[Coadaptive BCI research](https://brainmind.umin.jp/PDF/wt18/Carmena.2.pdf) motivates the design, not a language claim. [Fast-weight Transformers](https://proceedings.mlr.press/v139/schlag21a.html) remain a future candidate; bounded replay and gradient updates are not falsely described as implementing that mechanism.

[Execution registration](../../../lab/explorations/2026-10-05-coadaptive-language/design.en.md).

## In-run clarification

The user states their ideal peripheral is an intermediary translator without independent answering capability; stronger peripherals may also be compared and the ongoing run should continue. Exact original is in the Chinese plan. Decision: retain current arms and add a transcription-only adapter that never receives task-assignment supervision, within the same budget. System answering and content attributable to Core remain separate claims.

## 2026-10-05：阶段交付 / Phase delivery

E52 phase complete: adaptive peripherals and actual self-hearing delivered. Questions score 24/80 versus 25/80 without self-hearing and 31/80 with Core plasticity off. Literal linear transcription scores 4/4 per source versus Transformer 1/4; recalled-content translation remains unreliable, with no Core/default change.

[Report](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md)
