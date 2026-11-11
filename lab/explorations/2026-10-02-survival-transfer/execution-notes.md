# E27 execution and verification record / 执行与核查

Recorded 2026-10-03. Registration started under the 2026-10-02 directory. Original experiment data and historical Core identities remain intact.

## Source and decisions / 依据与决定

- Baseline `5f27cef`; native `threemind.continuous-memory/2`. Runtime/Core sources and binary identity are frozen in the independent study project. Source definitions and each runner revision are retained. No `src/` or `crates/` changes occurred in this task.
- User required self-grasp before pouring; the free-cup cohort was executed first. Rigid grains were explicitly accepted instead of liquid. Attached-cup control was permitted only after the primary had no effect.
- Death must follow failure to obtain energy and the existing Core lifecycle; no forced clearing of activation or rank-based killing. Survivors alone may reproduce. Living nonparents would remain preserved.
- [Original registration](design.zh.md), [English registration](design.en.md), [parallel execution amendment](execution-amendment.zh.md), [operational boundary](../../../docs/zh/plans/robot-survival-selection.md).

## Engineering sequence / 工程核查经过

1. Verified pinned Menagerie Panda revision `1b86ece576591213e2b666ebf59508454200ca97`. Windows checkout line endings initially failed byte checks; cached assets were restored from the pinned Git blobs, not accepted by relaxing the checksum. No unpinned asset was substituted.
2. A separate privileged IK/PD controller checked mechanical feasibility. Attempt 01 used a 20 ms control period and failed; attempt 02 at 2 ms achieved grasp/lift but a receiver-floor threshold excluded settled grains. The floor measurement was corrected before any formal candidate. Attempt 03 transferred 9/12 grains. Later attached-cup engineering validation transferred 3/12. These trials contain no ThreeMind controller and provided no demonstrations to candidates.
3. Thirty simulated seconds of finite-energy calibration measured 167.58985448814784 units/s in its final 10 seconds. Initial reserve 40300, capacity 161200 and 10100/grain were frozen before candidates. Exact restore and read-only observation checks passed. Calibration is not counted as learned task success.
4. Notebook registration initially rejected relative Markdown URLs after creating the project. The same project was recovered with fixed source links; `registration-recovery.json` records the error. No duplicate project or formal candidate was created by this repair.
5. After the first founder, isolated simulations were allowed in at most three processes; all per-candidate wall durations still add to the four-hour budget. No live machine telemetry was injected. One original range runner later encountered a case already owned by another process and refused it rather than taking over; completed cases were not repeated. All 24 formal cases finished without simulation failure or budget censoring. Pool shutdown warnings did not indicate missing simulation evidence.

## Formal outcome / 正式结果

| Cohort | Count | Mean simulated lifetime | Physical grasp / transfer | Survival and children |
| --- | ---: | ---: | --- | --- |
| Free cup | 16 | 222.77625 s | 0 grasps, 0 qualified grains | All starved, no children |
| Attached cup | 8 | 215.6825 s | Grasp requirement removed, 0 qualified grains | All starved, no children |

Formal wall duration sums to 12867.6710499 s (3.57435 h), simulated duration 5289.88 s (88.16467 min). The conditional expansion to 32 free-cup founders was not taken: after 16 failures, the remaining budget went to the registered eight attached-cup controls. The machine was not run to resource exhaustion. Empty lineages explicitly preserve extinction; dead “best” individuals were not promoted into parents.

The attached cohort recorded 84 settled spills; this is a count over restocked batches, not 84 unique original grains. Endpoint `grasped/lifted` fields in attached worlds mean the task requirements are waived; they are not learned grasp/lift events. Analysis uses physical events for that distinction.

## Replay and tool validation / 回放与工具验收

- Eighteen distinct relevant tests passed. Three database integration tests were skipped because the separate PostgreSQL test cluster at 55439 was stopped. Actual study publication uses the authorized project database and performs its own readback checks.
- Pytest temporary-directory access was denied in two sandbox attempts. The same scoped tests passed with approved execution. The final five-test reusable-tool suite passed, including explicit image-difference disclosure and recorded-stimulus replay. No user service was started/stopped to work around testing.
- Frozen prototype and extracted loop produce equal raw inputs, physical state and Core hashes in the comparison fixture. Interrupted/resumed CLI operation matches uninterrupted execution; a separate birth test clears immediate state while retaining inherited structure. Fixtures are engineering checks, not extra learning samples.
- A first strict free-cup visualization attempt failed sensory equality without saving complete mismatch details. It remains labelled unverified. A later free-cup replay matched all 10,900 sensory frames, events and final physical state. Observation rendering uses a separate MuJoCo data copy; this does not establish the cause of the earlier failure.
- Attached-cup 000 strict replay failed at 7.92 simulated seconds. A diagnostic without the overview renderer also reproduced a difference in luminance, so it is not attributed simply to observation-camera feedback. Explicit physical-only replay preserved exact physical measurements/events/final state; 15 luminance values across four frames differed by 1/255. Its receipt clearly records that sensory reproduction was not exact. No original frame was corrected or replaced.
- A post-hoc Core replay initially hit its separately assigned 300-second wall cap after 9,885 matching input/activity steps. This is a verification timeout, not a dead or failed experimental individual. It was retained and restarted into a fresh evidence folder with the tool's bounded 900-second limit. Final replay receipts, including exact endpoint status, are the authority for completion; the final report is generated only after both representative Core replays succeed.
- Inspection found no source edits to Core or Runtime. No experiment changed the ordinary defaults, forgetting, inhibition, resource depletion/recovery, novelty, intensity bonus or propagation schedule.

## Delivery / 交付

Reusable Python/CLI parameters and commands are documented in [Chinese](../../../docs/zh/plans/robot-survival-selection.md) and [English](../../../docs/en/plans/robot-survival-selection.md). Granular cohort launch is not yet integrated into the full graphical robot workflow; T08 records that remaining work. Existing notebook/report UI presents this study's design, report, plots and evidence.

Publication archives source identities, inputs/actions, initial/final models, context, trajectories, task/energy receipts, engineering failures, tool validation, replay results, analysis and reports. Archive members and uploaded PostgreSQL bytes are verified. Final IDs, byte counts and readback results belong to the delivery receipt. No historical data were deleted or migrated. Only local Git commits; no push.
