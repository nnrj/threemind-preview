# E56成功流程与E63当前流程：实际改变了什么

2026-10-08，查阅实际源码与原报告；本表是实现差别，不是已完成的逐因素因果结论。

| 方面 | E56四视场24/24的方案 | E63初始／普通纠错方案 | 本轮处理 |
| --- | --- | --- | --- |
| 问什么 | “请指出红色的球体”等，问句含所求属性名称 | “这是什么形状／颜色”，需回答属性名称 | 任务不同；不把成绩落差全归视觉 |
| 答什么 | 四个位置之一，再由伺服执行至所选位置 | 八个词之一，固定眼手以分离认识与动作 | 先把中央认识做好，再回到主动寻找和动作 |
| 视觉组织 | 四个预设物理视场，各4×4，共享同一读取函数 | 一只整幅眼，68个受体，中央清晰、外围稀疏；共享局部读取 | 当前不恢复人为预先分物；必要E64另组恢复历史方法 |
| 核心与来源 | continuous-memory/2，Core seed223 | 同核心版本，空白Core seed631 | 未直接继承旧模型；独立来源，不视为严格单因素比较 |
| 教学 | 104课、180模拟秒；教师指示物体、语句、先密后疏复习 | 104课、390模拟秒；一个居中物体，陈述后提问；另追加普通纠错 | 背景、重复、普通强度保留；教学时长和场景关系不同 |
| 外设校准 | 从来源快照副本采48＋12次真实请求；固定语料离线1200步 | 在每次示范后提问的后半段在线学习，个人缓存/Adam持续 | 用户授权后另分支采集真实无答案提问，集中继续校准自己的原外设 |
| 时间读取 | 在整段请求内均匀取8帧 | 问答末16帧、0.8秒 | 新分支在整段2秒内均匀取16帧；全部为原始数值 |
| 外设及学习状态 | 共享SpatialChoice；离线训练使用训练损失最低权重，阶段间组装 | 个人8词Transformer；原权重、Adam、缓存、RNG一直延续，取末态 | 当前不为了仿旧而重新初始化个人外设；E64精确复现另记 |
| 确认题变化 | 新布局和视角；形色组合种类在校准材料中已有 | 圆柱、立方体、圆锥的彩色组合未用于教学/校准 | 分别报告基础题与未见组合，不能把“新布局”当同等组合迁移 |
| 测试时间历史 | 每题从同一来源快照独立复制 | 32题顺序连续，保留答题过程的Core变化 | 当前问答流程保持；E64沿历史独立副本测试 |
| 对回答来源的结论 | 整体24/24成立；无Core结构学习另校准也24/24，固定头连接静默19、恢复24 | 本轮实际结果另列；无可靠表现前不扩展大量消融 | 不把系统可用与Core独占识别混为一件事 |

最直接可以应用的是：让外设校准看到**实际会遇到的无答案问题活动**，并保留问题经历的时间过程。其余差别不能在一次校准里偷偷全部修改。若集中校准和整段读取一起改善，只能先确认这套组合流程有效；需要分开估计各自作用时，使用固定活动的交叉读法或后续配平实验。

## English

E56 asked the system to locate a *named* attribute/conjunction among four objects; E63 asks it to name a single object's shape/color. E56's confirmation changes layouts/views of calibrated conjunction types; E63 tests previously untrained colored-cylinder/cube/cone combinations. E56 used four fixed fields, whole-question sampling, offline48+12-example fitting and independent test copies. E63 starts a different blank seed, has a whole eye, longer teaching, an online personal eight-word head, a trailing0.8-second window and sequential tests. These are multiple real differences, not evidence that vision alone caused the gap.

The approved current branch applies answer-free question calibration and whole-question sampling while preserving the same peripheral's weights/Adam and the reference organism. Any joint improvement validates that procedure under its tested conditions, not unique causation of every ingredient. Exact E56 blank reproduction remains a separate conditional experiment.

[E56报告](../2026-10-06-vision-correction/report.zh.md) · [E56源码](../2026-10-06-vision-correction/experiment.py) · [共享读取原实现](../2026-10-06-vision-correction/shared.py) · [当前校准登记](question-calibration-preregistration.md)
