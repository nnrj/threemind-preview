# R51t只读核验修正：输入总线的空待递送项

2026-11-14。592个科学阶段已正常计算完成，耗时6857.17秒，没有活动STOP或in-flight。首次运行冻结的核验脚本，在科学评分产出前遇到格式断言：脚本要求`pending == []`，但`threemind.input-bus/1`以字典保存待递送项，空值为`{}`。接口实现在`src/threemind_runtime/bus.py`的`InputBus.capture`。

随后独立读取592份最终观察者记录，全部符合原接口的空字典格式，没有未递送输入。修订的`analyze_timescales_v2.py`同时核对接口版本、字典类型和空值，其余输入、状态、时序与科学测量检查不变，并先核验写入资格v3。原核验脚本保留，没有覆盖；没有创建或推进个体，没有重新运行任何科学阶段，也没有改变原判据。

工作区`memory-timescales61-v1/audit-amendment-v2/proof.json`保留首次失败条件、592份格式核验计数，以及原核验、新核验、接口和未变科学测量模块的哈希。测量模块SHA256为`73f4e40543f20677ed3736c176ee6d734e5c374057e4616c601e6975fd6b5776`。

本说明只登记核验工具修正，不预告科学结论。完整分析以`analysis.json`与`audit.json`为准。后续只读核验入口改用`analyze_timescales_v2.py --work <当前工作区>`；正式计算已经完成，不再调用run。
