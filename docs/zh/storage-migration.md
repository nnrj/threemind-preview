# 存量迁移与研究文件目录

[English](../en/storage-migration.md) · [批准计划](plans/existing-data-migration.md) · [本轮交接与清理清单](plans/existing-data-migration-stage.md)

2026-10-10：批准存量清单已实际迁移并启用 `E:\ThreeMindData`，真实库为 schema 65。当前完整备份已隔离恢复；源副本与旧完整备份保留。不要再执行一轮相同迁移；使用原任务编号查询、核验或按条件回退。[实迁交付](plans/existing-data-migration-delivery.md)

## 数据放在哪里

`THREEMIND_DATA_ROOT` 默认为项目 `data`。本次批准目的地是 `E:\ThreeMindData`；它只改变研究原件的文件根，不搬 PostgreSQL 的物理数据目录。报告、笔记正文、输入、指标、恢复游标及节点／连接查询仍走数据库。

新研究脚本可用 `ResearchStorage(...).workspace_path("实验目录名")` 得到已登记根下的 `experiments/实验目录名`，再传给维护中的 `StudyConfig.work` 和记录器。该解析不创建目录、主体或重置旧个体；旧 `.work` 路径继续可用，冻结脚本保持原样。新入口接受外置根，持续产生的正式原件按原记录要求登记。

宿主控制区仍为 `data/storage-control`，或者显式配置的 `THREEMIND_STORAGE_CONTROL`：身份、密钥、锁、任务回执与成员映射留在固定控制区。原件位置有独立版本，历史 locator 和科学哈希不变。迁移后的文件读取核验新位置；损坏时明确报错，不用旧源副本掩盖问题。

运行检查点默认 `database`。可通过宿主配置 `THREEMIND_CHECKPOINT_BACKEND=filesystem` 或管理页面明确选择文件方式，已登记的宿主设置优先于环境默认。该选择不进入内核配置、不改变个体版本。文件方式先持久化并校验，再事务提交检查点及关联输入／观察；失败不能确认保存成功。完整宿主状态随检查点保存，不把一个 Core 原件称为完整系统。

## 管理界面与共同接口

更新后的“数据管理 → 存储位置”提供研究目录预览、确认执行、任务状态、继续、取消、校验、回退、清单下载，以及检查点后端选择。空间不足时禁止执行。目录变更由程序复制、校验并切换，不需人工逐文件搬运。页面关闭不代表取消任务；中断后查原任务编号，再继续。

UI、CLI、REST 和现有 Agent 操作目录共用 `RootChanges`、逐资源迁移及原件保存服务。宿主操作要求管理员，项目载体还检查项目写权及私人附件权限。REST 入口为 `/api/v2/storage/root-changes`、其 `/preview`、`/{id}`、`/{id}/manifest` 和 `/{id}/{action}`；检查点设置为 `/api/v2/storage/checkpoint-backend`。项目原件迁移与封存分别位于 `/api/v2/projects/{project}/storage/payload-migrations` 和 `/seals/{run}`。

批量预览依据科学引用和精确归档清单选择文件，排除 Git 源码、报告、协议及冻结夹具。2026-10-10 的清单选中 43 资源、32,984 文件和 4,242 数据库载体；其余 114 登记资源已分类为 68 源码／报告／夹具及 46 已发布包的展开工作区，原位保留；展开副本未经逐成员等价核验，不可自动清理。数据库载体包含媒体、笔记图片和实验／模型／导出包；没有封存的检查点不被选中。

## 命令流程

以下是通用操作流程。此次任务已经完成，日常无需重跑这些建立备份／新迁移的命令；查本次状态请用交付中的原任务编号。日常环境使用项目中的 Python，不需另开付费服务。

```powershell
$env:PYTHONPATH = "$PWD\src"
$tmPython = "$PWD\.work\kernel-venv\Scripts\python.exe"
& $tmPython -m threemind_lab.cli storage root-preview --local --destination E:\ThreeMindData
```

`--local` 使用 `.env` 的应用数据库和本地管理员上下文，不要求先启动 HTTP 服务；不替代备份账号。只支持 `root-*`、`checkpoint-backend`、`payload-migrate` 和 `seal`；其他宿主命令仍使用原 HTTP 接口。

备份命令从本机 `.env` 读取 `THREEMIND_BACKUP_DATABASE_URL`。目的目录必须新建、空间足够；备份账号 URL、密码及密钥值不写入命令、回执或资料包。示意路径请替换为实际有空间的磁盘：

`create --compression zstd:3` 可明确选择较快的备份编码；还支持 `zstd:1`、`gzip:1`、`gzip:6`，未指定时保持 PostgreSQL 原默认。清单记录实际选择，原件字节／科学哈希不变；安装的 PostgreSQL 工具必须支持所选编码。新目录和完整恢复核验仍必需，压缩不是空间充足的保证。

```powershell
& $tmPython -m threemind_lab.cli storage backup --pg-bin 'D:\Program Files\PostgreSQL\17\bin' create 'X:\ThreeMindBackups\storage-20261010'
& $tmPython -m threemind_lab.cli storage backup inspect 'X:\ThreeMindBackups\storage-20261010'
& $tmPython -m threemind_lab.cli storage backup --pg-bin 'D:\Program Files\PostgreSQL\17\bin' restore 'X:\ThreeMindBackups\storage-20261010' --new-database threemind_storage_verify --external-root 'X:\ThreeMindRestore\storage-20261010'
```

联合备份包括数据库、已登记原件、实际位置、成员映射、策略和检查点宿主设置；密钥另行安全保管。恢复仅允许新库和新目录，返回未启用的恢复登记；需核验身份、引用、恢复依赖及下一输入响应，不能用 `inspect` 成功代替恢复验证。

隔离恢复可用 `--relation-root observations=D:/ThreeMindRestore/observations` 将该表放到另一个新目录，以分配两盘空间。只影响新恢复库的物理表空间，原库、原件与逻辑内容不变；返回回执登记表空间名和目录。临时副本清理时先删除准确的新恢复库，再删除其已登记表空间和目录，不能删除日常 PostgreSQL 数据。

完整备份可用 `storage backup compact-research BACKUP_DIRECTORY` 无损压缩其内部研究原件。工具先验证旧备份，再对解码后的科学哈希和大小逐项校验，原子发布明确的 `/2` 备份格式，最后清理此备份内部被取代的字节表示；研究源副本、数据库导出及其他备份保持。中断可对同一目录重试，清理前后都由已发布清单指向完整字节。旧 `/1` 备份仍可读取；旧程序会拒绝 `/2`，不会把压缩字节误当原件。节省量取决于文件内容，仍须核验隔离恢复。

### 中断后的文件恢复

先查进程、原任务回执和恢复库见证，避免重复执行数据库复制。数据库恢复已完成而外部文件阶段失败时，可单独恢复文件：

```powershell
& $tmPython -m threemind_lab.cli storage backup restore-files 'X:\ThreeMindBackups\storage-20261010' --new-database threemind_storage_verify --external-root 'X:\ThreeMindRestore\storage-20261010'
```

此命令不连接或改写数据库；回执明确标为仅文件恢复，数据库必须另行核验。目标目录须为空或属于同一备份／目标的意图记录；已经发布的文件逐件核验后复用，未发布暂存可重做，内容冲突则停止而不覆盖。历史目标 ID 保持原样，物理目录按其哈希生成，避免把合法的含冒号 ID 当成 Windows 路径。

备份和恢复核验通过后，使用既有 `migrate` 明确升级数据库；运行服务需由用户按既有流程暂停／重启，不接管其进程。迁移命令不会由应用启动自动执行。

```powershell
& $tmPython -m threemind_lab.cli migrate
```

重新预览后，把返回的 `root_before.revision` 用作下列版本号。稳定请求 ID 在重试时保持不变；例中 `0` 仅是本轮迁移前读到的版本，实际操作应以最新预览为准：

```powershell
$tmChangeId = [guid]::NewGuid().ToString()
& $tmPython -m threemind_lab.cli storage root-plan --local --destination E:\ThreeMindData --expected-revision 0 --request-id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-execute --local --id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-status --local --id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-verify --local --id $tmChangeId
```

使用 `--output` 可将完整任务／预览写入一个不存在的 JSON 文件。`root-resume` 继续原任务，`root-cancel` 在安全文件／载体边界停止，`root-rollback` 在版本与写入条件满足时回退；这些命令都用同一 `--id`。已复制的文件保留，不自动删除。

批量执行逐对象核验并切换位置，所有选定项通过后才发布研究根和未来写入策略。部分完成时读取各对象的真实位置，不冒称全部完成。新写入、源变化、配置冲突或校验失败会阻止对应批次；恢复不得跳过冲突。发布意图与任务回执持久化，发布后进程退出可按原任务恢复结果。

大批次的固定选择清单按哈希单独保存，进度／取消日志只更新变化字段，避免每复制一个文件都重读重写全量清单。新逐资源任务使用 `/2` 操作日志；现有 `/1` 任务继续可读、可续。查看完整清单时核验身份和哈希；元数据缓存有大小限制，原子替换会使缓存失效，不缓存个体动力学状态。

不应直接改 `.env` 来代替迁移：登记根和请求根不一致时，程序返回待迁移状态并阻止混写，不创建一个看似空的新库。切换成功后可同步环境设置与登记根。

## 检查点与回退边界

单个数据库原件迁移使用 `storage payload-migrate --project PROJECT_UUID --kind artifact|media|note-image|checkpoint|blob --id OBJECT_UUID --target TARGET_ID --request-id REQUEST_UUID`；本地调用另加 `--local`。允许的目的地是已登记文件目标，原数据库字节及历史位置保留。

`storage seal --local --project PROJECT_UUID --id RUN_UUID` 是明确封存，要求主体已完成、停止写入，恢复边界受支持且依赖可核验。暂停待续训、协调器、依赖缺失或有活动作业的主体不得封存迁出。本轮未自动封存任何真实运行；既有 T12 的 `/4` 宿主保存问题仍另案，不被本轮工程夹具验证覆盖。

根回退检查新写入、资源版本和策略版本。切换后若已写入新资料，需另作反向迁移，不强行切回一个缺新数据的根。数据库原件回退也先验证保留的旧字节；回退、取消和归档均不等于删除。源副本清理须另出逐对象预览，正式研究原件不作为腾空间的普通缓存。
