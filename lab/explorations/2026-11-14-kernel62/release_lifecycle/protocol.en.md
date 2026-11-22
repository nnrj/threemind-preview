# Pre-release thresholds and local activity expiry: persistence reassessment

2026-11-15 · R51t10 · Preregistered protocol.

## Questions and authorized changes

The author approved a default-on, switchable threshold check before synaptic resource release in 6.2, repair of the lifecycle-maintenance defect, and reassessment of the earlier persistent-activity conclusion. This batch tests resource conservation, timely retirement of inactive nodes, and whether previously measured persistent activity survives the repair. The two changes are compared separately. Lifecycle state controls death and acceptance of later input; the repair is therefore a behavioral correction, not merely a display change.

New 6.2 subjects enable `resource_precheck_enabled` and `subthreshold_expiry_enabled`. The first compares effective connection weight times the offered signal and existing distance factor with the applicable excitatory/inhibitory connection threshold before releasing resources. No release occurs when neither signal qualifies. The common threshold switch, separate overrides, node-offer energy costs, and post-release transmission rules retain their meanings. The second schedules local settlement one internal microsecond after a positive sub-floor activation, preserving all arrivals at the current timestamp. Equality to the floor expires only when activation decay is enabled. The existing one-second quiescence interval remains; no whole-graph scan is added.

Historical 6.2 artifacts lacking the two fields restore with both disabled. Explicit experimental copies record configuration changes and complete before/after states. Production 6.1, earlier kernels, original subjects and evidence are unchanged. The successful historical-inhibition candidate remains a research implementation, separate from production 6.2.

## Fixed materials and comparisons

The unit is one of two curriculum blocks with exchanged C/E endings. Branches and questions are nested observations. Inputs are copied from delivered evidence and verified by hashes. Teaching and waiting are continuous. Causal diagnostics use registered complete copies. These passive mechanism measurements require no trained peripheral or additional teaching curriculum.

1. **Persistence, 40 stages.** Reuse the R51t1 material: 81.2 seconds of 011 teaching, 300 seconds of waiting with the original background but no task cues, and a 15-second observation. Cross the two Boolean changes. For each configuration and block, create two diagnostic copies after teaching: original inhibition and an inhibitory decay time constant reduced to one quarter. Each has one waiting and one observation stage. Preserve depletion-disabled, facilitation-enabled conditions.
2. **Production 6.2 prefix discrimination, 24 stages.** Four Boolean combinations and two blocks, each with 212.2-second teaching and separate AB/DB diagnostics. Other settings match the previous default reference. No parameter search follows the outcome.
3. **Completely stimulus-free tails, 20 copies.** Use the four R51t9 tail conditions and the successful `pre-old-high` reference, each in two blocks. For each completed teaching state, compare expiry repair off/on while preserving all other settings. Advance for at most 300 seconds, stopping normally upon death; record actual elapsed time rather than treating the requested endpoint as survival.
4. **Successful-reference prefix diagnostics, 8 copies.** From the two completed `pre-old-high` teaching states, compare expiry repair off/on for AB and DB. Preserve the research transmission path and curriculum; do not retrain the completed parents.

Total: 92 new stages/copies. A separate read-only audit examines the actual activity records supporting the historical R51t1 and R51t2 300-second conclusions. Those historical implementations are neither repaired nor rerun. Replaying the same materials in 6.2 produces new replication evidence.

## Endpoints and decisions

Engineering witnesses verify no resource release when both offered signals fail the precheck, release when either qualifies, independent thresholds and inheritance, disabled master threshold, complete restoration, and Python/Rust agreement. Local expiry must clear inactive entries and apply the existing quiescence rule without observation effects or loss of same-time summation.

The historical persistence criterion is unchanged: over every 10-ms sample in the 15 seconds following the 300-second wait, maximum activation among the five task nodes must exceed 1e-6. Both blocks must pass. Report late transmission increments, inhibition, and the fraction of task-node observations with activation at least 0.95 separately. A lifecycle label is never the persistence score.

Prefix discrimination retains the original criterion: the taught ending's activation peak minus the other ending's peak after the second cue exceeds 1e-6 for both AB and DB within a block. Report both blocks and all margins. Compare expiry repair at a fixed release policy and release policy at a fixed expiry setting. Changed activity or failure to reproduce an earlier positive receives an explicit conclusion without changing criteria or extending the search.

## Safeguards and delivery

Save complete initial/final states, lineage hashes, every input, activation/inhibition/direct/associative time courses, and whole-state observations at selected times. One scientific host; one-second guard; retain 5/4/5/25 GiB of commit/RAM/C/E resources. Originals are capped at 1 GiB and total additional peak storage at 4 GiB, including archive and API readback. Host limit two hours; stage limit 300 wall seconds; private memory limit 1 GiB. Preserve incomplete states and resource STOP evidence under the existing continuation rules.

Validate independent calibration codes with observation off/on, partitioned advance, host pause, restoration and both backends. Freeze sources, native build, materials and protocol before API registration and scientific execution. Deliver read-only arithmetic audit, bilingual conclusions, complete API archive readback with pending zero, synchronized backlog/history, and a local Git commit. The broad revalidation campaign remains paused; manuscripts are unchanged.
