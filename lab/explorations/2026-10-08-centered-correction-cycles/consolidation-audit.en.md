# Consolidation audit after E66 completion

[中文](consolidation-audit.zh.md) · [Experiment report](report.en.md) · [Audit data](consolidation-audit.json)

October 8, 2026, 11:07, Beijing time. After the three-round experiment, the user asked whether repeated external stimulation or associative traversal slows connection decay into persistent, still-decaying memory. This audit only reads complete saved states and compares the registered native implementation with frozen/current sources. It creates or advances no subject and adds no teaching, intervention, parameter change or kernel simulation.

**The mechanism exists and was enabled: coactivation/traversal raises stability, which protects weight from forgetting. Stability is itself reversible and capped at one; the implementation does not store a separate per-edge decay time constant that keeps lengthening with cumulative use.** Disabled consolidation therefore does not explain this study. Whether protection is sufficiently persistent, or causes a specific behavioral error, remains unknown.

## Actual identity and settings

The subject uses `threemind.continuous-memory/2` with `arrival-window` novelty. The native implementation fingerprint matches the initial registration, and seven relevant Rust/Python sources match their frozen copies byte for byte. Birth, initial teaching at 180 seconds, correction at 463 and 672.5 seconds, and the final 879.5-second source all have identical settings:

| Parameter | Value | Meaning |
| --- | ---: | --- |
| `plasticity` | `true` | Structural plasticity enabled |
| `edge_consolidation_enabled` | `true` | Positive updates to existing weights/stability enabled |
| `stability_gain` | `0.022` | Stability increment coefficient |
| `stability_decay_enabled` | `true` | Stability itself can decay |
| `stability_tau` | `666.6666666666667` seconds | Linear stability-loss scale, modulated by eligibility; not a weight half-life |
| `forgetting_rate` | `0.025` | Base weight-forgetting coefficient |
| `eligibility_tau` | `0.40247707040780034` seconds | Eligibility decay time constant |

All inspected node/edge silencing lists are empty. Of 144,159 final edges, 91,484 have stability at least 0.9 and 88,279 at least 0.99. Maximum stability is about 0.999935; maximum touch count is 26,384. Already after initial teaching, 80,164 edges exceed 0.99. These states support actual consolidation, not just an enabled flag; they do not identify correct shape concepts or exclude consolidation of irrelevant/background associations.

## Implemented updates

1. When coactivation selects an existing edge, positive updates increase weight and stability. Stability includes `stability_gain × score × (1 + ln(1 + touches))` plus a bounded sensory impulse, capped at one. Touch count influences reinforcement but does not update `stability_tau`. [Rust source](../../../crates/threemind-core/src/restoration.rs)
2. Successful transmission through a connection, after thresholds and resource conditions, increases weight, eligibility, stability and `touches`. Stability increases by `stability_gain × amount`. Propagation following external input and associative propagation use this local path; arbitrary visible activation does not guarantee an update to every connection. [Rust source](../../../crates/threemind-core/src/continuous.rs)
3. Eligibility decays first, followed by `S ← max(0, S − Δt / stability_tau × (1 − eligibility))`. An edge not traversed in the current step multiplies its weight by `[1 − 0.1 × forgetting_rate × 0.92 × (1 − S)]^(Δt/0.1)`. Higher stability slows weight loss; fading stability weakens that protection. [Same implementation](../../../crates/threemind-core/src/continuous.rs)

With no further reinforcement and negligible eligibility, the formula takes about 667 simulated seconds for stability to decrease from one to zero, or about 60 seconds from one to 0.91. This is a conditional interpretation of the existing formula, not a new idle simulation or a measured weight/behavioral-memory lifetime. Input, renewed traversal, eligibility, pruning and readout matter. High stability can make weight decay extremely slow, but there is no separate permanent protective layer immune to stability loss.

`continuous-memory/2` retains these memory updates and adds novelty handling during a birth arrival window; existing-edge consolidation is not disabled. Birth novelty bonuses and repeated-traversal consolidation are distinct paths. [Version entry](../../../crates/threemind-core/src/novelty.rs) · [Python reference](../../../src/threemind_kernels/memory.py)

## Limits and discussion

All 53 original correct fixed-development answers remain correct in all three retests. The seven earlier confirmation failures finish at 2/7; they were not all previously correct and then forgotten. E65 separately recorded regression of formerly correct answers; those studies must remain distinct. The complete subject also includes a continuing peripheral, and teacher conditions, reader mapping and position transfer can affect answers.

The experiment has stopped at its three-round limit. Extending reversible stability with a more persistent, still-decaying use-history scale, or first checking whether present retention is adequate, are discussion options rather than established fixes. Any later comparison should preserve current identities, subjects and evidence, register changed versions/parameters, and measure retention, interference and readout conditions. High aggregate stability alone is not proof of strong correct memory. No Core change or such comparison was performed here.
