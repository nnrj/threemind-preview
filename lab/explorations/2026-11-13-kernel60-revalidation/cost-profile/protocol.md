# R51b：定位6.0推进耗时 / Locate 6.0 advancement cost

2026-11-13。用户明确要求“定位耗时问题”。本批是隔离工程诊断，不恢复暂停的正式复验。目标：以实测区分结构检查、发送/接收、状态结算、衰减计算及调度的成本，给出具体优化顺序。

生产源码及已安装模块保持不变。复制当前提交的Rust源码到`.work/kernel60-cost/checkout`，只在副本加入函数计时及计数，编译到独立目录。记录原始和修改后源码、模块散列。计时字段不进入个体状态，不读取墙钟来决定动力学。测量开/关所得完整终态必须与正式模块相同；不相同则仪器无效。计时本身会增加墙钟成本，必须报告该开销，细粒度百分比只用于被测仪器内的分解。

材料沿用R51a：编码0起的512对互不相连双向节点，0时刻各接收0.8强度，推进10内部秒。确认`id=channel`。比较5.1与6.0真实默认配置，仅共同延长静息死亡等待；5次交替无插桩测量用于复核总差异。孤立新增工程样本没有教师、读出器或适配器学习。

6.0使用3次粗计时和3次细计时，分别测结构检查、发出、接收、状态结算、衰减、定时器及调度。另分0—1秒、1—10秒观察晚期活动及没有实际传出信号的发送尝试；分段推进的终态须与整段一致。计时标签互相嵌套，报告包含子调用和扣除子调用两种耗时，不重复相加。若插桩明显改变总时间，结合低干扰粗计时和无插桩对照解释，不能把仪器开销冒作生产耗时。

有限诊断对照，每项5次：6.0默认；结构检查间隔改为1内部秒；仅将衰减曲线改为指数；两项组合。后两项和间隔对照只用于拆解成本，不是候选默认，也不要求科学状态相同。另用4096节点各3次验证5.1/6.0的规模方向。总规模不超过100次推进，每次最多10内部秒；新增原件预算512 MiB，隔离编译预算4 GiB。每秒保留提交/RAM/C/E为5/4/5/25 GiB，完整工程边界停止。新的死宿主in-flight保留。若需要改变生产实现、降低检查频率或改变信号处理，须另经用户决定。

交付：分项数据、完整初末态及仪器一致性核验，双语明确结论和优化建议，追加R51研究进度及史书。本次目标是定位并量化耗时来源，不将临时对照当作已完成性能修复。

## English

The user requested cost diagnosis. This isolated engineering study keeps production source and installed modules unchanged. A separate Rust copy adds timing/counting only; wall-clock values never affect transitions or saved states. Instrumented and uninstrumented complete final states must agree exactly. Otherwise the instrument is invalid.

Reuse R51a's identifier-matched 1024-node fixture for ten internal seconds. Five alternating production comparisons verify total cost. Three coarse and three detailed profiles distinguish structural checks, emission, reception, settlement, decay and scheduling. Separately measure 0–1 and 1–10 seconds, including emission attempts with no transmitted signal; segmented continuation must match the whole interval. Report inclusive and exclusive time without double counting, and disclose instrumentation overhead.

Five-repeat bounded controls change only structural-check interval to one second, only decay to exponential, or both. These change dynamics for diagnosis and are not default recommendations. Three repeats at 4096 nodes check scaling. Limit: 100 advances, ten internal seconds each; 512 MiB evidence and 4 GiB isolated build budget. The 5/4/5/25 GiB host reserves remain. Formal revalidation stays paused. Deliver measured causes and prioritized recommendations, not an unapproved production optimization.
