# 2026-10-04 追加工具与决定 / Tooling addendum

本条记录E38运行中收到的两项补充；不改变E38登记。This records additions received during E38, without changing its registered experiment.

1. **可消化身体材料 / Digestible material.** 用户批准另版环境。实现`ocean-enclosure/2`：创始体用既有身体额度支付建设费，后代沿用亲代已支付的费用；可配置比例保留为材料，吞食按原效率及容量转移，余量列为损耗。原环境仍只转移储备。The new version retains paid material energy without changing Core or enclosure/shell conditions. It does not silently upgrade old states. Population selection benefit remains untested in this version.
2. **转弯摄食候选 / Turning-to-feed candidates.** 用户希望保存会转弯、最好兼会吞食的个体。新增历史记录筛查和可选实时只读观察器；参数属于观察标准，不限制个体动作。Current retrospective evidence identifies ten post-observation living snapshots from nine individuals across E37 and the first completed E38 segments. None of these initial ten snapshots has enclosure evidence for the same individual. Later segments may add entries; final counts belong in the final report.

候选全部以`.tmspecies`保存并入E38项目物种库。编号只在原海洋内唯一，E37的59号与E38的59号不是同一个体。界面详情包含原始证据、身体、环境协议及谱系。跨项目可以导出后导入；通用图形化海洋投放仍未完成。Candidate snapshots carry exact source-world identity. Library browsing/import/export works in UI/API/CLI; universal graphical population deployment is still open.

**验证 / Validation:** 23 distinct relevant tests passed: material accounting and restoration6, enclosure3, legacy contact8, species assets3, turning observer3. The added zero-construction comparison reproduces original Core states. Frontend build and1440/390px library inspection passed. One test attempt was blocked by Windows temporary-directory permissions; it passed on the authorized retry. A first turning implementation used unsupported NumPy 2D cross product; this was replaced by the explicit 2D determinant before screening any experimental data. No observed experiment was rerun because of this tooling correction.

转弯录像从真实轨迹导出、原速10秒、完整海洋加局部放大。初次把代际面板与局部放大同时开启被导出器拒绝，随后使用既有支持的全景＋放大布局；没有改变轨迹或伪造画面。Turning clips are measured full-habitat replays, not demonstrations in a new one-body arena.

输入记录仅按需顺序读取一次筛查，不重新计算世界，不全量复核旧哈希。Read-only screening scans relevant inputs once; no world simulation or bulk historical hashing.

[决定与原话 / Decision and request](../../../docs/zh/plans/ocean-material-and-turning.md) · [English](../../../docs/en/plans/ocean-material-and-turning.md) · [新环境完整海洋模板 / Template](../../templates/ocean-material-full-habitat.json)
