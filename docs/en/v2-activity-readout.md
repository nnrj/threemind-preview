# Temporal activity readout

[中文](../zh/v2-activity-readout.md)

2026-09-30: [Activity analysis V2 and reusable tools](v2-observation-tools.md) now record the complete bounded process. The V1 description below remains valid; new configurations default to V2.

The historical algorithm remains **Activity steady-state detection** (`temporal_readout`). Candidate membership, relative distribution and total amplitude must all stabilize. Historical classifications are unchanged; `residual_decay` is now displayed as “Amplitude decay”.

**Activity process analysis** (`activity_readout`, evidence version `threemind.activity-analysis/1`) separately measures:

- **Response-pattern convergence:** after delivery and minimum observation, every full excess-activity vector in the tail window is compared with the final normalized vector using total-variation distance. Zero/subfloor totals are never normalized. Save actual node activations at the first qualifying decision-window end.
- **Amplitude change:** stable, decaying, growing, varying or below floor. Declining amplitude does not invalidate stable proportions. Raw activation vectors/totals are retained separately from excess activity.
- **Periodic activity:** three nonconstant repeating cycles in equally spaced observations, checking both complete distributions and amplitude. Fixed membership with oscillating amplitude is measurable. This establishes sampled periodicity, not an exact continuous period.
- **Response end:** excess activity remains below the floor throughout the tail window. Background activity may persist; this is not Core death.

All four analyses have separate switches. Detecting a stable pattern does not terminate the other analyses. Observation ends when the response ends or its budget expires. Primary ranking is preserved in `primary_result.nodes`, `candidate_ids`, and `decision_activation`; `ranking_time_us` identifies its measurement time. `last_activation` always means the final sample of the overall observation window. Peaks and integrals remain separate. Missing pattern/period detection does not produce a fabricated primary response.

New UI protocols enable both observers, making process analysis the primary chat result and retaining steady-state results as comparison evidence without duplicate chat messages or AI triggers. Historical saved protocols without `activity_readout` leave it disabled on restoration. Historical standalone CLI defaults also remain intact.

Configure through the shared graphical/JSON catalogue. Temporal probe experiments select source inheritance, process analysis, or only the original algorithm, always on isolated copies. The result page exposes all four analyses, decision time, decision activation, window-end activation, peaks and trajectories. CSV/JSON/report columns distinguish `decision_activation` from historical `last_activation`.

CLI: pass `--readouts new-evidence.jsonl --readout-config config.json`, with:

```json
{"structural_readout":{"enabled":false},"temporal_readout":{"enabled":true},"activity_readout":{"enabled":true}}
```

The new analysis uses complete excess-activity vectors rather than the old top-candidate subset. Thresholds affect derived analysis only; complete node aggregates and positive raw/excess trajectories are retained. Missing positive-vector components mean zero; node presence must still be checked against complete node aggregates and source counts. Left-hold integration between samples is an estimate, not continuous observation.

The default complete-trajectory budget is 2,000,000 values per window, alongside node, sample, concurrent-window and time limits. Budget exhaustion explicitly censors observation rather than silently dropping nodes. A valid earlier pattern decision and a later observation cutoff are recorded separately. Insufficient coverage does not prove absence. Both observers share read-only samples and terminate independently; no result is fed into Core.
