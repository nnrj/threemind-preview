# 实验总览与统一记录

[English](../en/research-records.md) · [补全计划](plans/experiment-record-backfill.md) · [全量交付与缺项](plans/experiment-record-backfill-delivery.md) · [数据管理](data-management.md)

AI 执行与人工执行使用同一套研究记录服务。执行者只是检索字段，不降低记录要求。实验原件保持原样；数据库保存索引、小正文、固定修订关联和原件引用。历史补录不能代替缺失的原始采集，也不运行旧个体。

## 在界面中查找

侧栏 **实验总览** 默认查询全部有权访问的研究项目，可按编号、标题、项目、日期、内核、执行者、执行状态和资料完整性筛选。2026-10-10 后续调整使“记录与报告”“实验笔记”和其他主要资料菜单也默认跨项目浏览，资料显示所属项目，并支持主动筛选。某个项目为空，不表示全库为空。详见[全局浏览与归属](global-resource-browsing.md)。

修订说明：上期交付只新增全局实验索引，其他页面仍按当前项目展示；本次经用户批准扩大默认浏览范围。原补录记录、报告和交付证据保留。

历史相关内核标签来自原文中的显式身份和原生运行配置，用于检索。各分组的实际执行版本和参数以协议及保存配置为准；尚未确认的核身份保持待核查。早期 N01～N13 是本次检索标签，页面同时显示原札记编号 001～013。

详情展示协议、原报告、笔记、个体与阶段、修订和证据。笔记仍遵守作者权限。已支持的文本和 JSONL 分页查看；未知二进制仍保留原字节，通过下载或完整证据包访问。运行、检查点入口复用原有查看与回放，登记或查看不会推进模拟。

执行完成、运行失败、未启动和阴性结论分别保留。“已登记，未完整核验”只说明已有索引；“资料有缺项”明确指出缺项；“已核验登记资料”也只覆盖所登记的原件，不证明实验采集本来完整。

## CLI、REST 与 Agent

先按通常方式启动本地工作站，然后使用同一 Python 环境：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --query E64
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --kernel threemind.continuous-memory/3
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records --help
```

默认 API 地址为 `http://127.0.0.1:8877`，其他地址用 `--url`。服务端模式沿用已有登录配置，不把密码写入请求 JSON、实验原件或 Git。

`list` 还支持 `--classification`、`--from-date` 和 `--through-date`；日期使用 `YYYY-MM-DD`。临时开发记录需显式选择 `--classification development`，不混入默认正式研究列表。

`register`、`append`、`attach`、`text`、`finalize`、`verify`、`backfill-plan`、`backfill-apply`、`receipt` 共用 REST 保存服务。写操作通过 `--json` 指定请求文件；每次新操作使用新的 UUID `request_id`，重试保持原 ID 和原正文。不同正文复用 ID 会报冲突。`receipt --project <UUID> --request-id <UUID>` 查询已提交回执。

登记请求的最小例子如下；研究开始前应补齐研究问题及事前协议，阶段结束追加事实，结项再核验：

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "spec": {
    "source_key": "research:my-declared-study",
    "title": "已事前登记的研究",
    "executor": "ai",
    "classification": "formal",
    "execution_status": "planned",
    "question": "实际研究问题",
    "protocol": "实际协议，注明条件、完整个体、对照、阶段与判据"
  }
}
```

API：全局查询 `GET /api/v2/research-experiments`；项目操作位于 `/api/v2/projects/{project}/records`。请求结构、前置条件和权限由 `/api/v2/operations/catalog` 的 `records.*` 操作公开；现有 MCP 服务直接使用同一操作目录。

原件关联支持已授权的统一存储资源、固定版本报告／笔记、附件、运行和检查点。文件记录大小与 SHA-256；不接受任意主机路径。主机管理员通过 `POST /api/v2/storage/record-evidence-grants` 显式授予项目对某个已登记资源的读取权限。缺失原件用 `missing` 引用说明原因，不能伪造空文件。

修订使用同一个正文 `identity`、明确的 `expected_revision` 和 `revision_reason`；原修订及其哈希继续保留。历史 Markdown 中不适配笔记链接验证的相对链接原样保存为字面源码，详情按原文查看，不修改原字节或降低链接校验。

## Python 脚本

`threemind_lab.research_recorder.ResearchRecorder` 接受规范保存服务或现有 `OperationsClient`，二者选其一。使用 `register`、`append`、`attach`、`text`、`synchronize`、`finalize`。`save_original` 可持久保存不可覆盖的原字节；大型原件可继续使用原科研写入器，再关联已登记的存储引用。

记录器在实验目录下的 `.research-records` 保存请求、待同步状态与回执。数据库不可用时 `synchronize()` 留存请求；`synchronize(strict=True)` 保存错误状态后报错。恢复记录用 `resume_recording()`，它不恢复或清空意识。原件写入失败必须停止宿主推进，不能跳过输入后继续实验。

人工运行、配对研究、发育、定向选择、生态训练和独立评估会在出生／入队事务内登记协议；任务完成追加已有状态与检查点引用。`record_executor` 可选 `human`、`ai`、`mixed`、`unknown`，默认 `human`；`record_classification` 默认 `formal`，校准选 `calibration`，临时开发检查选 `development`。这些是宿主记录字段，不进入内核协议或动力学。研究者仍需补齐问题、解释性笔记与结项报告。

后续维护的 `lab/tools/service_study.py` 和发布器已接入记录器。历史冻结脚本不修改、不重跑；补录使用外部适配器。

## 原件导出与补录

详情可生成按实验的正式打包预览，数据管理使用 `kind=experiment`。报告修订、个人权限、原件哈希和只读运行依赖随正式包保存；导入索引使用新身份并保留来源，不能把历史引用自动变成运行中的个体。导入后再次打包也保留运行的原始表成员；单独一个描述文件不能冒充完整运行资料。

正式传输沿用既有容量与磁盘预留限制。很大的实验须按既有数据管理能力缩小选择或下载原始完整归档，不能为了导出绕过限制。**本机完整备份会占用大量空间；空间不足时传输明确停止。**

历史适配命令 `scripts/backfill-research-records.py inventory|preview|apply` 生成固定盘点、预览、请求和回执。`apply` 要求完整数据库备份及独立恢复验证清单；恢复只建立新临时库，不覆盖日常库、切换主机或启动模型。迁移仍用显式 `threemind migrate`。已补录资料重试复用固定预览，不重新把新补录正文当作历史来源。

已结项批次重试时核对固定来源及数据库完成回执，复用当时的核验结果，不重复登记每件原件；本地回执丢失也可恢复。需要重新检查当前原件时，使用 `records verify --project <UUID> --experiment <UUID> --hashes`，这与补录重试分开。

本次实际盘点、缺项与核验结果见交付文档；不要以目录数量代替已执行实验数量。
