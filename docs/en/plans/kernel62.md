# Kernel 6.2: stability-based retention and signal-type thresholds

2026-11-14. The author approved implementation on the basis of 6.1 and the R51t6 recommendations. This plan distinguishes implementation, functional checks, and selection of defaults.

## Authorized changes

6.2 has its own version, state schema, Python transitions and Rust transitions. The historical implementations remain intact. Common numerical functions, protocol types, energy accounting and local queue primitives remain shared.

The former “legacy retention” option is named **stability-based retention**, with `consolidation_mode="stability"`. Experience increases connection stability, and relaxation reduces it; greater stability slows weight decay. Growth and relaxation are independently configurable and enabled within this option by default. Reinforcement of the base weight remains separate. Connection-local periodic events implement this rule; a global scan is not required.

Single-age exponential, power-law, inverse-logarithmic and power-exponential decay remain available. Inverse-logarithmic decay remains the default within this family. Reinforcement preserves decay age by default. H timescale growth and relaxation remain optional and disabled by default. They are distinct from stability growth and relaxation and are not silently combined with the stability rule.

Immediate novelty is the preferred default candidate; arrival-window novelty remains available. Stability-based retention is initially an optional candidate. The default switches only after the relevant engineering and functional checks.

Inhibition remains enabled. A research preset sets its decay time constant to 0.0580338705786432 seconds. Another sets the shared connection signal threshold to 0.004 for inertial-response reversal studies. Neither preset is applied automatically. Presets store their expanded parameter values; they neither inspect answers nor reverse an output directly.

Two optional numeric overrides, `activation_signal_threshold` and `inhibition_signal_threshold`, resolve independently. A missing or null value inherits `signal_threshold`; explicit zero disables that type's numerical cutoff. Equal explicit overrides remain recorded as explicit values. `signal_threshold_enabled=False` disables both connection cutoffs.

Source-node send thresholds remain 0.004 for activation and 0.002 for inhibition. The shared connection threshold remains 0.0004; the deletion threshold remains 0.008. The hard weight gate remains disabled. Fixed-function addressing, address-based in-flight delivery, optional same-birth delivery, local deletion, optional global deletion scans, short-term resources, inhibitory learning and finite-energy mechanisms remain available.

Structural inheritance retains persistent connection state and decay age by default, resets fast activity and the child's clock, and offers an age-reset control. Saved historical individuals retain their original identities.

## Acceptance

Python, the native Rust extension, the independent Rust runtime, API metadata, command-line version selection and frontend configuration must agree. Tests cover full-state parity, save/restore, observation and host-pause invariance, partitioned advancement, exact 6.1 compatibility configuration, growth versus weight reinforcement, deletion order at simultaneous input, independent threshold fallback, zero and invalid values, and structural inheritance.

The bounded functional check reuses two exchanged prefix-material blocks. It compares single-age/stability retention and immediate/window novelty. Passive readout covers activation, inhibition, direct activity and associative activity throughout the original response interval. The original criterion remains: both prefix responses have the correct signed peak difference greater than 1e-6 in each block. These new engineering subjects are separate from historical formal subjects. Failure is reported without changing the criterion or historical scores.

Immediate novelty may become the 6.2 default only after this comparison and the engineering checks. Stability remains optional; inverse-logarithmic single-age decay remains the main retention default. An adverse functional contradiction blocks automatic default promotion. Selecting 6.2 never upgrades an existing individual.

The comprehensive replication campaign remains paused. The final assessment will identify which completed 6.1 results need a 6.2 bridge or renewed scientific test, according to the actual changed mechanisms. This task does not restart the campaign or revise the author's manuscript.

## Sources

[R51t6 report](../../../lab/explorations/2026-11-13-kernel61/prefix_components/report.en.md), [candidate assessment](../../../lab/explorations/2026-11-13-kernel61/prefix_components/evaluation.en.md), and [three functional investigations](../../../lab/explorations/2026-11-13-kernel61/dynamics_function/report.en.md). The R51t3 and R51t5 interpretations use their dated revision 2; earlier texts and data remain preserved.

## 14 November 2026: default decision after the functional check

All four configurations scored 0/2 exchanged-material blocks in both Python and Rust. Checks passed for 48 complete states, 32 processes and independent scoring. Stability-based retention combined with immediate novelty did not restore prefix discrimination in 6.2. Under the conditions specified above, immediate novelty is not promoted. The delivered 6.2 retains compatible arrival-window novelty, single-age inverse-logarithmic decay and existing thresholds; candidates and research presets remain selectable. The global new-individual default remains 6.1. Historical experiments, rules and reports are unchanged.

Completed 6.1 batches need not be repeated solely to change their version label. Future adoption of changed configurations requires evidence for affected claims. Resolve the prefix difference before resuming the campaign. [Results](../../../lab/explorations/2026-11-14-kernel62/report.en.md) · [Batch assessment](../../../lab/explorations/2026-11-14-kernel62/revalidation.en.md).


## 15 November 2026: reinforcement switches delivered; R51t7 boundary

The author additionally approved separate base-weight reinforcement switches for successful excitatory and inhibitory transmission, enabled by default: `activation_weight_reinforcement_enabled` and `inhibition_weight_reinforcement_enabled`. Other learning states and co-stimulation remain unchanged. Earlier 6.2 snapshots restore missing switches as enabled after checking the original definition/hash; originals are not rewritten.

R51t7 restored both prefix blocks in an isolated derivative using stability retention, immediate novelty and complete emission replacement. Disabling inhibitory reinforcement, changing inhibitory transmission alone, raising the excitatory threshold alone, and combining the latter two did not restore it. Formation and expression both contribute. Production 6.2 receives only the authorized reinforcement switches; other changes await the author and the main campaign remains paused. [Report](../../../lab/explorations/2026-11-14-kernel62/prefix_recovery/report.en.md).

## 2026-11-15: 6.2 pre-release and activity-expiry repairs; R51t10 interrupted

The author approved a default-on pre-release threshold check and required reassessment of persistence after lifecycle repair. Python and Rust 6.2 now expose `resource_precheck_enabled` and `subthreshold_expiry_enabled`, enabled for new individuals. The first checks the applicable excitatory/inhibitory connection thresholds before resource release. The second schedules sub-floor positive activation for local settlement at the next microsecond, preserving same-time summation and the existing one-second quiescence interval. It affects death and acceptance of later input and is recorded as a behavioral repair. Historical 6.2 artifacts missing the fields restore with both disabled. The global new-individual version remains 6.1.

Engineering regression passed 478 tests; eleven database integration checks were skipped because the independent test database was not running. Native, standalone Rust and frontend builds passed. The new wheel is installed; running services were not restarted. Six 6.1 implementation files are unchanged. Read-only historical verification confirmed positive task activation throughout 1,502 samples in each of two curriculum blocks for kernels 1 and 2 and the short-inhibition 6.1 condition. The ranges were 0.0171540–0.0230551 and 0.0604104–0.0811919, with no records reaching 0.95. Those persistence findings remain supported.

Only the first 81.2-second teaching stage of the 92-stage R51t10 plan completed. Repeated full-state hashing caused excessive recording overhead; the next waiting stage then hit a 300-second wall-time assertion without complete final-state preservation. This was an instrument error, not a scientific negative or a complete-state pause. STOP, in-flight, failed-branch evidence and the complete teaching state remain intact. The corrected recorder produced identical complete states and records in both backends across four configurations and passed a forced wall-budget test that finishes the stage before pausing. Recovery awaits the author's confirmation under the standing dead-host rule and has not occurred.

Research record `1047029e-d54a-5f2f-8f56-5db7a0503731` is explicitly interrupted. Its 499-member evidence package passed complete API readback with pending=0. This verifies preserved evidence, not completion of the 92-stage scientific targets. The main campaign remains paused and manuscripts are unchanged.

[Report](../../../lab/explorations/2026-11-14-kernel62/release_lifecycle/report.en.md)

## 2026-11-15: R51t10 completed; genuine persistence and prefix findings retained

The author explicitly authorized a new copy. The complete 81.2-second teaching state was reused and the remaining 91 stages completed. The interrupted wait, STOP, in-flight marker and 499-member interruption originals remain intact. Waiting retained 300 fixed background inputs. The earlier phrase “dead host” meant a recording-timeout process exit, not an individual dying from absent input. The recovery restriction appears in earlier automated continuation prompts; this does not establish a verbatim personal instruction from the author, and the attribution is corrected here.

Configuration calls in the original 20 tails settled nodes and masked stale activity. Eight additional tails were prospectively registered from teaching states whose flags were set at birth, with no reconfiguration or repeated teaching. With the repair disabled, activation was zero at the one-second sample but life remained active at 300 seconds. With it enabled, death occurred at about 1.996 seconds under the original one-second quiescence rule, with an empty active set. No further transmission occurred after the first zero sample in any condition. This comparison confirms the local expiry repair.

With background input retained and inhibition decay time divided by four, all four switch combinations maintained task activity for the 15-second window after 300 seconds in both curriculum blocks. Pointwise maximum activation was 0.0604104–0.0811919, with no 0.95 saturation. Original inhibition passed 0/2 throughout. The successful research configuration retained 2/2 prefix discrimination with repair off or on; all production-default combinations remained 0/2. Across 20 paired processes, the largest difference in four activity fields was 4.34e-19, preserving all prior functional judgments. The repair corrects false survival labels while preserving genuine persistence and successful prefix discrimination; the two switches alone do not restore default prefix capability.

Verification covered 348 main and 60 supplementary complete states, 40 new processes and six historical processes. All 1206 archive members passed complete local research-API readback, pending=0. Research identity 1047029e-d54a-5f2f-8f56-5db7a0503731 and its interruption history are retained. Scientific execution has ended; the comprehensive campaign and manuscripts remain paused. No additional production-kernel or default changes occurred during continuation.

[Report](../../../lab/explorations/2026-11-14-kernel62/release_lifecycle/completion/report.en.md)
