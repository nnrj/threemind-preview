const platform: Record<string, string> = {
  任务状态: "Task status",
  文件系统: "File system",
  意识工作台: "Consciousness workbench",
  研究中心: "Research centre",
  资料中心: "Research library",
  系统设置: "System settings",
  文档与帮助: "Documentation and help",
  研究项目: "Research projects",
  用户与权限: "Users and permissions",
  意识档案与模型: "Consciousness archives and models",
  使用文档: "User documentation",
  没有此功能的访问权限: "You do not have access to this feature",
  "可向管理员申请相应功能权限。资料归属和实验状态仍由服务端核验。":
    "Ask an administrator for the required permission. The service also checks ownership and experimental constraints.",
  "请联系管理员检查角色权限。":
    "Ask an administrator to check your role permissions.",
  账户管理分类: "Account management categories",
  角色与权限: "Roles and permissions",
  用户与角色分配: "Users and role assignments",
  "一个用户可拥有多个角色。角色提供功能权限，资料范围另行核验。":
    "A user can hold multiple roles. Roles grant capabilities; access to each resource is checked separately.",
  角色: "Role",
  分配角色: "Assign roles",
  重置密码: "Reset password",
  角色与功能权限: "Roles and capabilities",
  "权限同时约束菜单、按钮和后台接口。超管可访问全部资料；科学锁和历史版本约束仍然有效。":
    "Permissions govern menus, controls and API access. Superadministrators can access all resources; scientific locks and historical revisions remain enforced.",
  新建角色: "New role",
  角色标识: "Role key",
  功能授权: "Capabilities",
  内置角色: "Built-in role",
  全部功能与资料: "All capabilities and resources",
  编辑权限: "Edit permissions",
  删除角色: "Delete role",
  "仅未分配给用户的自定义角色可以删除。内置角色不可删除。":
    "Only unassigned custom roles can be deleted. Built-in roles cannot be deleted.",
  确认删除角色: "Confirm role deletion",
  初始密码: "Initial password",
  "至少 12 个字符。密码不会进入日志或研究记录。":
    "At least 12 characters. Passwords are excluded from logs and research records.",
  角色名称: "Role name",
  "勾选功能及可用资料范围。菜单可见不等于拥有资料操作权限。":
    "Select capabilities and their resource scopes. Menu access does not grant resource operations.",
  保存权限: "Save permissions",
  "将撤销此用户的旧会话；密码不回显。":
    "Existing sessions for this user will be revoked. The password is never displayed.",
  新密码: "New password",
  设置密码并撤销会话: "Set password and revoke sessions",
  我的账号: "My account",
  修改密码: "Change password",
  "修改密码将撤销其他登录会话，当前会话保留。":
    "Changing your password revokes other sessions and keeps this session.",
  当前密码: "Current password",
  确认密码: "Confirm password",
  "密码已更新。": "Password updated.",
  保存密码: "Save password",
  "系统 AI 目录": "System AI directory",
  首次设置本机账号: "Set up the local account",
  "登录 ThreeMind": "Sign in to ThreeMind",
  "为现有 local 身份设置密码，保留全部原有资料与作者关系。":
    "Set a password for the existing local identity. All resources and authorship are preserved.",
  "登录本部署的账号，进入意识工作台。":
    "Sign in to this installation to open the consciousness workbench.",
  记住会话: "Remember session",
  设置密码并进入: "Set password and continue",
  配置来源: "Configuration source",
  系统新建默认值: "System creation defaults",
  模板: "Template",
  项目预设: "Project preset",
  "采用所选配置，替换草稿": "Apply selected configuration to draft",
  "项目只决定保存位置和访问权限，不改变当前配置草稿。":
    "The project determines storage and access, without changing this configuration draft.",
  新建归属项目: "Create destination project",
  创建项目并选用: "Create and select project",
  创建后立即启动: "Start immediately after creation",
  创建并准备: "Create and prepare",
  "请先选择归属项目，或新建一个项目。":
    "Choose a destination project or create one first.",
  "已将所选配置复制到草稿；只有再次采用才会替换草稿。":
    "Selected configuration copied to the draft. It changes only when you apply another configuration.",
  "先编辑意识配置，再选择保存项目。默认创建后保持未启动；已有意识的配置不会改变。":
    "Edit the configuration, then choose a destination project. New instances are prepared by default; existing instances are unchanged.",
  未启动: "Not started",
  启动: "Start",
  "查看不改变运行状态；离开页面也不会暂停意识。":
    "Viewing does not change the runtime state. Leaving this page does not pause the consciousness.",
  "尚未启动。配置已保存，点击“启动”后才会推进模拟时间。":
    "Not started. Configuration is saved; simulation time advances only after you click Start.",
  "创建、打开和观察意识。运行与刺激由你明确控制。":
    "Create, open and observe consciousnesses. Running and stimulation require explicit actions.",
  "打开一份意识，观察它的变化": "Open a consciousness and observe its changes",
  "这里展示意识网络、属性、刺激与读出。进入页面不会自动启动意识或开启设备。":
    "View the network, properties, stimuli and readouts. Opening the page does not start the consciousness or enable devices.",
  最近创建的意识: "Recently created consciousnesses",
  查看全部意识: "View all consciousnesses",
  "尚无意识。可以先编辑新建配置，再选择保存项目。":
    "No consciousnesses yet. Edit a new configuration first, then choose a destination project.",
  "打开只查看原实例，不自动运行、克隆或恢复到历史状态。":
    "Opening views the original instance without automatically running, cloning or restoring it.",
  搜索意识: "Search consciousnesses",
  项目筛选: "Project filter",
  全部有权访问的项目: "All accessible projects",
  包含已归档: "Include archived",
  "此范围内没有意识。请调整筛选，或新建意识。":
    "No consciousnesses in this scope. Adjust filters or create one.",
  内核: "Kernel",
  我的通知: "My notifications",
  项目通知规则: "Project notification rules",
  "项目选择已授权的邮件服务，并保存自己的事件订阅与接收人。传输凭据在系统设置中维护。":
    "Projects select authorised mail services and store event subscriptions and recipients. Transport credentials are managed in system settings.",
  邮件服务: "Mail service",
  仅站内通知: "In-app notifications only",
  启用通知: "Enable notifications",
  发送邮件: "Send email",
  邮件接收人: "Mail recipients",
  事件订阅: "Event subscriptions",
  保存通知规则: "Save notification rules",
  宿主邮件服务: "Host mail services",
  "这里配置传输和凭据。项目在自己的配置中选择服务与通知规则。":
    "Configure transports and credentials here. Projects select services and notification rules in their configuration.",
  添加邮件服务: "Add mail service",
  查看与编辑: "View and edit",
  尚无邮件服务: "No mail services",
  "没有邮件服务也可保留站内通知。":
    "In-app notifications remain available without a mail service.",
  邮件传输方式: "Mail transport",
  启用服务: "Enable service",
  "SMTP 安全方式": "SMTP security",
  "API 密钥": "API key",
  "密钥已配置；留空保留。": "A key is configured; leave blank to retain it.",
  "清除 API 密钥": "Clear API key",
  "密码已配置；留空保留。":
    "A password is configured; leave blank to retain it.",
  "清除 SMTP 密码": "Clear SMTP password",
  保存服务: "Save service",
  "项目组织实验、意识与研究资料；系统服务和显示偏好独立管理。":
    "Projects organise experiments, consciousnesses and research resources. System services and display preferences are managed independently.",
  返回项目列表: "Back to projects",
  项目不可访问: "Project unavailable",
  "请返回项目列表检查权限或项目身份。":
    "Return to the project list to check access and identity.",
  查看项目配置: "View project configuration",
  尚无研究项目: "No research projects",
  "可以先在意识工作台编辑新建配置，保存时再创建或选择项目。":
    "Edit a configuration in the workbench, then create or select a project when saving.",
  项目概况: "Project overview",
  项目创建预设: "Project creation preset",
  项目成员: "Project members",
  观察者: "Observer",
  保存项目名称: "Save project name",
  "项目预设只在新建时主动选用，不会覆盖现存意识或新建草稿。":
    "Project presets are applied explicitly during creation. They never overwrite existing instances or drafts.",
  "个人显示偏好、宿主服务与新建意识默认值分别管理。项目预设在研究项目中查看，已有意识在工作台调整。":
    "Manage personal display preferences, host services and creation defaults separately. View project presets under Research projects and existing instances in the workbench.",
  新建意识默认值: "Consciousness creation defaults",
  存储与迁移: "Storage and migration",
  配置模板: "Configuration templates",
  "这些显示偏好仅保存在本浏览器，并按登录账号分别保存。不会改变意识动力学。":
    "These preferences are stored in this browser separately for each account. They do not change consciousness dynamics.",
  "系统默认配置已保存，仅用于以后新建的意识。":
    "System defaults saved for future instances only.",
  新建意识的系统默认配置: "System defaults for new consciousnesses",
  "在选择项目之前配置新意识。已有意识始终使用其保存的配置；项目历史配置在项目详情中查看。":
    "Configure a new instance before choosing a project. Existing instances keep their saved configuration. Historical project configurations are in project details.",
  当前新建默认内核: "Current default kernel for creation",
  内核工厂默认: "Kernel factory defaults",
  系统保存配置: "Saved system configuration",
  保存系统默认配置: "Save system defaults",
  创建配置模板: "Creation configuration templates",
  "模板保存内核、感官外设、身体和运行协议的配置，不包含个体状态或学习权重。":
    "Templates contain kernel, peripheral, body and runtime configuration. They exclude instance states and learned weights.",
  新建模板: "New template",
  尚无创建模板: "No creation templates",
  "可以直接使用系统默认配置创建意识，也可保存常用配置为模板。":
    "Create with system defaults, or save frequently used configurations as templates.",
  模板名称: "Template name",
  保存模板: "Save template",
  新建笔记: "New note",
  新建世界或躯体: "New world or body",
  编写记录或报告: "Write a record or report",
  "导入、导出与数据操作": "Import, export and data operations",
  创建对话实验: "Create conversation experiment",
  创建比较实验: "Create comparison experiment",
  导入与模型管理: "Import and model management",
  创建实验: "Create experiment",
  请选择研究项目: "Choose a research project",
  "选择项目后查看其执行队列和额度。":
    "Choose a project to view its execution queues and limits.",
  平台: "Platform",
  成员项目: "Member projects",
  菜单: "Menus",
  意识: "Consciousness",
  查看意识: "View consciousness",
  启动与继续: "Start and resume",
  sender: "Sender",
  smtp_host: "SMTP host",
  smtp_username: "SMTP username",
  smtp_port: "SMTP port",
  timeout_s: "Timeout (s)",
  cooldown_s: "Cooldown (s)",
  daily_email_limit: "Daily email limit",
  structure_recurrence: "Structure recurrence",
  run_completed: "Run completed",
  run_failed: "Run failed",
  run_dead: "Model activity exhausted",
  run_blocked: "Run needs attention",
  export_ready: "Export ready",
  analysis_ready: "Analysis ready",
  job_failed: "Background job failed",
  execution_health: "Execution health warning",
  工作台面板: "Workbench panels",
  "属性、刺激与读出": "Properties, stimuli and readouts",
  授权项目: "Authorised projects",
  "项目通知规则 JSON": "Project notification rules JSON",
  "停止领取新任务不终止已有租约，也不改变意识动力学。":
    "Stopping new job claims does not terminate existing leases or change consciousness dynamics.",
  "在同一界面管理用户、多角色和功能授权。科研资料仍保留原有身份与修订。":
    "Manage users, multiple roles and capabilities in one interface. Research identities and revisions are preserved.",
  "SMTP 主机": "SMTP host",
  "SMTP 用户名": "SMTP username",
  "SMTP 端口": "SMTP port",
  "超时（秒）": "Timeout (s)",
  "冷却间隔（秒）": "Cooldown (s)",
  每天邮件上限: "Daily email limit",
  "已将所选配置复制到草稿；保存归属不会再次替换草稿。":
    "Selected configuration copied to the draft. Changing the destination will not replace it.",
  "请选择归属项目，或新建一个项目。":
    "Choose a destination project or create one first.",
  "先编辑正文，保存时选择项目；保存后可继续关联数据与编辑完整内容。":
    "Draft the content first and choose a project when saving. You can then link data and continue editing.",
  保存并继续编辑: "Save and continue editing",
  "默认退出后意识继续运行。账号过期、断网或关闭页面也不会自动暂停；只有明确选中的实例才会请求暂停。":
    "Consciousness keeps running after logout by default. Session expiry, disconnection or closing the page does not pause it. Only explicitly selected instances receive a pause request.",
  "可选：暂停这些实例后退出": "Optional: pause these instances before logout",
  "此实例由实验管理，不能独立暂停。":
    "This instance is managed by an experiment and cannot be paused independently.",
  已确认暂停: "Pause confirmed",
  "没有正在运行且可访问的实例。": "No accessible running instances.",
  查看更多实例: "Load more instances",
  "正在确认所选实例已暂停，请保持此窗口。":
    "Confirming that the selected instances have paused. Please keep this dialog open.",
  "实例 {name} 尚未确认暂停，账号保持登录。请查看实例状态后重试。":
    "Pause has not been confirmed for {name}. You remain signed in. Check the instance state before retrying.",
  "暂停 {count} 个实例后退出": "Pause {count} instances and log out",
  "退出，意识继续运行": "Log out and keep consciousness running",
  项目资料工具: "Project data tools",
  项目执行队列: "Project execution queues",
  "暂停已提交，等待确认": "Pause submitted; awaiting confirmation",
  "已受理的暂停不会撤销；重试只查询这些实例的暂停结果，不重复发送命令。":
    "Accepted pauses remain in effect. Retrying checks their result without sending the command again.",
  "关闭（已提交的暂停仍有效）": "Close (submitted pauses remain in effect)",
  "没有此实例的暂停权限。":
    "You do not have permission to pause this instance.",
  "保存后该用户的旧会话将被撤销。":
    "Saving revokes this user's existing sessions.",
  保存新密码: "Save new password",
  "选择所属项目后可从机器人库选择；自定义协议也可在 JSON 中配置。":
    "Choose a destination project to select a stored robot, or configure a custom protocol in JSON.",
  "选择所属项目后可从世界库选择；自定义协议也可在 JSON 中配置。":
    "Choose a destination project to select a stored world, or configure a custom protocol in JSON.",
  应用研究预设: "Apply research preset",
  标题: "Title",
  "先配置新意识，再选择保存归属。默认创建后保持未启动，已有意识的配置不会改变。":
    "Configure the new consciousness first, then choose its destination. It remains unstarted by default. Existing instances keep their configuration.",
  "此处管理已选项目的对象和工具。各资料菜单仍提供统一的跨项目列表。":
    "Manage objects and tools for this selected project. Resource menus continue to provide a unified cross-project list.",
  实验与训练工具: "Experiment and training tools",
  世界与躯体工具: "World and body tools",
  模型与导入导出工具: "Model and transfer tools",
  项目数据管理: "Project data management",
  "存储配置由具有系统管理权限的账号修改；只读账号可查询与核验。保存配置只影响未来写入。":
    "Accounts with system management permission can change storage configuration. Read-only accounts can inspect and verify it. Configuration changes affect future writes.",
  "请在上方选择内核版本，JSON 不能更换内核。":
    "Select the kernel version above; JSON cannot switch the kernel.",
  内核参数: "Kernel parameters",
  内置配置模板: "Built-in configuration template",
  当前参数: "Current parameters",
  采用项目预设: "Use a project preset",
  预设来源项目: "Preset source project",
  采用预设参数: "Use preset parameters",
  "项目预设与当前内核不同，不能作为此内核的模板。":
    "The project preset belongs to another kernel and cannot configure this kernel.",
  "此历史内核采用自己的帧感官编码规则，文字节点编码由 sensory_encoding 设置。":
    "This historical kernel has its own frame sensory encoding; sensory_encoding controls text node encoding.",
  系统默认模板: "System default template",
  "此内核使用 Python 实现；不会替换为其他内核版本。":
    "This kernel uses its Python implementation; no other kernel version is substituted.",
  "所选模板不属于当前内核。":
    "The selected template belongs to another kernel.",
  "模板参数已载入；可以继续调整，已有意识不会改变。":
    "Template parameters loaded. You can continue editing; existing consciousnesses are unchanged.",
  "已基于所选模板修改参数。":
    "Parameters have been modified from the selected template.",
  "模板只设置当前内核的参数，可以继续手动调整。":
    "The template configures this kernel; parameters can also be edited manually.",
  将当前参数保存为模板: "Save current parameters as a template",
  "当前参数已保存为模板，不包含个体状态或学习权重。":
    "Current parameters saved as a template, without individual state or learned weights.",
  "替换当前参数？": "Replace current parameters?",
  "当前参数已有修改。采用新内核或模板将替换这些修改，取消会保留当前草稿。":
    "Parameters have been edited. Choosing another kernel or template replaces those edits; cancelling preserves the draft.",
  替换参数: "Replace parameters",
  从此实例参数创建模板: "Create a template from this instance",
  "仅复制已保存的参数，不复制个体状态、学习权重或实验身份。":
    "Copies saved parameters only, without individual state, learned weights or experiment identity.",
  "当前参数已有修改。切换内核将替换这些修改，是否继续？":
    "Parameters have been edited. Switching kernels replaces those edits. Continue?",
};
export default platform;
