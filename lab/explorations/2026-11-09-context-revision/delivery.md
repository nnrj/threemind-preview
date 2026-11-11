# R43 首批交付 / First-batch delivery

2026-11-09。8个独立个体全部完成，G2为8/8达标，G1/G3/G4均0/8。主计分与另一份逐题计数实现一致，2,856个完整边界、136组连续链及2,688道正式题通过核验。[中文报告](report.zh.md) · [English report](report.en.md)

正式输出采用三个个人时序Transformer适配器：1秒20帧原始记录，入模8帧，每帧激活/抑制/直接/联想四项。均值激活投影是单列的事后诊断，没有改变行为或成绩。

The eight-individual batch is complete. G2 passes in 8/8; G1/G3/G4 each pass in 0/8. Formal output used temporal Transformers and four activity fields. The mean-activation projection is a separate post-result diagnostic.

## 平台与完整读回 / Record and full readback

- Project: `09e358fa-b05a-4bc0-93b2-643148fb72ab`
- Record: `4159a847-5671-504a-b0dc-800fca835e96`
- Execution: **completed**; evidence coverage: **verified**; pending: **0**.
- Archive: `originals-v1.zip`, **573,213,406 bytes**.
- SHA256: `d615b82cea65085458331e84438dc6c7ea15528722690b96a7ac38855dfc46b9`.
- 8,911 listed members, plus the enclosed manifest. The archive was downloaded in full through the API; its hash and every manifest member were verified.
- Both protocols and both reports were read back as exact text: four documents.

原件目录：`E:/ThreeMindData/experiments/2026-11-09-context-revision/v1`。最终凭据位于 `publication/completion.json`、`publication/final-verification.json`、`publication/document-readback.json`、`publication/download-receipt.json`；完整下载包在 `readback/originals-v1.zip`。

Originals and receipts are in the work directory above. Review was by the execution assistant, with separately implemented arithmetic. This does not claim external or human replication. Publication here means recording in the existing local research API, not posting to an external journal or repository.

## 状态解释 / Status interpretation

`status.json`保留科学宿主结束时的 `awaiting-analysis / 8` 快照；`postprocessing/automatic-analysis.json`保留自动分析结束时的 `awaiting-report-review` 快照。完成状态以本交付和平台回执为准。不得因这些历史快照重新运行个体或重复分析。

Scientific and automatic-analysis status files retain their historical end-of-stage snapshots. The publication receipt is the completed delivery state. They are not instructions to replay the study.

普通教学和测试全态连续；相反历史和干预是登记副本。本批没有更改Core及默认、回退正式个体、恢复旧实验、修改作者论文、使用云端费用或push。后续方向另列研究总表R43，不在本批自动追加。
