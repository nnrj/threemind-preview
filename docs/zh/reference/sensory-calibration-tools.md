# 感官校准与双向联想研究工具

[English](../../en/reference/sensory-calibration-tools.md) · [E45登记](../../../lab/explorations/2026-10-05-language-calibration/design.zh.md)

2026-10-05。本工具仅用于外部研究，未改变Core或原感官协议。

`lab.tools.sensory_calibration`提供三类可复用能力：

- `matched_frames`：明确的剂量、重复、同时递送或逆序干预。保持每路合法幅度和独立intensity，不用提高强度来偷偷引入强刺激巩固。同刻多帧与单帧合并不同。
- `paired_visual`：在适配器声明的共同观测内分配固定视觉总量。不同来源的背景仍分开递送。
- `process_vector`、`SensoryResponseLibrary`：按实际时间积分保留短暂活动；与独立物理采样/响应模板比较。输入只有匿名通道活动和冻结模板，没有问题、答案或当前教学对应。等分、静默和零活动可返回“无可区分领先项”。完整轨迹仍须保留。

研究人员和Agent可使用同一Python接口，或对JSONL过程离线读出：

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.sensory_calibration --library library.json --input processes.jsonl --output observations.jsonl
```

输出只能表示“与某物理响应样式相近”，不能由五射线输入重建完整主观图像。该分析是附加研究读出，不覆盖旧判据。

数值约定：`process_vector` 计算梯形积分后除以观察窗长，即活动的时间加权平均值；不会把更多采样点误算为更强活动。同长度窗口的积分与平均值仅差常数。E45 的两秒主指标及固定短窗分别保留，不能事后把表现较好的短窗改作原主指标。

`lab.tools.oscillator_sensor.OscillatorSensor`提供明确的模拟质量—弹簧振动及固定频带测量，保存质量、弹性系数、阻尼、波形、采样率和频谱。它不是完整声场或生物耳蜗。物体语义和音名不进入Core。

E45的`experiment.py`提供prepare/sensory/select-input/parameters/select-parameters/formal/summary命令；每次研究有独立目录、项目、预算和完整配置。`visual_reader.py`校准实际感官响应；`expression.py`训练分感官语言观察头；`composition.py`提供分段教学；`interventions.py`和`continuous.py`记录干预与无新教学过程。这些脚本是冻结实验方案，不是可随意覆盖已有项目的通用新建命令。新时序头尚未接入日常聊天默认设备。
