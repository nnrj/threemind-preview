# 全局资料浏览与项目归属

[English](../en/global-resource-browsing.md) · [批准计划与验收](plans/global-resource-browsing.md) · [实验总览与统一记录](research-records.md)

2026-10-10 调整后，研究概览及主要资料菜单默认展示全部有权访问的项目。项目仍标识资料归属和成员权限；浏览时无需先猜资料存在哪个项目。

## 浏览、筛选与操作

- **研究概览**汇总可访问资料，展示可搜索、分页的项目列表；点击“按此项目浏览”主动缩小范围。
- 侧栏 **浏览范围 → 全部项目**是默认值。选择具体项目后，在各菜单中继续使用该筛选；刷新页面重新从全局开始。旧 `tm2.project` 浏览器偏好不再隐式生效。
- 实验、比较、世界、对话、数据、模型、笔记、记录与报告、数据管理均有跨项目资料列表，显示所属项目、类型、状态和更新时间，支持搜索与分页。笔记继续只显示本人有权访问的正文；私人资料包及其载体保持原权限。
- **记录与报告**可按实验记录／报告分类；**实验笔记**可按笔记／草稿分类；**模型与证据**可按意识、先天模型、物种、附件和归档包等类型筛选。归档资料需主动选择归档筛选。
- 点击资料进入所属项目的详情或原有工具，顶部明确显示 **所属项目**。旧意识链接按已授权的对象身份定位，并补入所属项目链接参数；编辑器切换页签不会丢掉归属。“返回全部资料”清除详情及浏览筛选。
- 新建意识先显示 **所属项目**选择；全局浏览时不默认选择第一个项目。其他新增／导入／管理操作通过“新建或管理资料”选择项目后使用原有工作区。若已主动选择浏览项目，会显示该项目作为可确认的归属。
- 打开旧资料不会将其移动到浏览筛选中的项目。设置中的项目默认、外部工具、通知与执行资源等操作也明确选择归属；显示、设备与主机存储设置继续使用其原作用范围。

数据库中只有索引、原件引用或历史协议的内容，仍从实验详情访问原件；全局列表不会伪造新的原生世界、运行或模型。计数是保存资料的数量，不是成功实验次数。

## 启用与只读接口

本机本次已显式执行 schema 63 迁移，前端已构建。若 ThreeMind 正在运行，按原方法正常停止并重新启动，再刷新浏览器即可；本次没有接管该服务。其他本地副本更新代码后执行：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
```

这只是数据库结构／元数据读取策略升级，不是实验数据搬迁。原始资料、旧个体、原报告和修订链保持。

三个新增查询沿用现有登录身份：

- `GET /api/v2/browse/overview`：资料数量及项目列表，支持 `project`、`q`、`offset`、`limit`，项目页默认 12 条。
- `GET /api/v2/browse/resources`：`kinds` 指定类型，支持 `project`、`q`、`subtype`、`archived=active|archived|all`、`offset`、`limit`。资料页默认 50 条，最大 100 条。
- `GET /api/v2/browse/location/{kind}/{id}`：按身份解析有权访问的资料归属；不可访问的对象明确报错。

没有 `project` 时查询全部授权项目，有此参数时必须验证成员资格。查询使用只读事务和固定元数据投影，不读完整轨迹／检查点字节，不进行刺激、恢复、学习或新建笔记本；不提供跨项目批量写入。

## 开发验收复现

后端测试使用 `tests_v2/conftest.py` 指定的隔离 PostgreSQL 测试集群（默认 55439），自动创建、删除各自临时数据库。

浏览器验收先启动该测试集群，再在一个终端运行：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe tools/browsing_acceptance_server.py
```

该辅助程序不读取 `.env`，在固定隔离集群创建合成资料，提供 `127.0.0.1:8898` 页面，且不启动模拟 worker。另一个终端构建前端并执行：

```powershell
cd threemind-ui
npm run build
$env:THREEMIND_E2E_URL = 'http://127.0.0.1:8898'
$env:THREEMIND_BROWSE_FIXTURE = "$PWD\..\.work\global-browse-ui-fixture.json"
node node_modules/@playwright/test/cli.js test e2e/globalBrowsing.spec.ts
```

结束时在仓库根运行 `Set-Content .work/global-browse-ui.stop stop` 或对验收服务按 Ctrl+C；辅助程序退出并删除自身临时数据库。合成资料和截图仅作工程验收，不登记为正式科研实验、不进入 Git。
