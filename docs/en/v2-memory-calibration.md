# Memory calibration kernel continuous-memory/2

This version retains all memory/1 mechanisms and adds the creation-only `novelty_mode` parameter. Identity: `threemind.continuous-memory/2`; state: `threemind.continuous-memory-state/2`; hypothesis: `threemind.hypotheses/continuous-memory2`. All four prior kernels and snapshots remain restorable. Relabeling an old state is not a conversion method.

## Local novelty

The formula comes from Git `97d8592:core/threemind/runtime.py`: a new edge touching an existing neighborhood can receive a one-time bonus for weak, nonzero associative reentry, `gain × max(0, 1 − min(1, reentry / reference))`. There is no semantic interest, importance, or unfamiliarity score. Isolated births, zero propagation, and reentry at or above the reference receive no bonus.

- `immediate` preserves memory/1 birth-time evaluation exactly, apart from identity and diagnostic metadata.
- `arrival-window` (new-creation default) freezes prior-neighborhood eligibility, gain, reference and a deadline equal to the next propagation time scheduled at birth plus its delay. It accumulates actual endpoint associations within that window and processes same-time arrivals before awarding once. Direct input does not become associative evidence, and future activity is not read.

A node-to-pending-edge index supplies local inputs without a new full-network scan. Disconnecting/deleting cancels pending births; rebirth receives a fresh serial. All pending amounts, deadlines, serials, and diagnostics survive exact snapshots and Python/Rust restoration. Structural inheritance clears this short-term state; exact snapshots do not. Disabling plasticity or silencing an endpoint/edge cancels the bonus at settlement. Changing gain/reference affects subsequent births; pending births retain their captured parameters. Changing mode requires a new consciousness.

Diagnostics distinguish births, ineligibility, disabled gain, absent reentry, reference saturation, awards, and cancellations. `requested_bonus` is the formula amount. `weight_bonus` and `stability_bonus` are actual capped settlement increments for arrival-window mode only; their immediate-mode zeros must not be interpreted as missing birth bonuses.

## Intensity and forgetting

The existing extra consolidation factor remains `intensity_gain × max(0, intensity − 1)`. Intensity 1 does not trigger this extra term, while ordinary first/repeated-contact consolidation remains. Calibration uses 0.4, 1, 1.5, 2, and 4, retaining saturation and actual energy accounting.

Forgetting comparisons separately stop weight forgetting, or weight/stability/node-support slow changes, while preserving other mechanisms. There is no justified conversion from 300 simulation seconds to human lifespan; compare the model's own activation, resource recovery, trace, stability, and forgetting timescales.

## Default selection after calibration (2026-09-30)

The [786-instance report](../../lab/explorations/2026-09-29-mechanism-calibration/report.en.md) retains positive effects, zero results and complete controls. New creation selects memory/2 with arrival-window settlement; causal/9, memory/1 and immediate settlement remain available. Both novelty calibration modes use a 1-second facilitation time constant. The new-creation facilitation default remains 0 (extra facilitation disabled), so the reported percentages are not promises for every configuration.

Changing propagation interval, delay or gain affects subsequent births; pending windows retain their deadline/parameters. An explicit retiming intervention can leave an existing window without reentry, yielding zero bonus rather than extending it to manufacture an effect.

New UI/API/CLI creation and definitions use the current default; restoration follows saved identity/configuration. Historical RunSpec and ecology-job/1 documents without kernel_id still mean causal/9. Explicit Python Config/MemoryConfig types retain causal/9/memory/1 identities. Existing saved project defaults are never overwritten.

Subsequent default update, 2026-10-08: the September 30 calibration and then-current /2 decision above remain intact. Current creation selects [/3 activity-dependent retention](plans/memory-retention-v3.md), preserving arrival-window novelty. Old individuals and explicit /2 research protocols do not migrate.
