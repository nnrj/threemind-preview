# Order expression under timing perturbations and dose-matched teaching

14 November 2026, R51q. This batch repeats E22B/C under comprehensive revalidation plan v2, using the frozen 6.1 kernel. The transmission signal threshold remains 0.0004, the deletion threshold 0.008, and other defaults are unchanged.

**This batch confirms that 6.1 expresses event order despite perturbations in teaching time. With stimulus counts and doses matched for every channel, a shared reference still supports order expression more effectively than the tested separate-reference arrangement. The timing of the K stimulus that maintains network activity does not explain these target responses.** All three preregistered objectives were met. Every historically positive condition remained positive, and 28 additional conditions passed. No scientific stopping condition was triggered; the remaining planned experiments continue.

## Why these comparisons were needed

R51p found order responses after shared-reference teaching and no target activation after separate-reference teaching. Those courses also differed in the number of presentations to the reference channels. This batch matches counts and doses before comparing pairing arrangements, testing whether the difference is explained solely by the amount of stimulation. Two further comparisons independently vary teaching and K timing, and perturb the timing of successive teaching pairs.

The original four anonymous material blocks, 100121–100124, supplied 192 continuous teaching references and 576 diagnostic copies. Each reference completed its course continuously. Each registered diagnostic copy received one cue or one observation without a cue. The material sample size is four; 192 and 576 count conditions. Readout is passive and follows the activity over time. No personal adapter is trained in this batch.

In the basic course, one reference repeatedly receives AX followed by BX, while the other receives BX followed by AX. Both are tested with X alone. Letters are report symbols; the kernel receives anonymous codes and numerical values. Activation, inhibition, direct activity and associative activity are recorded for all nodes every 20 ms. The primary measure integrates A and B activation over the full five seconds after the cue, subtracts the respective integral without a cue, and compares the two targets. Order expression requires the net difference to reverse sign when teaching order is reversed, with an absolute difference above 1e−6 activation·s in both directions. A stronger response to the later target is a recency effect; a stronger response to the earlier target is a primacy effect.

The three families contain 176 bidirectional comparisons: 72 for teaching and K timing, eight for timing perturbations, and 96 for dose-matched references. Full schedules, doses and criteria are specified in the [preregistered protocol](protocol.en.md).

## Results

| Comparison | Original E22 passes | 6.1 passes | Conclusion |
|---|---:|---:|---|
| Crossed teaching and K timings | 48/72 | 72/72 | Order expression at every tested timing; 24 additional positives |
| Fixed timing and perturbations between pairs | 8/8 | 8/8 | The tested perturbations preserve order expression |
| References with matched counts and doses | 12/96 | 16/96 | All 12 positives retained; four added for sparse shared references at 30 s |

All positive 6.1 responses show recency. The historical scores were matched individually to all 176 new comparisons. Original evidence and criteria remain intact.

### Teaching time and the stimulus maintaining activity

Teaching is shifted by 0, 40 or 60 ms, independently crossed with K shifts of 0, 40 or 60 ms. Both facilitation time constants, zero and one second, are retained. X is given 30 s after teaching. All 72 bidirectional comparisons pass, with net recency differences from 0.000357796 to 0.00335343 activation·s.

Holding teaching time, facilitation, material block and teaching order constant gives 48 comparisons across the three K timings. Raw and net activation integrals for A and B are identical in every comparison: the maximum difference is zero, meeting the preregistered 1e−12 criterion. **The order responses are not caused by K occurring at one particular tested time.**

### Perturbing the time of each teaching pair

The fixed condition shifts each pair by 40 ms. The perturbed condition uses 12 frozen offsets ranging from 7 to 67 ms. The interval within each pair remains 50 ms. Both arrangements pass 4/4 comparisons after a 30 s wait.

The mean net recency difference is 0.00155324 activation·s under fixed timing and 0.00152124 under perturbation, a ratio of 97.94%. The corresponding historical ratio was approximately 99.91%. Expression is retained, with a small reduction in amplitude. **Order expression does not require each pair to occur at exactly the same millisecond offset; the primary perturbation objective is met.**

### Reference relationships after matching counts and doses

Each shared-reference round presents AX, BX, CZ and DZ. Each separate-reference round presents AX, BZ, CZ and DX. Both courses repeat 12 rounds: A through D each occur 12 times, and X and Z each occur 24 times, at strength 0.4. Reversing AB/BA changes only the order of the first two objects. Dense rounds begin every 1.1 s; sparse rounds every 5 s. After teaching, separate copies wait one or 30 s and receive X, Z, or a joint X/Z cue.

Response values below are mean net recency differences across both teaching directions and all four material blocks, in activation·s. Each cell for X contains four bidirectional comparisons.

| Course and reference | X cue after 1 s | X cue after 30 s | Z and X/Z at both waits |
|---|---:|---:|---:|
| Dense, shared | 4/4; 0.0000810164 | 4/4; 0.000362513 | 0/16 |
| Sparse, shared | 4/4; 0.00169123 | 4/4; 0.000365862 | 0/16 |
| Dense, separate | 0/4 | 0/4 | 0/16 |
| Sparse, separate | 0/4 | 0/4 | 0/16 |

All 16 X-cue comparisons after shared-reference teaching express order. In the remaining 80 comparisons, raw A and B activation is zero throughout the observation window. These negative outcomes therefore reflect an absence of target activation, rather than cancellation caused by subtracting the no-cue reference. Joint cues supply 0.25 to each channel: total dose matches a single cue at 0.5, but each channel receives half that strength. The result concerns this specific cue condition.

After dense shared teaching, the net difference is larger at 30 s than at one second; after sparse shared teaching, the relationship is reversed. The relationship between waiting time and expression depends on the course. Connection history, current state and cue conditions jointly determine expression; elapsed time alone cannot replace its measurement.

## Scientific conclusions and meaning for ThreeMind

This batch excludes two specific explanations: that order differences arise solely from the timing of the activity-maintaining K stimulus, and that the advantage of shared references arises solely from stimulus counts or total dose. After matching counts and doses, shared-reference teaching still produces order responses and separate-reference teaching does not. **The combinations and temporal order experienced during teaching affect how 6.1 subsequently responds.**

This supports ThreeMind's experience-dependence claim. The same current cue expresses different teaching orders; expression tolerates the tested timing perturbations and remains present in every historically positive condition. The added positives extend the range of conditions supporting order expression in this batch. Response amplitudes and negative conditions are reported alongside those comparisons.

All three targets are closed explicitly: the K-timing explanation is excluded, order expression under timing perturbation is confirmed, and the role of a shared reference under matched doses is confirmed. E21 bodily formation, E22 state exchange and recovery, and the remaining capability experiments proceed at their planned original scales.

## Evidence, verification and resources

Read-only checks verified 12,864 complete states, 50,752 inputs and 768 stages, including genuine 6.1 identity, fixed-function addresses, state continuity, timing, doses and defaults. The maximum difference between ordinary integration and independent 45-digit decimal integration was 1.3877787807814457×10⁻¹⁷. Pass counts at the secondary 1e−9 threshold match those at the primary 1e−6 threshold. For all three apparatus courses, normal observation, no observation, sparse observation, complete save/restore and a host pause produced identical final Core hashes. Analysis neither created nor advanced subjects.

Before the formal run, storing every teaching snapshot as a small separate file projected actual allocation ratios of 2.021 and 2.042 against corresponding historical units. The budget rule prompted a storage review. Packing the same complete snapshots losslessly into one ZIP_STORED file preserved every byte and complete-state hash across 192 apparatus states. Courses, snapshot counts and state contents were unchanged; the original separate apparatus files remain available. See the [storage amendment](storage-amendment.en.md).

Scientific computation took 1209.40 s, or 20.16 minutes, with peak private memory of 598.01 MiB. At analysis, logical file size was 176.19 MiB and actual allocation 190.51 MiB. Actual allocation per unit was 1.616–1.779 times its historical counterpart, below the twofold review threshold. The 5/4/5/25 GiB resource reserves were maintained throughout, with no resource STOP or dead-host in-flight state.

Originals are stored at `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/order-reference61-v1`, research record `3513f983-f694-5d94-a720-bc90a50fcd95`. New results are in `analysis.json`; 176 matched historical comparisons and source hashes are in `postprocessing/historical-comparison.json`; verification is in `audit.json`. The archive, member manifest and complete API readback receipt are `originals.zip`, `manifest.json` and `publication/completion.json`. Closure requires verified coverage and pending=0. This is an internal project replication.
