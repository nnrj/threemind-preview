# Preregistration: memory, sequence, transfer and adaptation

2026-09-30, baseline 36c1ea7. A new independent study tests capability gains from the new input facilities without changing Core dynamics or previous evidence. Read-only instrumentation may live inside Core if hash-neutral; current public interfaces are preferred.

## Fixed conditions and controls

Use continuous-memory/2, reporting ordinary defaults and the 1-second facilitation preset separately. Keep arrival-window novelty (.018, reference .2), forgetting, inhibition, resource depletion/recovery, thresholds, clock and anonymous mapping unchanged. Physics advances at 5 ms and sensing at 20 ms. Labels and objectives remain external.

A separate synthetic channel supplies weak maintenance input every .5 seconds at intensity .2 during waits and probes. It is never grouped with task input and is not represented as real telemetry. This avoids treating a dead, frozen snapshot as a continuously maintained memory.

Input conditions: full joint plus inertial sensing; remove accelerometer/gyroscope but keep joint sensing; attenuate full physical amplitudes to match the removed-sensor condition's total dose without changing the intensity parameter; shuffle inertial sample timing while preserving each channel's total and other sensing. Closed-loop timing controls use a causal 200 ms delay, not future values. Joint sensing is also proprioception: removing IMU is not removing all proprioception. Raw measurements and every research transformation are retained.

Physical clips are generated from positive/negative initial poses of the same MuJoCo pendulum. Additional anonymous cue/outcome channels are declared experimental markers jointly presented with a measured frame, not predefined concepts or falsely attributed physical measurements.

## Calibration

Calibration seed 930199 is excluded from substantive statistics. At most 16 short cases compare intensity .03, .1, .3 and 1. Choose one common dose using survival, measurable shared joint-channel response and sustained saturation only, never answer accuracy or sensor advantage. Save the fixed selection before main execution; stop an unmeasurable family rather than change Core. Main seeds are 930101–930104; reserve 930105–930108 for separately registered confirmation of bounded, consistent and non-saturated effects. Seeds test wiring variation; time samples are not independent subjects.

## Four families

**Retention.** Present each physical-pose/cue combination 12 consecutive times initially, then interleave consolidation. Branch the same trained state to waits of 1, 60 and 300 simulated seconds, then cue A, cue B or no cue. Include untrained controls. Primary evidence is joint-target activation ranking at the pattern-convergence decision, with all ranks, legacy stability analysis and non-convergence preserved. Targets are specified by the sensor protocol beforehand. Secondary evidence includes cue-minus-no-cue response, selectivity, connection strength/stability, residual activity and saturation. Distinguish retained structure, recallability and ongoing activity; do not equate simulation seconds to human years.

**Order.** Teach AB followed by a shared ending C plus outcome X, and BA followed by the same C plus Y. The orders have equal elements and dose; first exposure repeats each example 12 times before interleaving. A control breaks order/outcome association while balancing outcome counts. Test AB or BA with identical C but no X/Y, after matched .5- or 5-second waits. Score X/Y rank selectivity and its reversal, not mere state inequality. No external timestamp conveys the answer; recency and ending input are controlled. Non-convergence is separately reported, not replaced by the final frame.

**Transfer.** Reuse trained retention clones after the 1-second wait. Present physical input without the teaching marker in the original world, an unseen starting angle and unseen gravity, in both directions. Test marker recall against untrained clones with the same readout. Retain units, timelines and dose; transfer across physical parameters is not unrestricted conceptual transfer.

**Closed-loop adaptation.** A MuJoCo cart with one actuator experiences opposite constant external forces. Keep the existing anonymous motor projection, without choosing a motor brain region. The external objective is remaining near the track centre; measure squared displacement, centre occupancy, limit contact and motor work. Inactivity or stereotyped movement is not inherently pathological. Each instance gets three 10-second episodes with the body reset to the same start, while consciousness continues. The selective control disables positive connection consolidation only, retaining forgetting, node dynamics and birth; do not use global plasticity, which also freezes some forgetting. Test clones in matching and reversed force environments for 10 seconds from identical body starts, with full/removed/delayed IMU. Include passive physics. Distinguish structural change, behavioral change and objective improvement against initial performance, consolidation-off and passive controls.

## Analysis and execution

Pair seed/preset/parent comparisons, publish every seed, effect sizes, convergence coverage and missingness. Resample at the seed level if intervals are needed. Secondary outcomes cannot silently replace a failed primary measure. Validate dose matching, identical endings, metadata-neutral hashes, unit conversion, paired time axes, recovery, reproducible physics and read-only scoring before calibration. Run retention/order/transfer before closed-loop work. Save tool failures; register scientific changes before executing them.

Limits: 1536 new instances, 4 hours aggregate simulation wall time, one worker, 4 GiB RSS. Stop expansion at 3 GiB new evidence and hard-stop at 4 GiB; reserve 2 GiB RAM, 5 GiB on C and 15 GiB on E. Shared account starts at 66%; +8 percentage points stops expansion and +10 stops new simulation. Use stage checks and a STOP file; reserve the final GiB for publication. Old projects remain unchanged. Publish bilingual design/results, full evidence and state hashes in a new project; local commits only, no push.
