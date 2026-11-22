# 2026-11-13：性能暂停后的有界定位

R51a首条件已触发预设暂停：1024节点、1024有向连接，10内部秒，第二组5次比较的墙钟比8.55、CPU比9.67。正式科学复验停止。原件显示6.0扫描204800个节点/连接项，5.1扫描数为零；两者最终规模相同。

为区分固定函数寻址和从5.3继承的规则，本次仅增加5次5.3/6.0工程比较，材料、时长、配置及保存内容与首条件相同，交替运行次序。假设：若5.3与6.0耗时和扫描计数接近，则显著成本差异已存在于5.3，不由6.0繁殖操作造成。直接推进的基准未调用繁殖函数。记录状态散列、扫描、节点/连接访问及计时，完整交付。它不恢复任何科学批次，也不修改内核或默认。

另以四条曲线和两种继承策略，共8个新生工程样本，检查独立Rust可执行程序读入Python产生的后代、接收相同新刺激、导出完整状态，与Python原生后端逐状态比较。旧版本14次出生见证已通过，保留源提交a84bafda和见证文件。

English: Formal revalidation is paused after the registered performance gate. A bounded five-repeat 5.3/6.0 comparison now locates whether the cost predates fixed addressing. It uses the same 1024-node/1024-edge fixture, ten internal seconds and alternating order, with complete states and counters. No reproduction is called by that benchmark. Separately, eight newborn fixtures (four decay curves, two inheritance-age policies) test complete continuation through the standalone Rust executable. These engineering checks do not resume the scientific campaign or change any dynamics/defaults.
