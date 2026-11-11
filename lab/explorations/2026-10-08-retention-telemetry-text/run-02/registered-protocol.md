# 整句单帧文字对照：运行前追加登记

2026-10-08，run-02 创建及 Core 运行前登记。继承 [原登记](protocol.md) 的四组、时点、课程、指标、冻结遥测、配置及停止条件，只有以下明确差异。本批属于用户授权的文字保持对照；不修改 run-01 的任何个体、外设、证据或 Core。

## 追加原因与读出边界

run-01 采用逐字单帧文字载体，四组在全部检查点的 TT 与 TB 均为 0；530s 文字节点存在，故不是文字未输入，而是没有建立文字连接。检查现有 `edge_birth_policy=co-stimulus` 及 `_associate` 路径，只有同帧触达的不同节点可成为新边候选。每帧只有一个字符，无法形成字际新边。这是实验输入与既有出生策略的适配问题，不能解释为两种遗忘规律导致连接丢失。原始结果、执行脚本、登记及全部快照保留于 run-01。

四个**新空白个体**改为已有 `TextSensorConfig.frame_characters=24` 的默认帧宽，七字句子一次完整输入一帧；提示词也是一帧。编码仍是原 `literal-character`，gain=1、intensity=1、NFKC、seed 相同；保留 50ms 帧间隔配置但这些短句均只有一帧，不产生帧间间隔。既有感官按字符数平方根缩放，所以七字句每字幅度为 `0.72/sqrt(7)`，双字提示为 `0.72/sqrt(2)`，不另补偿强度。不改变默认建边机制，不加人工边，不延续或移植 run-01 状态。

这样测量的是“整句共同出现的字信号形成的连接”的保持和消退，不能称为字序理解。两方案输入严格相同；与 run-01 同时改变了同现方式和幅度，不能把跨批差异单独归因于某个遗忘机制。run-01 是完整保留的输入适配阴性证据，run-02 才能在形成了文字边的前提下解释其保持。

仍先执行两模式各 24s Python/Rust 状态比较；若发现正文与实际输入不符或两后端决定不一致，保存失败并停止解释。全部设定在 run-02 结果出现前锁定，不因命中或保持结果改变课程、门槛或时点。若此载体仍不能形成文字边，报告无法测量，停止继续搜索有利输入。

## English amendment

Registered before run-02. Run-01 created text nodes but no text-related edges: one character per frame supplies no distinct same-frame pair under the existing default co-stimulus edge birth policy. Preserve that run as an input-design negative, not forgetting evidence.

Create four separate blank subjects using the existing default frame width of 24, so each seven-character sentence and each two-character cue is a single frame. Keep the literal-character encoder, seed, intensity, gain, schedules, telemetry, Core settings and endpoints. Its existing square-root normalization remains untouched (0.72/sqrt(7) per sentence character, 0.72/sqrt(2) per cue character). No old subject, peripheral or Core is replaced. This measures retention of co-present character connections, not word order or language understanding. Do not attribute cross-run changes solely to forgetting. The run-02 script and this amendment are frozen with the evidence; no outcome-driven parameter search follows.
