# M2 fusion apparatus v1: acceptance failed before scientific origins

16 October 2026; protocol `m2-fusion/1`, frozen commit c948f33. None of the eight scientific origins or 448 scientific copies ran. Instrument acceptance failure is not a negative receiver-mechanism result.

Excluded apparatus origin 917001 completed 16 instrument paths: ordinary/frequent observation, save/restore and wall-clock pause for each of four interventions. Within every intervention all four final whole hashes agree. Immediate 0→1 reversal matches 1→1 double-sham except branch identity.

Acceptance failed because the initial whitelist allowed only `core.config.context_mix`, while native serialization also correctly changed `core.definition.config.context_mix` and `core.definition_hash`. Source code copies configuration into the definition and recomputes its canonical hash. These identity fields must not be deleted from storage/comparison. Preserve the original passed=false result and apparatus-in-flight marker; do not retrospectively pass v1.

Reviewed revision 2 explicitly requires configuration/definition agreement and hash recomputation, with a new excluded apparatus origin 917002 and unchanged scientific design. This report does not claim that revision 2 has passed. See [revision 2](pilot-m2-fusion-v2.en.md). No original individual was rolled back and no Core code or scientific-source count changed.

Originals: `E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v1`. Project 1f6090f2-3855-4fea-b128-d4ec9ce447f4; record 7af929e0-7f95-5685-b7b2-5ddce4ce08ea. Close this apparatus batch with failed status after complete API archive readback and verification. Retain the marker and never rerun v1.
