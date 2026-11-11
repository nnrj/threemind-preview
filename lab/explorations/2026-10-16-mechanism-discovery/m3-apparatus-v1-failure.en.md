# M3 confirmation apparatus v1: lineage-check failure before science

16 October 2026. Frozen revision ee36465; originals m3-confirmation-v1; record ec99096b-2bd0-558f-a54d-831f8e65b395. [中文](m3-apparatus-v1-failure.zh.md)

**Conclusion: formal apparatus validation failed because its comparison treated correctly declared sham-branch lineage as an unwanted state change. No scientific origin was run. This supplies neither a positive nor a negative M3 criterion score.** The instrument-validation error is identified and preserved; a separate revision corrects only the lineage comparison.

Purpose and expectation: before the 64-origin confirmation, verify whole-state equivalence under ordinary execution, frequent observation, save/restore and wall-clock pause for all five implementations. A sham must add only declared lineage; immediate restoration must reproduce its parent exactly. These conditions and the RNN teaching-match check were expected to pass.

Results: all four paths have identical whole-state SHA256 values within each implementation, covering 20 paths. RNN standardized matching residuals are 0.3355836868 and 0.0632318926, both within the original 0.5 limit. The overall gate is nevertheless false; the executor preserves apparatus-in-flight and exits as specified. Scientific N=0, with no scientific units, host or progress. This is an apparatus failure, not five scientific system failures.

Diagnosis: the frozen check requires `restored.save()==sham.save()==parent.save()`. The existing `fork('sham')` deliberately creates a `branch` field containing the parent-state hash, sham label and unchanged internal time. Its whole dictionary therefore cannot equal the parent without that newly declared lineage. The validation condition contradicts the registered branch convention. Diagnosis uses frozen-source inspection and isolated instrument regressions; no v1 originals or scientific subjects were rerun or repaired.

Disposition: preserve v1 code, protocols, all 20 path states, matching result, failure result and marker. Archive with failed status and verify the full original package and text through the unified API. Revision v2 has a separate entry point, directory, record and idempotency namespace. Its sham must equal the parent plus exactly the declared branch; every other field remains identical. Restoration still requires exact whole-state parent equality. Five-system isolated tests also reject altered body state or branch labels. The four criteria, 64 source seeds, teaching, statistics, Core and scientific execution are unchanged.

Meaning for ThreeMind: this identifies a defect in research-instrument validation and requires a fresh formal apparatus check. It supplies no new scientific evidence for or against the model and leaves the previous eight-origin result unchanged. Other authorized batches continue; M3 science waits for the v2 apparatus gate. No scientific subject was rolled back, reborn or cleared of an incomplete experience.
