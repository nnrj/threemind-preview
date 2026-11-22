# R63n: Teaching timing, temporal jitter and dose-matched references

Preregistered protocol, 15 November 2026. This batch repeats E22B/C under the comprehensive revalidation plan v2, retaining its four anonymous material blocks and registered conditions. Registration follows successful R63m completion, full API readback and zero pending requests. The frozen kernel is 6.3, with signal threshold 0.0004, deletion threshold 0.008 and all other defaults unchanged.

## Questions, expectations and decisions

First, could the timing of the maintenance stimulus K explain differences attributed to teaching timing? Teaching and K offsets are varied independently. For each fixed teaching condition, we compare the raw five-second activation integrals of A and B and their cue-minus-blank integrals across three K offsets. A maximum range no greater than 1e−12 activation-seconds counts as unchanged. If all 48 comparisons meet this condition, the tested K offsets do not explain the target-response differences. Otherwise, the affected conditions establish a contribution of maintenance timing.

Second, does dense teaching require every pair to occur at precisely the same offset? Fixed timing is compared with a preregistered jitter sequence. All eight bidirectional comparisons—four blocks and two timing arrangements—must preserve order expression. Each comparison requires opposite signs of the net A−B response after AB and BA teaching, with both absolute differences exceeding 1e−6 activation-seconds. Recency and primacy are reported separately; either can meet this order criterion.

Third, is the effect of a shared reference explained by greater exposure of one channel? Two reference arrangements have identical per-channel counts and doses. The primary expectation is preserved order expression in all eight dense, shared-reference X comparisons at one and 30 seconds. All 96 reference comparisons are also reported, including separate references, sparse teaching and combined cues. Success with separate references would demonstrate a wider effective range in 6.3. Success restricted to shared references would support a role for the arrangement of paired stimuli in this course. Raw and blank-subtracted responses are retained throughout.

Failure of either the second or third primary expectation is a clear adverse difference from an established positive mechanism: preserve and deliver the batch, then pause the campaign for the user's decision. A newly detected effect of maintenance timing is reported as a mechanistic difference, without presuming every difference is adverse. Criteria remain fixed. Historical counts, response magnitudes and the earlier 99.91% jitter-retention ratio are comparisons, not mandatory numerical replicas.

## Courses and sample structure

The four material blocks are 100121–100124. A, B, C, D, X, Y, Z and K are readable record labels; the Core receives fixed anonymous codes, numerical intensity and timing. Teaching intensity is 0.4. K has intensity 0.2 and normally recurs every 0.5 seconds; every course first receives K at time zero. All 50,752 input records have been checked against historical originals, including enqueue and delivery times, elements, doses and ordering.

| Comparison | Teaching course | Conditions and size |
|---|---|---|
| Teaching and K timing | Twelve AX/BX pairs, 2.5 seconds between pair starts and 50 milliseconds within a pair; common Y at 32.2 seconds | Teaching offsets 0/40/60 milliseconds crossed with K offsets 0/40/60 milliseconds, facilitation constants 0/1 second, AB/BA; 144 teaching references |
| Bounded temporal jitter | Twelve AX/BX pairs, 550 milliseconds between starts and 50 milliseconds within a pair; Y at seven seconds | Fixed 40-millisecond offset versus the frozen sequence 12/52/48/30/43/67/7/10/28/11/38/10 milliseconds; 16 teaching references |
| Dose-matched references | Twelve rounds of shared AX, BX, CZ, DZ or separate AX, BZ, CZ, DX | Dense/sparse courses, shared/separate references and AB/BA; 32 teaching references |

In the first comparison, only K timing during teaching changes. The first K remains at zero, followed by K at 0.5 seconds plus the assigned offset and then every half-second. After teaching, all conditions return to the common half-second grid. In the jitter comparison, seed 22001 fixes the entire sequence; both frames within a pair move together, preserving their 50-millisecond interval. In the reference comparison, each object A–D appears 12 times and X and Z each appear 24 times. Each frame contains two elements. Dense rounds last 1.1 seconds, with slots at 0/50/550/600 milliseconds and a common ending at 13.2 seconds. Sparse rounds last five seconds, with slots at 0/50/2500/2550 milliseconds and an ending at 60 seconds. AB/BA changes only the first two objects; C and D keep their positions.

The first two comparisons use X=0.5 or no cue after a 30-second wait. Reference comparisons use no cue, X=0.5, Z=0.5 or X/Z=0.25 each after waits of one or 30 seconds. Combined cues match total dose, while their per-channel intensity is half that of a single cue. Every diagnostic observation lasts five seconds.

There are 192 continuous teaching references, 576 single-test diagnostic copies and 768 stages. The material unit remains four blocks; conditions, copies and questions do not increase the independent sample count. Teaching is continuous, and each registered causal comparison copy receives one diagnostic test. No trainable adapter is needed. Additional correction or increasingly spaced review would change the timing and dose being tested and is therefore not inserted into these fixed mechanism courses.

## State, measurement and apparatus checks

The established R63k executor and lossless state encoding are reused with the new registered schedule. Complete Core states are saved before and after every teaching frame, at teaching and diagnostic endpoints, and immediately before each probe: 12,864 states in total. Input-bus and observer state, random state, delivery records and all-node activity are preserved. Activation, inhibition, direct activity and associative activity are recorded every 20 milliseconds throughout the five-second window.

Independent apparatus material uses seed 100196 and one course from each family. Normal observation, observation disabled, sparse observation, full save/restore and host pause must produce identical final Core hashes. Apparatus material is excluded from scientific results. After computation, read-only checks verify continuity, each teaching snapshot and every input; 45-digit decimal arithmetic independently checks integration. No subject is advanced to reconstruct missing evidence.

Teaching snapshots support descriptions of how connections change. Analyses of formation beyond the registered response criteria are labeled additional interpretation and cannot replace primary measures. The 1e−6 threshold is primary; results at 1e−9 are a numerical check. Denominators are 72 teaching/K-timing comparisons, eight jitter comparisons and 96 reference comparisons, totaling 176 bidirectional comparisons.

## Budget, stopping and delivery

One scientific host runs at a time. A one-second guard preserves 5 GiB of commit headroom, 4 GiB of available RAM, 5 GiB on C and 25 GiB on E. Limits are 1 GiB private memory, two hours per batch and ten minutes per teaching reference with all its diagnostics. Resource pauses occur at complete-unit boundaries. Orphaned in-flight state, unverifiable originals, observation effects or answer leakage are preserved and reported.

Related historical originals total 102,940,395 logical bytes. Each unit is budgeted at 1.5 times its historical allocation; reaching twice the historical allocation or exceeding the estimate by 50% pauses the batch for review. Originals, archive and API readback each have a 1 GiB cap, with another 128 MiB for analysis and the 25 GiB E-drive reserve. The cost of complete per-lesson snapshots is checked in the apparatus and first complete unit.

Bilingual reports answer each question and explain its significance for ThreeMind, preserving differences from historical results. Full archive readback and pending=0 precede closure. Coverage, backlog and histories are updated, followed by a local commit without pushing. The E21 bodily-state factorial comparison and E22 early-state exchange and recovery remain separate pending sub-batches.

This batch repeats historical R51q with new 6.3 subjects and retains its materials, courses, comparisons and criteria. Function-level comparison found no changes to material construction or measurement; read-only checks against original inputs passed. Previously validated tooling corrections are included before registration: pristine zero-time birth is checked as waiting, and complete evidence uses lossless encoding. Tools are prepared; no registration or formal subjects exist yet.
