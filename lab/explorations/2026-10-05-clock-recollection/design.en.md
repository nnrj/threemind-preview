# E51: a perceptible clock, now and just-now teaching

Registered2026-10-05 before execution. Follows the user's clarification that temporal concepts and retelling forms require teaching. Core/defaults and the original language encoder remain unchanged; E50 is preserved. This batch tests seconds-scale now/just-now, not hours or yesterday.

The four-object MuJoCo world remains populated. An external pointer rotates once per4 simulated seconds; four directional light sensors sample its projected illumination every.25s. Environment time sets pointer position and delivery times, but Core receives only anonymous measured quantities, no semantic temporal tags or object IDs. Teacher clock-reading words are ordinary teaching.

Twelve directed object pairs: seeA, thenB one second later; teacher demonstrates current-object sentences, asks and answers what was seen just now and what is seen now, and names the clock reading. Each entire demonstration initially repeats10times consecutively, followed by two increasingly spaced reviews:144episodes. Language frames actually arrive20ms apart, an explicitly recorded presentation change, not a new encoder. Ordinary intensity1, test-question intensity.5; inherited paired visual dose10. The existing E50 physical telemetry tape covers every course and probe.

Source223 first; only after90% external training fit is source279 attempted. Maximum256sources/probes,4model fits,2h cumulative computation, one worker; RSS4GiB/CUDA3GiB,2GiB evidence soft/6GiB hard, freeRAM2/C5/D15/E15GiB. Shared account baseline51%,+4stops expansion,+6stops new compute. No old data cleanup.

The local E50 reader sees six measured fields across17actual samples in2s, no baseline subtraction or per-example scaling. External supervision may teach full answer sentences; inference/Core receive no target labels.

Hold out four ordered pairs `(i,(i+1)%4)` from expression calibration. Eight remaining pairs×two questions×two views give32training observations, plus4clock questions. Core itself has seen all12demonstration types: this tests recounting new observed sequences, not unseen-logic mastery. Test all12pairs×two questions on new views (24), plus4clock phases. Identical current object/clock can follow different past objects, preventing current-scene-only past answers.

On four held-out pairs compare stationary clock, shifted origin and doubled speed (24probes). These are probe-time interventions, not lifelong clock ablations. Truth follows actual event order. A no-learning Core copy gets the same course with plasticity disabled and24matched questions; immediate traces remain, so its success would limit claims of learned temporal concepts.

Score past/current questions separately, including temporal wording and object names. Underfit teaching or chance-level held-out past answers stop expansion into hours/days. Successful short-scale recall would motivate later selective pathway silencing/rescue; no auxiliary classifier will be substituted for natural expression and called successful retelling. Preserve inputs, real times, raw activity, errors and life states; publish through Lab services. The clock is a kinematic environmental reference, not a claim about subjective time.

Before execution: clock answers refer to question onset while the observed pointer continues moving. Held-out clock views shift by.12radians within the same sector, rather than duplicating the exact calibration stimulus. Each complete source plan has114source/probe records; two total228within the256limit.

Instrument correction after source223teaching but before any probe delivery: a single visual frame with total amount10 violates the per-channel[0,1]contract and was rejected. Preserve the failed directory; use five actual same-view samples, amount2each,40ms apart, intensity1. No clipping or strong-intensity substitution. Source teaching was already distributed across frames and remains valid. Probe keys gain`-frames`to distinguish the unexecuted failure.
