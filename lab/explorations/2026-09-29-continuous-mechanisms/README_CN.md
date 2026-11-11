# 连续版机制归因实验

[通俗结论和完整报告](report.zh.md) · [English](README.md)

2026-09-29，341 个实例。重点是解释短时突触资源、快痕迹、局部上下文分别在先前的顺序相关现象中起了什么作用。核心结论：短时资源与既有抑制、逐边门槛及学习后的权重共同形成偏向；快痕迹贡献很小，上下文在本任务没有贡献；门槛 ±10% 会破坏对应。全部旧结果保留，内核和默认配置未改。

项目 `e769cd2d-c636-41b0-a266-6af1cca4b805`。设计、补充方案、结果笔记、九份实验记录和中英文报告通过 Lab 服务入库。原始证据和父本状态可在报告附件下载。

## 编排入口

以下命令从项目根目录执行，使用 `.work/kernel-venv/Scripts/python.exe`。需要本地配置好的 ThreeMind PostgreSQL；不需要启动前端、API、GPU 或云模型。

```powershell
$studyRunner = 'lab/explorations/2026-09-29-continuous-mechanisms/run.py'
& .work/kernel-venv/Scripts/python.exe $studyRunner prepare
& .work/kernel-venv/Scripts/python.exe $studyRunner validate
foreach ($bits in @('111','110','101','100','011','010','001','000')) {
    & .work/kernel-venv/Scripts/python.exe $studyRunner factorial --bits $bits
    if ($LASTEXITCODE -ne 0) { break }
}
& .work/kernel-venv/Scripts/python.exe $studyRunner test-switch
& .work/kernel-venv/Scripts/python.exe $studyRunner baseline
& .work/kernel-venv/Scripts/python.exe $studyRunner background
```

这是已完成研究的复现说明，**不要再次 prepare 覆盖原项目**；它会拒绝重复建立。继续已有未完成的阶段可重用上述分组命令，已完成实例按哈希读取，不覆盖。全新独立复现应复制此编排目录，显式配置新的 WORK、项目和预算；先写新方案。exact validation 需要本地上一轮块 0 的证据作为参考，没有该资料时应明确建立新的复现基线，不删除校验来冒充通过。

`diagnose.py preregister` / `diagnose.py run` 是在第一阶段结果之后登记并执行的固定六组诊断。`analyze.py` 输出 `analysis-v2.json`；旧分析保留，v2 将死亡导致 B 未递送的对照正确标为不可用。`mechanistic.py` 从已有状态复算门槛分支、绘图，不执行新的训练。`audit.py` 核对 341 个实例及父本，`publish.py` 校验并发布证据包和报告。

所有结果写 `.work/continuous-mechanisms-20260929/` 和此新项目；不扫描旧 data。`common.py` 从上一轮编排复制，隔离了目录和预算。测试用 `reconfigure` 的变更记录在副本中，不回写父本。`Observer` 只收集公开事件，10 毫秒全节点轨迹不反馈模型。

## 证据结构

- `freeze.json`、`frozen-sources/`：实验前方案和执行源码摘要。
- `validation.json`：原训练状态/原读出精确复现，观察方式不改变状态。
- `factorial-*.json`、`test-switch.json`、`background.json`、`baseline.json`、`diagnostic.json`：全部条件，无择优隐藏。
- `cases/*/result.json`：实例 ID、状态摘要、配置、读出和指标。
- `trajectory.jsonl.gz`、`transmissions.jsonl.gz`：全节点轨迹和完整公开事件。
- `parent-state.json.gz`、`snapshots.json`、`states.jsonl.gz`：训练父本、关键状态、诊断全状态。
- `analysis-v2.json`、`mechanistic.json`、`audit.json`、`trajectory-parity.json`：分析、公式复算、审计、上下文开关逐轨迹一致性。

资源上限和口径见 [design.md](design.md)；实际最终用量见 [delivery.zh.md](delivery.zh.md)。附件的 `archive-manifest.json` 逐项列出 SHA-256，上传前重新读取校验。最终交付记录在发布之后生成，因此单独保留，不声称它包含在先生成的证据包中。
