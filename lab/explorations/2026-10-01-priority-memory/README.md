# 优先验证批次的执行入口

**登记三批已完成，2,808 个新实例，完整输入和状态核验通过。** [中文报告](report.zh.md) · [English report](report.en.md) · [交付与平台入口](delivery.zh.md) · [Delivery](delivery.en.md)。完整科学结果及阴性条件在报告中；后续研究留在待办，未混称为本批已完成。

设计见 [中文](design.zh.md)、[English](design.en.md)。背景反向与顺序扩展各有独立的事前登记文件。此目录是一个已登记研究批次，默认使用原工作目录恢复，**不覆盖已完成案例，不重建旧数据库**。

在项目根目录，使用既有隔离 Python 环境和本地 `.env`：

```powershell
$env:PYTHONUTF8 = '1'
$py = '.work/kernel-venv/Scripts/python.exe'
$study = 'lab/explorations/2026-10-01-priority-memory'
& $py "$study/runner.py" status
& $py "$study/runner.py" matrix
& $py "$study/runner.py" profiles
& $py "$study/runner.py" interference
& $py "$study/reversal.py" --sham-only
& $py "$study/reversal.py"
& $py "$study/sequence.py"
```

顺序执行，单 worker；`--block` 可限定已登记材料块。`prepare` 仅首次初始化，已登记后再次调用会拒绝。运行时会检查额度记录是否在 30 分钟内更新；必须由实际账户查询填写 `.work/priority-memory-20261001/usage.json`，不得猜测。任一失败副本保留，不能通过覆盖原 key 重做。

完成后：

```powershell
& $py "$study/analyze.py" --name analysis-final
& $py "$study/interpret.py"
& $py "$study/analyze_reversal.py" --name reversal-final
& $py "$study/analyze_sequence.py" --name sequence-final
& $py "$study/tables.py"
& $py "$study/audit.py"
& $py "$study/figures.py"
# 中英文报告与图表核对后，再运行发布：
& $py "$study/publish.py"
```

分析输出也不覆盖已存在文件；阶段查看使用不同的 `--name`。审计通过后写入 STOP，阻止继续模拟；发布只使用既有证据。资源中止的部分交付必须在审计时明确 `--partial-reason`，不能冒称完整批次完成。

顺序分析可用 `--block 100121 --name sequence-first-block` 检查已经完整完成的单个材料块；输出明确列出材料块，最终表格导出要求全部四块和完整案例数，不能拿局部结果冒充全批结果。

可复用设施：`lab/tools/service_study.py` 提供受预算约束的实例、公开输入总线、状态分叉、检查点和证据；`lab/tools/study_input_audit.py` 为自带完整定义的匿名帧和刺激体提供逐载荷／逐帧核查，保留原始字节与 JSONB 导出的差异，拒绝把其他感官按默认配置解码；`lab/tools/study_publication.py` 提供笔记、记录、报告和证据归档。本批归档包含少量明确列出的旧父本与物理重放材料，不包含旧数据库。实验脚本不直接改写 Core 内部状态。来源、观察与公开研究干预均单独留证。

The commands operate on this registered study, resume completed cases without overwriting them, and stop after audit. For a new independent study, register a new StudyConfig identity and work directory rather than editing this study's frozen protocol. The shared tools expose the same Runtime and Lab operations available to the application; original carriers, delivered stimuli, model states and observer results remain distinct evidence.
