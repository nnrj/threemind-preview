# E67 protocol revision 4: resume all four arms and compare scale/storage

[中文](design-r4.zh.md) · [Original protocol and revision 3](design.en.md)

Decision date: October 12, 2026. This revises the experimental protocol, not a kernel version. Earlier protocols, completed curricula, individuals and originals remain intact.

The user reauthorized both `/4` retention conditions after the ongoing `/2` and `/3.1` work, requested grades, performance, connection scale and total versus subject-only storage, and prioritized pausing `/4` if disk space becomes insufficient. The user accepted reusing the same curricula and questions, without demanding identical learning processes, and requested before/after correction comparisons.

## Subjects, curricula and scores

Finish the already-running two-arm revision-3 sequence and its initial exports first. Then run `/4 adaptive-half-life` and `/4 legacy-stability` sequentially, alternating their order across rounds. Two-arm completion is an interim delivery, not completion of the expanded E67.

The additional arms use the frozen initial lesson bank, all three existing correction courses, calibration/development/final questions and original apparatus. The correction courses were generated from `/2` and `/3.1` errors, not retrospectively from four arms: 165, 120 and 108 lessons. Each mainline therefore has 497 lessons and 865.5 simulated teaching seconds, excluding calibration sampling and evaluation. Internal states and answers need not match.

Adaptive `/4` resumes its own complete lesson-48 checkpoint. Preserved lesson-49–65 originals must compare byte-for-byte when replayed; conflicts stop execution without overwriting. The stability arm starts from its originally registered new blank complete individual. Each retains its own identity, kernel, configuration, peripheral/optimizer/RNG, body, mappings and recent activity. No background-only retention stage is added.

Report initial scores, every correction/review score, paired question transitions and final unseen-location scores separately. Calibration fit is not a test grade. Necessary additional `/4` correction may be registered separately from the equal-curriculum main comparison, preserving the original mainline state and scores. It must use opened development failures, not the main final questions; its additional teaching amount, cost and new final holdout must be frozen before execution. This amendment neither invents improvement nor authorizes an unbounded number of extra rounds.

## Scale and storage definitions

At matched stages report nodes, edges and density. Separate:

1. All research files for each arm plus its replay: trajectories, calibration corpora, historical checkpoints and interrupted originals included. Shared protocols, recorder journals and analysis are counted once separately.
2. One current complete individual at the last fitted source: Core, personal peripheral weights, optimizer/RNG, body/world, mappings and restoration-required recent activity. Exclude old checkpoints, full trajectories, feature corpora and videos.
3. Core-only canonical JSON and independently gzip-encoded size, computed without saving a duplicate. This is not a complete subject or an exact allocation within a jointly compressed file.
4. Logical file bytes and Windows file allocation. Shared installed application/dependencies and PostgreSQL physical pages cannot uniquely be assigned per model and are not silently reported as zero. Database recording overhead and file totals must be distinguished.
5. If memory is reported, distinguish instrumented-host RSS from the RSS increment after isolated read-only complete restoration, using CPU peripherals for a common measurement. The latter includes allocator/runtime effects; it is not exact object heap size, GPU memory or a change to experimental execution devices.

Subject-only storage must retain complete continuation state. Measurement, decompression, plotting and read-only restoration do not deliver inputs, learn or advance simulation.

## Execution and safety

Keep the active two-arm executor and frozen source unchanged. A separate coordinator waits for its computation/export completion, obtains the same exclusive resource writer lock, verifies registered sources/questions and resumes `/4`. It must verify actual process/state evidence rather than the chat's apparent status.

Reserve 30 GiB free disk for `/4`, pausing it earlier than the existing arms' 15 GiB boundary. Preserve the last complete checkpoint, saved originals and pending records. Do not delete evidence, skip recording, create a replacement individual or overwrite a replay mismatch. Reconcile receipts and resume from the saved boundary after interruption.

Use the existing normal-account authentication channel to check/renew a valid session, retaining actor identity and honoring revocation. Never put credentials in logs. Register this revision successfully before starting. Subsequent expiry, logout or network loss affects platform synchronization only: already-authorized local work continues with durable originals and pending requests, visibly marked pending sync. Resubmit under the original request identities after authentication is restored. Loss of login is not a pause command. Original-file failures, scientific-content conflicts, explicit stops and resource limits still halt work while preserving complete sources. Final publication requires ordinary authenticated verification.

Native timing retains saved pre-checkpoint cumulative measurements. The resumed `/4` initial stage's wall time covers only the new segment and must not be ranked as its full initial-course elapsed time. State replay and interruption overhead separately; overnight non-execution is not computation.

No Core/default/identity changes are authorized by this scope amendment. Decisive dynamics fixes still need a new kernel subversion. Preserve the two-arm analysis edition, produce a separate four-arm summary and four-video entry point, verify formal records, and only then finalize the expanded experiment.
