# Kernel 6.2 implementation, functional check and revalidation

14 November 2026. Implementation and verification are complete. The 6.2 options are delivered. Prefix recovery failed, so default promotion and the comprehensive campaign remain paused.

## Objectives

The author requested implementation of the discussed candidates as 6.2: name stability-based retention and provide independent growth and relaxation switches; support both a common connection signal-amount threshold and separate activation and inhibitory thresholds; and retain research presets for short inhibition decay and inertial-response reversal. The implementation covers Python, Rust, the independent runtime, API, commands and frontend. Historical versions and individuals retain their identities.

The functional check has a separate target: determine whether stability-based retention combined with immediate novelty restores correct responses to both prefixes in the two original exchanged-material blocks. It uses the historical criterion without changing the threshold after seeing results. Engineering correctness and functional recovery are assessed separately.

## Implemented changes

| Item | Implementation in 6.2 |
|---|---|
| Stability-based retention | `consolidation_mode="stability"`; greater stability slows weight forgetting; each connection updates through local events |
| Stability growth and relaxation | Independent switches, enabled by default within this option; disabling stability growth preserves reinforcement of base weights by actual transmission |
| Single-age decay | Exponential, power-law, inverse-logarithmic and power-exponential curves remain available; inverse-logarithmic remains this family's default, and reinforcement preserves age by default |
| H time scale | Growth and relaxation remain optional for single-age decay, disabled by default and distinct from stability-based retention |
| Separate connection thresholds | Each type can override the common threshold independently; null inherits the common value, and explicit zero disables that type's numerical cutoff |
| Equal explicit thresholds | Each field remains stored and read separately; the resulting trajectory matches the equivalent common threshold |
| Research presets | The inertial-reversal preset uses a common connection threshold of 0.004; the short-inhibition preset uses a decay time constant of 0.0580338705786432 seconds; both require explicit selection |
| Retained mechanisms | Fixed-function addressing, local deletion, in-flight delivery policies, finite energy, short-term resources, inhibition and complete structural inheritance |

Source-node activation and inhibitory sending thresholds remain 0.004 and 0.002. The common connection signal threshold remains 0.0004, the deletion threshold 0.008, and the hard weight gate is disabled by default. The three presets expand into actual configuration values. They do not adjust themselves from task answers. Presets can be combined in the interface because each changes only its listed fields.

6.2 has separate Python and Rust transitions, a kernel definition and a saved identity. Common numerical, queue and storage infrastructure remains shared. The SHA256 hashes of all six 6.1 implementation files match their pre-task values. [Mechanism details](mechanisms.en.md) specify the formulas and controls.

## Engineering verification

The final complete test run passed all 338 tests. Coverage includes full-state comparison with compatible 6.1 configurations, Python/Rust agreement, save and restore, non-perturbing observation and host pauses, partitioned advancement, separate thresholds, local versus global deletion, input at a deletion instant, inheritance, JSON/TMIND round trips through the independent Rust runtime, and actual 6.2 defaults when created without a configuration file. The frontend passed type checking and its production build. Python Runtime, Transformer and Lab wheels and the native Rust wheel were built.

The configuration catalogue exposes 131 fields for 6.2. Python defaults match the Rust default JSON. The independent runtime restores complete states under their 6.2 identity. The verified native wheel is installed in the project's `kernel-venv`; source packages retain their existing editable installation. Running services were not restarted and will load the new version at their next normal restart.

## Prefix functional check

The check uses two original exchanged-material blocks and crosses two retention rules with two novelty timings. Each condition completes continuous teaching, preserves the complete parent, and creates two declared diagnostic copies for the AB and DB prefixes. Activation, inhibition, direct activity and associative activity are recorded for 15 seconds at 10-millisecond intervals. Complete-state digests before and after observations check that observation leaves the state unchanged. Both prefixes must produce a signed correct-target peak difference greater than 1e-6 for a block to pass.

Each backend has eight taught parents and sixteen diagnostic copies, totaling 24 stages. The two backends therefore execute 48 stages, while the number of material blocks remains two. Readout rules, teaching material and enqueue order follow the original comparison. No readout is retrained.

Python and Rust completed all conditions. Read-only checks verified 48 complete states, 32 processes and the target peak differences. The maximum cross-backend difference across the four activity variables was 2.1684×10⁻¹⁹.

| Connection retention | Novelty timing | Passing Python blocks | Passing Rust blocks |
|---|---|---|---|
| Single-age inverse-logarithmic | Arrival window | 0/2 | 0/2 |
| Single-age inverse-logarithmic | Immediate | 0/2 | 0/2 |
| Stability-based | Arrival window | 0/2 | 0/2 |
| Stability-based | Immediate | 0/2 | 0/2 |

In each block, one prefix produced the correct preference and the other produced the opposite preference. **The prefix-recovery target failed. In these two materials, restoring stability-based retention and selecting immediate novelty is insufficient to restore prefix discrimination.** The existing positive 5.1 evidence remains valid. The next investigation should locate the first divergence in formation and expression under the same materials and test the contributions of transmission, inhibition and node rules.

Immediate novelty is therefore not promoted to the default. The delivered 6.2 retains the compatible arrival-window, single-age inverse-logarithmic configuration and existing thresholds. Immediate novelty, stability-based retention and the two other research presets remain explicitly selectable. The global new-individual default stays at 6.1. Exact sources used by the functional check were archived separately; this default decision does not rewrite its records.

## Cost

A separate small native-backend benchmark used 64 nodes and 128 connections, with five repetitions in alternating order and median timings. Teaching advanced to 10 internal seconds, followed by advancement to 300 internal seconds. Artifact encoding was timed separately.

| Configuration | Teaching computation | Subsequent silent computation | Final artifact |
|---|---:|---:|---:|
| 6.1 reference | 5.473 ms | 0.0055 ms | 91,146 bytes |
| Compatible 6.2 | 5.449 ms | 0.0042 ms | 91,575 bytes |
| 6.2 stability plus immediate novelty | 9.920 ms | 56.170 ms | 33,715 bytes |

The compatible configuration has similar computation time and a 0.47% larger artifact. Stability-based retention continues to schedule local connection updates during silence: this apparatus recorded 129,121 expiration checks and zero full-graph scans. Its connections were all deleted by the end, whereas the single-age reference retained 128. The smaller artifact reflects a different dynamical outcome. The additional computation supports offering stability-based retention as an option initially.

The prefix check computes complete-state digests before and after every observation. Its wall time includes substantial serialization and verification work and is not used as a Core performance measure.

## Revalidation

Completed 6.1 experiments retain their scores and conclusions. **The delivered 6.2 configuration retains 6.1 dynamics, so changing the version number alone does not justify repeating every completed batch.** Future use of immediate novelty, stability-based retention, or changed thresholds or inhibition requires targeted revalidation: first prefix discrimination and persistent activity, then connection formation, causal blocking, transplantation, process readout, order and the four criteria. Reporting 64-group or 48-source confirmation results for a changed configuration requires corresponding new evidence. Unchanged control artifacts may be reused after verification.

The remaining shape/color, ecological and 3-SAT batches stay in the original plan. The main campaign remains paused,[Public edition: manuscript editing or private locator omitted.] The [batch-by-batch assessment](revalidation.en.md) explains the scope and reasons.

## Evidence and recalculation

The [6.2 plan](../../../docs/en/plans/kernel62.md) records the scope and default-selection conditions before implementation. `validate_prefix.py` executes the bounded functional matrix. `audit_prefix.py` independently recalculates target peak differences and compares both backends' four recorded activity processes without running individuals. `benchmark.py` measures the separate engineering workload. The [verification summary](verification-summary.json) records decisions and material hashes. Complete engineering artifacts are in Git-ignored `.work/kernel62-prefix-01`; benchmark originals are in `.work/kernel62-benchmark.json`. Historical research data were not rewritten.

Final native wheels are in `.work/kernel62-wheels-final`, Python distributions in `.work/kernel62-python-wheels-final`, and the independent Rust executable at `.work/native60-final/release/threemind-runtime.exe`. This delivery is a local build and engineering functional check, not a new formal batch closed through the research API.


## 15 November 2026 follow-up: R51t7 localization and recovery

The original four-configuration 0/2 results and artifacts above remain intact. Separately registered R51t7 added two enabled-by-default base-weight reinforcement switches and completed 94 isolated stages. Inhibitory weight-off alone failed; complete emission replacement restored 2/2 in a derivative retaining 6.2 fixed-function addressing. Production transmission remains unchanged, pending the author's decision. [New report](prefix_recovery/report.en.md) · [Full API readback receipt](prefix_recovery/delivery.json).
