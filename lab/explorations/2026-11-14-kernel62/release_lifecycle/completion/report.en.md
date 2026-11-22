# Persistent activity and prefix discrimination after lifecycle repair

15 November 2026 · R51t10 completion edition. The earlier interruption report and all originals are preserved. This edition reports the authorized continuation in a new research copy.

**Conclusion: the local expiry repair removes the error in which the individual remains labeled active after activation has stopped. Previously demonstrated genuine persistence and prefix discrimination in the successful condition survive the repair.** With background input retained and the inhibition decay time shortened, both curriculum blocks maintained task activation throughout the 15-second window after a 300-second wait. The original inhibition condition did not. The new pre-release check and lifecycle repair alone did not restore prefix discrimination in the production-6.2 default configuration; the successful research configuration continued to pass.

## Purpose and expectations

The author approved restoring the signal check before synaptic resource release and requested lifecycle repair and reassessment of the persistence findings. We varied the two switches separately to test resource release, termination after activation ceased, and preservation of the previously observed persistence and prefix discrimination.

The pre-release check and local expiry repair have Python and Rust implementations. Both are enabled for new 6.2 individuals; historical artifacts missing these fields restore their original behavior. The global default for creating individuals remains 6.1. No further kernel or default changes occurred during this continuation.

## Experimental organization

The original plan comprised 92 stages: 40 persistence stages, 24 production-6.2 prefix stages, 20 no-input tails and eight prefix diagnostics of the successful reference. Independent material consists of two curricula with exchanged C/E correspondences. Copies, stages and samples do not increase the number of independent units. Teaching and waiting were continuous; interventions and diagnostics used registered complete research copies. No trainable peripheral was involved.

Persistence was tested after 81.2 seconds of teaching, a 300-second wait and a 15-second observation period. Waiting retained 300 fixed background inputs without teaching cues on the five task channels. The separate no-input tails stopped all inputs. These conditions measure persistence with background stimulation and activity cessation without input, respectively.

The original persistence criterion required the maximum activation among the five task nodes to exceed 1e-6 at every sample, recorded every 10 milliseconds over 15 seconds, with 1502 points including before/after records. The prefix criterion required the taught ending's peak activation after the second cue to exceed the alternative ending's peak by more than 1e-6. Both AB and DB had to pass for a curriculum block to qualify.

## Interruption, recovery and supplementary measurement

After the first complete 81.2-second teaching stage, repeated whole-state hashing in the recorder caused the next wait to exceed a 300-second wall-clock assertion. The process exited without a complete waiting-state checkpoint. **The exit was caused by recording-tool timeout; the waiting material retained background input.** The original STOP, in-flight marker, incomplete recording and 499-member interruption package remain intact.

The author explicitly authorized a new copy. The `release-lifecycle62-v1-r1` directory reuses the verified teaching state and executes the remaining 91 stages without repeating teaching. The revised recorder preserves sampling and event order. In independent apparatus checks, complete states and recordings were byte-identical across both backends and four configurations. Reduced recording overhead is an instrumentation improvement.

After the 92 stages, verification identified a confound in the 20 original tails: calling the configuration interface settles existing nodes even when the repair stays disabled, clearing stale activity before observation. Those records remain valid descriptions of behavior after configuration intervention. Eight additional tails were prospectively registered using completed teaching states whose flags had been set at birth. They called no configuration interface, repeated no teaching and injected no stimulus. Initial digests exactly matched their complete parents.

## Results and interpretation

### 1. The lifecycle maintenance error is repaired

Each row includes both swapped curriculum blocks. Time is measured from the complete teaching state.

| Pre-release check | Expiry repair | First zero-activation sample | Final state and actual elapsed time |
| --- | --- | --- | --- |
| Off | Off | 1 second in both blocks | Still active at 300 seconds; two stale active-set entries each |
| On | Off | 1 second in both blocks | Still active at 300 seconds; two stale active-set entries each |
| Off | On | 1 second in both blocks | Dead at 1.996250 seconds; active set empty |
| On | On | 1 second in both blocks | Dead at 1.996078 seconds; active set empty |

No further excitatory or inhibitory transmission occurred after the first zero-activation sample in any of these conditions. With the repair enabled, the death time in the complete state was exactly one second after quiescence began, as required by the existing rule. Changing the pre-release check did not resolve the stale label; enabling local expiry did. The comparison establishes the repair's effect.

### 2. Genuine persistent activity is reproduced

| Inhibition condition | Four combinations of the two switches | Fifteen-second process after the 300-second wait | Passing blocks |
| --- | --- | --- | --- |
| Original decay time, 0.232135 seconds | Same outcome throughout | All five task activations zero | 0/2 for each combination |
| Decay time divided by four, 0.058034 seconds | Same outcome throughout | Maximum task activation at each point: 0.0604104–0.0811919 | 2/2 for each combination |

The shorter-time condition retains inhibition. No task-node activation reached 0.95 during observation, so persistence did not arise from prolonged activation saturation. Read-only inspection also confirmed positive activation in six historical processes: two blocks each from versions 1 and 2 and the short-inhibition 6.1 condition. **The earlier persistence finding reflects recorded activity and survives the lifecycle repair. Inhibition decay time remains an important determinant of sustained task activity in this material.**

### 3. The successful reference retains prefix discrimination; defaults do not recover it

The successful research configuration combines stability-based retention, immediate novelty, historical inhibitory propagation, the higher excitatory connection threshold and pre-release screening. With the expiry repair either off or on, both curriculum blocks passed. Correct-ending peak advantages were approximately 0.00097837 for AB and 0.00273543 for DB, exceeding the original 1e-6 threshold.

All four switch combinations in the production-6.2 default configuration passed 0/2 blocks. With pre-release screening enabled, AB retained a negative advantage of approximately −0.00013329, whereas DB had a positive advantage of approximately 0.00013332. The two questions did not both pass. These two switches alone do not restore default prefix discrimination; the established successful combination remains effective.

Across 20 paired repair-off/on processes, the largest pointwise difference in activation, inhibition, direct and associative activity was 4.34×10⁻¹⁹. All original criterion outcomes agreed. The repair corrected the survival state while preserving the functional conclusions from these measured processes.

## Implications and next decisions

The requested repair and reassessment are complete. The demonstrated 300-second persistence and prefix findings remain usable. Survival time follows the repaired lifecycle rule; activity is measured directly from process records. Persistence with background stimulation and decay without any input are reported separately.

The two authorized 6.2 defaults remain enabled. Default prefix discrimination is still absent; the successful research configuration and its conditions are identified. This study did not promote its remaining research rules to production defaults. The comprehensive replication campaign remain paused under the author's earlier decision, pending subsequent mechanism choices. [Public edition: manuscript editing or private locator omitted.]

## Evidence, cost and verification

The main continuation took approximately 301 seconds; the eight supplementary tails took 6.14 seconds. The previously completed first teaching stage took approximately 78.98 seconds and was reused. Peak private memory during the main continuation was approximately 105.4 MiB. Available commit memory, physical RAM and free C/E space stayed above the 5/4/5/25 GiB reserves.

Read-only verification covered 348 main complete states, 60 supplementary complete states, 40 new processes and six historical processes. Independently calculated peak scores exactly matched the recorded scores. All 499 interruption-package members, the original markers and the teaching state were verified unchanged. Originals are in `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/release-lifecycle62-v1-r1`; `final-audit.json` and `publication/completion.json` provide final verification and API readback records. This was an authorized copy-based recovery under the same research identity, with the interrupted and replacement branches explicitly distinguished.

The [recovery note](../recovery.en.md) clarifies the restriction's provenance: it appears in this conversation's October automated continuation prompts, and the E69 incident—experience through 2010 seconds but a complete state only at 2004 seconds—explains its purpose. Earlier attribution to a verbatim personal instruction from the author was too strong and has been corrected. The rule protects traceable evidence and experience.
