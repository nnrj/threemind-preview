# E24 · Target response and matched telemetry controls

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


[中文报告](report.zh.md) · [English report](report.en.md) · [中文设计](design.zh.md) · [English design](design.en.md) · [执行记录 / Execution notes](execution-notes.md)

## UI

选择相应实验项目，在“刺激与输出”的已保存活动读出中打开过程分析，使用 **目标响应与局部收敛**。填入目标节点 ID，点击分析；高级项可调整窗口与阈值。页面保留全局分类，另列目标轨迹、积分、末态、局部判定及完整 JSON 下载。未知节点会报错。目标应在确认性实验前指定；事后选取属于探索。

The target card supplements saved process readouts. It does not replace the original classification or alter the model. Desktop and mobile use the same analysis API. Full-data export is independent of timeline pagination.

## CLI / Python / API

The operation catalog exposes `observation.target`; the existing observation batch protocol accepts the same `target` tool and options. Python uses `threemind_runtime.observation_tools.analyze_targets`.

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_runtime.observation_cli target --input readouts.jsonl --window WINDOW_ID --node-ids 1 3 --settle-us 800000 --output targets.json
```

Use actual IDs from the selected record; `1 3` refers to the representative E24 AB example, not every model. Output must be a new file. Compressed JSONL input is supported, bounded at 64 MiB decompressed.

```text
GET /api/v2/projects/{project}/runs/{run}/readouts/{record}/target?node_ids=1,3
GET /api/v2/projects/{project}/runs/{run}/readouts/{record}/target?node_ids=1,3&download=true
```

Defaults: `settle_us=800000`, `pattern_drift_max=0.08`, `amplitude_drift_max=0.12`, `response_floor=1e-8`, `epsilon=1e-12`. The tool accepts complete saved activation vectors, rejects unknown IDs and does not infer omitted top-k nodes as inactive. First local decisions rank actual activation at that time. No decision is null; recorded terminal zero remains zero.

## Evidence and reproduction

`run.py` has prepare/acquire/matrix/expression/live stages. Each stage resumes only its own completed cases; frozen designs/config/source identities are checked. `calibrate.py` reads E23 without new simulation. `analyze.py summarize` and `audit` read saved evidence; `figures.py` produces PNG/SVG. Outputs use exclusive creation. Do not delete old results to rerun: use a separately registered study and new work directory.

Raw local evidence is in `.work/target-background-20261002`, also archived in the study's ThreeMind project through `publish.py`. The archive includes the exact selected E23 source files, calibrated target output, live tapes, raw physical measurements, input/envelope exports, final states, analysis, figures, CSV and frozen source/design versions. `publication.json` and the later delivery receipt are outside the immutable archive; its manifest checks every member.

The four acquisition blocks are not population-level samples. No Core changes, no revived dead instances, no modification of historical data, no new physical quantum experiment. The actual live observer ordering is disclosed in both reports.


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-10-02-target-background/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [tables/background-trajectories.csv](/api/v2/storage/research-artifacts/research-artifact:2e3f372ff348227b41526ee5/content) — 1290 B; SHA-256 `d381097a3ba8817b310f78bbaa6c6215428f92d38f5f8956eec6d8d483d7ad76`.
- [tables/live-pairs.csv](/api/v2/storage/research-artifacts/research-artifact:b5ab3620a5ad56b91cef2cfc/content) — 458 B; SHA-256 `9f7960ddcee64f20b1a5c08ea44aeff9709cd689176ddda6c279960c32bb273f`.
- [tables/live.csv](/api/v2/storage/research-artifacts/research-artifact:f14bc1dafc1f94bb53131425/content) — 3606 B; SHA-256 `7ba14891856ca63440e6dd87afb7dc1d7e76b700b1f48a9e26855d1239130221`.
