# Response readout / 短暂响应读出

[中文报告](report.zh.md) · [English report](report.en.md) · [中文设计](design.zh.md) · [English design](design.en.md)

新的 `threemind.response-readout/1` 只分析已存完整向量，不推进模型。默认无最短持续时间，主视图显示同一实际采样的激活排序，旧稳定条件单独保留。

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_runtime.observation_cli response --input saved-events.jsonl.gz --window WINDOW_ID --node-ids 1 3 --output response-new.jsonl
```

`--node-ids` 可省略，表示全节点；多个窗口需明确选择 `--window`。输出必须为新文件。不要从跨实例不同的节点数字推断同一意义，应使用各自保存的通道身份。

Python: `analyze_responses(record, node_ids=[...])` in `threemind_runtime.observation_tools`. Offline `run_tool("response", {"record": record}, {"node_ids": [...]})` and the JSON batch protocol use the same function. API: `GET /api/v2/projects/{project}/runs/{run}/readouts/{id}/response`; `node_ids` optional CSV, `download=true` exports all events/rankings. UI responses page events/samples by `offset/limit`; `event_index` selects one response, `rank_offset` pages its activation ranking. Operation ID for agents/MCP: `observation.response`.

Raw tool results include all events, episodes, source SHA-256, annotation-only labels, and original classification/coverage. `observed_peak` means a sampled rise and fall, not causal proof of competition. `response_entry`, `already_active`, `leader_change` and `episode_maximum` explain why a snapshot is retained. The numeric tolerance can be set to zero; no fixed 800 ms gate exists. Default detail uses greatest total activation, earliest on a tie.

Old `target` CLI/API remains `threemind.target-observation/1`; its local stability algorithm is unchanged. Neither tool interprets answer meaning or changes Core.

Calibration scripts: `analyze.py` reads only registered E23/E24 files, writes a fresh `.work/response-readout-20261002/verified` result, and refuses to overwrite completion. `figure.py` plots actual archived samples. Reanalysis needs the original source paths or their archived copies. `publish.py` registers the new read-only study and publishes notes, reports and evidence without running models.
