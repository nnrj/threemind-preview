# 执行工具修正 / Execution tooling correction

2026-09-30。执行至 85 个已保存实例时发现，脚本使用 `registered-probe` 来源标识；现有读出器把不属于 manual/ai 的标识归为 ambient，而默认不以背景来源开启窗口。**不是模型未收敛，是观察窗口没有登记。** 原始输入、轨迹、内核状态全部保留，不将缺失窗口计为负结果。

仅在本研究脚本将探测来源改为 `manual-registered-probe`。新探测保存在原路径下 `/registered`，从完全相同的父检查点出发；若已有旧探测，逐个验证最终 Core 状态哈希相同。未训练条件和无提示轨迹仍保留；无提示本来就不伪造刺激窗口。修改不改变感官编码、输入量、递送时间、内核或分析阈值。预计加上保留的旧探测仍低于 384 实例上限。中断记录和本修正随完整证据归档。

At 85 saved instances, the runner's `registered-probe` source was found to be classified as ambient by the existing observer. Ambient-triggered windows are disabled by default. **This was missing observer registration, not nonconvergence.** Inputs, trajectories and states remain intact; missing windows are not negative outcomes. The runner now uses `manual-registered-probe`, writes separate `/registered` probes from the exact same parent checkpoints, and checks final Core hashes against previous probes. No encoding, input dose, timing, dynamics or analysis thresholds change. No-cue controls retain their actual trajectories without fabricated windows. The interrupted attempt and this correction are archived; the total remains within 384 instances.
