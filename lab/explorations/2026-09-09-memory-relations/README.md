# 重复关联与关系组合 · 2026-09-09

[中文报告](report.md) · [English report](report.en.md) · [预案](protocol.md) · [范围补充](amendment.md)

本轮计算已结束。配对刺激形成了可被探针读出的特异关联，但结果依赖感官编码与探针强度；没有验证出亲属角色的组合迁移。未修改 Core 动力学。

## 在本地平台查阅

选择研究项目 **重复记忆与关系组合 · 2026-09-09**：

- **实验笔记 → 笔记本 → 默认笔记本**：原预案、先导后范围补充、最终图文总结。最终总结中有完整曲线图与原始数据附件链接。
- **记录与报告 → 实验记录**：重复配对、匿名探针敏感性、关系组合三份记录。
- **记录与报告 → 实验报告**：`探索报告：重复关联与关系组合（2026-09-09）`。使用“查看”阅读；已生成 Markdown 和 HTML 及其证据包，可在“导出”中下载。报告图表从冻结分析来源生成。说明区按现有设计只显示图片说明文字，完整科学图片在笔记和本目录。
- **模型与证据／数据查询**：查询本项目900个小型训练或探针意识。900不是独立统计样本数；主分析是8个编码种子，其他探索为2个种子。

项目 UUID：`900840b0-d00d-450c-9669-72600cea7c40`。报告 UUID：`35372970-502a-4b1f-918f-8d7b5be8f05c`。全部其他对象与附件标识、哈希见 [platform.json](platform.json)。对象标识只对当前数据库有效，文件没有包含数据库凭据。

两个便于检查和按需导出的12轮训练父本（种子41203）：

| 模式 | 意识 UUID | 末态哈希 | 节点／边 |
|---|---|---|---|
| 匿名 | `f12416e6-35d5-4af8-9661-cf067add24a3` | `cea701951f1676821bcc237548f1a3ba24c03ce15dc7af4d9f071d6c19ce7c62` | 49／1632 |
| 明文 | `61063d73-440d-4f55-b993-ccf763c3fca5` | `64ccacab97f8d65b0dc3e0c2e1a51dab453b51475e20520ac97c28c8faf2e08e` | 7／24 |

它们是保存的实验末态。探测使用独立副本，原始末态没有被追加训练。

## 复现

使用当前项目已配置的 Python 环境、原生内核与 PostgreSQL；无需启动网页或通用 worker。先在平台新建研究项目，取得它的 UUID。下列命令将生成**新的真实实验数据**，不是查看现有结果；本轮交付过程中不再执行这些命令。

```powershell
$studyProject = "填写新建研究项目的 UUID"
$rawDirectory = ".work/memory-reproduction-new"
$scriptDirectory = "lab/explorations/2026-09-09-memory-relations"
$env:PYTHONIOENCODING = "utf-8"
.venv/Scripts/python.exe "$scriptDirectory/run.py" --phase pilot --attempt 02 --project-id $studyProject --output-dir $rawDirectory
.venv/Scripts/python.exe "$scriptDirectory/run.py" --phase memory --project-id $studyProject --output-dir $rawDirectory
.venv/Scripts/python.exe "$scriptDirectory/run.py" --phase relations --project-id $studyProject --output-dir $rawDirectory
.venv/Scripts/python.exe "$scriptDirectory/run.py" --phase sensitivity --project-id $studyProject --output-dir $rawDirectory
.venv/Scripts/python.exe "$scriptDirectory/analyze.py" --input-dir $rawDirectory --output-dir .work/memory-reproduction-analysis
```

脚本拒绝覆盖同名原始包；不要绕过它删除原始证据后重跑。敏感性阶段复用同一新项目、同一输出目录中 memory 阶段的父本。分析命令只读取结果，不推进模型。若只需重算此次结果，从平台下载各阶段原始 ZIP，把各包内的 `results.json` 分别放成 `pilot-02-results.json`、`memory-results.json`、`relations-results.json`、`sensitivity-results.json`，再执行最后一条命令。

实验原始包内保留实际执行的 `harness.py` 和实现指纹。当前 `run.py` 在计算结束后添加了输出目录／项目参数并进行了格式整理；动力学调用和实验条件未改。实际分析源码也作为平台附件冻结；当前分析脚本随后补充了输入／输出目录参数。需要逐版本审计时，以冻结附件为准。

`publish.py` 是本次数据库的受限发布脚本，使用 `platform.json` 的发布日志重试，只认领自己创建的任务，调用已有来源捕获、记录、笔记和导出服务。**不要用它把另一个复现实验发布成此次报告**。独立复现应使用新的对象和发布日志。

## 预算与验收

实验限单进程、15分钟计算、2GiB进程内存、200MiB原始包、约500MiB项目数据库估计；可用内存低于3GiB或磁盘低于15GiB也停止。数据库预算包含节点／边查询投影和索引估计，不能只数压缩检查点。Codex额度另由代理读取账号用量控制，脚本没有访问或购买额度的能力。

- 原生相同协议10对哈希一致；Python参考重放无结构差异，最大浮点差约 `1.735e-18`，不宣称跨后端逐位一致。
- 3份记录、1份报告、3篇笔记已通过实际服务读取；附件逐个校验 SHA256。
- 页面验收覆盖报告正文、8个冻结数据图表和表格、笔记模式转换、2张完整曲线图、原始包下载链接及 Markdown／HTML 导出。
- 验收中发现 Tiptap Markdown 链接产生的 `title:null` 被后端笔记校验误拒绝。修复只放行受限的链接标题属性，仍校验 URL 和长度；原稿及数值没有被改动。测试覆盖转换后的保存／重读及非法 URL、过长标题拒绝。

采集积压修复的实现、压力场景和限制见 [采集积压验收说明](../../../docs/zh/plans/capture-backlog.md)。
