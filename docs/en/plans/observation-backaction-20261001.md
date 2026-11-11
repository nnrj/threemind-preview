# Feasibility of observation effects and delayed choice

[简体中文](../../zh/plans/observation-backaction-20261001.md)

2026-10-01. Status: assessment and candidate design following the user's proposal. **Execution has not been decided or registered; no new simulation has run.** Core, input mapping, existing consciousness criteria and historical evidence remain unchanged.

## Three distinct questions

1. Does reading state change Core evolution through software side effects or scheduling?
2. Does observation workload alter CPU, memory or I/O telemetry that subsequently enters the model as stimulation? This is a measurable environmental feedback effect with value independent of a quantum explanation.
3. Can a later choice to observe alter the distribution of earlier outcomes without a forward information path? This is a separate hypothesis, not established by either of the first two effects and not a standard quantum prediction for this software system.

## Literature and implementation evidence

Delayed-choice erasure uses quantum states, entanglement, measurement devices and correlations between two outcomes. In Kim et al., sorting by the partner detection reveals complementary interference patterns. Unsorted statistics do not thereby carry a readable message about a future choice. Physical measurement and a person later viewing its record are different operations. [Original experiment](https://arxiv.org/abs/quant-ph/9903047) [Standard quantum analysis](https://arxiv.org/abs/1908.03920)

Ma et al. physically implemented causally disconnected choices with entangled photons. Preventing software messages is not equivalent to implementing spacelike separation and quantum measurement conditions. These experiments do not establish that human attention or later viewing rewrites recorded past events. [Experiment](https://arxiv.org/abs/1206.6578)

Core advances from saved state, timestamped inputs and simulated time. Wall-clock time and readout conclusions are not direct dynamics variables. The same full state, configuration, backend and timed inputs should reproduce the same result. E22's nine representative observation-disabled replays matched full Core hashes; this supports those paths without exhausting all possibilities. [E22 report](../../../lab/explorations/2026-10-01-recovery-reference/report.en.md)

Code inspection confirms that host, process and runtime telemetry can encode CPU load, memory pressure, I/O and execution timing. Reading without writing Core does not guarantee absence of system-level feedback: observation workload can change subsequent measured input. This is a concrete path worth isolating. Copying a software snapshot provides identical classical records, not quantum entanglement.

## Suggested experimental sequence

### First stage Fixed input replay

Choose sixteen existing full snapshots covering active, recovering and in-flight states. Preserve configuration, forgetting, inhibition, energy mechanisms, queues and clocks. Preserve any pseudorandom state or its realized input stream. Replay the identical timestamped inputs for all three telemetry scopes, including activity-maintaining background. Do not replace fixed input with absent background or alter encoding.

| Condition | During execution | Purpose |
| --- | --- | --- |
| A | No extra process reads; common terminal capture | Minimal observation baseline |
| B | Frequent reads with recorded output | Full observation path |
| C | Same reads but discard output bodies | Separate reading from output handling |
| D | No model reads; independent computation/I/O approximating the workload | Test load and scheduling; record matching quality |

Two repeats per condition give at most 128 short replays. Keep advance boundaries, inputs and end times identical. Compare complete terminal Core states, excluding external report metadata. A reproducible difference triggers localization of the earliest divergence in fresh copies and checks of inputs, queues, random state, numerical updates and reader side effects.

All groups have common terminal recording; A is not physically never measured. Repetition of a deterministic clone does not create independent probabilistic trials or imply a 50:50 null. Proposed bounds: one worker, twenty minutes, 512 MiB new evidence and existing memory/disk reserves. Stop expansion at the first reproducible divergence and investigate rather than accumulating significance.

### Second stage Live telemetry feedback

Register separately after stage one. Randomly interleave live observed/unobserved conditions and record raw physical measurements, encoded inputs, delivery times, external load and model activity. Replay each realized stream into an otherwise unobserved clone to test whether it reproduces its Core outcome.

Reproduction shows that the recorded input is sufficient to produce the difference; it does not automatically exclude every other influence or demonstrate quantum collapse. Live sampling is replaced only in the isolating replay conditions, with the recorded background retained. Do not describe responses to different inputs as observation effects under identical inputs.

### Third stage Optional later-choice control

Freeze an early outcome definition, such as the difference between two target activation integrals, and rules retaining all trials. Complete that window and save its record and checksum commitment. Only then let an independent program, unable to read model outcomes and sharing no model random state, generate a fresh random choice of later extra observation versus no extra observation. Do not supply that choice to the model beforehand or derive it from the outcome.

Compare **all committed early outcomes** under the later random assignments. Do not select successful trials from later readout values or treat one significant result as confirmation. Outcome variation must have an auditable source. Sample size requires a prespecified effect size, power and stopping rule; the first stage's 128 deterministic replays are not automatically an adequate statistical test.

The common early record already involves observation. This checks independence from a later additional observation choice; it does not reproduce quantum erasure. A bias warrants preserving evidence, examining allocation, timing, shared randomness, selection and physical/software channels, followed by independent replication. Neither assume every discrepancy must be a bug nor call it quantum merely because a classical cause has not yet been found.

## Feasibility and priority

Stage one is feasible locally and improves instrument reliability. Stage two can measure real coupling between observation and the model's physical host. Small versions are worthwhile. Stage three is an optional independent consistency check, not currently a recommendation for a large statistical campaign.

A nonclassical quantum claim needs a controlled physical quantum system, a suitable witness and checks of that witness's assumptions. Probabilistic output, software randomness, a quantum random input source or correlated classical copies alone do not establish quantum Core dynamics. A future adapter could connect genuine quantum experiments, while separating the apparatus's contribution from the model's. No decision to acquire quantum hardware or change Core is made here.

## 2026-10-01 execution authorization and registration

The user subsequently authorized isolating telemetry feedback, repeating an established result under no background and random background, and arranging further observation checks. The opening unapproved status describes the earlier assessment and is preserved.

E22 dense teaching-order reversal is selected. Initial source/input inspection finds periodic synthetic K, not live telemetry; the feedback pathway cannot retrospectively explain this particular old result. [E23 preregistration](../../../lab/explorations/2026-10-01-observation-background/design.en.md) specifies three backgrounds, same-input observation controls, actual live-input replay and a bounded later-choice check. Its criteria and budgets govern execution. Results will be recorded separately after running.

## 2026-10-01 completion note

[E23 bilingual report and evidence](../../../lab/explorations/2026-10-01-observation-background/report.en.md): random background retained the selected order effect; background-free early processes matched but subsequently died; fixed-input observer states matched; all 12 final live-input replays matched; 128 later-choice trials showed no detected association with earlier results (stratified permutation p=0.957). The proposal, preregistration, failed/pilot records and corrections remain available. Core is unchanged. No physical quantum experiment was conducted; this phase stops expanding.

## User proposal in translation

The exact Chinese text is retained in the linked Chinese version. The following is an English translation of an exploratory question, not a confirmed physical interpretation:

> Before the next step, I would like to make an observation: can we see different results caused by quantum effects in the model? My hypothesis is that even if a probe does not intrude into Core, probing itself changes the consciousness's outcomes in space and time. I imagine testing copies of the same instance by analogy with quantum experiments, including entanglement, mirrors and changed gates, where results appear determined before light arrives and observation seems to influence what happens. Could a probabilistic outcome become statistically biased when probed rather than not probed? Could a later observation, concealed from the side where the outcome arises, cause an associated state to appear earlier? My description is confused. Please assess feasibility and necessity and suggest a design if feasible.
