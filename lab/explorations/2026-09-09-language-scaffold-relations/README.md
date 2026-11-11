# 教学探索：父亲的父亲与问答迁移

本轮为用户授权的有限实验，沿用 causal/9、state/6、text-sensor/2。没有修改 Core、数据库 schema、感官映射实现或 UI。所有输入都通过既有文本感官与输入总线；输出使用既有隔离探针服务，不生成 AI 答案。

## 阅读顺序

1. `protocol.md`：原先方案；`preflight.json`：输入编码检查。
2. `amendment.md`：独立校准失败之后、正式种子训练之前固定的修订；原始方案和失败数据没有覆盖。
3. `instrument-decision.json`、`physical-timing.json`：只据实际传输与饱和选择测量条件的结果。
4. `report.md` / `report.en.md`、`summary.json`：结论与机器可读数据。
5. `family-cases.csv`、`probe-observability.csv`、`time-courses.json`：逐查询结果。
6. `evidence-index.json`：所有来源恢复点、完整证据 ZIP 和哈希；需相应 ThreeMind 项目访问权限。

平台项目为 **教学探索：父亲的父亲与问答迁移 · 2026-09-09**。实验笔记含原方案、修订和完整报告；记录与报告含校准记录、两项对照记录和综合报告。弱探针使用已有校准父本，不另计新意识。

## 执行与复核

从仓库根目录使用现有 `.venv/Scripts/python.exe` 执行本目录脚本。脚本使用本地 `.env` 中的应用账号；不要把密码写入命令或报告。无需启动通用 worker 或浏览器；写库经 Lab 的项目、意识、输入、检查点、校准、笔记和研究文档服务完成，作业领取仅限本脚本新建的编号。

实际顺序是 `check_design.py` → `run.py preflight` → `run.py init` → `run.py calibration` → `run.py decide`（预期报告校准不通过）→ `weak_probe.py` → `decide_instrument.py` → `run_diagnostic.py` → 有余量时 `run_diagnostic.py --long` → 分析、证据验证和出版。初始化、各计算阶段和追加校准均拒绝覆盖已有项目日志；不要为了重跑删除现有项目或证据。

`check_analysis.py` 验证指标方向、交换祖父后真值改变和缺失通道处理。`analyze.py`、`curves.py`、`verify_evidence.py` 读取已有证据，不继续训练。`publish.py` 使用出版日志避免重复创建记录。

紧凑逐案例结果保存在被 Git 忽略的 `.work/language-scaffold-relations-20260909/`，并作为 artifact 落库。换机器复算时，先通过平台 artifact 下载恢复这些同名结果文件；不要用重跑模型替代原始测量。基础训练流程复用前一研究目录的 `run.py`，其内容哈希与 Core/原生二进制哈希均写入证据。完整实现源码包、当前实验脚本也随报告归档。

本轮没有自动清理旧数据，也没有把人体语言、逻辑或正确答案写进 Core。报告里的词通道投影是一种外部观察，不能代替对全部分布式活动的解释。
