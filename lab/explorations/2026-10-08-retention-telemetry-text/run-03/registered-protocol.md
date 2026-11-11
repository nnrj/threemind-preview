# 完整旧 /2 对照：用户追加要求后的运行前登记

2026-10-08，run-03 创建前登记。用户原话：“然后你测完当前的之后，在适当的阶段，用同样或类似的的测试用/2测一下，看旧版内核的表现。我怀疑我们经过一通修改后，退化了。”此前另强调：“注意进行适当重复，看保持情况”。本批根据新增明确授权，测试**完整** `threemind.continuous-memory/2`，不是把 `/3` 个体改版，也不是把 `/3` 方案 2 重命名为旧版。

两个新的空白 `/2` 个体，重复/单次各一；使用 run-02 已冻结的文字感官配置、接线、完整输入清单、物理 host 遥测、课程、保存点、原边世代指标和提示副本。四句各 57 次、0.5→32s 渐疏及共同末次呈现不变；单次组仅末次呈现。字句进入同一帧，强度及归一化不变；不按新结果选择有利课程。物理背景仍至 834s，保持主端点仍为 530/560/650/830s。

`/2` 使用自身原默认，唯一共同例外仍是 `quiescence_death_us=10^12`。不加入 `/3` 自动支持度/H 节点回收，也不为匹配结构修改旧版参数。此为**完整版本对照**，其与 `/3` 的差异不能全部归因于边遗忘方式；另将 `/3 legacy-stability` 与 `/2` 比较，以识别新版共同机制是否在本批产生差异。

首次先核对原生库及源代码哈希，再对重复课程前 24s 做独立 Python/Rust 完整状态比较（1e-12/1e-14 容差）及同后端严格恢复。完整主线仍由 Rust release 独立执行；t530 保存/分批/观察一致性及提示不回写父线同原登记。缺失的 `/3` 专有 H 字段标为不适用，不能伪填为零证明保护缺失。Core 不改；原 run-01/run-02/trace-01 不改；共享实验工具的新版本和本批脚本冻结留存。任何失败保留独立目录，不覆盖原结果。

主问题：同输入下 `/3` 默认是否比 `/2` 更快失去原文字边及词色配对边，重复有无改善，提示是否可辨；另看 `/3` 方案 2 是否恢复旧版该项表现、节点回收是否仍有差异。保留“基线未表达，不能叫后来答错”的边界，不把有限结构退化推广为所有能力全面退化。背景停输入后的清理与持续背景留存分别报告。

## English registration

Before run-03, the user explicitly requests a full `/2` comparison and suspects regression. Create separate blank repeat/single subjects with the exact run-02 frozen text sensor, wiring, inputs, telemetry, 57-presentation curriculum, endpoints, original-edge cohorts and copied cue probes. Use `/2` defaults except the same extended quiescence grace; do not transplant `/3` node retention into the old kernel. This is a full-version comparison, with `/3 legacy-stability` retained as an additional comparator. Verify source/native identity and Python/Rust prefix agreement/restoration first. Preserve all prior evidence and freeze the new instrument version. Missing `/3` H fields are inapplicable, not zero. No Core/default changes, no outcome-dependent curriculum adjustment and no inference of global capability regression from this limited mechanism study.
