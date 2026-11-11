# R48 权重依赖衰减研究交接

> 公开存档说明：下文是该日期的交接记录，不是当前运行指令或启动授权。运行任何实验须先核对当前状态与协议。


## 2026-11-11最终覆盖：两批科学与Rust均已完成

R48a/b均已completed/verified/pending0，宿主退出、无STOP/in-flight。B的awaiting-analysis仅旧计算状态，禁止重跑；实际结项依据publication/completion.json。B包220,490,039字节、6,907成员，SHA256 bd7119ae068894fc21d1f19b5eecaa57e368a71763049dbb22f77fce767f13c3。慢档即时初学128/128对111/128，少三分之一优化更新；两种候选四项完整目标全0/8；逆对数8、8、4、8。无综合默认候选，本轮结束。

科学交付后已合入独立Rust/Python/native/runtime身份，63个Rust源文件与编译树逐字节一致；406项定向回归、wheel54项重叠验收、Rust20项均通过。50条件150次规模测量完成。工程原件、二进制、源码和报告包位于engineering-v1，11,377,690字节、468成员，SHA256 0e8a3f6ea6101c7601697a171c96b9cffcb6d2f755f97c78027797e5a34caedc。现用安装与服务未替换。集成脚本不可重跑，测试记录均已存在。末尾Git数据检查与本地提交以Git实际状态核查；不push。

后续若有新假设，应另立协议；不得把本批即时收益改写为完整保持成功。所有原分数、原报告与失败回执保留。下方内容均为历史进度，不再是行动入口。

## 2026-11-11 06:10核查：35/40，结束后的工具已就绪

历史观测：R48b35/40，o6/matched-slow已完成，最后来源即将开始；宿主11576创建时间1794345150.7838318仍匹配，STOP无、stderr空。最近提交约10.7GiB、RAM11.2GiB、E94.2GiB、C16.8GiB。不得据这个数字重跑或预写结论。

`.work/finish-r48b-data.py`已单次启动，工具会话8542，等待该宿主退出，然后只运行analyze/audit/diagnostics、复制R48a只读复习附录、inventory。输出`.work/r48b-postprocess.out.log`、错误同名.err.log。不能重复启动；若它失败，先读已生成原件，只补缺项。正式宿主会话89114。然后人工阅读分数和审计、完成报告、出版审阅与API全文原包读回。A/B完成前不改src/crates。

Rust测试程序已编译（会话3242退出0），`.work/r48-rust-test-build.err.log`列出两个测试exe；尚未运行。wheel安装到`.work/r48-wheel-check`成功，但普通沙箱无法读其pip生成目录，曾误找到现用旧模块。已在扩大权限的只读检查中确认真实隔离路径和NativeWeightDecay类，`wheel-install-verified.json`补正，旧失败receipt保留。wheel模块SHA为0b41496e602c2132c3e85ff7909a2ee704197d4a848337c9f5e2d285a8b62dcd，与直接cargo产物不同；两者都需验证，不能假定同一二进制。没有更新现用环境。

两批交付后依次运行`.work/integrate-r48-native.py`（无参）及`.work/r48-extra-integration.py`，后者同步配置目录、54项新测试和一个旧配置测试的5.3/R48隐藏参数范围；不改动力学。`.work/verify-runtime-r48.py --target delivery|wheel --output <新的目录>`会断言实际加载路径，并运行相应工程检查；wheel检查需扩大权限读取隔离安装目录。完成后独立运行时测试、等规模性能测量、双语工程报告、产物归档、双语史书/总表/两种文言和本地提交都还未完成。`.work/r48-guide.zh.md/en.md`是待验收后采用的说明草稿。

## 2026-11-11 05:47左右核查：完整培养20/40，Rust构建完成

本段为历史观测，接续仍读实际进程与最新完整边界。R48b status记录20/40，o0—o3五组均完成，o4逆对数运行中；PID11576/创建时间1794345150.7838318真实匹配，最新完整文件哈希一致，无STOP、stderr空。每秒守卫在宿主线程中运行。近期提交余量约10.7GiB，RAM约11.1GiB，C16.8GiB、E94.4GiB。源码和课程冻结不变。

独立目录的Rust程序、原生模块及Windows abi3 wheel均编译完成。`.work/r48-delivery/`保存产物，build-receipt是“仅编译”回执；尚未动态验收或更新现用安装。`.work/integrate-r48-native.py`与`.work/r48-extra-integration.py`的实际仓库操作须等两批API完整交付后才执行。配置说明、36项原始工程测试加18项补充检查、性能脚本已在`.work/r48-native-stage/`准备；不要把准备数量写成已通过数量。

只读R48a复习诊断另存`.work/r48-teaching-followup-v1.json`，快档两种实现均在长间隔中发生连接删除与重建；原A包未改。将作为B报告的明确事后附录保留。B新增diagnostics.py只读完整已提交文件，需B全批及独立审计完成才执行。第一版A报告不再原位修改。

## 2026-11-11 最新覆盖：R48a已交付，R48b已运行

R48a 的1,280序列已完成，独立审计2,560边界及5,120校验值一致。快档弱经历遗忘8/8，但两种权重档三类300秒结构/表达均0/8，与相应匹配指数通过分数相同；逆对数复习/强刺激表达7/8、8/8。没有综合默认候选。双语报告、原件包及成员已完整API读回，completed/verified/pending0，包24,292,846字节、9,417成员、SHA256 `617f7782c1b2847bb43268f5e34b81c9ecb7254cf7ce5ff6ec32d8c9c72ecab1`。旧awaiting-analysis是计算状态，不可重跑。

R48b单次启动，PID11576、创建时间1794345150.7838318，仅为启动历史。已核验真实命令为joint/driver.py run，首个完整个体完成，第二个正在连续培养；最新位置必须读current.json和实际进程。首日志joint-v1/logs/first.out.log、first.err.log；首宿主工具会话89114。冻结参数不变，未见STOP或stderr。

Rust候选在`.work/r48-build-tree`独立副本编译（首构建工具会话16500）；本仓库src/crates和正式科学实现仍未改。`.work/integrate-r48-native.py`无参数时要求两批publication/completion.json均存在，才向实际源码加入独立候选入口；`--prepare-tree`已执行，不能重跑。同目录准备测试须等科学批结束后再执行，不能把工程示例当正式实验或改变宿主后端。构建资源及后续清理不授权删除旧证据。

## 2026-11-11 运行中覆盖与 Rust 实现提醒

R48a 已单次启动，最近只读核查完成 653/1280 序列，未见 STOP、错误日志为空，活宿主的 in-flight 为正常单元。启动观察 PID 20208、创建时间 1794344118.852399 只是历史坐标，续接须核对真实命令与创建时间。日志为 assay-v1/logs/first.out.log 和 first.err.log。统一 API 登记 project `6a6b439d-bf2e-4da2-840c-5695c224c761`、record `aa70f38d-6464-51f1-9226-15355094e844`。

R48b 已准备并登记，project `6a3eb80d-7d53-45f3-a1e8-37c8b64eabd3`、record `1663e2c1-430f-539f-9e0b-aa6a2af33e91`，协议双语读回一致、pending=0，尚未启动。R48a 交付后才启动 R48b，禁止重复 prepare。

用户补充“最后别忘了运行时版本（Rust版本）的实现”，要求继续现有任务。两批冻结科学运行和原包交付完成后，将同一候选规则加入 Rust 内核、Python 原生绑定及独立运行时，检验逐状态一致性、完整保存恢复、旧版本回归和性能；保留独立实验版本身份，不改默认。准备草稿在 `.work/r48-native-stage/`，尚未合入 src/crates。科学运行期间不修改冻结实现或安装包，不切换后端。

2026-11-11，当前为运行前准备。用户明确授权检验 dw/dt=−w[λmin+λextra(1−w)]。具体对照、参数、目标及预算见[局部协议](protocol.zh.md)及[完整个体协议](joint/protocol.zh.md)，不得把本文的准备状态当作科学运行结果。

独立研究身份 `threemind.experimental-weight-decay/1`，代码仅在本目录；src、crates、现用安装、生产默认及旧个体均未改。五组为逆对数、权重快/慢、弱权重匹配指数快/慢；全部节点支持度固定逆对数，Python后端。只修改边权衰减，真实执行既有强化、传导、资源和时钟规则。

R48a 8来源1280独立培养序列，工作区`E:/ThreeMindData/experiments/2026-11-11-weight-dependent-decay/assay-v1`。R48b 8新来源40完整个体，工作区同根`joint-v1`。两批串行；R48a交付后才启动R48b。R48b必须有个人时序Transformer、Adam/RNG、教学、2/6/18秒复习、最多两轮纠错、反转及重学，不能用局部实验替代。

工程验证：`.work/r48a-instrument-v1`32项、`.work/r48b-instrument-v1`33项通过，两者共享公式检查，不能相加为独立科学证据。`.work/r48-theory-engineering-v1.json`为数学投影及64节点Python成本；不是持续培养记录。复用了R47方法，旧源码原位保留。

运行前经统一API登记并完整读回协议。每秒资源守卫5/4/5/25GiB，启动提交≥8GiB；孤立in-flight或死亡不清除、不回放。检查实际PID、创建时间、命令、STOP、当前完整边界与回执，避免重复启动。prepare/run/分析/审计原件都只创建一次；同名已存在时先核对，不覆盖。API-only8877可复用，不开旧队列。E69/E67/E68和旧自动任务继续暂停。

所有科学原件置于E:/ThreeMindData，双语报告、史书、稳定R48进度同步；原包及双语全文通过API读回pending0后交付。只本地提交，不push。候选无综合收益也正常结项；参数不据正式成绩更改。
