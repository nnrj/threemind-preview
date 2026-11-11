# 活动过程与可复用检测工具

[English](../en/v2-observation-tools.md)

本期改的是观察工具，未修改内核动力学。原有活动稳态判定、活动过程分析 V1 和历史结果保留；新建配置默认 V2，采样间隔 20,000 微秒。省略版本仍解释为 V1，旧意识不会自动升级。

## 页面

进入意识的**时序与截面读出**：

- **无刺激观察**：打开观察窗口，不发送刺激。运行中处理命令后开始；暂停时在继续运行后开始。需要启用 V2；原有研究计划和生态实验的控制边界仍适用。
- **过程摘要**：直接显示活动、增强、减弱、消退及再次激活节点数，与收敛结果分开。聊天中的时序消息也显示摘要。
- **过程检测工具 → 展开过程分析**：查看曲线及节点变化。V1 保存了完整向量的旧记录也可重新分析，不覆盖原记录。曲线和节点分页面读取，明确显示范围。
- **对照另一条完整轨迹**：填写证据编号，可指定同项目另一意识。适用于同源副本或身份对应的节点。可按绝对模拟时间或各自首样本对齐。缺失时刻不补零，无交集不算相同。
- 原来的收敛排名、窗末激活、峰值、CSV、完整 JSON、轨迹图保留。新增增强、减弱、变化量及首次激活次序排序，不删除其他节点。

V2 保存整个有界窗口，默认 12 模拟秒；首次收敛或响应消退不提前关窗。死亡、运行停止、预算不足仍会结束观察并明确标识。新默认将最大周期样本数设为 60，配合 20 ms 采样保留 1.2 秒的周期搜索范围。

## 指标与边界

| 指标 | 含义 |
|---|---|
| 原始活动 | 完整正激活向量，其余分量为零；不只记录前几名，不依赖词语模板。 |
| 增强／减弱 | 相对刺激前实测均值的正、负差。减弱本身不证明抑制因果。基线缺失、部分覆盖或零参考会提示。 |
| 峰值与时刻 | 每节点自己的峰值、首次／最后活动。不同时间的峰值不拼成虚假同时状态；另存整体增强最大那个实际采样时刻的值。 |
| 持续及积分 | 采样间左值保持估计，区分递送期间及之后；不外推最后样本之后。无刺激观察没有递送边界，这两项为不可用，不杜撰输入阶段。 |
| 再次激活 | 降至报告容差以内后再次升高；首样本已活动只表示观察到一段，不宣称在那里真正开始。 |
| 累计变化 | 相邻采样激活变化绝对值之和。终态一样仍可有不同过程。 |
| 分布转移 | 相邻非零完整向量归一化后的总变差距离；总激活不变、活动转移到另一批节点仍可检测。 |
| 轨迹比较 | 对共同采样时刻的对应节点做有符号差分，记录最大差异、首次／最后差异及时刻。 |

报告容差 `process_epsilon` 默认 `1e-12`，只影响标识和计数，不裁剪原始数据或改变内核门槛。分类及收敛时刻排名保持原义，`process` 是独立证据。活动、答对任务、意识是不同命题。

采样不是连续观测，未采到的变化不能事后补造。窗口结束不表示之后没有活动。应结合覆盖范围、最大采样间隔、触发诊断与预算原因解释；`process.coverage_complete` 仅说明请求的有限过程是否按间隔完整采样。

## 复用与编排

采用 **Python 库＋固定工具目录＋声明式批处理**。现有研究计划仍负责刺激、等待、快照及实验控制，操作目录向 CLI/MCP 提供同一 REST 能力。不另建平行实验系统，不在计划里执行任意插件代码。

```python
from threemind_runtime.observation_tools import analyze_record, compare_records
from threemind_runtime.observation_probe import probe_copy, ProbeBudget
analysis = analyze_record(record)
comparison = compare_records(cued_record, uncued_record, relative=True)
control = probe_copy(source, duration_us=5_000_000)  # source: StateImage
probe = probe_copy(source, duration_us=5_000_000, frames=frames)
blocked = probe_copy(source, duration_us=5_000_000, frames=frames,
    interventions=[{"action": "silence", "edges": selected_edges}])
restored = probe_copy(source, duration_us=5_000_000, frames=frames,
    interventions=[{"action": "silence", "edges": selected_edges},
                   {"action": "unsilence", "edges": selected_edges}])
```

副本探针不改原状态及参数，复用原感官帧，记录原状态、干预前后和最终状态哈希。默认限 60 模拟秒、120 墙钟秒、64 MiB 证据、4 GiB 进程内存；超限抛出 `ProbeLimit`，不是阴性结果。保留 Core 在途事件，但不恢复外界设备及世界状态，闭环仍用 World/Ecology Runtime。删除节点或清除活动不是天然可逆，恢复须逐项验证。

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.observation_cli list
& $py -m threemind_runtime.observation_cli process --input old-window.json --output process.jsonl
& $py -m threemind_runtime.observation_cli compare --input cue.json --right no-cue.json --relative --output comparison.jsonl
& $py -m threemind_runtime.cli --model model.tmind --clock unbounded --until-us 12000000 --readouts new-observation.jsonl --observe
```

新安装入口叫 `threemind-observation`，已有 `threemind-observe` 仍用于生态观察。`--until-us` 是绝对模拟截止时间，须大于已恢复模型时间。`--observe` 不撤回在途事件，未使用时保持 CLI 原默认；恢复上下文也不强制升级。

离线输入支持 JSON、JSONL、gzip；多条记录通过 `--window`、`--right-window` 选择。只写新输出。单输入解压上限 64 MiB，离线每条轨迹上限 200 万激活值，输出上限 256 MiB。

批处理计划示例：

```json
{"schema":"threemind.observation-batch/1","steps":[
  {"tool":"process","inputs":{"record":{"path":"cue.json"}}},
  {"tool":"compare","inputs":{"left":{"path":"cue.json"},"right":{"path":"no-cue.json"}},"options":{"relative":true}}
]}
```

运行 `python -m threemind_runtime.observation_cli batch --input plan.json --output results.jsonl`。相对路径基于计划目录，最多 32 步；失败保留已完成步骤。新工具通过代码注册及测试加入。

在线操作名为 `observation.process`、`observation.compare`；无刺激观察使用 `consciousness.command` 的 `readout_observe`。迁移 054 添加 V2 worker 能力约束，升级沿用现有迁移和重启流程。

环境选择、匹配对照边、跨种子节点对齐及群体统计仍含实验假设，本期没有把单轮规则升格为通用正确答案。

[校准报告](../../lab/validations/2026-09-30-process-readouts/report.zh.md)

## 2026-10-02：目标响应与局部收敛

在“过程检测工具”中输入节点 ID，点击“分析目标响应”。不必等待全局收敛，也无需重新运行意识。展开局部判定参数可调稳定窗口、分布距离、幅度变化及归一化下限；结果显示原全局分类、过程峰值／积分、窗末值、首次局部模式收敛、首次局部稳态和当前尾段状态。曲线分页，JSON 导出包含完整派生分析、参数与源记录哈希。

`threemind.target-observation/1` 不替换旧算法。默认连续 800 ms、分布距离 ≤0.08；模式稳定而幅度衰减时不称稳态，稳态另要求相对总幅度跨度 ≤0.12。无活动不构成稳定响应；缺口不连接成完整观察。默认下限 1e-8 仅限制比例归一化，不裁剪峰值与积分。目标只限定这项派生分析，全部原始活动仍可查看。没有局部收敛也可能有明确短暂响应。

Python：`analyze_targets(record, node_ids=[1, 2])`，从 `threemind_runtime.observation_tools` 导入。

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_runtime.observation_cli target --input readout.json --node-ids 1 2 --settle-us 800000 --output target.jsonl
```

批处理用 `tool: "target"`、`inputs.record`、`options.node_ids`。在线操作名 `observation.target`，GET `.../readouts/{record_id}/target?node_ids=1,2`；`download=true` 导出全部，沿用项目访问权限。未知节点报错，不伪装成无响应。目标及参数在确认性检验前固定；事后选择必须标注探索。源数据不足或删失仍原样报告。[E24 设计](plans/target-response-background-20261002.md)

2026-10-02 验收：工具复核了旧 E23 的 80 个实际窗口，其中 16 个全局未定窗口有目标活动，但 A/B 均未满足 800 ms 局部稳定。E24 三背景实验也保留了相同的短暂目标响应而出现不同的全局分类。工具没有把它们改称收敛。页面的目标曲线使用实际记录的时间范围；原始记录与完整 JSON 可独立核查。[结果与操作说明](../../lab/explorations/2026-10-02-target-background/README.md)
