# E24 delivery verification

2026-10-02. Project **E24 目标响应与遥测背景对照**, ID `9f1aa861-2656-4af9-b3bb-4195f982cebd`.

- All 160 cases, bilingual designs and result notes are stored through ThreeMind services in the local database.
- Chinese report: `a1c704ac-1412-5bc4-a538-e6cb050d8cf4`; English report: `9b21660d-0837-5100-95a2-5b2fa62bb556`. Open the project's Records and Reports module.
- Three raw temporal records cover telemetry, randomized and absent backgrounds. Rendered tables contain 73, 73 and 4 nodes; A/B peaks and integrals match raw trajectories. Unresolved random-background convergence values remain null.
- Archive `395d2b5e-b817-432a-b9ca-81a5cfd66c56`: 70,127,314 bytes, 2,034 verified members. Reading database chunks back yields SHA-256 `40d09d3675e7150bdb2cc2ea9d1f88e3d88ad2e1590ae9a3059e7e740e312c30`, identical to the local archive.
- 304 selected historical source files are included unchanged. 48 kernel source files and the native binary match baseline. 11,781 frames/envelopes and 160 final states pass the audit; 84 deliberately pending frames remain preserved.
- Local evidence, selected historical copies, archive and database growth total 422,684,082 bytes, approximately **0.394 GiB**, below the 2 GiB budget. Whole-database growth is counted conservatively and can include unrelated writes.
- Aggregate case execution wall time: **404.40 s**. Shared-account readings: **93% → 94%**, not exclusively attributable to this task.
- **47** affected Python/Rust and CLI/API checks pass; production UI build succeeds; read-only browser interactions and downloads pass at 1440/390 pixels. Task-owned test services are stopped; user services were not restarted.

Reports and records were read back and content hashes verified. The archive includes CSV, figures, physical measurements, queues, inputs, states, trajectories, derived analyses and frozen sources. This receipt is generated after archive sealing and retained separately. No Core mechanism, historical instance or product default was changed. No Git push.

[English results](report.en.md) · [Tool usage](README.md) · [Execution limitations and corrections](execution-notes.md)
