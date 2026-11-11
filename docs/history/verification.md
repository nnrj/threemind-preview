# 史书初编验收 / History compilation verification

日期 / Date: 2026-10-01

## 交付与取证范围

四个版本共 53 个目录条目：现代中文、英文各 22 篇，文言纪传体 5 卷、文言编年体 4 卷。条目包括正文、史料、索引和凡例，不把目录全目算成新的实验报告。编纂前文献登记 389 个已跟踪 Markdown 文件，选录首期《ThreeMind项目》20 条原始消息，保留消息身份、时间和文本校验值。

史书直接读取项目文档，未建立数据库副本。此次没有运行新的动力学实验，没有修改 Core、历史意识、实验结果或模型版本，没有扫描大型 `data/`。日期与决策取证的不足写在各章，不用文学改写填补。

## 验证结果

| 检查 | 结果与边界 |
| --- | --- |
| `tools/validate_history.py` | 4 版、53 条目通过；现代双语对应、目录完整性与本地链接有效。不会把原话中的过期历史链接改写为新链接。 |
| 原话校验 | 20 条选录文本的 UTF-8 SHA-256 与登记值逐条相符；校验值用于发现后续变动，不代替对原始会话的取证。 |
| 文档后端 | `tests_v2/test_history.py` 与 `tests_v2/test_doc_resources.py` 共 8 项通过；覆盖目录、双语读取、HTTP 只读与路径／资源边界。未连接实验数据库。 |
| 前端生产构建 | TypeScript 检查与 Vite 构建通过；既有图形、笔记等大包仍有超过 500 kB 的构建提示，本次未改其打包方案。 |
| 浏览器交互 | `e2e/history.spec.ts` 共 3 项通过：1440 与 390 像素视口、英文界面与文档入口。覆盖四版切换、搜索、原件往返、页内定位及刷新、报告图片、源码与下载、错误入口，无页面脚本错误或整页横向溢出。 |
| 视觉检查 | 实际检查桌面、手机视口截图，正文可读，手机目录折叠，不让长目录挤走正文。自动截图保存在忽略的 `.work/browser-results/` 中，不作为实验数据提交。 |
| Python 静态检查 | 新增文档路由、阅读服务、验证器、相关文档服务及测试通过 Ruff。 |

验收使用临时的 `127.0.0.1:8911` 只读服务，没有启动数据库或实验 worker，也没有重启正在使用的 ThreeMind 服务。这不是生产服务部署或真实移动设备验收；正常 Lab 在重启加载新代码后提供新增接口，前端需使用本次构建。独立阅读器启动办法见[说明](README.md)。

## Delivery and evidence scope

The four editions contain 53 catalogue entries: 22 modern Chinese, 22 English, five Classical Chinese biographical volumes and four Classical Chinese chronological volumes. Entries include narrative, sources, inventories and editorial rules. The frozen source inventory lists 389 tracked Markdown documents; 20 selected original messages from the early ThreeMind conversation retain identity, time and text hashes.

The reader serves Markdown directly, without a second database copy. This compilation ran no new dynamics experiments, changed no Core behavior, old instances, model identities or experimental results, and did not scan the large `data/` directory. Missing historical evidence remains explicitly missing.

Validation passed: catalogue and local links; all 20 archived text hashes; eight focused Python tests; the TypeScript/Vite production build; and three browser tests covering desktop/mobile layouts, four editions, English UI, chapter search, original-source navigation, anchors, figures, Markdown and downloads. Desktop and mobile screenshots were also inspected. Existing large-bundle warnings remain; no claim is made that these bundles were optimized.

Tests used an isolated, loopback-only reader on port 8911, without PostgreSQL or workers. No existing Lab service was restarted. Browser viewport checks do not substitute for physical-device testing or deployment. The normal Lab service loads the new routes on its next restart; see the [reader instructions](README.md) for database-free access.
