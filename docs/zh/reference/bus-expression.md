# 原始输出总线与表达器校准

2026-10-05，E49。[English](../../en/reference/bus-expression.md)

`threemind_runtime.activity_stream.RawActivityStream`是可订阅的只读输出口。`sample(engine)`读取当前全部节点，经OutputBus复制给各消费者；不推进时间、不只选活跃节点、不注释语义、不压缩、不回写。`publish(frame)`用于同协议重放。采样由调用者显式控制；不同观察频率不是动力学默认。

常规语言`ProcessFeatures`仍保留旧身份：它只提取激活，按哈希桶/时间箱合并，抑制、部分通道身份和箱内先后不能从其最终特征恢复。损失发生在观察器，不能笼统叫总线丢包。旧模型仍按旧协议工作，新表达研究使用原始口，不静默换解释。

命令：

```powershell
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_calibration train --manifest layout.json --input teaching.jsonl --output new-reader.safetensors
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_calibration decode --manifest layout.json --input observations.jsonl --checkpoint new-reader.safetensors --output words.jsonl --device auto
```

清单采用`threemind.raw-state-expression/1`。每行`{"id":"optional","process":{...}}`，训练时另有`text`教学目标；解码输入拒绝该字段。轨迹先走OutputBus，再按声明通道/字段/采样数交给表达器。保留原始幅度，无提示原样输出，不附加当前问题或对话缓存。观测命令输出完整文本/字节与是否结束，不按答案筛选。

小数据默认每轮完整均衡训练，`--sampling random`复现有放回抽样；`--checkpoint`在训练时表示继续已有外设学习，Core不变。可用`--steps`、`--learning-rate`调节。最多64教学样例，CPU回退，默认30分钟/RSS4/GPU3GiB约束。旧`development_model.fit`、旧检查点及内核默认保持。

逐字准确率用于有限四名字标定，不是语言能力定义。模糊表达、片段、针对错误的再次教学均应记录。外设继续训练的改善与重新教意识的改善必须分别报告。

新CLI训练的检查点附匿名通道/字段清单；解码及继续训练拒绝同宽却不同顺序的清单。旧研究检查点依照其原收据指定外部清单，不能猜测通道顺序。此接口不等于所有连接状态的完整快照。实际CPU CLI、标签拒绝、顺序拒绝已验证，见[E49验收](../../../lab/explorations/2026-10-05-bus-expression/verification.json)。
