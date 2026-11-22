# Lossless whole-state storage for R63k

15 November 2026, before registration. This retains the storage method already verified in R51n. TMIND keeps the same ZIP member names, order and byte contents, while using Deflate compression on disk. Every encoding checks each member byte-for-byte and verifies the decoded whole-state digest with the existing ArtifactCodec. Core, subjects, input ordering, observation and scientific decisions are unchanged.

After the new apparatus checks, `compact_run.py prepare` verifies all apparatus states, saves a compressed example and file-level proof, and registers the evidence in this batch's research record. Formal execution then uses `compact_run.py run`. It substitutes only this lossless file encoder and invokes the same frozen scientific procedure. Original apparatus files are retained.

Physical allocation is measured with Windows FileStandardInfo for both historical references and new units. The two-times-historical and 1.5-times-estimated stopping multipliers remain. Registration records the actual reference values rather than treating logical file length as physical allocation. The tools and this note are frozen at the first registration; the subsequent proof uses measurements from the new apparatus.
