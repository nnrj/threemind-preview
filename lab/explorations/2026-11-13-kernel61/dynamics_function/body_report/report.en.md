# Identical taught states can produce opposite responses; a higher threshold did not improve closed-loop posture control

14 November 2026 · R51t3 · Four encoding blocks, 120 static diagnostics, 160 Core-controlled tasks and 16 body references: 296 stages.

## Scientific conclusions

**The same connections and activity state left by teaching can produce opposite response preferences under different transmission conditions.** Starting from the same complete taught state and changing only the test-time activation-transmission threshold from 0.0004 to 0.004 reversed both response directions in all four encoding blocks. With inertial sensing removed and joint sensing retained, both thresholds preserved the taught directions. This completes the causal comparison from an identical taught state.

**The higher threshold did not achieve the preregistered benefit in closed-loop posture control.** Under one actuator polarity, posture error decreased by 8.61%, below the 10% criterion; under the other, it increased by 0.49%. No Core-controlled condition reached stable posture, whereas the body's PD reference succeeded in 8/8 trials. The result does not support raising the default transmission threshold to 0.004 for this task.

## Purpose and previous evidence

R51m found reversed responses after the same teaching material, but thresholds differed from birth. That established a difference between whole configurations without separating formation from expression. This experiment first changed the threshold only before testing identical taught states, then connected the activity process to a simulated body to measure action consequences.

Four encoding blocks reused declared R51m parents taught at ordinary stimulus intensity. Core, input queue and observer history were preserved, with no additional teaching. Five conditions were compared: full sensing; inertial sensing removed; removed inertia with same-time total stimulus dose matched; shuffled inertia; and no teaching. These are descendants of existing parents, not newly independent birth sources.

Every copy first settled its configuration at the same internal clock. All nodes, connections, events and random state were then compared. Only the threshold and its duplicated storage metadata differed between arms. Static positive, negative and blank probes used the historical 0.6–5.6-second process window with blank subtraction. Direction required a peak difference above 1e-5 and an integral difference above 1e-6.

## Static reversal results

| Sensing condition | Threshold 0.0004 | Threshold 0.004 | Encoding blocks |
| --- | --- | --- | ---: |
| Full sensing | Both taught directions | Both opposite directions | 4/4 |
| Joint sensing only | Both taught directions | Both taught directions | 4/4 |

Direction is defined by the teaching relation. Activation, inhibition, direct and associative processes were recorded; scoring did not select the brightest single moment. All sensory controls, blank-subtracted quantities and individual values are retained in `analysis.json`.

This supports retaining reversal as a reproducible and intervenable mechanism for research. The precise statement is now supported by matched taught states, rather than by the earlier comparison of configurations that differed from birth.

## Closed-loop body and action rule

The existing gravity-pendulum model had mass approximately 0.419 kg, arm length 0.6 m, gravity 9.81 m/s², damping 0.002 and joint limits ±3 rad. Each eight-second task started at +0.7 or −0.7 rad and received a same-direction 0.5 Nm disturbance from 4 to 4.2 seconds. The task was to return toward neutral posture and damp motion; no untaught target-selection problem was introduced.

The Core received actual body sensing every 20 ms. A fixed process readout integrated A-minus-B activation over the preceding 0.5 seconds. Differences beyond ±1e-6 activity-seconds produced the corresponding 2 Nm torque; otherwise torque was zero. Both actuator polarities were tested. Actions changed subsequent sensing, forming a genuine simulated closed loop. Body state, torque, Core, observer, recent readout and random state were saved together.

Online removal excluded inertial channels. Dose matching rescaled remaining same-time inputs to the full-sensing total. Shuffling randomly permuted values across 12 inertial channels while preserving their same-time total; this online channel permutation is distinguished from the historical teaching-time shuffle. Zero-action and PD controllers were body references. The PD controller directly used angle and velocity and was not a ThreeMind output.

The primary measure was angle root-mean-square error over eight seconds. Velocity, final-second error, effort, switches and stable-posture success were separate outcomes. The high threshold needed at least a 10% primary-error reduction in at least 3/4 blocks, without a deterioration of at least 10% under the opposite polarity, to count as functional improvement.

## Closed-loop results

The table reports mean angle RMS error in radians. Each cell contains two initial directions in each of four encoding blocks: eight trajectories, not eight independent worlds.

| Sensing/teaching | Positive polarity, 0.0004 | Positive polarity, 0.004 | Negative polarity, 0.0004 | Negative polarity, 0.004 |
| --- | ---: | ---: | ---: | ---: |
| Full sensing | 1.7990 | 1.6441 | 2.4292 | 2.4411 |
| No inertial sensing | 1.3312 | 1.5245 | 2.4546 | 2.4338 |
| No inertia, dose matched | 1.4839 | 2.6885 | 2.4706 | 2.4377 |
| Shuffled inertial channels | 1.4273 | 1.6821 | 2.4500 | 2.4214 |
| Untaught | 0.5031 | 0.5031 | 0.5031 | 0.5031 |

Trajectories were numerically identical across the four anonymous encodings within each condition. This demonstrates stability under these encoding permutations; no independent-population significance test is inferred from them.

For full sensing with positive polarity, increasing the threshold reduced primary error by 8.61% and velocity RMS by 10.66%, but increased final-second posture error by 14.21%. With negative polarity, primary error increased by 0.49% and velocity RMS by 12.82%. Actual inertial information also failed to consistently outperform all dose-matched, shuffled and removed-inertia controls.

None of the 160 Core-controlled tasks kept both absolute angle below 0.1 rad and absolute velocity below 0.2 rad/s throughout the last second. Zero-action error was 0.5031 rad with 0/8 successes; PD error was 0.1035 rad with 8/8 successes. Untaught systems generated no A/B motor drive and matched zero action. The fixed-torque rule applied to taught responses produced larger swings.

**The experiment therefore yields a clear positive mechanism result for response reversal and a clear negative result for posture-control benefit.** Response direction can change, but converting it directly into sustained fixed torque did not produce an effective stabilizing policy. The result rejects the expectation that restoring reversal with this readout rule is sufficient to improve posture control. It supports retaining the present default threshold, rather than treating reversal as universally beneficial or harmful.

## Motivation, verification and delivery

Brooks and Cullen studied different processing of sensory information during active and passive self-motion in the primate cerebellum. Their work motivated separating the presence of inertial information, response changes and closed-loop usefulness. [Brooks and Cullen, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC6100740/). Usefulness here is measured from ThreeMind's own posture and action outcomes.

All 296 stages, 888 complete Core states and 76,136 inputs passed verification. Maximum independent arithmetic error was 4.44e-16. Full body/Core/observer restoration, extra observation and host pauses preserved matching end states. The first audit mistakenly included duplicated threshold configuration and its derived hash in scientific-state equality. A separate v2 audit normalized only those metadata; all remaining state was compared exactly. The original audit and explanation are retained, and no experiment was rerun.

Scientific host time was about 9.04 minutes, with peak private memory about 663.01 MiB. File allocation is recorded in `storage-before-publication.json`. Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/closed-body61-v1`. Full API readback and zero pending requests close the batch, recorded in `publication/completion.json`. Parents, copies, production Core, defaults and manuscript remain intact.

Figure: `figures/reversal-and-posture.png`, `.svg`, and `.pdf` in the evidence package, drawn read-only from recorded trajectories.

Before publication: logical files 191.73 MiB; unique allocated space 199.46 MiB; no additional hard-link paths. Later archive and readback copies are excluded.
