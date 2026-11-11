# 语言共同发育与连续活动工具

[English](../../en/reference/language-development-tools.md) · [研究计划](../plans/language-development.md)

这些工具位于外设与观察层，未修改 Core。它们既可由 Agent 调用，也可供研究者编写教学脚本。E44 的报告、实验记录和连续译文查看器在对应研究项目中提供。现阶段不是面向日常聊天的成熟语言中枢。

## 从文本编译普通刺激

Python API：`threemind_transformer.development.compile_stream(text, model, StreamInput(...), intensity=1)`。

新协议 `threemind.language-character-stream/1` 逐字符输出因果 Transformer 特征，使用 NFKC；默认64维、按绝对值保留4路、每帧总量1、字符间隔20000微秒。`top_k=0` 为稠密对照。正负特征各用匿名通道；协议、接线种子和输入模型权重都必须固定。旧整句向量及文本协议保留原义。

返回值仍是现有 `Stimulus` 及空标签，可以经 `ReadoutSession.schedule` 或既有匿名刺激 API 递送。Core 不接受词义、物体名称或答案。组合不同感官时，只有明确的共同采样才可合帧；不能根据相同时刻自动混成一次观测。

## 记录与转换一段活动

`TrajectoryBasis(channels, bins=16, residual_buckets=16)` 明确列出已登记通道。每个时间格保留完整活动的峰值；未登记通道仍进入单独的桶并报告计数和身份。原始轨迹不能因投影而丢弃。`activity_changes` 统计上升、再入及总激活变化，本身不判断活动来自外部还是内部。

每行输入是一个过程：`start_us`、`planned_end_us`、`trajectory`；后者逐帧包含 `time_us` 和 `nodes`，节点有 `id`、`channel`、`activation`。

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_transformer.development_cli project --input process.jsonl --basis basis.json --output features.jsonl
& $py -m threemind_transformer.development_cli train --input calibration.jsonl --basis basis.json --output expression.safetensors --device auto --steps 1600
& $py -m threemind_transformer.development_cli decode --input features.jsonl --model expression.safetensors --output words.jsonl --device auto
```

训练每行必须提供 `values` 和外部教师给定的 `text`；空文本是明确的表达终止样本。训练目标不传入 Core。模型从随机权重开始，安全张量文件保存架构、时间格、通道基准及训练信息。`auto` 在 CUDA 可用时使用 GPU，否则用 CPU；显式 `cpu` 可强制不用 GPU。GPU 执行中失败应保留错误后另用 CPU 重试，工具不隐瞒失败。现阶段没有跨设备数值完全相同的承诺。

输出保留原始 UTF-8 解码结果、生成字节、是否终止。乱码和空文本都是真实结果。相邻窗口不传递文字缓存，上一句不会变成下一句的提示，译文不会回灌意识。模型接收完整过程投影；不能因为它说出熟词，就当作确认某个想法。

CLI 拒绝覆盖已有输出，单次输入上限256MiB、16384行；这不是完整的资源调度器。大型实验使用 `lab/tools/service_study.py` 的实例、时长、内存、磁盘和额度预算。E44 完整驱动程序位于 `lab/explorations/2026-10-04-language-development/`，以登记的选择文件约束正式路线与种子。

## 教学装置和解释边界

`lab/tools/language_teaching_world.py` 提供具有重力、四个刚体和五条实际测距/颜色射线的小型 MuJoCo 教学装置。教师改变相机视角；对象名称只用于教师记录。它没有主动躯体控制，不替代完整海洋或机器人行为实验。

应并列保存：原始活动、外界输入、实际传导、文字及无提示/未教学/静默等对照。内部贡献由相同背景下的干预确定；表达可靠性由没进入输出器训练的新经历检验。语言外设能学会描述感官活动，与意识已经通过语言回忆新知识，是分别验收的能力。
