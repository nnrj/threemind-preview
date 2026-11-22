# Candidates for 6.2: novelty, connection retention and an inertial-sensory preset

2026-11-14. These recommendations use completed studies R51t2–t6. This is an assessment, not implementation authorization. Production kernels and defaults are unchanged; the comprehensive replication campaign remains paused.

## Recommendations and evidence

| Item | Recommendation | Direct evidence |
| --- | --- | --- |
| Immediate novelty | Retain the existing option and prioritize it as a candidate default for 6.2 | Combined with legacy retention, it recovered both prefix curricula; arrival-window novelty did not. Disabling the immediate bonus exactly preserved success, so the advantage here is avoidance of an adverse window effect. |
| Arrival-window novelty | Retain as an option; do not treat the earlier transient-response gain as universal superiority | Earlier calibration was positive but omitted prefix discrimination. Weights learned with the window transferred failure into a successful recipient. |
| Legacy connection retention | Include an optional reference and candidate for 6.2; evaluate before choosing the default | Stability-dependent slowing of forgetting and transmission-driven weight reinforcement were individually necessary in the successful combination. Genuine 3.1/5.1 recovered; the current 6.1 combination has not. |
| Automatically enabling H growth and relaxation with legacy retention | Keep these mechanisms separate initially | Legacy weight forgetting uses stability, not H. Enabling H flags may do nothing; making H act as well would define a new hybrid. |
| Inertial-sensory reversal preset | Provide an optional, initially disabled preset that exposes its resolved parameters | Raising the connection signal threshold from 0.0004 to 0.004 after identical teaching reversed responses in 4/4 blocks. The registered closed-loop posture benefit was not achieved. |

## Choosing between novelty modes

6.1 already supports `novelty_mode="immediate"` and `"arrival-window"`, with the latter as default. Immediate mode does not require inventing a new feature. The assistant proposed the arrival window and the author authorized it before implementation; the [authorization audit](novelty-authorization.en.md) gives the original statements and dates.

In R51t6, disabling the immediate bonus completely, retaining only its weight increment, or retaining only its stability increment produced 18 exact endpoint matches and 18 exact process matches against the reference. These results reject the explanation that an additional immediate bonus is required to retain the prefix relation. Transferring window-trained weights into the successful recipient abolished discrimination; the reverse exchange restored it. Default selection should protect relational discrimination rather than reward stronger activation alone.

**Immediate mode is my preferred candidate default for 6.2; arrival-window mode should remain available.** Before selecting a production default, test the candidate with 6.2 addressing and transmission on the same prefix material, then check novelty-related retention, selectivity during persistent activity, and completed mechanism findings affected by the change. That is a separate selection task; R51t6 has completed its registered component-localization targets.

## Why legacy retention and H are different

Legacy retention stores connection stability s between zero and one. Co-stimulation and actual transmission can increase s; disuse reduces it. With the legacy parameters, every 100 milliseconds a connection that did not actually transmit in that period multiplies its weight by `1−0.0023×(1−s)`. Higher s slows forgetting. A recent-transmission variable can slow the decline of s, and transmission in the current period can exempt the connection from that weight-decay update. These are distinct effects.

The current time scale H controls the rate of a selected decay curve. Increasing H and relaxing it implement a different retention scheme. Both schemes express the idea that experience affects forgetting, but they use different state variables and update rules. Legacy retention does not slow forgetting by increasing H.

The proposed organization is:

1. Retain single-age decay as one family, with exponential, power-law and inverse-logarithmic options and the existing meanings of H-related controls.
2. Add legacy stability retention as a separate candidate family. Enable its own stability growth and decline by default within that option, with independent disabling controls. Keep reinforcement of base weights separate; disabling retention growth must not silently disable transmission learning.
3. Establish the complete legacy rule as the reference first. R51t6 separately removed period-specific decay exemption and recent-transmission protection without losing success. Their joint removal has not been tested, so this is a candidate simplification, not a verified combined deletion.
4. Do not restore global graph scans. If implementation is authorized, use 6.1 local events and timers and verify complete-state and Python/Rust consistency.

A candidate combining stability protection with H growth and relaxation would need an explicit hybrid formula: which decay term H controls, how the two influences combine, and comparisons with each scheme alone. The present evidence does not establish a need to combine them, so that hybrid is not recommended as the initial default.

## Which threshold the inertial-sensory preset changes

The verified parameter is the **connection signal-amount threshold**, `signal_threshold`: retain `signal_threshold_enabled=True` and increase the value from 0.0004 to 0.004. It tests the amount computed after connection weights, synaptic resources and other transmission terms, and affects both activation and inhibitory signals. It is neither the weight-deletion threshold nor the source-node controls `activation_send_threshold` and `inhibition_send_threshold`; those remained unchanged in these comparisons.

An experimental configuration or UI preset can therefore be called “inertial-sensory reversal experiment preset.” Applying it should display `signal_threshold=0.004`, save the fully resolved configuration and permit explicit editing. It should be disabled for ordinary new individuals, should not adjust itself according to answers or observed reversal, and should not silently override other parameters. This reuses an auditable configuration without adding a rule that directly reverses output.

Reversal was recovered on the tested materials. Its bodily consequence was also tested: the primary error decreased by 8.61% with positive wiring, below the registered 10% target, and increased by 0.49% with reversed wiring. None of 160 Core-controlled trials stabilized; the PD reference stabilized in 8/8. These results support preserving the preset for research, not making it a universal default. Whether a new task reverses still depends on its inputs, learned state and dynamics.

## Implementation scope [Public edition: manuscript editing or private locator omitted.]

The completed work comprises the authorization audit, isolated component experiment and candidate assessment. No 6.2 implementation, 6.1 default change or campaign restart has occurred. If implementation is approved next, specify which completed findings are affected and require checking; do not erase existing 6.1 evidence or automatically repeat every experiment.

[Public edition: manuscript editing or private locator omitted.] Historical findings, replication and this causal decomposition should retain their actual versions. The [study report](report.en.md) and [historical report revision 2](../dynamics_function/prefix_cross_report/report-r2.en.md) preserve that progression.
