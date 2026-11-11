# M2汇合装置v1：验收未过，科学来源未启动

2026-10-16，协议`m2-fusion/1`，冻结提交c948f33。8个正式来源和448个科学副本均未运行。本结果是仪器验收失败，不能报为接收机制的阴性。

装置来源917001的四种操作分别进行普通/频繁观察/保存恢复/墙钟暂停，16条完整仪器路径完成。每种操作的四个最终完整哈希相同；0→1立即恢复与1→1双假操作除分支身份外完全一致。

验收失败原因：初版白名单仅允许`core.config.context_mix`，实际还改变`core.definition.config.context_mix`及`core.definition_hash`。原生源码保存时明确复制完整配置到definition并重算canonical_hash；这是配置身份的同步，不能从保存或比对中删除。初版`passed=false`和apparatus-in-flight原件保留，不改判为通过。

已经审阅的修订2将完整定义与配置一致性及定义哈希重算作为显式检查，用新排除装置917002重新验收，科学设计不变；尚未以本报告声称新装置通过。见[修订2](pilot-m2-fusion-v2.zh.md)。不存在原个体回退、Core代码改变或额外正式来源。

原件目录`E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v1`。项目1f6090f2-3855-4fea-b128-d4ec9ce447f4，记录7af929e0-7f95-5685-b7b2-5ddce4ce08ea；以failed状态结束本装置批次，完整压缩包及哈希通过统一API读取核验后保存回执。标记保留，禁止重跑v1。
