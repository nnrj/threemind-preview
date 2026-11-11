# E47交付与复现

2026-10-05。[报告](report.zh.md) · [English](delivery.en.md)

平台项目：**E47 表达延迟与新经历**，ID `4e645e2b-1408-4e6b-a651-a8e12acf765c`。实验设计、阶段发现、最终中英文报告和完整证据通过ThreeMind服务存入独立项目；在“实验笔记”“记录与报告”中选择该项目。文档菜单也可按路径打开报告。准确的发布标识以本目录`delivery.json`为准，资源增量以`publication-resources.json`为准。

## 直接查看

- [逐题与时间查看页](../../../.work/expression-alignment-20261005/expression-alignment.html)：切换个体、经历、观察范围、表达训练和方向，保留错误词、空白、采样区间。附正常/目标静默/其他连接静默对照。
- [主要图表](findings.png)、[原始单位的活动过程图](process-patterns.png)、[结果JSON](results.json)、[事后熟悉答案统计](interpretation-checks.json)。
- [通用工具与CLI](../../../docs/zh/reference/expression-observation-tools.md)。CPU可运行，CUDA不可用自动回退；不要求Docker。

查看页1440及390像素的选项、表格、时间显示、溢出和脚本错误检查均通过；截图在工作目录`viewer-qa/`。图表已经目视检查。既有生产页面未改，不以这个离线页面的验收冒充生产聊天集成。

## 证据和运行顺序

工作证据：`.work/expression-alignment-20261005`，包含1458项来源/探针、原始过程、模型及观察清单、物理遥测录制带、计时、校准、干预和平台收据。旧E46依赖由`dependencies.json`指向原项目/原归档，未复制整包旧数据；E47用到的冻结输入权重和背景副本单独保存。已有状态没有被继续训练或改写。

实验脚本以项目Python执行，本批已完成，**不要在同一输出目录盲目重跑**。输出采用新文件语义，恢复时读取已经完成的项目；重新复现应先选新的研究ID/工作目录并固定旧依赖。

1. `experiment.py prepare`登记，`calibration`补充B探针；`latency.py`测试实际窗口处理方式。
2. `features.py`比较B读法；`new_experience.py`创建C来源及探针。
3. `expression.py features/train`，再以`--scope all`执行同操作；原映射、训练/测试边界和24个模型清单均保存。
4. `mediation.py`运行已登记的60个命名干预副本。
5. `results.py`生成数值、图表和查看页；`diagnostics.py`描述熟悉答案复用；`viewer-check.mjs`验证查看页。
6. `publish.py`经服务发布报告、记录、笔记、附件及单次归档；检查本项目文档哈希，不重新全量核验所有历史数据。

存储预算工作证据6GiB停止扩展、工作＋归档＋数据库10GiB硬上限；本批未接近上限。记录计算57.72分钟，额度观测起点43%、计算结束44%；共享账户增长保守计入，不声称是精确的本任务消耗。

## 未实施范围

新对应门槛未过，按计划未展开关系组合和更大词表。没有修改Core、参数默认、输入映射或死亡条件，没有运行无提示差值读出来判定梦境。生产实时聊天、无需副本的表达器、主动发言和一般语言理解仍未交付。

下一阶段建议和原因见报告末尾及研究总表R17/T07；本轮新增工具可复用，不要求为每次研究另建一套总线或数据库。
