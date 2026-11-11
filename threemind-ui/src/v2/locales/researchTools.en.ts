const researchTools: Record<string, string> = {
  "按窗口末次激活降序；未收敛的窗口仍如实保留，不能当成收敛答案。":
    "Sorted by final sampled activation. Unconverged windows are preserved and are not treated as converged answers.",
  "末次激活／投影": "Final activation / projection",
  完整原始记录: "Complete original record",
  "此快照没有时序读出记录。": "This snapshot has no temporal readouts.",
  实验包上传载荷: "Uploaded bundle payloads",
  "上传记录需结合实验包引用人工核对；此处不执行删除。":
    "Review uploads together with bundle references before cleanup. This page does not delete data.",
  搜索附件: "Search attachments",
  实验快照: "Experiment snapshots",
  保存实验快照: "Save experiment snapshot",
  "先暂停意识和实验计划。快照保留模型、在途输入、读出上下文与阶段游标。":
    "Pause the consciousness and its research plans first. Snapshots preserve the model, pending signals, readout context and stage cursor.",
  选择意识: "Select a consciousness",
  "附带笔记、报告与工具模型（可选）":
    "Include notes, reports and tool models (optional)",
  附件分类: "Attachment category",
  工具模型和已完成制品: "Tool models and completed artifacts",
  "正在提交…": "Submitting…",
  恢复的意识: "Restored consciousness",
  "查看原始证据；恢复会创建暂停的新意识，不覆盖来源。":
    "Inspect original evidence. Restoration creates a new paused consciousness and preserves the source.",
  证据内容: "Evidence contents",
  "时序读出（主要观察指标）": "Temporal readouts (primary observation)",
  另建身份继续实验: "Continue under a new identity",
  确认并记录外部条件变化: "Acknowledge and record external condition changes",
  新意识名称: "New consciousness name",
  恢复为暂停的意识: "Restore as a paused consciousness",
  "实验包不得超过 8 GiB。": "Experiment bundles must not exceed 8 GiB.",
  "已上传分块与所选文件不一致，请选择原文件。":
    "An uploaded chunk differs from this file. Select the original file.",
  "上传校验失败。": "Upload verification failed.",
  实验快照与交换: "Experiment snapshots and exchange",
  "完整保存当前实验边界，按需下载或在另一台 ThreeMind 上只读导入。模型 .tmind 与实验包用途不同。":
    "Save the committed experiment boundary, download it or import it read-only into another ThreeMind service. A .tmind model and an experiment bundle serve different purposes.",
  "压缩包上限 8 GiB；临时目录保留 15 GiB。原数据不会因打包或导入被清理。":
    "Archive limit: 8 GiB; temporary disk reserve: 15 GiB. Export and import preserve original data.",
  导入实验包: "Import experiment bundle",
  "逐块上传，随后进行整包校验":
    "Uploading chunks, followed by complete verification",
  暂停上传: "Pause upload",
  "重试上传（复用已校验分块）": "Retry upload (reuse verified chunks)",
  尚无实验快照: "No experiment snapshots yet",
  "暂停一个意识后保存快照，或导入已有实验包。导入不会自动运行。":
    "Pause a consciousness to save a snapshot, or import an existing bundle. Import does not start execution.",
  来源修订: "Source revision",
  查看与恢复: "Inspect and restore",
  实验包任务: "Bundle tasks",
  保存快照: "Save snapshot",
  导入校验: "Verify import",
  恢复实验: "Restore experiment",
  查看实验包: "Inspect bundle",
  打开意识: "Open consciousness",
  取消任务: "Cancel task",
  计算工具默认值: "Compute tool defaults",
  "只影响之后新建的 Transformer 任务；意识内核、已有任务和实验协议保持原配置。":
    "Applies to new Transformer tasks. Consciousness kernels, existing tasks and experiment protocols retain their configuration.",
  "显存预留（MiB）": "GPU memory reserve (MiB)",
  "自动选择需要测得稳定至少 20% 加速。GPU 故障的 CPU 重试从同一初始条件开始，不拼接两次轨迹。":
    "Automatic selection requires a measured, consistent speedup of at least 20%. CPU recovery after GPU failure restarts from the same initial conditions; trajectories are not spliced.",
  "打开 Transformer 工具": "Open Transformer tools",
  工作进程报告的设备: "Devices reported by workers",
  "尚无可见工作进程报告；请启动 worker，实际设备以任务证据为准。":
    "No visible worker reports yet. Start a worker; task evidence records the actual device used.",
  未安装可选依赖: "Optional dependency unavailable",
  "AI 与命令行接入": "AI and command-line access",
  "页面、CLI 和 MCP 使用同一服务、权限和校验。先查看协议，再执行；响应不确定时，用原请求编号查询回执。":
    "UI, CLI and MCP share services, permissions and validation. Inspect the protocol before execution. After an uncertain response, query the receipt using the original request ID.",
  "MCP 连接配置": "MCP connection configuration",
  "将命令替换为已安装环境中的 threemind-mcp 绝对路径。服务端账号密码在本地环境变量中填写，不粘贴到聊天。":
    "Replace the command with the installed threemind-mcp absolute path. Set server credentials in local environment variables; do not paste them into chat.",
  "文件传输可选：由宿主设置 THREEMIND_MCP_TRANSFER_DIR；Agent 只能在该目录内交换已校验的实验包。":
    "Optional file transfer: the host sets THREEMIND_MCP_TRANSFER_DIR. Agents can exchange verified bundles only within that directory.",
  可用操作与真实协议: "Available operations and API schemas",
  搜索操作: "Search operations",
  选择操作: "Select operation",
  "浏览器无法建立图形画布，仍可通过数据查询查看记录。":
    "The browser could not create a drawing surface. Records remain available in data queries.",
  "当前使用 Canvas 2D 显示回退；只影响画面，不改变意识计算。":
    "Using the Canvas 2D fallback. This affects display only, not consciousness computation.",
  "重试 WebGL": "Retry WebGL",
  内核版本: "Kernel versions",
  更早记录: "Earlier records",
  设计阶段重复实验: "Design a repeated-stage experiment",
  第几次重复: "Repetition index",
  "匿名帧（原始通道与相对时间）":
    "Anonymous frames (raw channels and relative time)",
  "相对时间（微秒）": "Relative time (microseconds)",
  删除通道: "Remove channel",
  添加帧: "Add frame",
  阶段重复实验: "Repeated-stage experiment",
  结果观察: "Observe results",
  "阶段编辑器需要 research-plan/3 协议。":
    "The stage editor requires research-plan/3.",
  校验通过: "Validation passed",
  次刺激: "stimuli",
  阶段与重复: "Stages and repetitions",
  "每个阶段按顺序执行其中步骤，再按重复次数完整循环；完成后进入下一阶段。重复游标与推进目标会保存，暂停恢复不重新教学。":
    "Each stage executes its steps in order for the specified number of repetitions before the next stage. Repetition cursors and advance targets are saved; resumption does not repeat completed teaching.",
  "阶段协议 JSON": "Stage protocol JSON",
  完整重复次数: "Complete repetitions",
  步骤: "Steps",
  删除步骤: "Remove step",
  添加阶段: "Add stage",
  资源与执行上限: "Resource and execution limits",
  展开后步骤数: "Expanded step count",
  "计算工具与 Agent 接口": "Compute tools and Agent interfaces",
  只读操作: "Read-only operation",
  "写入操作：执行时仍检查权限、修订号与资源限制。":
    "Write operation: execution checks permissions, revision and resource limits.",
  发送匿名刺激帧: "Send anonymous stimulus frames",
  推进模拟时间: "Advance simulation time",
  命名状态引用: "Named state reference",
  实验注记: "Experiment annotation",
};
export default researchTools;
