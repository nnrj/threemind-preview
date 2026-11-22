# 6.3 环形环境人工选择实验

本目录保存本次新实验的方案、执行与分析代码。它不覆盖旧E13，也不属于暂停中的全面复验批次。主实验AS63-01的16个独立群体、5056段过程和布局对照AS63-02的768段过程均已完成并通过原件核验。

主实验观察到了部分亲代与后代的区域倾向一致，但没有同时实现两个相反方向的连续两代保留。定向选择相对随机选择的平均收益为0.042和0.127个百分点；逐代增强及继承状态相对空白内核的收益也未达到预定标准。完整的阴性结果及亲子一致性均予保留，未追加种子、世代或调整判据。

[中文报告](report.zh.md) · [English report](report.en.md) · [布局对照](layout-report.zh.md) · [图表](figures/)

## 两个独立登记的记录

| 记录 | 问题 | 科研API记录标识 |
| --- | --- | --- |
| AS63-01 | 在固定区域环境中，候选本身的倾向能否经人工选择和出生继承保留并增强？ | ef022c6e-a0f6-5bb0-acfa-e9b0629e19bc |
| AS63-02 | 交换区域布局后，实时感知控制与原动作重放有何差异？ | d268901c-e0df-5de0-a809-2775a0ef0065 |

两者归属项目 d0a04159-ee0f-4200-ada9-13d5ce7197b7。原件分别在仓库忽略目录：

- .work/artificial-selection63-20261117
- .work/artificial-selection63-layout-20261117

## 设计与方法

[主方案](protocol.zh.md)规定16个独立群体、三代、两个定向选择条件和随机选择。评估通过候选完整状态副本完成；只有正式子代调用 threemind.birth/2。选择用两个起点，保留测试用另四个起点；各代区域布局不变。每代全部候选参与比较，不只统计优胜者。384个不继承内核状态的匹配对照用于检验持久状态继承的作用。

[布局方案](layout-protocol.zh.md)使用全部192个第2代候选，在两个起点分别比较交换布局后的实时控制与旧动作重放。它单独登记，不改变主实验的样本和判据。

[工程补充](continuation-protocol.zh.md)将主实验的原件、归档、读回预留各由3GiB增为4GiB，保留六小时计算及其余系统限制。一次声明的完整步骤边界暂停用于切换存储预算；[续接工具](resume_tools.py)以完整状态承接未完成阶段，保留所有已发生输入和活动。原始study.py、科学协议、冻结清单和暂停原件均保留，执行器差异见[核对文件](continuation-runner.diff)。

## 可复核代码

- ring.py：固定区域闭环装置与完整状态保存。
- study.py：最初冻结的主执行器；continuation_study.py：追加工程执行器。
- apparatus.py、resume_tools.py：独立装置和完整续接检查。
- layout.py：另行登记的布局控制及装置检查。
- analyze.py、analyze_layout.py：原件审计与预定统计。
- verify_statistics.py：从群体汇总直接用二项组合数复算精确符号检验和Holm校正。
- figures.py、design_figure.py：从审计后的结果及固定设计生成中英文PNG、可编辑SVG和PDF图表。
- tables.py：生成小型汇总、全部预定比较和运动描述表。
- describe_layout_symmetry.py：复核对称起点的事后描述，未增设成功判据。
- deliver.py：原件清单、完整归档、科研API下载读回及记录结项。

运行环境为项目的 .work/kernel-venv/Scripts/python.exe。不要对正在运行的目录重复启动执行器。完整分析命令为：

    .work\kernel-venv\Scripts\python.exe lab/explorations/2026-11-17-artificial-selection63/analyze.py
    .work\kernel-venv\Scripts\python.exe lab/explorations/2026-11-17-artificial-selection63/analyze_layout.py
    .work\kernel-venv\Scripts\python.exe lab/explorations/2026-11-17-artificial-selection63/figures.py

原始节点、输入、轨迹和状态仅保存在忽略目录及对应科研资源中，不进入Git。这里的检查由同一助手执行，属于内部复核，不能冒称独立团队复现。


## 2026-11-18 交付完成

布局对照AS63-02的768段过程也已完成。实时控制相对旧动作重放的目标区域停留比例差，两个选择方向分别为-23.216、+23.297个百分点；预定双向目标未达到。具体方向、区间及判据见独立报告，布局结果不改变主实验评分。

两批原包分别有26616和3954个成员，经本地科研API完整下载后逐成员校验；双语报告读回一致，两条记录均已结项，pending=0。此次没有改动生产内核、旧实验、当前论文或其他暂停批次。

[完整统计表](tables.zh.md) · [群体汇总](population-summary.csv) · [主实验回执](delivery.json) · [布局对照回执](layout-delivery.json)

六组图均提供中文和英文版本，包含PNG、可编辑SVG和PDF，共36个图文件。
