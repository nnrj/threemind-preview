# R63t1: Replicating the causes of sustained activity and prefix discrimination

Prepared on 16 November 2026; the research API receipt determines registration time. The author authorized rerunning the original plan and all studies added during the 6.1 replication on 6.3. This batch repeats all 476 stages of R51t1 with its two exchanged curriculum blocks. Historical controls use their genuine implementations; the current-version conditions use 6.3 in place of 6.1. Production rules and defaults are unchanged.

## Purpose and expectations

We ask which conditions maintain task-node activity after 300 seconds without a new task prompt, which interventions stop that activity, and which conditions distinguish A–B–C from D–B–E when the intermediate stimulus B is shared. We also test whether the signal threshold that restored inertial reversal restores either of these effects.

The historical experiment found both effects in genuine /1. Version /2 retained sustained activity and recovered prefix discrimination with immediate novelty enhancement. Stability-based retention restored sustained activity in /3.1 and /5.1. In 6.1, disabling inhibition maintained activity, but the candidates tested did not restore prefix discrimination; raising the transmission threshold to 0.004 did not restore both effects. This replication tests those causal findings and any new changes following the state-settlement fixes in 6.3. A repeated known negative is reported as such. Greater activity of one ending does not substitute for correct responses to both prefixes.

## Conditions, materials, and the complete individual

The original 384 stages, 80 added retention-control stages, and 12 novelty-timing stages are all registered before this run. Their original registration dates and exploratory sequence remain in the historical record. The 26 configurations are:

- Genuine /1, /2, /3.1, /5.1, /5.3, and /6.3, plus /3.1 with strong-stimulus fatigue disabled.
- In 6.3 from birth: transmission threshold 0.004; zero transmission threshold; zero activation and inhibition sending thresholds; disabled fatigue, inhibition, inhibitory reinforcement, short-term enhancement, or reception-context mixing; exponential decay; and the combination of threshold 0.004 with disabled fatigue.
- Complete research copies of the unchanged 6.3 teaching endpoint with the threshold raised, fatigue disabled, inhibition disabled, or short-term enhancement disabled only after teaching.
- Stability-based retention in /3.1, that retention combined with manual node retention in /3.1, and stability-based retention in /5.1; immediate novelty enhancement in /2 and /6.3.

Every condition uses the same two blocks exchanging C and E. Blocks, configurations, research copies, and stages are counted separately; 476 is not the independent sample size. The completed historical case lists determine inputs, timing, parameters, and scores. Only current-version identities and new research identities change. The original E12 implementation was /1; its original results provide the historical witness, retaining the earlier correction of a mistaken /2 label.

The sustained-activity condition uses the original 011 configuration: resource depletion disabled, short-term facilitation enabled, and connection reinforcement enabled. Teaching lasts 81.2 internal seconds, followed by 300 seconds with the original background inputs and no new task prompt. Sequence teaching lasts 212.2 seconds, followed by a one-second wait. Separate complete copies receive AB or DB with a one-second interstimulus interval. Teaching and review intervals follow the original material. These passive mechanism measurements need no trained reader, body, or actuator. Core, input bus, random state, and readout history are preserved continuously. Declared post-teaching interventions use separate copies with an intact reference.

## Measurements and decisions

The task nodes are A, B, C, D, and E. Teaching and waiting are sampled every 100 ms; each 15-second diagnostic window is sampled every 10 ms for activation, inhibition, direct activity, and associative activity. Observation, saving, host pauses, and plotting do not advance simulation time.

The original sustained-activity criterion requires activity at the end of the 300-second wait and maximum task-node activation above 10⁻⁶ at every sample of the following 15-second window. Both blocks must pass for recovery. Actual cessation time, amplitude, saturation, and the life label are reported separately. Copies of the 300-second state additionally enable depletion, disable facilitation, combine those changes, or disable connection reinforcement. A zero endpoint cannot demonstrate termination by an intervention when activity was already absent before it.

Prefix discrimination is the peak activation of the taught ending minus that of the other ending, measured from the second cue onward. Both AB and DB must exceed 10⁻⁶ in a block, and both blocks must pass for recovery. Areas and other activity measures are retained and independently recalculated with high-precision arithmetic, without replacing the primary peak measure. Two prefixes that still favor the same ending fail the original criterion.

Teaching-period and post-teaching effects are reported separately. If no candidate restores a target, the negative result is delivered without extending the search. A historical positive condition dropping from 2/2 to fewer than 2/2 is a new adverse difference requiring preservation and discussion. Repeated known negatives are delivered normally before other authorized studies continue. Failure to reproduce the unchanged /1 witness requires checking implementation identity, materials, and instrumentation, not changing the criterion. Default changes require a separate decision.

## Apparatus, budget, and delivery

Nineteen apparatus stages use independent encodings and seed 9291199, covering /1, /2, /6.3, and immediate novelty conditions. Diagnostic checks compare ordinary observation, no observation, full save/restore, and a host pause; final Core state and reader history must agree. Native binaries, kernel sources, executor, materials, criteria, and historical evidence hashes are frozen. Twenty default 6.3 endpoints must match corresponding endpoints from the new R63q batch. All complete states, input deliveries, intervention changes, and process calculations are audited read-only.

One scientific host checks resources every second, reserving 5/4/5/25 GiB for available commit memory, physical RAM, C:, and E:. Private memory is capped at 1 GiB, each stage at 300 seconds, and the batch host at two hours. Originals, archive, and API readback each have a 2-GiB allowance, with 128 MiB for analysis; startup requires more than 31.125 GiB free. Apparatus measurements calibrate physical allocation against equivalent historical records. Twice the historical allocation, a 50% unit-budget overrun, or insufficient resources causes a pause at a complete boundary. New orphaned in-flight states are preserved rather than retried.

Streaming JSON and lossless compression retain all recorded fields while reducing transient memory. Delivery comprises bilingual reports, originals, parent-copy relationships, read-only audits, and comparisons. Closure requires a complete research-API package readback and pending=0. Reports state purpose, expectation, results, analysis, scientific conclusion, and meaning for ThreeMind.
