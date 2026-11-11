# 平台登录与 AI、脚本访问

本说明对应 2026-10-11 的平台层级调整。Lab 默认需要平台登录；Core 的动力学与独立 Runtime 本机执行不需要平台账号。平台账号不写入个体配置、模型包或检查点。

## 首次设置和浏览器会话

本机尚无可登录超级管理员时，WebUI 显示首次设置，设置用户名和至少 12 字符的密码。它为原本的本地账号设置登录方式，保留已有项目、个体和研究资料归属；不会重建数据。已有可登录账号时直接登录。

正式 Lab 在本机和服务端均要求登录，不再提供免登录的 `authentication=local` 模式；`THREEMIND_AUTHENTICATION` 只能设置为 `session`。这不影响独立 Runtime 的本机免平台登录运行。

普通会话有效期为 12 小时，“记住登录”为 30 天。页面刷新和关闭页面不暂停意识；退出只撤销相应会话，不停止后台任务。另一个浏览器或 CLI 的会话不因此一并退出。超级管理员可访问全部个人资料；其他角色的访问范围由操作权限、资料范围和项目成员关系共同决定。

## CLI 登录和受保护配置

在仓库根目录使用实际的 Python 环境。以下以现有环境为例：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth login --username local --interactive --remember
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth status
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli ops list
```

如果首次设置时修改了用户名，把示例中的 `--username local` 换为实际用户名。单人使用可直接以超级管理员登录一次并复用该配置，不强制为每个实验签发限定委托；有限委托是按需要收窄 AI／脚本权限的可选方式。

`--interactive` 仅在交互终端提示密码。AI、脚本默认不交互：没有凭据时立即给出明确错误，不挂起等待密码。一次登录保存可跨命令、跨进程复用的会话；普通命令结束不会退出账号。客户端在会话接近到期时刷新，主动刷新可用 `auth refresh`；过期后需重新登录。

默认配置名为 `default`，可用 `--auth-profile research` 选择另一份。每份配置与 API origin 绑定，不向另一服务发送凭据。Windows 默认保存在当前用户 `%LOCALAPPDATA%\ThreeMind\auth`，由当前 Windows 用户的 DPAPI 加密；POSIX 使用当前用户的私有目录和文件权限。配置中不保存密码。`--auth-dir` 或 `THREEMIND_AUTH_DIR` 可指定保护区位置；它是宿主控制资料，不是实验原件，不应提交 Git、打进实验包或发送给 AI。

```powershell
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth logout --auth-profile default
```

账户会话退出会请求服务撤销并清除本地配置。委托配置退出仅移除本地凭据，需由签发人使用 `auth revoke` 撤销服务端委托。不同平台会话不会因普通客户端关闭被撤销。

## AI 的有限委托

聊天授权表示可以做什么；平台凭据证明由谁执行，两者不能互相代替。AI 使用原签发人的身份，并另记执行来源和委托编号；它不会自动获得超级管理员身份。

签发前确定目标资源、操作与期限。下面为某一个项目的读取、刺激和研究记录委托示例；将占位项目编号替换为真实 UUID，截止时间由命令生成，按实际任务删减操作：

```powershell
$delegation = @{
  name = 'AI research session'; source = 'ai'
  actions = @(
    @{ action = 'runs.read'; scope = 'member_projects' }
    @{ action = 'runs.stimulate'; scope = 'member_projects' }
    @{ action = 'research.read'; scope = 'member_projects' }
    @{ action = 'research.write'; scope = 'member_projects' }
  )
  resources = @(@{ kind = 'project'; id = '<真实项目 UUID>' })
  expires_at = [DateTimeOffset]::UtcNow.AddHours(8).ToString('o')
}
$delegation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath .work\ai-delegation.json -Encoding utf8
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth delegate --json .work\ai-delegation.json --delegate-profile ai-research
```

定义文件没有密钥。签发命令将一次性返回的委托凭据直接保存为独立受保护配置，不在输出中打印 token；已有目标配置不会被覆盖。委托必须限制至少一个资源，有效期最长 30 天，不得超过签发人的当前权限，不能管理账号、角色或再签发委托。资源可为 `project`、`run`、`experiment` 或 AI `service`；选定子资源不会授权整个项目列表。

```powershell
$env:THREEMIND_AUTH_PROFILE = 'ai-research'
$env:THREEMIND_EXECUTION_SOURCE = 'ai'
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --project '<真实项目 UUID>'
# 签发人可从自己的账户配置查询并撤销：
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth delegations --auth-profile default
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth revoke --auth-profile default --id '<委托 UUID>'
```

委托到期、撤销、原账号停用或原角色权限收窄都会生效；委托不能自行刷新。任务权限不够时补齐具体委托或让签发人操作，不切换为隐式本地超级管理员。外部 AI 服务的目录读取、配置管理与实际调用是不同权限，管理服务不自动授权花费调用。

自动 AI 环境、解释和生态观察在保存配置时记录原执行账号及委托。后续调度与实际发送前重新核验当前权限；有限委托失效后不会借用账号的完整权限继续。启用自动调用需要服务使用权限及其目标操作权限，续用时须签发新委托并显式保存配置。普通会话退出不会暂停后台工作，撤销或到期的委托则停止其授权的后续操作；已经发出但结果未知的请求保留“不确定”状态，不自动重发。

## 非交互来源、REST、MCP 和 Python

共用以下宿主环境变量，不需要读取浏览器 Cookie：

| 变量 | 用途 |
|---|---|
| `THREEMIND_API_URL` | API origin；默认 `http://127.0.0.1:8877` |
| `THREEMIND_AUTH_PROFILE` / `THREEMIND_AUTH_DIR` | 选择受保护配置与保护区 |
| `THREEMIND_API_TOKEN` | 宿主显式提供 Bearer 凭据，优先于配置；不自动落盘 |
| `THREEMIND_API_USERNAME` / `THREEMIND_API_PASSWORD` | 兼容宿主提供的账号密码；用于签发可复用会话，不写入配置 |
| `THREEMIND_EXECUTION_SOURCE` | `human`、`ai` 或 `script`，仅执行来源，不赋权 |

远端 API 使用 HTTPS。本机回环 HTTP 可用；工作站模式仍仅接受回环访问。MCP 使用 `python -m threemind_lab.mcp_server` 的 stdio 入口和同一配置，默认标记来源 `ai`。普通实验操作不要求每一步人工登录；明确敏感的操作继续使用其人工确认流程。

REST 的 `POST /api/v2/auth/token` 返回 Bearer 会话，`POST /api/v2/auth/refresh` 旋转会话，`GET /api/v2/me` 核验身份。委托使用 `/api/v2/account/delegations` 的列表、签发和单项撤销接口。Cookie 写请求仍需 CSRF，Bearer 无需浏览器 Cookie。密钥不写入协议、报告、回执或实验记录。

Python 脚本使用 `OperationsClient.from_environment(source='script')`；记录器可用 `ResearchRecorder.from_environment(directory, project, source='script')`。AI 可将来源改为 `ai` 并选择委托配置。记录器按原规则持久化登记、阶段、原件、报告与结项，不触发 Core 运算。服务暂时不可用时保留待同步记录；原件不能可靠保存时宿主必须停止继续推进。

断线或响应不明时，先查询原请求编号的回执，再决定重试；不要另造编号重做刺激。客户端不在 401 后自动重新登录并重放写请求。恢复录入日志只是恢复记录渠道，恢复意识仍须使用其完整系统检查点。

## 独立 Runtime 边界

独立 Python/Rust Runtime 的本机库和命令行执行保持免平台登录。当前命令行没有网络管理服务。以后由宿主暴露网络接口时，其监听范围、认证或可信代理门禁属于宿主部署配置；不在 Core 中引入账号、密码或权限动力学。模型原件也不携带平台会话。
