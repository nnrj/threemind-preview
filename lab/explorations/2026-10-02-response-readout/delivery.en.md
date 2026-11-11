# E25 delivery verification

Completed 2026-10-02 with no new model simulations or changes to kernel dynamics.

- Platform project: **E25 短暂响应读出校准**, `53d7cd0b-d008-44ba-bc11-afdd35fb9c37`.
- Chinese report: `e1ba6941-5b63-5724-86b7-d3160371c96e`; English: `7ed0f8df-15bc-5990-b5bc-4bc69791e16e`. Notes include bilingual designs/results and execution corrections.
- Evidence artifact: `e9c6c47b-93fa-4a3d-adcf-fb2fcda1c742`, 15,686,092 bytes; 977 members verified. Database bytes match the local archive.
- SHA-256: `9499dd9fe15dd4dce34f2c468eb38b98e9431a2a2a34c693366af0ceb047ecf3`.
- Local files approximately 33.5 MiB, database growth 15.6 MiB, total 49.1 MiB including archived source copies. Originals were neither removed nor overwritten.
- 57 affected Python/Rust, API and CLI checks passed; frontend build, two browser tests at 1440/390 px and Ruff passed. All four history editions and 55 chapters passed bilingual/link validation.
- Old `target-observation/1` is unchanged. All 48 kernel source files and the native binary match E24. All 684 source evidence hashes match before/after.

In the platform, select the project above, then Records and reports → Reports. For a complete temporal record in any project, open Stimuli and outputs → select record → Process tools → Response readout; legacy sustained stability remains selectable. Use the new frontend build and backend version; running user services were not automatically restarted.

Authoritative derived data is under `.work/response-readout-20261002/verified/`. The first grouping summary in its parent directory is retained as a corrected execution record, not the final uncued statistics. See [report](report.en.md) and [execution notes](execution-notes.md).
