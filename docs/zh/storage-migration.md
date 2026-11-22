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

## 新实验使用多个数据目录

未配置多盘时，实验继续使用现有数据根下的 `experiments`。要使用其他磁盘，可在「数据管理 → 存储位置 → 实验数据目录与多盘分配」中添加宿主机上的绝对目录。数字较小的优先级先用。每个目录可以设置占用上限，每块磁盘可以设置最低剩余空间。上限包括该目录中已有文件的实际占用。多个目录位于同一个卷时共享剩余空间，并采用最高的保留值。

启动实验前，按预计同时存在的数据填写峰值预算，包括原始记录、检查点文件、临时文件、归档和需要落盘的回读副本。默认先找能容纳整项预算的一块盘。单盘放不下时，预览会显示缺口。如果可以按世界或批次独立写入，可为每一项起名并勾选「允许本次实验跨目录存储」。一个世界、一个文件或一个分卷始终写在一个目录。分配后，实验可按名称找到原目录。拔盘会中止依赖该盘的操作，接回原盘后可按名称重新打开。Windows 下重新分配盘符时，系统会核对卷身份和目录身份。

命令行与网页共用同一份分配记录。以下命令在宿主机本地运行。省略 `--local` 时通过已认证的 ThreeMind 服务访问服务端磁盘。

```powershell
threemind storage pool status --local
threemind storage pool configure --local --json directories.json
threemind storage pool preview --local --json budget.json
threemind storage pool reserve --local --json budget.json
threemind storage pool path --local --name aquatic --part world-a
```

配置示例中 E 优先、H 备用，两盘分别保留 25 GiB 和 5 GiB。再次编辑时使用 `status` 返回的当前 `revision` 作为 `expected_revision`。若要限制目录最大占用，将对应的 `limit_bytes` 改为字节数。

```json
{"expected_revision":0,"directories":[
  {"id":"primary","path":"E:/ThreeMindData","priority":10,"reserve_bytes":26843545600,"limit_bytes":null},
  {"id":"portable","path":"H:/ThreeMindData","priority":20,"reserve_bytes":5368709120,"limit_bytes":null}
]}
```

下面的 `budget.json` 示范如何给一个世界、两个归档分卷和一次文件回读预留空间。正式实验应按各自的实测规模填写预算。

```json
{"name":"aquatic","allow_split":true,"parts":[
  {"name":"world-a","kind":"data","bytes":4294967296},
  {"name":"vol-1","kind":"archive","bytes":2147483648},
  {"name":"vol-2","kind":"archive","bytes":2147483648},
  {"name":"check","kind":"readback","bytes":1073741824}
]}
```

新实验可通过 `StudyConfig.for_experiment(...)` 让研究工具按硬预算分配目录。多分项实验在预留后用 `part="world-a"` 打开对应工作区。其他脚本用 `ResearchStorage.workspace_path(name, part=...)` 取得实际路径。写死盘符的旧脚本继续按原路径运行。历史数据和数据库有各自的存储位置。

数据写完以后，`archive` 将各数据分项写入同一个标准 ZIP 字节流，按预算直接写到分卷，无需先在某块盘上保存完整 ZIP。`verify` 校验各卷的字节数和 SHA-256。`extract` 可从跨盘分卷中还原指定文件到预留的回读目录。管理页也提供这三项操作。将归档给其他人使用时，按清单顺序把各卷的原始字节拼接即可得到普通 ZIP。

```powershell
threemind storage pool archive --local --name aquatic
threemind storage pool verify --local --name aquatic
threemind storage pool extract --local --name aquatic --part check --member world-a/trajectory.json
threemind storage pool finish --local --name aquatic
```

通过 HTTP 可从 `/api/v2/storage/experiment-pool` 查询或配置目录，使用 `/preview` 和 `/reserve` 分配空间。已归档的实验可从 `/studies/{name}/manifest` 取得有序清单，或用 `threemind storage pool download --name aquatic --part vol-1 --output volume-1.bin` 下载并核对单卷。完成实验会释放未用预算并保留定位记录；只有尚未创建工作目录的预留可取消。联合备份保留宿主机分配表与已发布分卷清单，实验原件仍按既有流程登记或单独备份。

完成实验以后也可按需取出某个文件。例如，运行 `threemind storage pool extract --local --name aquatic --member world-a/trajectory.json --output trajectory.json`，即可在当前目录得到原文件。网页可选择「下载归档中的文件」。

## 整项实验的同步、备份、迁移与归档

在“数据管理 → 存储位置 → 实验数据目录与多盘分配”中为目录选择用途。要给运行盘腾空间，请把归档目录设在另一块硬盘上。例如，实验在 E 盘运行时，可以在移动硬盘 H 上设置 H:\ThreeMindArchive。网页会优先推荐位于其他物理磁盘的在线归档目录。同盘目录也可手动选择，用于整理文件。只有运行目录参与新实验的分配；同一存储卷上的多个目录共用可用空间和磁盘保留值。在 Windows 上，程序查询卷对应的磁盘编号，避免把同一硬盘的两个分区误认作两块硬盘。[Windows 卷与物理磁盘](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents)

展开“实验同步、迁移与归档”，选择实验、操作和目标目录，再预览和执行。旧实验可在“登记已完成的历史实验”中按运行目录查找，确认已停止写入后登记。发现范围是该运行目录的 experiments 目录下的直接子目录。分散在若干运行目录的已登记实验按各自的分项一起处理。

| 操作 | 数据写在哪里 | 完成后从哪里访问实验 |
| --- | --- | --- |
| 单向同步 | 目标目录的 replicas 下。以后同步会复用相同文件并保留仅在目标端存在的文件。目标文件有独立修改时会提示冲突。 | 原位置 |
| 版本备份 | backups 下每次建立单独版本，随盘保存文件清单、校验值和版本回执。 | 原位置。可选定一个历史版本，用新实验名恢复到运行目录。 |
| 迁移 | 另一个运行目录。 | 相同实验名指向新运行目录。 |
| 归档 | 归档目录。如果已有完全相同的同步副本，将直接使用该副本。 | 相同实验名指向归档盘。拔盘后仍可查询目录和传输记录。 |
| 取消归档 | 选定的运行目录。 | 相同实验名重新指向运行目录，实验保持完成状态。 |

本机已将 `H:\ThreeMindArchive` 登记为 `portable-archive`，供 `E:\ThreeMindData` 中的实验跨盘归档。`H:\ThreeMindData` 继续作为备用运行目录。以下示例使用本机目录标识和示例实验名 `aquatic`。

~~~powershell
threemind storage transfer discover --local --directory primary
threemind storage transfer adopt --local --directory primary --name aquatic
threemind storage transfer preview --local --operation archive --name aquatic --to portable-archive
threemind storage transfer sync --local --name aquatic --to portable-archive
threemind storage transfer archive --local --name aquatic --to portable-archive
threemind storage transfer list --local
threemind storage transfer release --local --job <上一步归档的任务编号>
threemind storage transfer unarchive --local --name aquatic --to primary
threemind storage transfer backup --local --name aquatic --to portable-archive
threemind storage transfer restore --local --name aquatic --backup <备份版本编号> --to primary --as aquatic-restored
~~~

迁移、归档或取消归档完成时，旧副本仍在原盘。页面上的“释放旧副本”和命令 release 会重新核对当前副本和旧副本，再从旧盘释放空间。核对覆盖文件长度、SHA-256、空目录、文件和目录的修改时间，以及 NTFS 创建时间。多个分项分处不同盘时，新建一个公共父目录来容纳它们。访问时间会随系统读取而变化。具有独立用途的硬链接会阻止释放；符号链接、重解析点及 NTFS 额外数据流会阻止普通文件复制。已登记证据通过实验路径与资源定位器跟随迁移。使用绝对旧路径的外部脚本须改用实验名称或现有定位器。

磁盘意外断开后，可按同一任务编号 resume，已复制且通过校验的文件会复用。如果源数据在中断期间发生变化，程序会告知原因。完整的数据盘备份即使换了宿主机，也可用 import-backup --directory <目录标识> --name <实验名> --backup <版本编号> 登记，再通过 restore 还原。数据库中的记录和实验目录以外的公共证据仍使用既有的整机联合备份。pool archive 继续负责 ZIP 分卷打包。

通过 API 访问 /api/v2/storage/experiment-pool/transfers。读取清单、预览和查询任务需要 data.read，启动、恢复和释放需要 data.manage。省略命令中的 --local 使用同一组认证接口。HTTP 启动操作返回任务编号，可按编号查询进度和失败原因。
