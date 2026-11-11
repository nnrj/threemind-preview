# 活动对照与带时间戳的语言读出

[English](../../en/reference/expression-observation-tools.md) · [E47设计](../plans/expression-alignment.md)

研究工具 `lab.tools.expression_observation` 在外部读取已记录的过程，不持有Core对象、不写入内核。与E46原工具并存，旧清单仍按旧协议执行。

## 时间与解读

`threemind.timed-expression/1` 分别保存窗口ID、模拟采样起止、进入队列、开始解码、完成解码、整批解码耗时。后三项是宿主机时间，前两项是模型时间；不可相减假造模型延迟。画面显示时应按原采样窗口关联输出，晚显示不意味着晚期仍有对应激活。

`threemind.expression-observation/1` 支持绝对活动、同状态无提示副本差值、真实前窗均值差值；可同时纳入激活和抑制。负变化保留，数值地板1e-8；直接输入通道排除由清单明确声明，原始证据不会因此裁剪。两个字段用外部特征列排列，不生成新受体、不改映射。

**同状态无提示副本是研究工具，不是普通部署感官。** 它要求从相同快照、相同背景时间线运行一份无提示对照。前窗模式只需要已经发生的观察，但并不保证有同等分辨率。显示差值、解码结果和原始活动应分别标注。

## 命令

在项目根目录，以已安装ThreeMind的Python执行：

```powershell
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_observation project --manifest manifest.json --input processes.jsonl --output features.jsonl
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_observation decode --manifest manifest.json --input processes.jsonl --output words.jsonl --device auto
```

输入每行为`id`、`process`和模式需要的`baseline`；过程必须含`start_us/end_us/planned_end_us/trajectory`，节点含`channel/activation`，联合模式还必须有`inhibition`。同状态基线须完全同一采样区间；前窗不能包含未来。单文件至多256MiB、16384行。输出以新文件方式建立，拒绝覆盖。

清单含`observation`（projection/mode/fields/schema），解码另含相对清单位置的`checkpoint`与训练专用`feature_calibration`。新实验的模型清单可直接使用；只读投影不需要模型。`auto`/`cuda`在CUDA不可用时回到CPU，输出记录实际设备。原始生成token、错误文字、空文本均保留；此工具不把文字变成内核的发言命令。

E47采用从零的小Transformer以及有限词表相似度工具作对照；后者的候选短语和相似度不等于通用自然语言能力。模型权重、观察清单、校准来源和绑定个体应一起保存，不能只拷贝权重后误用另一个意识的内部表示。

## 连接控制与适用限制（2026-10-05）

`lab.tools.connection_controls.cross_domain_masks(image, left, right)`接收导出的状态字典和两个不重叠的通道集合，返回跨集合连接及等数量其他连接掩码。只构造研究干预配置，不持有/更改Core。控制按权重就近选择，返回逐边误差、总权重及`topology_matched: false`；数量不足时返回`None`，不能把“就近”包装为已经配平。真正执行必须使用显式研究副本的现有静默接口。

E47实际控制权重仅为目标的66.3%～72.7%，应随结果一起解释。工具不承诺目标连接是语义脑区，也不把通路静默等同于高级推理消融。

**同状态差值会移除提示与无提示共有的活动；归一化还会去掉总幅度。** 全部通道差值不是完整原始状态。尤其不能把同一无提示活动减去自身，再以0判定没有独白或自主活动。E47新头训练了无提示→空白，定位为提示响应工具；自然独白仍应使用未经这种相减的连续证据和独立验证。[E47报告](../../../lab/explorations/2026-10-05-expression-alignment/report.zh.md)
