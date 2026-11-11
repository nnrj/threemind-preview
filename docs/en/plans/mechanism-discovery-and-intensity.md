# Facilitation and strong stimulus mechanism study

[中文](../../zh/plans/mechanism-discovery-and-intensity.md) · [Research backlog](research-backlog.md)

2026-09-30. This discussion authorizes explicit artificial controls, searches for existing local explanations, selective ablation and independent replication. We examine history-dependent sensitivity and whether lasting strong-input effects need a separate intensity bonus. Ordinary defaults and historical consciousnesses remain unchanged before evaluation.

## Facilitation

Facilitation temporarily increases a connection's tendency to release after recent transmission. It differs from lasting consolidation and does not create unlimited resources: increased release can deplete the available pool, so the next actual transmission may still be weaker.

The implementation retains an available fraction x, utilization u and timestamp per edge. Between transmissions u decays with its facilitation time constant; at release it increases by U(1-u), and the released fraction is ux. U defaults to 0.5, resource recovery to 0.8 seconds, and facilitation to zero, meaning disabled. The research preset uses 1 second, an exponential time constant, not an abrupt expiry. Refractoriness, self-inhibition, facilitation and consolidation are distinct.

[Markram, Wang and Tsodyks, 1998](https://pmc.ncbi.nlm.nih.gov/articles/PMC20259/) supplies a biological experimental and modelling reference for activity-dependent utilization and depletion. It does not establish optimal ThreeMind parameters. Previous one-second facilitation improved some retention measurements but not all motor tasks. Retain ordinary zero initially and compare 0.1, 0.3, 1 and 3 seconds, reporting interference, saturation and uncued activity alongside retention.

## Preserving historical kernels

Creation and restoration first bind kernel identity, state schema and complete configuration. Registry entries dispatch to preserved implementations. Continuous and LIF derived kernels additionally validate mechanism definitions and definition hashes; causal/9 has a frozen baseline description and behavioral witnesses. Restoration uses saved parameters rather than new-creation defaults and rejects identity/schema mismatches. Propagation clocks, pending events and local operator histories are saved too.

Earlier causal/1 through causal/8 are read-only in the current registry: they cannot resume execution here and are not automatically converted to a new kernel. Replaying them requires the matching historical code and environment. This differs from the still-supported older kernels that continue under their saved identities.

A version string alone cannot preserve behaviour if shared code changes. Frozen witnesses, historical-state regression and preserved implementation paths remain necessary; implementation hashes provide provenance.

## Artificial controls for discovering local mechanisms

Define measurable effects and counterexamples first. A deliberately artificial gain may serve as a labelled research control, separate from normal dynamics and claims about physical mechanisms. An observed benefit establishes task-specific functional utility, **not that nature must implement the artificial rule or that the model must produce that outcome**.

Disable the artificial rule and seek similar effects in the existing mechanisms. Keep unrelated forgetting, inhibition and resource dynamics enabled. Separate learning, retention and expression, and use sham interventions, selective ablation, restoration, matched no-cue copies and new materials. Similar outputs alone do not establish identical mechanisms. Prefer an adequate existing local explanation; consider new grounded mechanisms only after identifying the missing function.

Distinguish source quantity, encoded input, reception, activation increment and subsequent network response. Monotonic direct response at a fixed state can coexist with history-dependent whole-network sensitivity.

## Scope

Use continuous-memory/2 with unchanged mapping, clock and propagation threshold. Set the existing intensity_gain to zero to remove the separate bonus, versus 0.075. Switch facilitation using its existing time constant. The edge consolidation switch gates positive existing-edge updates, not forgetting, edge birth, node histories or all plasticity. A condition with both named factors disabled is therefore not a non-learning network.

Ordinary first/repeat consolidation still depends on incident drive after removing the extra bonus. If it explains the effect, report that formula-level explanation rather than attributing everything to emergence. See the [prospective experimental design](../../../lab/explorations/2026-09-30-intensity-mechanisms/design.en.md) and subsequent report for decisions.

## Completed study

Completed 1246 stored instances, six bilingual registrations and four observation-free replays with identical full Core hashes. The [report](../../../lab/explorations/2026-09-30-intensity-mechanisms/report.en.md) covers factorial controls, formation ablations, facilitation constants, history/cue sensitivity, expression interventions and connection restoration.

Birth, ordinary touch consolidation and novelty produced part of the strong-input advantage without the extra term. One-second facilitation mainly aided early expression and did not fully replace the extra term's later weak-cue gain. Ordinary defaults remain unchanged; subsequent associative studies should prioritize the one-second research setting. Hot-switch state inheritance is a separate open issue, distinct from continuously enabled development. The [backlog](research-backlog.md) retains outstanding work; completing this study does not complete all research.

## Researcher discussion

The researcher proposes constructing an explicit, possibly ungrounded functional control when the desired effect is known but its permitted mechanism is unclear; if useful, seek comparable behaviour without that control, locate the cause through ablation and improve the identified mechanism. The motivating hypotheses are that sensitivity primarily develops through experience and strong-stimulus effects can arise from more basic local mechanisms. The Chinese document preserves the original wording; the methodological qualification above is an explicit assessment, not an alteration of the researcher's statement.
