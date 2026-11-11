# E64 execution handoff — read before changing a running experiment

> 公开存档说明：下文是该日期的交接记录，不是当前运行指令或启动授权。运行任何实验须先核对当前状态与协议。


Updated 2026-10-08. This is an operational handoff, not a replacement for the hypotheses, source reports or preregistration.

Documentation follow-up, 2026-10-08: at the user's request in the new conversation, the checked E56/E64 methods and execution safeguards are consolidated in the [training protocol (中文)](../../../docs/zh/training-protocol.md) / [English](../../../docs/en/training-protocol.md). Read it before a new teaching/calibration/evaluation batch. This addition does not change the completed study's results, gate, STOP or unexecuted branches.

## Authoritative request and order

1. Stop further E63 old-subject correction; its STOP file remains.
2. Audit E56's actually successful procedure before retrying. `audit.md` is complete.
3. User explicitly chose **one object in the center of one whole eye; answer shape/color**, not four-field pointing. E64 begins from a blank Core and its own new peripheral.
4. Only if blank tests meet the fixed criterion, calibrate the paused old individual's **own** peripheral. Do not transplant E64's head or overwrite E63.
5. If both work, document a separate experimental-procedure standard alongside the unchanged Core hypotheses.
6. After experiments, explain why the earlier procedure drifted, based on source/execution evidence. Context compression is not an established explanation. Decide whether a new conversation would help; do not create one without the user choosing it.

## What is fixed

- Study project `1ac69750-2c92-4123-b3dc-155dd25f1d04`, work `.work/centered-restart-20261008`.
- `design.zh.md` / `design.en.md`, `audit.md`, `.work/.../questions.json` and frozen registration define the experiment.
- Blank continuous-memory/2 seed223, sensory/text91; original E56 kernel/text configs are checked before stimulation. Do not change Core/defaults/mapping.
-104lessons,180simulated seconds;48real query windows;1200-step calibration;12practice questions;original5round exposure schedule;12later windows;continued calibration on48+12.
- E56 temporal architecture with an eight-word head for this selected task. All inference is raw Core activity,8frames across a full1second question. The same peripheral weights, Adam/RNG, body, Core and recent history are saved together.
- Each evaluation starts from the same complete source. Two32-question sets, each≥24correct and≥12/16per property, gate the old-subject branch. Do not quietly change this gate after scores arrive.
- `old_calibration.py` preserves original E63 PersonalVocabulary/Adam and its2second/16frame query contract; only genuine question calibration and whole-question reading change. It is conditional and must not start early.

## Final measured state at this handoff

No simulation is running. All nine E64 ordinary stages completed:104lessons/180s;48query samples; first-fit training48/48; practice11/12;5exposures on one error,39seconds;12later samples; final-fit training59/60; primary25/32(shape10/16,color15/16); confirmation27/32(shape12/16,color15/16). Calibrated types18/20and20/20; uncalibrated types7/12both. This is one trained source, not two independent seeds.140creations/restores,27.93compute minutes.

**The fixed branch gate did not pass. Neither fixed-reader edge interventions nor old-subject calibration ran.** Do not interpret existing conditional scripts as completed experiments or silently loosen the criterion. Substantial improvement remains a positive finding. Reconsidering the branch order is possible as a NEW dated decision, not a rewrite of the completed study.

E63 is closed (91.83compute minutes,15creations/restores). Its stopped calibration has44.45seconds and no fitted checkpoint. The original corrected subject is preserved at `.work/rehearsal-centered-20261007/cases/centered-correction/system`; do not replace its own peripheral with E64's. The original STOP stays. E63 ordinary correction matched2→7/32,shape0. Rehearsal actual arrivals0/12,2/12,2/12. Its full replay has482clips/28050frames.

E64 final complete source is `.work/centered-restart-20261008/cases/final-fit/system`. Formal questions use copies. Keep the original source unchanged. Full replay249clips/7100frames includes failures. An exact four-field draft in the neighboring directory was never executed and is superseded for this task.

## Commands and boundaries

Use `.work/kernel-venv/Scripts/python.exe` and the commands in README. Do not restart simulation merely to reopen or publish results. `analyze.py`, `replay.py` and `publish.py` never advance Core; the first two preserve existing output rather than replacing it. Per-study `delivery.json` and `.work/.../publication.json` identify actual archived artifacts and reports. If delivery is interrupted, resume publication idempotently, not simulation.

Actual account reading was21% when registered,22%at the end of simulation/report preparation; cumulative origin18%, expansion stops23%, simulations stop24%. Other tasks contribute to account change. No more simulations are scheduled. The original guard remains90compute minutes,384creations/restores,4GiBprocess,2GiBfreeRAM,C5/E15GiBreserves,2GiBnew evidence plus archival reserve to4GiB. Old data untouched. No Docker/service operation/push.

## Next research decision (not already performed)

- Read `report.zh.md` / `report.en.md`, `audit.md` and `docs/{zh,en}/plans/experimental-procedure-audit.md` before proposing changes.
- Five repeated errors mostly concern previously uncalibrated color/shape combinations. Normal teacher correction plus reviews of earlier correct cases is a candidate next step; retain this complete baseline and predeclare held-out questions. Do not repeat the entire optics/resolution search without evidence.
- Fixed-head connection attribution can be registered against the already useful25/32baseline; perfect scores are not necessary in principle. This batch's gate nevertheless remains unchanged, so no attribution result exists yet.
- Old-subject calibration remains conditional and unexecuted. The requested hypothesis-level experimental success standard also remains conditional; the retrospective supplies safeguards, not a falsely validated universal recipe.
- The procedure failures are traced to controller changes, bundled variables and unenforced preflight comparison. Context compression is not established as the cause. A fresh conversation after delivery is recommended with this handoff, but none was created automatically.
