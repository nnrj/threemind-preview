# 结果后诊断登记：重复期间 H 是否曾增长

2026-10-08。run-02 已完成；在教学结束和各保持保存点，方案 1 的最大连接 H 均为 30 秒。该结果不能证明 H 从未增长，可能在两次观察间增长又回落。追加只读重放以区分这两种情况，不改输入、参数、读出窗口或结论标准，也不重教原个体。

对 run-02 两种重复组，重新执行原始完整入队清单至 530s，前 24s 每 100ms，之后各原定句子开始后 100ms 及 530s 只读捕获 H、边权及累计传输统计。保留每帧文字边 H 最大值、权重总量及数量，最后状态哈希必须与原 t530 完全一致。观测到的峰值是该采样下的峰值，不称精确连续峰值。此为结果后机制诊断，不混作预登记的主要比较，也不据此搜索更有利输入或增益。

Post-result read-only replay: resolve whether H briefly grew between the registered checkpoints. Replay the exact run-02 repeated inputs and settings to 530s, observe every 100ms through 24s and 100ms after each later sentence. Require the final canonical state hash to match the original run exactly. Report sampled peaks, not exact continuous maxima; no new teaching, altered input, parameter tuning or changed endpoints.
