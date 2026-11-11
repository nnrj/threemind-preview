# Git 纪事与取证边界

[简体中文](git-register.md) · [English](../../../en/history/sources/git-register.md)

## 为什么 Git 从八月开始

根提交 `97d8592` 并非项目起点。首期对话 8 月 24 日轮次 `01a0338c-028d-7683-8898-d175d966c34c` 记录 `data/records.json` 在旧历史中曾达到 3811.40 MB，推送被拒；用户提出备份后重建干净 Git，助手建议保留旧历史备份、重新导入代码。现存根提交与这段记录相符。本次未取得该旧备份，不能声称已恢复全部早期提交。早期对话和 lab 札记作为独立史料补充。

## 怎样核查公式与恢复

`git show 97d8592:core/threemind/runtime.py` 可读旧巩固实现；`git show c42baed` 可查 V3 恢复；`git show 347e57a` 可查活动死亡更新。这里只给只读命令，不要求切换或覆盖当前工作树。提交标题是当时作者的摘要，不是本书对所有行为的重新验收。时间是 **committer 时间及原时区**，不能等同实验全部完成日。

## 当前历史中的提交

| 提交 | 提交时间 | 当时标题 |
| --- | --- | --- |
| 97d8592 | 2026-08-24T20:26:07+08:00 | init |
| f5eb58b | 2026-08-25T10:13:40+08:00 | add mouse and ear |
| aa484a3 | 2026-08-25T11:17:47+08:00 | update ear and eye |
| 09a5c61 | 2026-08-25T21:54:46+08:00 | fix: ear and eye |
| 962def6 | 2026-08-25T23:39:38+08:00 | fix: ear and eye |
| 0c5e64a | 2026-09-05T20:55:43+08:00 | feat: update |
| ea6c8ba | 2026-09-05T22:43:29+08:00 | feat: update |
| dd8a9d8 | 2026-09-06T01:22:06+08:00 | feat: restore file sensory adapters and passive output organs |
| 23652f3 | 2026-09-06T01:59:10+08:00 | feat: restore physical telemetry with audited delayed feedback |
| 4e43349 | 2026-09-06T02:53:22+08:00 | feat: restore recoverable structural and temporal readouts |
| 9839e04 | 2026-09-06T03:59:59+08:00 | feat: restore bounded and auditable live media capture |
| 425f1a3 | 2026-09-06T04:35:01+08:00 | feat: restore independent organ cadence and continuous monitoring |
| 309b077 | 2026-09-06T05:06:50+08:00 | feat: restore versioned optional causal mechanisms and parameter controls |
| 78f911b | 2026-09-06T05:44:10+08:00 | feat: restore model resource budgets and verifiable accounting |
| 14de159 | 2026-09-06T07:00:56+08:00 | feat: restore energy accounting and explicit external supply |
| 33e3496 | 2026-09-06T07:53:59+08:00 | feat: restore input attention and explicit scalar modulation |
| 54e859a | 2026-09-06T08:58:00+08:00 | feat: restore causal spatial experiments and historical geometry |
| 8067e0c | 2026-09-06T09:35:28+08:00 | feat: restore recoverable environment and body tools |
| 98b8a2e | 2026-09-06T10:31:44+08:00 | feat: restore scoped network devices and recoverable input sessions |
| 228c02c | 2026-09-06T11:15:32+08:00 | feat: unify adapter contracts and scoped capability inspection |
| 67203eb | 2026-09-06T11:59:25+08:00 | feat: add resumable database media uploads with bounded carrier reads |
| 69b9d0f | 2026-09-06T12:52:02+08:00 | feat: restore stimulus and readout conversation with evidence links |
| 0bdb5e1 | 2026-09-06T13:53:47+08:00 | feat: restore source admission and recoverable per-frame competition policies |
| 402eb59 | 2026-09-06T14:45:50+08:00 | feat: add model annotations, exact lineage and reference-protected cleanup |
| 05a22ac | 2026-09-06T15:23:20+08:00 | feat: restore graphical paired study design and typed runtime conditions |
| 5e3c370 | 2026-09-06T16:29:47+08:00 | feat(lab): add checkpoint-bound manual research console and stepping |
| fa23e82 | 2026-09-06T17:08:13+08:00 | feat(lab): execute durable research plans with typed commands and templates |
| 4e5af3c | 2026-09-06T17:57:25+08:00 | feat(lab): add encrypted AI providers and independent durable call queue |
| 022aacd | 2026-09-06T19:03:13+08:00 | Restore external AI environment, interpretation and research tools |
| 3b0db4d | 2026-09-06T23:28:06+08:00 | Restore network display controls and optimize passive readouts |
| 2fca4f3 | 2026-09-07T00:15:37+08:00 | Stream checkpoint-scoped evidence and cache unchanged graph queries |
| 5f1d157 | 2026-09-07T01:13:19+08:00 | Restore project notifications and independent SMTP and Resend delivery |
| 903f138 | 2026-09-07T01:38:54+08:00 | Restore named state capture with atomic receipts and device naming preferences |
| 11eaf5c | 2026-09-07T03:01:27+08:00 | Restore UI language selection while preserving research and editor state |
| 4a1233f | 2026-09-07T03:33:42+08:00 | Centralize deployment and project execution limits with audited GUI controls |
| d529291 | 2026-09-07T04:21:49+08:00 | Match worker capabilities and retain per-attempt execution receipts |
| ccbf898 | 2026-09-07T04:28:36+08:00 | Bound container resources and isolate the Lab data network |
| 1022374 | 2026-09-07T05:50:09+08:00 | Add private research notebooks with dual editors and immutable revisions |
| 63d1e91 | 2026-09-07T06:53:40+08:00 | Add fixed research evidence and versioned records and reports |
| 2bb8314 | 2026-09-07T07:49:56+08:00 | feat(reports): export fixed revisions with verifiable evidence bundles |
| 79f30aa | 2026-09-07T08:23:40+08:00 | feat(reports): generate reviewed-scope AI drafts with fixed evidence |
| 908595e | 2026-09-07T09:04:27+08:00 | feat(reports): capture fixed input and intervention event evidence |
| 4b28da2 | 2026-09-07T09:45:27+08:00 | docs(deploy): verify isolated Linux application and worker recovery |
| 54044c4 | 2026-09-07T10:00:08+08:00 | feat(reports): publish fixed revisions with explicit evidence access |
| 5a5f0dd | 2026-09-07T10:50:02+08:00 | feat(training): add developmental runs and reusable innate lineage |
| 2d47dd0 | 2026-09-07T11:22:06+08:00 | feat(training): separate environmental variation from inherited sensory identity |
| 4029c5b | 2026-09-07T11:22:40+08:00 | docs(training): record final environment configuration validation |
| d66f72a | 2026-09-07T12:19:40+08:00 | fix(readouts): preserve raw activity independently of causal interpretation |
| 7fd8c0a | 2026-09-07T13:47:01+08:00 | feat: add directed multigeneration training and fixed research evidence |
| db115a0 | 2026-09-07T15:02:17+08:00 | feat: add configurable physical worlds and standalone body runtime |
| f268d83 | 2026-09-07T15:47:05+08:00 | feat: add reviewable AI world and body proposals |
| 43636d9 | 2026-09-07T16:21:15+08:00 | feat: add ecological rules and shared physical population adapters |
| 60c1928 | 2026-09-07T18:11:09+08:00 | feat: add ecological populations, atomic recovery and graphical research tools |
| 8dad833 | 2026-09-07T18:38:35+08:00 | feat: add standalone ecology CLI and atomic population interchange |
| b8936e9 | 2026-09-07T19:16:58+08:00 | feat: add fixed ecological population reports and graphical resource ledger |
| f285808 | 2026-09-07T19:39:54+08:00 | fix: isolate headless renderer failures and allow repeated database bootstrap |
| 62a0b6b | 2026-09-07T20:07:16+08:00 | fix: preserve histogram precision and readable PDF table fragments |
| 2d447e3 | 2026-09-07T20:13:27+08:00 | perf: copy population evidence only for active subscribers |
| 7a41f88 | 2026-09-07T20:31:16+08:00 | docs: verify ecological deployment and record measured capacity limits |
| 5767a60 | 2026-09-07T20:56:10+08:00 | feat: preserve anonymous device wiring across model deployments |
| 4648672 | 2026-09-08T01:55:13+08:00 | feat: add evidence-bound ecological observation and warnings |
| 4a973c6 | 2026-09-08T02:25:18+08:00 | feat: add standalone observation and optional speech |
| d316a3c | 2026-09-08T03:06:22+08:00 | feat: add independent birth assessments and fixed report decisions |
| 20b91c2 | 2026-09-08T03:36:35+08:00 | feat: add optional evidence-bound ecological AI commentary |
| 2d76d3d | 2026-09-08T04:09:46+08:00 | feat: add optional execution resource and progress warnings |
| a04903f | 2026-09-08T04:45:48+08:00 | feat: add shared adapter contracts and offline integration checks |
| 31122f3 | 2026-09-08T05:08:31+08:00 | fix: make adapter validation results readable on narrow screens |
| 95a6db5 | 2026-09-08T05:19:52+08:00 | docs: record final reconstruction and deployment acceptance |
| 0d334e7 | 2026-09-08T09:25:39+08:00 | fix: default consciousness to continuous operation with optional duration |
| 32d4634 | 2026-09-08T09:43:34+08:00 | docs: audit legacy and current kernel behavior and retract parity acceptance |
| c42baed | 2026-09-08T19:14:11+08:00 | fix(core): restore V3 local laws with causal propagation clock |
| 5ef9a46 | 2026-09-08T20:08:19+08:00 | fix(core): preserve optional boundaries around restored V3 dynamics |
| a741a3b | 2026-09-08T20:08:25+08:00 | feat(lab): expose restored parameters and acknowledged organ controls |
| 53342ac | 2026-09-08T20:21:39+08:00 | feat(ui): restore inline consciousness chat and sensory controls |
| 304ef25 | 2026-09-08T20:31:04+08:00 | docs: record V3 restoration decisions and acceptance evidence |
| 347e57a | 2026-09-09T01:00:39+08:00 | fix(core): make inactivity the only death rule |
| 99a1e87 | 2026-09-09T03:37:55+08:00 | fix(capture): decouple packet admission from model checkpoints |
| b1d8954 | 2026-09-09T04:42:54+08:00 | fix(notes): accept Markdown link titles in document saves |
| b35a816 | 2026-09-09T04:44:09+08:00 | research: record bounded memory and relational exploration |
| 522dbec | 2026-09-09T08:16:42+08:00 | feat: calibrate isolated sensory probes and audit experiment storage |
| b95d128 | 2026-09-09T08:37:23+08:00 | research: validate calibrated pair memory and held-out family composition |
| d4f4db2 | 2026-09-09T18:14:53+08:00 | lab: record bounded language teaching and relation diagnostics |
| ba2c7b3 | 2026-09-09T20:04:38+08:00 | lab: verify blocked sentence teaching and matched pair controls |
| e5317b5 | 2026-09-09T20:06:12+08:00 | lab: preserve published experiment evidence byte hashes |
| db4e0a4 | 2026-09-09T20:54:59+08:00 | lab: repeat sentence teaching with default sensory mapping and exact carriers |
| 6b568a4 | 2026-09-10T03:17:28+08:00 | feat: preserve temporal evidence across runtime and research reports |
| 8ed2603 | 2026-09-10T03:18:27+08:00 | fix: restore continuous chat and expose temporal research workflows |
| 480a4e4 | 2026-09-10T03:19:29+08:00 | docs: record temporal chat acceptance and manual backup guidance |
| 6c106ca | 2026-09-10T09:44:19+08:00 | research: repeat sentence teaching with temporal endpoint evidence |
| 468b7a5 | 2026-09-10T10:59:22+08:00 | research: record bounded time comparison and resource stop |
| ab6681c | 2026-09-10T17:36:21+08:00 | research: test unpunctuated pairing with temporal endpoint rankings |
| 300dfee | 2026-09-10T19:11:02+08:00 | feat: expose optional text stimulus intensity in CLI inputs |
| f3f6053 | 2026-09-10T19:21:47+08:00 | research: evaluate pairing with recorded host background and ten-second inputs |
| b53fba1 | 2026-09-24T02:00:38+08:00 | feat: update docs |
| 4f39b9a | 2026-09-28T19:20:01+08:00 | test: freeze causal9 behavior and bind kernel research principles |
| f306d04 | 2026-09-28T19:38:06+08:00 | feat: introduce explicit kernel identities and validated runtime definitions |
| b422040 | 2026-09-28T20:18:16+08:00 | feat: add versioned continuous candidate with native and standalone recovery |
| 691a499 | 2026-09-28T21:50:25+08:00 | feat: add independent spiking kernel and bounded local Transformer tools |
| c008c5d | 2026-09-28T22:01:46+08:00 | feat: expose versioned kernels and local comparison tools across screen sizes |
| eb21fdf | 2026-09-29T08:56:03+08:00 | feat: add shared research operations, resumable stages and optional compute devices |
| 8a1cff3 | 2026-09-29T10:14:23+08:00 | feat: add verified experiment bundles and research tool interfaces |
| ecbf243 | 2026-09-29T12:21:50+08:00 | fix: render private report attachments and readable mobile tables |
| 0d32a0b | 2026-09-29T12:22:27+08:00 | research: record bounded multi-kernel calibration and comparison study |
| 6b793fd | 2026-09-29T13:27:19+08:00 | docs: add plain-language interpretation of candidate kernel experiments |
| 27c0034 | 2026-09-29T14:06:38+08:00 | Investigate continuous kernel mechanism attribution with bounded experiments |
| aa3fb7f | 2026-09-29T15:34:21+08:00 | Append synaptic memory discussion and design isolated DFL experiments |
| 9d59720 | 2026-09-29T16:06:00+08:00 | Add isolated DFL research kernel with preserved baseline behavior |
| 52dc8a0 | 2026-09-29T16:40:08+08:00 | Run bounded DFL memory experiments and publish audited bilingual results |
| b9c2459 | 2026-09-29T17:25:23+08:00 | Document energy supply distinction and staged autonomous activity experiments |
| fd7fbac | 2026-09-29T18:28:05+08:00 | lab: test input timing and inherited environmental preferences |
| 3b69b8f | 2026-09-29T19:23:03+08:00 | docs: append autonomy discussion and causal interpretation corrections |
| 4195eeb | 2026-09-29T19:24:03+08:00 | research: verify history-dependent internal activity changes behavior |
| 2d782dd | 2026-09-29T20:41:57+08:00 | docs: append fixed autonomy criteria and retention hypotheses |
| c57bb1d | 2026-09-29T20:42:46+08:00 | research: validate autonomy criteria and retention with 802 instances |
| 0a94f42 | 2026-09-29T23:13:52+08:00 | feat: isolate runtime and add versioned activity process readouts |
| 5d99b1d | 2026-09-29T23:35:34+08:00 | feat: add versioned local novelty arrival-window kernel |
| a346fa0 | 2026-09-29T23:36:49+08:00 | research: preregister intensity novelty and retention calibration |
| 93286bc | 2026-09-30T00:37:57+08:00 | research: publish bounded mechanism calibration and retention evidence |
| 6241016 | 2026-09-30T00:38:45+08:00 | feat: select calibrated memory kernel for new consciousnesses |
| 965ed11 | 2026-09-30T17:31:15+08:00 | docs: freeze stimulus baseline and peripheral research boundaries |
| be403d2 | 2026-09-30T17:51:00+08:00 | feat: add traceable stimulus units and peripheral inertial sensing |
| 3351a33 | 2026-09-30T17:51:57+08:00 | research: preregister bounded stimulus and physical reference comparisons |
| c24e30f | 2026-09-30T18:29:45+08:00 | fix: validate random fixtures and preserve failed compute progress |
| 36c1ea7 | 2026-09-30T18:30:12+08:00 | research: publish stimulus comparisons and GPU device acceptance |
| 5c9c3ae | 2026-09-30T18:55:37+08:00 | research: preregister memory sequence transfer and adaptation comparisons |
| 46f3d43 | 2026-09-30T19:28:03+08:00 | research: add paired trajectory analysis and sensory intervention controls |
| 5110e10 | 2026-09-30T20:30:51+08:00 | research: verify memory retention transfer and embodied adaptation |
| 2d23297 | 2026-09-30T21:38:12+08:00 | Add bounded process observations and reusable research tools |
| 189ba10 | 2026-09-30T22:44:36+08:00 | Register intensity mechanism study and consolidate research backlog |
| e83aedd | 2026-09-30T23:54:52+08:00 | Record intensity mechanism ablations and publish verified research evidence |

---

编纂于 2026-10-01；所述历史截至该日。原始材料与后来的解释分列，原件保留。
