# R63d: Eight-source replication of the four autonomy criteria on 6.3

Preregistered on 15 November 2026 under the original-scale revalidation plan v2. This is the eight-group X3 replication. The subsequent 64-group confirmation requires its own registration; neither these sources nor instrument materials enter that sample. Historical E15, X3 and M3 evidence and criteria remain intact.

## Scientific question

Does 6.3 exhibit experience dependence, selective internal causation, temporal interaction and feedback adaptation under the same anonymous teaching and ring environment? Do the four comparison implementations retain their previous pattern of results? The expected result is that 6.3 passes all four criteria while each comparator lacks at least one. A comparator that passes must be reported as possessing the measured properties. This batch tests the four scientific targets and apparatus before the independent confirmation.

## Subjects, peripherals and continuity

Eight independent encoding sources, seeds 1036100–1036107, each pair five implementations: reactive, finite-state, local Hebbian, fixed recurrent network with a personal RLS readout, and ThreeMind. There are 40 system units and eight source groups. Instrument seed 1036002 is excluded. The four controller implementations are unchanged; ThreeMind explicitly uses current 6.3 defaults. All receive the same eight public stimulus channels, materials and interface seeds. Their declared learning rules and sizes are retained without further tuning. Core has a fixed A−B readout; the recurrent comparator learns its readout by the existing teaching rule.

Each system has two continuous opposite-history teaching lives: 16 rounds of XYA/ZWB or XYB/ZWA, order counterbalanced by seed parity, channel amplitude 0.4 and stimulus intensity 1, followed by a one-second delay. Independent K=0.2 inputs sustain activity. Probes provide X=0.8 or no cue; temporal probes add Y=0.8 at 0.5 seconds. The full response process is recorded every millisecond. Comparators update only on their declared 50-ms grid or explicit input, so observation adds no update steps. All causal and diagnostic copies are registered separately from intact references.

Four closed-loop lives, PPP, PQP, QQQ and QPQ, each continue for 90 internal seconds in three 30-second stages. P and Q exchange the position–input relationship. Position determines sensation, output changes velocity and position, and velocity changes feedback. Model, personal readout and RLS state, random state, interface mappings, inputs, recent trajectories, body and actuator are saved. Stage diagnostics are explicit copies with a common body position and never feed back into the continuous life. Stage two also has same-input replay, replay with reversed motor sign, and genuinely closed-loop motor reversal copies.

## Frozen measurements and thresholds

1. Experience dependence: half the opposite-history difference in the X-minus-blank response integral from 0.1 to 0.3 seconds must have absolute magnitude above 1e−4.
2. Selective internal causation: under both histories, the target intervention changes the response by more than 1e−4 and ten times the sham error; the matched effect is at most 25% of the target effect; restoration error is at most 1e−9. Core uses XY-to-AB target connections and ZW-to-AB matched connections. Other systems retain their declared state interventions. Restoration actually applies the intervention before restoring the complete parent. The RNN selects 8+8 hidden coordinates using teaching-only matching with residual limit 0.5. A new teaching-only Core validity audit requires two edges per group, equal degrees, and absolute mean weight and activity residuals at most 0.02. This checks matching validity without changing scientific scores; failure is invalid measurement, not a negative result.
3. Temporal interaction: the 0.5–1.5-second integral of XY−X−Y+blank must differ by more than 1e−4 between intact and declared communication-blocked conditions under at least one teaching history.
4. Feedback adaptation: reversal versus stable environment must change the second-stage common-body diagnostic by more than 1e−4 in at least one direction. Closed-loop motor reversal must change inputs and model state, while same-input replay and replay with reversed motor sign preserve model state.

The historical X3 batch threshold remains at least six of eight sources for each criterion. Report each criterion, the number of sources jointly passing all four, and all source-level values separately. Passing each aggregate criterion is not described as every individual jointly passing. This pilot does not select results by confirmatory significance or add sources after results.

Invalid matching, observation or replay stops the batch with evidence preserved. If valid measurement shows 6.3 below the historical 6/8 threshold on any criterion, or a comparator passes all four and changes the prior discrimination conclusion, complete the current batch and pause the campaign for the author's decision. Otherwise deliver the registered result and continue eligible original-scale confirmation and remaining mechanism questions.

## Apparatus, resources and delivery

Before formal subjects, verify identical whole final states under ordinary observation, frequent observation, save/restore and wall-clock pause for all five systems. Sham adds only declared lineage; restoration returns the exact parent. Freeze the changes from historical pure measurement functions, production sources and native binary. The added Core matching audit is registered before formal teaching.

Run one scientific host at a time. Monitor every second and retain 5/4/5/25 GiB of commit/RAM/C/E headroom, with a 1-GiB private-memory cap. Pause after a complete system unit, preserving its reference and diagnostic states. Cap originals at 768 MiB, archive and readback at 768 MiB each, and analysis at 128 MiB: 2.375 GiB peak plus the 25-GiB reserve. Limit the batch to two hours. Preserve any new dead-host in-flight marker; do not rerun or roll back without authorization.

Expected output is 40 system units, 2,560 probes, 4,240 complete scientific states and 160 loop replay groups. Analyze saved data only and independently recompute integrals, all criteria and body/input feedback. Bilingual reports state purpose, expectation, results, interpretation, scientific conclusion and meaning for ThreeMind. Complete API readback of originals and reports with pending=0 closes the batch. Do not change manuscripts, old experiments or Core.

This batch uses current 6.3 defaults and genuine saved identity. The four controls, teaching, temporal windows, closed-loop courses and criteria remain unchanged. Relative to R51g, the target kernel implementation and whole-state version identity differ. Function-level checks verify the measurement port.
