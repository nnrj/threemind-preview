# 备份与按项目、批次整理数据

[English](../../en/plans/backup-and-cleanup.md)

本轮未清理或重新分析历史研究数据。升级无需先清库；是否保留旧实验，由用户决定。以下步骤供手动操作，程序不会自动执行。

## Navicat 备份

在 Navicat 连接实际的 `127.0.0.1:5433`，选择 ThreeMind 专用数据库 `threemind`，不是初始化用的 `postgres`。使用具备完整读取权限的管理账号；应用账号受项目行级权限限制，不适合直接制作整库备份。

1. 先在 ThreeMind 暂停研究任务、停止采集，再按正常停止流程退出工作站。
2. Navicat 主窗口选择“备份”，建立该库的备份，选择全部对象及数据。
3. 查看执行结果；通过备份文件的“打开所在文件夹”找到实际文件，复制到选定的备份盘。
4. 在另一个新建数据库演练恢复，确认表、函数、触发器、权限及研究记录完整，再考虑清理原库。

菜单名称按 Navicat 版本可能略有不同；上述对应官方手册的 Backup、Object Selection 和 Restore Backup from 流程。[Navicat 16 Windows 手册，第 15 章](https://www.navicat.com/manual/pdf_manual/en/navicat_16/win_manual/navicat_en.pdf)

## 推荐的 PostgreSQL 原生整库备份

ThreeMind 使用 RLS、函数、触发器、约束和数据库内二进制证据。为完整保留数据库定义，建议额外使用 PostgreSQL 自带的 `pg_dump` 自定义归档；它支持压缩及选择性恢复。[PostgreSQL 17 备份说明](https://www.postgresql.org/docs/17/backup-dump.html)

下面由用户在终端执行；路径和管理账号按本机实际情况填写，密码在本地提示中输入，不放进聊天或命令参数：

```powershell
& 'D:\Program Files\PostgreSQL\17\bin\pg_dump.exe' -h 127.0.0.1 -p 5433 -U postgres -d threemind -F c -f 'D:\Backups\threemind-before-cleanup.dump' -W
& 'D:\Program Files\PostgreSQL\17\bin\pg_restore.exe' --list 'D:\Backups\threemind-before-cleanup.dump'
```

使用不存在的新备份文件名，目录事先创建。列出归档内容仅是初步检查，不能代替实际恢复验证。恢复到另一个新建空库，避免覆盖当前库；不要直接使用带删除或原库重建选项的示例。[PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)

`pg_dump` 不备份集群级角色；另行记录 ThreeMind 的 owner、app 角色和授权，跨实例恢复时需要重建。`pg_dumpall --roles-only` 可导出角色，但包含同一实例的其他角色，须由实例管理员按需操作。[PostgreSQL 17 pg_dumpall](https://www.postgresql.org/docs/17/app-pg-dumpall.html)

数据库之外，另外妥善保存项目根目录 `.env`（含加密密钥等本地配置）、当前代码提交及自行导出的模型／证据文件。备份含敏感信息，不加入 Git。导出的一个模型不等于整个研究平台的备份。

## 清理选择

先按项目或实验批次决定保留范围，保留实验设计、原始刺激、协议和种子、来源模型、对照与失败结果、完整读出、分析及报告之间的引用。不能只因结果不支持假设或状态为失败就删除。

确认无保留价值的试操作项目、重复测试批次及未被使用的临时导出，可以列入候选。到“设置 → 实验存储检查”自行发起只读检查，再结合已有模型档案的清理预览核对引用，最后由用户执行明确的清理操作。

不要在 Navicat 中单独清空 `events`、`checkpoints`、`artifact_chunks` 或报告表：这些数据存在外键、不可变记录和证据引用关系。归档只改变可见性，不释放空间；删除后的空间回收也不等于文件立刻缩小。本轮没有新增绕过这些约束的删除脚本，也不要求迁移旧测试数据。
