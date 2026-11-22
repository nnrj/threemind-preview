# 6.2 pre-release thresholds and lifecycle repair: implementation and persistence audit

15 November 2026. Engineering delivery and interim R51t10 report. Research record: `1047029e-d54a-5f2f-8f56-5db7a0503731`. **The engineering changes are complete; the 92-stage scientific comparison remains incomplete.**

## Findings

**6.2 now checks the applicable signal threshold before releasing synaptic resources.** The check is enabled by default and can be disabled. A signal below its connection threshold no longer triggers resource release. Excitatory and inhibitory signals use their respective existing thresholds; either can qualify for one release. Isolated tests covered neither signal qualifying, excitation alone qualifying, and inhibition alone qualifying.

**Sub-floor activation now leaves the active set promptly.** Previously, a positive activation could enter the active set without receiving an expiry timer because it was already below the zeroing floor. Observation projected the activation to zero, while the stale active-set entry obstructed quiescence and death detection. The repair settles that node one internal microsecond later, then applies the existing one-second quiescence interval. In the single weak-input test, death occurred at 1,000,001 internal microseconds; simultaneous weak inputs could still accumulate into effective activation. The change affects death timing and acceptance of subsequent stimuli, so it is a behavioral repair, not just a display correction.

**The earlier measured 300-second persistence findings remain supported.** A read-only audit checked six historical processes, each containing 1,502 samples. Maximum task-node activation was positive at every sample. These were actual activity records, not merely an `active` label. The corresponding post-repair 6.2 comparison has not finished; the historical audit is not a completed replication in the repaired version.

## Implemented rules

New 6.2 individuals enable `resource_precheck_enabled`. For each signal type, effective connection weight times offered signal times the existing distance factor is compared with the applicable connection signal threshold. If neither type qualifies, no resources are released. If either qualifies, the existing release rule determines the actual signal amount, followed by the existing transmission check. Node sending thresholds, node-offer energy costs, weight gates and subsequent learning rules retain their meanings. Disabling the master connection signal threshold also disables pre-release filtering.

The option is named “pre-release threshold check” to distinguish it from a source node's sending threshold. It uses current local connection quantities, not task answers or a prediction of downstream activation. Because it changes resource use and subsequent dynamics, it is not described solely as a performance optimization.

New individuals also enable `subthreshold_expiry_enabled`. Positive activation below the zeroing floor is settled at the next internal microsecond. Equality to the floor expires only when activation decay is enabled. All input at the current timestamp can accumulate before settlement; no whole-graph scan is added. Disabling this option reproduces historical maintenance behavior.

Historical 6.2 artifacts lacking these fields restore with both options disabled after verification of their original definition and hash. Historical kernels, individuals and original evidence remain intact. The global new-individual version remains 6.1; this task changes the two defaults for newly created 6.2 individuals. Both switches are exposed in the API configuration catalogue. The running API service was not restarted.

## Historical persistence evidence

These experiments stopped task cues while retaining fixed background input. After a 300-second wait, activity was observed for 15 seconds at 10-ms intervals, including records immediately before and after the observation-window start, giving 1,502 points. Persistence was assessed from the actual activation of five task nodes.

| Historical condition | Curriculum blocks | Range of maximum task activation across 15 seconds | Fraction of task-node records reaching 0.95 | Finding |
|---|---:|---:|---:|---|
| Original kernel version 1 | 2 | 0.0171540–0.0230551 | 0 | Persistent activity supported |
| Original kernel version 2 | 2 | 0.0171540–0.0230551 | 0 | Persistent activity supported |
| 6.1 with inhibitory decay time reduced to one quarter | 2 | 0.0604104–0.0811919 | 0 | Persistent activity supported |

The two blocks exchange the taught endings. They are material blocks; branches and sampling points are not additional independent individuals. Six processes, twelve complete initial/final states and the referenced original-file hashes passed verification. The evidence that changing inhibitory decay can restore persistent activity remains valid. The newly identified lifecycle defect does not negate these measured processes.

## Why the new comparison stopped

The registered 92-stage plan separates pre-release checking from lifecycle repair and includes stimulus-free tails, production 6.2 prefix tests and prefix tests of the successful research reference. The first continuous teaching stage finished at 81.2 internal seconds. Its complete state has digest `93be6e86084b5470215770eae9184b19e9430e19c87e4dde1717d6a41f3f8629`.

During the next waiting stage, repeated whole-state hashing made recording unnecessarily expensive. A 300-second wall-time assertion then raised an exception without saving the complete final state of that waiting stage. A complete-boundary pause had been requested, but the assertion triggered first. This was a research-tool error. The incomplete wait provides no scientific outcome and is not a normal complete-state pause. STOP, in-flight, incomplete recording files and the complete teaching state are retained. No recovery or rerun has occurred.

Peak private memory was approximately 83.3 MiB, and all four resource reserves remained above their limits. The interruption arose from recording overhead and timeout handling, not insufficient memory or disk space.

The recorder has been corrected. Routine sampling uses the tested read-only observation API; full-state verification remains in apparatus checks and at saved boundaries. Across four switch combinations and two backends, eight independent-code checks produced identical final-state hashes and byte-identical decompressed process records with the old and new recorders. Native recording of an eight-internal-second calibration fell from approximately 2.31–2.44 seconds to 0.060–0.065 seconds. This is an instrumentation cost comparison. A separate forced wall-budget test confirmed that the revised tool finishes the complete stage before pausing; both backends produced the same states and records as the unforced reference.

The proposed recovery preserves the failed branch and creates a new research copy from the verified 81.2-second teaching state, retaining the original materials, 92-stage plan and criteria. Teaching is not repeated. Under the author's requirement to request approval after a new dead host with in-flight state, this recovery has been submitted for confirmation and has not been executed.

## Engineering validation and next step

The final regression run passed 478 tests. Eleven independent database integration tests were skipped because the test database was not running; they are not counted as passes. Checks covered Python/Rust agreement, historical artifacts, same-time weak-input accumulation, configuration switches, complete restoration, the standalone Rust runtime and frontend build. The new native wheel is installed in the project environment. Running services were not restarted. Historical source versions and originals remain intact; manuscripts and the comprehensive replication campaign remain unchanged.

This delivery corrects resource-release ordering and active-set maintenance. It implements the author's selected treatment of weak signals and aligns lifecycle detection with actual activity. The next step is the registered before/after comparison, which will establish the effects of the new defaults on persistence and prefix responses. This interim report preserves the earlier process evidence and identifies the unfinished comparison explicitly.

Evidence: this directory's bilingual protocol, `study.py`, `recording_v2.py`, `recording_budget.py`, `historical_audit.py`, and the new work directory's originals. R51t10 has not reached scientific completion.
