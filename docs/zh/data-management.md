# 数据管理与存储位置使用指南

日期：2026-10-10。对应已批准的[实施计划](plans/data-management-and-storage-separation.md)。本次只实现通用数据分离、打包和迁移工具；除明确批准的仓库误提交产物归档外，未迁移真实实验、未升级真实用户数据库、未启动或接管用户服务。迁移 060/061 和数据往返只在隔离 PostgreSQL 与临时目录验收。本次 Git 历史清理在本地完成，没有推送远端；远端同步须另行安排。

**同日后补：以上为原交付时的范围记录。用户随后已对日常使用的本地数据库执行增量迁移；原生扩展安装遗漏已修复，本机 `doctor` 的 schema 与 native 检查通过。** 项目当前只有本地环境，原文“正式部署”指日常本地库，区别于隔离测试库，未声称存在线上环境。其他实验数据迁移仍未执行。操作见下文“本机数据库与原生扩展更新”。

## 2026-11-10：日常提交的文件大小规则

作者要求放宽过严的本地限制，避免影响开源贡献。现在普通文件单个不超过 50 MiB 时正常通过；超过 50 MiB、但不超过 100 MiB 时只警告，检查仍返回成功；超过 100 MiB 时拦截。这对应 [GitHub 普通 Git 文件的大小规则](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)，不是 Git 本身的默认限制。论文 Word、PDF 和普通文档不再因达到 1 MiB 而要求逐项登记。

实验原始数据、检查点、完整轨迹和正式数据包仍按原用途规则排除；必要冻结夹具及模板保留原有的有限例外。检查只读取暂存对象，失败不会删除、移动或取消暂存文件。运行 `python scripts/check-git-data.py` 检查本次暂存内容，或加 `--all-tracked` 检查整个索引；修正问题并重新暂存后再提交。详见[当前规则](../../lab/artifact-index/README.md)。以下旧交付记录保留其当时范围。

## 权限和界面

工作台进入“数据与写作 → 数据管理”。项目成员可查询其可见资料；打包计划、导入和原生恢复要求研究者或项目所有者。私有笔记及包含私有资料的数据包保持本人可见，项目所有者身份不会自动获得他人私有笔记。清理候选目录和清理预览要求项目所有者。宿主存储目标、类别策略、离线资料、迁移及仓库归档原件只允许宿主管理员管理或读取。

服务模式使用登录会话和写操作 CSRF；工作站本地身份只接受回环连接。CLI 使用 `--url`、`--username`，密码由本地提示或 `THREEMIND_API_PASSWORD` 提供。远程登录必须使用 HTTPS，不能把账号或密码写进 URL。

资料目录可按项目、实验、个体、种群、批次、数据集、标签及时间筛选。可以选择若干资料，也可以预览当前范围的完整打包。目录中“查看资料”提供类型、版本、来源与恢复边界；完整原始内容通过显式来源对象读取或数据包下载查看。

## 正式数据包

`.tmdata` 使用 `threemind.data-bundle/1`；多卷另有 `.tmdata.json` 总清单。项目资料打包自动收集必要依赖和已保存的完整历史。必要分卷或对象缺失、哈希不一致时拒绝登记或恢复，不生成貌似完整的空附件。每卷最多 8 GiB 压缩载荷，解析另有展开大小、对象数及总量预算；上传还受部署的显式暂存预算约束。CLI 默认传输总量为 8 GiB，可用 `--maximum-bytes` 显式调整；单卷上限不能调整绕过。

SHA-256 校验说明字节与所提供的清单一致，不替代作者身份或原签名验证。原报告分享、权限与签名语义仍按其原格式解释，导入不会据此自动获得权限或恢复旧分享。

把选择写入 `selection.json`，例如：

```json
{"filters":{"experiment":"实验 UUID"}}
```

也可使用 `{"resources":[{"kind":"document","id":"报告 UUID"},{"kind":"note","id":"笔记 UUID"}]}`，或 `{"run":"运行 UUID"}`。CLI 的基本流程：

```powershell
threemind data list --project PROJECT_UUID
threemind data detail --project PROJECT_UUID --kind document --id DOCUMENT_UUID
threemind data export-plan --project PROJECT_UUID --json selection.json --request-id REQUEST_UUID
threemind data export --project PROJECT_UUID --plan PLAN_UUID --request-id EXPORT_REQUEST_UUID
threemind data job-status --project PROJECT_UUID --id JOB_UUID
threemind data bundles --project PROJECT_UUID
threemind data bundle --project PROJECT_UUID --bundle BUNDLE_UUID
threemind data download --project PROJECT_UUID --bundle BUNDLE_UUID --volume 0 --output records.tmdata
threemind data manifest --project PROJECT_UUID --bundle BUNDLE_UUID --output records.tmdata.json
```

多卷下载逐卷指定 `--volume`（从 0 开始）。下载保留 `.partial`，不会覆盖已有证据；正式下载完成后校验记录的字节数和 SHA-256。导入提供全部卷及总清单：

```powershell
threemind data preflight --project TARGET_PROJECT_UUID --file records.tmdata
threemind data import --project TARGET_PROJECT_UUID --file records.tmdata --request-id IMPORT_REQUEST_UUID
threemind data preflight --project TARGET_PROJECT_UUID --manifest-file set.tmdata.json --file part1.tmdata --file part2.tmdata --maximum-bytes 17179869184
threemind data restore-records --project TARGET_PROJECT_UUID --bundle IMPORTED_BUNDLE_UUID --request-id RESTORE_REQUEST_UUID
threemind data object --project TARGET_PROJECT_UUID --bundle IMPORTED_BUNDLE_UUID --id document:SOURCE_DOCUMENT_UUID
```

导入先登记只读来源；报告与调用者的笔记原生恢复是另一步。原生恢复使用新的本地编号，保留来源版本、作者、时间、原始哈希及对应的投影哈希，并映射固定引用和正式附件链接。原始包及来源对象保持原文。原公开分享信息只保留证据，不复活旧 URL、凭据或授权。已知外层包中的未知对象可以只读登记；未知外层格式直接拒绝。

恢复实验主体另用 `resume-plan` 与 `resume`，必须提供来源对象编号，通过对应专用适配器核验后建立暂停副本。通用运行和协调器事实不能直接变成可运行主体；Core-only 状态不能冒充完整主体。旧实验包、语言包、种群或物种包保持各自接口和证据边界，可从原模型库或专用工具进入；旧报告分享 ZIP 也不自动获得原生恢复资格。`threemind data cancel --project PROJECT_UUID --id JOB_UUID --request-id REQUEST_UUID` 取消未提交任务，已经提交的原包和记录保留。

预检和主体恢复须使用同一运行后端。界面“主体恢复运行后端”选择 `native` 或 `reference`，改变选择会使旧预览失效；CLI 在 `preflight`、`resume-plan` 与 `resume` 中传入相同 `--backend`。未显式指定的 REST/CLI 请求使用部署的后端设置，预检返回实际选择的 `backend`。

## 存储目标与迁移

2026-10-10 更新：新增批量研究根变更、数据库载体外置及可选文件检查点，具体范围、命令和恢复边界见[存量迁移指南](storage-migration.md)。下文三类外置范围是原交付时的说明；新增 `checkpoint` 类别仅供明确配置，运行默认仍存数据库。真实库仍为 schema 63，本期实际迁移等待用户清理空间；尚未安装 64，尚未搬迁。[阶段交接](plans/existing-data-migration-stage.md)

PostgreSQL 继续保存权威科学状态。允许外置的类别只有 `media-original`、`note-image`、`export`；离线研究文件使用单独的宿主位置登记。文件目录、S3 兼容对象存储和数据库原件后端有明确目标身份与配置版本。类别策略只影响未来写入，提交时冻结目标版本；更换设置不会暗中重写旧 locator。普通目录或云同步目录须满足路径与普通文件要求，符号链接、Windows reparse point、控制区及私有仓库元数据不能作为资料根。

控制区默认 `data/storage-control`，可由 `THREEMIND_STORAGE_CONTROL` 明确指定；它保存注册、锁、候选和任务回执。目标配置与凭据加密需与应用的 `THREEMIND_SECRET_KEYS` 配置一致，服务端只返回 `has_secret`。S3 凭据通过 UI 的密码字段或 `threemind storage target --json target.json --s3-credentials` 本地提示输入；不要在普通 JSON、命令参数、报告或数据包中保存明文凭据。

`threemind storage inspect` 查看宿主配置。目标注册 JSON 示例：

```json
{"kind":"filesystem","name":"实验原件","path":"E:/ThreeMindData","expected_revision":0}
```

```powershell
threemind storage target --json target.json --request-id REQUEST_UUID
threemind storage policy --category note-image --json policy.json --request-id POLICY_REQUEST_UUID
threemind storage resource-register --json resource.json --request-id RESOURCE_REQUEST_UUID
threemind storage resource --id RESOURCE_ID
threemind storage plan --json migration.json --request-id PLAN_REQUEST_UUID
threemind storage execute --id PLAN_UUID --request-id COPY_REQUEST_UUID
threemind storage status --id PLAN_UUID
threemind storage verify --id PLAN_UUID --request-id VERIFY_REQUEST_UUID
threemind storage activate --id PLAN_UUID --expected-revision RESOURCE_REVISION --request-id ACTIVATE_REQUEST_UUID
```

`policy.json` 含 `target_id` 与当前策略的 `expected_revision`。`resource.json` 含 `resource_id`、`target_id`、`relative_path`、`writer_mode` 和 `expected_revision`；可另显式登记 `legacy_paths`。`migration.json` 含资源编号、目的目标编号、目的相对路径、当前资源版本；`request_id` 可由上述 CLI 提供。`writer_mode=unknown` 只允许检查；`sealed` 必须确实已停止写入；`cooperative` 要求写入程序实际使用存储锁和写入协议，不能靠声明使旧脚本自动安全。

顺序是“计划 → 复制 → 校验 → 单独启用”。复制期间原映射不变，启用后仍保留原件。`resume` 从已核验的文件边界继续，`cancel` 取消复制；`rollback --expected-revision ...` 是有条件的映射回滚，启用后若已有新写入或注册改变，需要反向迁移计划。未知结果先查原请求和对象状态；重试须复用相同请求编号，不能换编号盲目重发。宿主回执可用 `threemind storage receipt --id REQUEST_UUID` 查看。

已归档的仓库误提交实验原件另在“存储位置 → 归档实验原件”分页查询。`threemind storage artifacts --json filters.json` 对精确清单筛选；例如 `{"q":"E63","offset":0,"limit":50}`。`threemind storage artifact --id research-artifact:RESOURCE_HASH --output original.json.gz` 只下载已登记原件，并在服务端核验原始字节哈希；不会扫描任意数据目录。

宿主管理员还可选择已登记且停止写入或遵守协作协议的离线目录，检查后“打包所检查的离线资料”。没有研究项目时也可直接使用宿主存储页面。目录包保存所选范围内的全部普通科学文件及字节哈希，不推断目录外依赖，不虚构项目、运行历史或完整主体恢复能力。它使用正式包格式，导入项目后仍是只读来源档案；报告与笔记的原生还原和专用主体续跑与此不同。

本次获批准的归档资料已登记为 29 个 `archived-study:<原实验目录名>` 封存资源；基准文档数据为 `archived-study:docs`。可在宿主列表直接选择，其余真实实验目录没有据此自动登记或迁移。

```powershell
threemind storage resource --id RESOURCE_ID
threemind storage export --id RESOURCE_ID --expected-revision RESOURCE_REVISION --request-id EXPORT_UUID
threemind storage export-status --id EXPORT_UUID
threemind storage export-manifest --id EXPORT_UUID --output offline.tmdata.json
threemind storage export-download --id EXPORT_UUID --volume 0 --output offline.v001.tmdata
threemind data preflight --project PROJECT_UUID --manifest-file offline.tmdata.json --file offline.v001.tmdata
threemind data import --project PROJECT_UUID --manifest-file offline.tmdata.json --file offline.v001.tmdata --request-id IMPORT_UUID
```

多卷时下载并传入全部分卷；包始终写到固定宿主控制区 `data-transfers/host-EXPORT_UUID`，REST 不接受任意输出目录。查询包回执及下载要求宿主管理员身份。总清单和每卷下载均按登记字节数、SHA-256 核验；打包操作不修改源文件或启用新位置。

## 完整性、清理和备份

完整性检查区分逻辑原件字节、数据库索引/WAL和后端物理占用；不能由逻辑字节推断物理空间。`threemind data integrity --project PROJECT_UUID --verify --maximum-bytes 1073741824` 有界校验本人可见原件。界面复用原实验存储检查与模型库的归档/清理工具。

`threemind data candidates --project PROJECT_UUID --limit 200` 查看未登记的上传候选；候选目录只扫描有界控制日志，不扫描桶或任意目录。未知、未完成或最近上传只能诊断，不能自动删。`cleanup-preview --id CANDIDATE_UUID` 返回引用检查、阻挡原因和预览 token；人工永久执行还须 `cleanup --id ... --token ... --confirm-name ...` 输入准确对象名称。已登记或被引用的不可变原件受到保护，Agent/MCP 清理接口仅允许查询与预览。归档、取消任务和永久删除不是同一操作。

备份由管理员在宿主机手动执行，数据库管理连接仅从 `THREEMIND_BACKUP_DATABASE_URL` 读取：

```powershell
threemind storage backup --pg-bin C:/PostgreSQL/bin create E:/Backups/ThreeMind-2026-10-10
threemind storage backup inspect E:/Backups/ThreeMind-2026-10-10
threemind storage backup --pg-bin C:/PostgreSQL/bin restore E:/Backups/ThreeMind-2026-10-10 --new-database restored_threemind --external-root E:/RestoredThreeMind
```

备份包含数据库、明确登记的外置原件、位置元数据和校验清单，实际加密钥需另行安全保管；`--key-id` 只记录钥的标识，不包含钥值。恢复只允许新数据库和新的外置目录，结果为未启用状态，不能覆盖生产库或替换正在运行的主体。部署 060/061 须由管理员按[运维文档](v2-operations.md)执行明确的数据库迁移，并在部署后重新核验；本次隔离验收不代表真实环境已升级。

## REST、Agent 与报告版本

项目接口以 `/api/v2/projects/{project}/data` 为根，包括目录、详情、`export-plans`、`exports`、`jobs/{id}`、`imports/preflight`、`imports`、`bundles`、`restore-records`、`objects`、`resume-plan`、`resumes`、完整性和清理预览。宿主接口以 `/api/v2/storage` 为根。服务 operation catalog 是 UI、CLI 和 MCP 的共同发现入口，明确项目/宿主范围、权限、回执、人工确认及真实的回滚限制；增加一种传输方式不会绕过业务服务检查。

仓库报告的原 URL 默认仍读原版。只读 `/api/v2/documents/versions?path=...` 查询系列；`content?path=...&revision=2` 指定版，`latest=true` 显式读最新版，两者不能同时指定。`threemind report-revisions versions --path lab/EXPERIMENT/report.zh.md` 查询清单；新修订用 `revise` 提供正文文件、原因、日期、稳定操作 UUID、预期父版号和父版原始哈希。修订声明必须描述实际发生的工作，不能提前声称尚未执行的数据迁移。

报告 `sha256` 保留发布时的原始字节身份。新清单另记录 `canonical_sha256` 与 `canonicalization=utf8-crlf-to-lf/1`，只允许 Git 检出的 CRLF/LF 差异；读取返回实际 `read_sha256`、`byte_identity_matches` 及 `integrity`，明确区分原始字节与 Git 文本身份。旧清单没有该字段时仍严格核验原字节。实验原件、媒体、包和导出字节不会因此放宽验证。

## 本机数据库与原生扩展更新

本地工作站使用 `.work/kernel-venv`。数据库升级与 Rust 扩展安装是两个步骤：`migrate` 自动按顺序补齐 SQL，不编译或更新原生模块；仅设置 `PYTHONPATH=src` 也不能更新虚拟环境中已安装的 `.pyd`。先暂停任务，正常退出工作站及独立 worker，保持 PostgreSQL 运行。

```powershell
Set-Location E:\WORKSPACE\AgentWork\threemind
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

迁移读取项目 `.env` 的 `THREEMIND_MIGRATION_DATABASE_URL`，成功输出 `Schema is up to date.`。`doctor` 验当前 schema、数据库连接及实际原生内核；这不是完整数据往返验收。缺连接配置才补相应变量，不重新执行 `setup-local`。

若源码更新后再次报 `unknown continuous kernel identity` 或缺少 `NativeLocal`，须将当前 Rust 扩展安装到同一解释器环境，不能通过修改旧意识版本或切换默认内核规避。可显式构建 wheel 后安装；以下 `--offline` 要求所需 Rust 依赖已缓存：

```powershell
.\.work\kernel-venv\Scripts\python.exe -m maturin build --release --offline --manifest-path crates/threemind-native/Cargo.toml --out .work/native-update/wheels
.\.work\kernel-venv\Scripts\python.exe -m pip install --no-index --no-deps --force-reinstall .\.work\native-update\wheels\threemind_native-2.0.0-cp311-abi3-win_amd64.whl
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

wheel 名称随实际构建输出；项目版本变化时不要盲用旧文件。2026-10-10 本机已经完成此安装，七种已实现内核可原生加载，无需重复安装。后续正常启动用 `scripts/start-lab.ps1 -Python .work/kernel-venv/Scripts/python.exe`。失败路径现在也会关闭数据库连接池，不留下本次错误中的线程退出等待。没有启动工作站或修改旧个体。
