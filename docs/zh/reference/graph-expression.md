# 局部活动表达器

[English](../../en/reference/graph-expression.md) · [E50 登记](../../../lab/explorations/2026-10-05-graph-expression/design.zh.md)

此工具位于 `threemind_transformer` 外设包，不改变意识、Core 参数或输入映射。旧固定布局的表达器和 `graph-expression/1` 均保留。新 `/2` 使用从零训练的注意力解码器，把匿名节点在一段时间中的实测活动译成字节序列；没有预训练词义，也没有跨窗口对话缓存。

## 默认读什么

默认 `local` 读取一个完整原始观察窗口，再保留参与该窗口活动的节点：有非零激活／触达流，或观察到抑制上升。对这些节点保留激活、抑制、直接触达、联想触达、新生抑制、待分配抑制六个实测字段，以及真实采样时间。弱活动不会因排名低而丢弃，节点活动结束后的零值仍保留。默认取 17 个已有采样点，不插值捏造节点。

它不读取全部休眠连接，不提供对象名称、教学答案、外部任务身份；不减去无提示副本，不按每道题归一化。纯静默结构及没有其他参与、只是单调衰减的抑制不进主表达，但仍在原始证据中。默认不读连接；研究者可用明确的 `graph` 输入比较实际边及历史状态，不能把这个离线诊断称作默认输出路径。

匿名通道使用原始 32 位身份；局部节点编号只用于连接索引。网络可出现新节点，输入节点排列不承载词义。`/2` 内部用固定可逆的有符号 `log1p` 表示测量值，避免累计次数淹没微小活动；原始协议、保存值和 Core 输出不变。这是外设神经网络的数值表征，不是重新定义刺激或把回答拉向预期。

## Python 和命令行

```python
from threemind_transformer.local_activity import local_process, FIELDS
from threemind_transformer.graph_expression import GraphExpressionConfig, fit, load

config = GraphExpressionConfig(node_fields=FIELDS, use_edges=False)
# raw 是 RawActivityStream 取得的 start_us/end_us/trajectory 观察窗口。
prepared = local_process(raw)
model, manifest = load("expression.safetensors", "cpu")
print(model.decode([prepared]))
```

PowerShell（在项目环境中）：

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_transformer.graph_expression_cli config
& $py -m threemind_transformer.graph_expression_cli prepare --input raw.jsonl --output local.jsonl
& $py -m threemind_transformer.graph_expression_cli train --input teaching.jsonl --output expression.safetensors
& $py -m threemind_transformer.graph_expression_cli decode --input probes.jsonl --checkpoint expression.safetensors --output words.jsonl
```

每行使用 `{"id":"可选的外部收据","process":{...}}`；训练可另带 `text`，推理不接受教学标签。`id` 仅在结果中回传，不进入神经网络。默认 `--view local` 接收原始窗口；`prepare` 导出准备后的局部协议，读这份文件时使用 `--view prepared-local`。显式 `--view graph` 才读取完整图协议。三种视图都必须与检查点字段一致；不会把旧检查点悄悄升级。

继续训练使用 `train --checkpoint 旧文件 --output 新文件`，保持配置一致并新建检查点；已有文件不覆盖。`--device auto` 在 CUDA 不可用时回退 CPU，也可明确 `--device cpu`。训练标签只用于外设监督；不能由此推断 Core 已学到标签的含义，需要反向教学、相同感官输入不同经历、选择性屏蔽及恢复／移植等实验支持。

## 边界与限制

- 单次输入 256 MiB、训练 128 条、解码 512 条；每条默认最多 32 帧、每帧 512 节点，超限明确报错。可配置的上限仍受包内硬限制；不会静默截取前若干节点。
- 默认 4000 步、单次 1 小时，可显式调至最多 4 小时；进程 4 GiB、CUDA 张量 3 GiB，保留至少 2 GiB 可用内存。训练只按训练准确数与损失选检查点，不以测试题选模型。
- 当前模型常用输出是有限教学词汇。没有提示时输出的词，不自动叫“内心独白”；没有人为标签可以确定它的意义。训练集拟合好也不保证新经历或长时继续活动后翻译正确。
- `RawActivityStream`／图观察与实际发出的传输信号不同。总线负责复制分发；主表达读取的是局部活动观察，尚未证明只读实际传输事件同样有效。[总线核查](../../../lab/explorations/2026-10-05-graph-expression/bus-audit.zh.md)
- 本期提供 Python／JSONL 命令和可在项目文档及报告页阅读的证据；没有把新模型未经验收地替换生产聊天默认表达器。
