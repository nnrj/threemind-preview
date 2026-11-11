# 连续版机制归因：完成记录

[English](../../en/plans/continuous-mechanism-attribution.md)

状态：**已执行并核查，2026-09-29**。按用户要求，本轮只解释上一轮连续版的“机制组合效果”，不修改跨时间生边机制，不修改内核或默认参数。

完成八组合消融、教学对应交换、教学顺序反转、测试时开关切换、旧基线、有背景与无背景对照，以及预先登记的六组参数诊断，共 341 个实例。

结论：短时突触资源是关键新增机制，并与既有抑制、逐边门槛、训练形成的权重共同作用。前缀没有激活结尾时，也能改变连接资源，让下一次 B 的响应发生区别。快痕迹在本任务只贡献约 0.093% 的平均差值；局部上下文没有可测贡献。门槛 ±10% 会使对应失效或反转，收敛输出仍为 0/64，因此下一步需要研究稳健性，不能把瞬时区别称为稳定推理。

- [中英文完整报告及图表](../../../lab/explorations/2026-09-29-continuous-mechanisms/report.zh.md)
- [实验前设计](../../../lab/explorations/2026-09-29-continuous-mechanisms/design.md)
- [第二阶段诊断方案](../../../lab/explorations/2026-09-29-continuous-mechanisms/diagnostic-plan.md)
- [命令、证据与复现边界](../../../lab/explorations/2026-09-29-continuous-mechanisms/README_CN.md)
- [交付与最终资源](../../../lab/explorations/2026-09-29-continuous-mechanisms/delivery.zh.md)

平台项目：`e769cd2d-c636-41b0-a266-6af1cca4b805`，名称 **2026-09-29 连续版机制归因**。实验笔记与记录、报告分开保存。原实验未被覆盖。

后续状态：跨时间生边、门槛分离、恢复速度的系统性验证均未在本轮实施；不能把建议当作已经完成的内核修改。
