# E24 执行记录 / Execution notes

2026-10-02。保留设计、输入、案例、原始全局判定与历史证据；以下区分工具开发中发现的问题和模拟执行情况。

- 开发态工具对已序列化的微秒字符串曾缺少整型转换；旧记录校准检出后，在登记与所有新模拟前修复并增加回归。没有改内核。A saved microsecond string required integer conversion in the derived analyzer; calibration caught and tests covered it before study registration/simulation.
- 主矩阵前，把研究输入载荷改为已有公共匿名 `frames` 形式，确保可用原协议重新解码。来源和随机化依据保留在冻结材料中，刺激数值不变。Earlier acquisition used real telemetry and was unaffected. No failed matrix pilot was substituted.
- Windows 沙箱最初拒绝临时目录／子进程，获得执行权限后使用独立测试数据库；最终相关 47 项全部通过，不以跳过项冒充通过。The final affected run had 47 passes; earlier permission failures were engineering checks, not model outcomes.
- 390 像素浏览器检查发现长实验名撑宽页面，已修正换行；补齐局部状态中文显示与目标图时间范围。1440/390 最终均通过；原始旧记录导出字节保持一致。The final CSS matches the validated styling; unrelated formatter churn was removed.
- 事前的随机负载顺序恰为四区组全部 minimal→dense，并未形成交错；未重抽种子或补样本。报告明确保留时序混杂，不能把全部宿主差异单独归因于负载。The random table is retained verbatim; order balance was not achieved.
- 160 个新案例全部完成，无失败案例。84 帧在观察边界后仍待递送，完整保留，不算丢帧。死亡的无背景实例不复活，不补零或伪称完整五秒观察。All actual inputs, final states and source hashes passed the separate audit.
- 生成图表前检查 Matplotlib 安装信息时，Windows 终端对许可证版权字符报编码错误；不涉及依赖安装、模拟或数据，随后直接导入并生成图表正常。A package-metadata display encoding error did not affect computation.

模拟顺序为采集、主矩阵、表达阶段、实时负载和精确重放，单 worker。所有新观察只在现有运行时之外分析数据；Core 源码及原生二进制未改。Temporary web-only review and test database services are task-owned and stopped after validation; user services are not restarted.
