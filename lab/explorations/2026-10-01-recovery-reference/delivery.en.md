# E22 delivery and post-hibernation verification

[简体中文](delivery.zh.md) · [Report](report.en.md) · [Registration](design.en.md)

Recorded on 2026-10-01 after the computer resumed. This is a separate supplement; the previously published reports, original experiments and evidence archive remain unchanged.

## Delivered evidence

All 1,520 registered cases completed, with 30.74 minutes of aggregate case wall time. Inputs, states, trajectories, readout windows, figures and bilingual reports are stored in the dedicated project **“2026-10-01 感官恢复、维护时机与共同参照”**. Archive-inclusive local and database growth at delivery was 1,790,530,921 bytes, approximately **1.668 GiB**. This supplement and verification files add a small amount separately.

| Platform item | ID |
| --- | --- |
| Project | `5e4f46e7-5d55-44de-a2b6-9707e2057387` |
| Chinese report | `d94c83b3-37a9-5483-a0be-edd761e0caca` |
| English report | `c76b0570-9d10-5352-9eef-ddf90effadc1` |
| Complete evidence archive | `3a9a1f0b-7981-4409-9d34-1efd02c4ffe7` |

The archive contains 275,233,497 bytes and 14,558 manifest members plus the manifest itself. SHA-256:

`8b328d152599b426096d03706c80c9964c861aaecaa52cdd5f7fb781c558b764`

## Effect of battery exhaustion

**No adverse effect on this batch was found; rerunning it is unnecessary.** Power events and saved timestamps place simulation, audit, publication and archive read-back before hibernation. All times below are Beijing time (UTC+08:00):

| Time | Event |
| --- | --- |
| 13:28:37 | Dedicated study registered |
| 14:21:37 | Experimental audit finished; STOP written |
| 14:27:39 | Reports and archive published and verified; delivery receipt saved |
| 14:28:06 | Recorded low-power entry, with hibernation-page write data |
| 19:19:41 | Recorded wake, with hibernation-page read data |
| 19:31:30 | Additional post-resume data verification completed |

The log includes `TargetState/EffectiveState=5`, `HiberPagesWritten`, `HiberWriteDuration` and `HiberReadDuration`, consistent with the user's account of hibernation. The queried relevant power events after registration contain no unexpected power-loss/shutdown event 41 or 6008.

Post-resume checks found:

- The ZIP hash matches the pre-hibernation receipt, and all 14,558 members pass individual checks. All 14,545 corresponding local evidence files match. The remaining entries are twelve archived publication-source copies and the usage monitor refreshed after wake; their archived bytes also pass verification.
- All 1,520 database checkpoints decode successfully, with chunk checks and full Core hashes matching local states and original receipts. Historical sources and registered implementation files also match their recorded hashes.
- All 68,640 input frames are delivered. The project's nine publication/source jobs are complete, with no pending or leased jobs and no partial temporary files.
- All 1,520 copies are `paused`, the intentional post-experiment state preserving recoverable snapshots; this does not indicate incomplete experiments.
- Bilingual reports, eight original readout records, three published result/delivery notes and the database evidence archive pass another read-back.
- Git connectivity verification exits with code zero and reports no corruption. Unreferenced blobs were preserved, not cleaned up.

The checks cover E22 evidence, its referenced sources and this repository, not the entire computer or other projects. No instance was resumed, no new simulation ran and Core was unchanged. The 30.74-minute case wall total predates hibernation and excludes its duration.

Account usage after wake was 91%, versus 88% at registration and 90% at original delivery. This is shared-account usage and cannot all be attributed to this task. The no-expansion threshold has been reached and the registered study is already complete; remaining work is documentation and delivery only.

## Audit trail and follow-up

The dedicated local evidence directory `.work/recovery-reference-20261001/` retains `delivery.json`, `resume-audit.json`, `power-events-after-study.json`, `git-integrity.json` and the executed `resume-verifier.py`. The executed copy has SHA-256 `92358f962b338cc68255c73d65ea008a96ca6ab61bc739cf30fcaeb2d2a9a405`; repository `verify_delivery.py` subsequently received only UTC-alias and import-order style changes. This supplement is also saved as a notebook entry in the same project.

The remaining scientific questions are the individual fast-state contributions to early reversal, propagation timing versus arrival timing, and per-channel joint-cue dose; see the [research backlog](../../../docs/en/plans/research-backlog.md). Existing results and criteria remain unchanged, and extra-intensity replacement remains deferred.
