# 物种库与包裹吞食候选选择

2026-10-04。根据用户补充实施。这里“物种”是研究资产的直观称呼，不把保存一个个体视为证明生物学物种分化。

## 已落地的最小完整保存

“模型与证据 → 物种库”可浏览、搜索、导入和导出当前项目的候选。`.tmspecies` 是 ZIP 容器，包含版本化清单和原始 `.tmind` 意识状态。清单包含身体可遗传性状、完整身体快照、输入输出映射种子、环境协议、来源时刻、祖先与能力证据。界面、API和命令行访问同一数据库记录。每次保存不可变，更正或追加证据另存新版，不覆盖旧候选。

保存并不重新训练，也不把能力说明送进内核。部署为后代时采用既有 `birth/1` 规则：保留结构、清空活动与短时状态；身体继承、初始能量来源明确登记。原快照仍能解码供核对。一个个体包不包含周围海洋的全部状态；原实验的完整世界快照另行保留。

本期图形界面支持库管理。新实验的海洋投放用 Python 工具 `lab.tools.ocean_species.seed_founders`，见 [E38登记](../../../lab/explorations/2026-10-04-ocean-species/design.zh.md) 和 [执行器](../../../lab/explorations/2026-10-04-ocean-species/experiment.py)。通用图形化投放编排仍待接入，不能标为已完成。

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_species save SNAPSHOT 59 candidate.tmspecies --name "包裹吞食候选" --evidence evidence.json
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_species import candidate.tmspecies --project PROJECT_UUID
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_species list --project PROJECT_UUID
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_species export ASSET_UUID exported.tmspecies --project PROJECT_UUID
```

API：`GET/POST /api/v2/projects/{project}/species`；`GET .../species/{id}`；`GET .../species/{id}/download`。上传表单字段 `file`。项目权限与其他研究记录一致。包上限64MiB，拒绝额外条目、状态身份不一致和非有限数值。

## 选择实验

先保存E37的59号300秒状态。其226.06秒发生一次完整包裹；保存状态不是事件发生的瞬间。另开E38：53体完整海洋，其中11体继承候选，其他42体保持原始身体差异；前300秒同供给，之后原供给与减半供给对照。既保留环境选择，也明确人工复制的来源。若未出现重复吞食，不无限追加到成功；候选和阴性结果都保留。

原请求、预算、成功分层及停止条件见[E38中文原话与设计](../../../lab/explorations/2026-10-04-ocean-species/design.zh.md) / [English](../../en/plans/species-library.md)。
