# 内部模式语言读出工具

[English](../../en/reference/native-expression-tools.md) · [E46](../plans/native-expression.md) · [中枢适配器](central-adapters.md)

本工具位于Core之外，输入是已有观测接口的匿名时间轨迹。与物理感官模板比较是另一种工具；这里允许学习个体实际形成的分布式模式。

- `threemind_transformer.native_readout.NativeProjection`：版本化的通道排除、16段过程特征、量值下限、未知通道报告。默认不读问题/答案等元数据，不回写状态。
- `PrototypeLanguage`：样本的余弦注意力与有限短语，支持未知/等分/静默；其概率是未校准的相似度，不是语义真值概率。
- `lab.tools.native_expression.FeatureCalibration`：只在训练集拟合均值/尺度，冻结后用于测试；不读取测试答案或统计。对训练/测试标记作显式检查。
- 既有`TemporalLanguage`：从零字节生成Transformer，接收时间过程，不把类别编号当成提示。模型清单包含特征、训练来源、个体绑定、共享范围和权重文件；权重使用同目录相对路径，便于一同归档。

## 等价操作入口

Python可以直接调用上述类；CLI处理JSONL，不覆盖输出文件。

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout project --config projection.json --input processes.jsonl --output features.jsonl
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout fit --config attention-settings.json --input training.jsonl --output prototypes.json
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout decode --config prototypes.json --input features.jsonl --output words.jsonl
& .work/kernel-venv/Scripts/python.exe -m lab.tools.native_expression --manifest expression.json --input processes.jsonl --output translated.jsonl --device auto
```

`attention-settings.json`可为`{}`。训练行至少包含`split: "train"`、二维`values`和`text`；拟合入口拒绝测试行。`processes.jsonl`每行包含`start_us/end_us/planned_end_us/trajectory`，轨迹节点至少有`channel/activation`。可以用`{"process": ...}`包装；模型不会获取包装内其他字段。配置由`NativeProjection.to_dict()`生成，表达清单由E46训练器保存。CPU始终可用；`auto`或请求CUDA但CUDA不可用时选CPU，并在结果中记录设备。不调用远程供应商。

这里返回的是**内部活动的被动语言释读**。将其显示为消息不证明意识主动选择发言。原始轨迹、原始文字、未知项与错误必须一同保留；不调用另一个语言模型润色成看似合理的独白。

E46脚本提供prepare、旧数据重评、sources、表达train/initial、continuations和new-experience阶段。它们使用固定登记及独立项目，不是用来覆写既有实验的脚本。研究平台内用报告/证据查看输出；本批未把试验性新语言头替换成日常聊天默认设备。
