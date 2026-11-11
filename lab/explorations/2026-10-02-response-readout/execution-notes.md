# 执行记录 / Execution notes

- 2026-10-02：Windows 沙箱拒绝 pytest 临时目录访问。未改权限或项目逻辑，获准在隔离目录运行后相关测试通过。
- 首次离线汇总把 E23 的字符串 `cue="none"` 按布尔真值解释，导致“无提示窗口”计数为 54，遗漏 40 个旧窗口；响应提取、逐点排序与 94 个有响应窗口的判定不受影响。核对源协议后显式把 `X` / `none` 转换，正式结果写入 `.work/response-readout-20261002/verified/`。初次输出及当时的分析脚本保留于父目录，不能将其无提示分组计数引用为正式结果。8 个 live 原始记录本来没有完整活动窗口，不猜测缺失响应。

The initial offline summary treated E23's string `cue="none"` as truthy, undercounting uncued windows (54 instead of 94). Response extraction and simultaneous rankings were unaffected. The corrected analysis explicitly decodes `X`/`none`; verified outputs are separate, with the initial script and outputs preserved. Eight original live runs contain no complete activity window; missing responses are not inferred.

- 首次入库登记因笔记不接受相对 Markdown 链接而停止，留下独立项目登记。发布脚本将文档链接转换为平台 `/docs?doc=...`，并用相同操作 ID 完成登记；不重复创建项目，也不修改笔记校验或内核。/ Initial publication stopped because note validation rejects relative Markdown links. The publisher resolves them to local document URLs and resumes the same registration with idempotent operation IDs.
