# E67 typical-case causal diagnosis

This adjunct is linked to E67 and has its own managed resource,
`research:e67-causal-probes-20261012`. Originals live in
`E:\ThreeMindData\experiments\2026-10-12-e67-causal-probes`.
It never starts, stops or controls the main four-arm host.

Read [the protocol](design.en.md) ([中文](design.zh.md)) before running anything.
Twelve deliberately selected final cases are diagnostic material, not a new
held-out score or permission to change the existing individuals. The ordinary
authenticated research API records the protocol, references and reports in E67.

The implementation uses CPU-only inference and native Core copies, one thread,
below-normal process priority and one logical CPU. It stops itself on resource
shortage. The final report must disclose its concurrent interval when discussing
/4 wall-clock performance; this is not a dedicated-machine benchmark.

Commands use the existing environment and managed storage (repository root):

```powershell
$env:PYTHONPATH = 'src'
.\.work\kernel-venv\Scripts\python.exe -X utf8 lab\explorations\2026-10-12-e67-causal-probes\probe.py register
.\.work\kernel-venv\Scripts\python.exe -u -X utf8 lab\explorations\2026-10-12-e67-causal-probes\probe.py run
.\.work\kernel-venv\Scripts\python.exe -X utf8 lab\explorations\2026-10-12-e67-causal-probes\analyze.py
```

Do not duplicate an active runner. Completed cases are skipped. An unfinished
case directory causes an explicit stop for inspection instead of overwriting
its partial evidence. The source plan/hash is immutable; an incompatible tool
change needs an explicit additional revision, never editing the frozen source.

After reviewing both report bodies, `probe.py publish` saves them and the new
evidence references. It does **not** finalize the main E67 experiment.
The frozen first publisher requeued four protocol references with a process
role; the canonical service correctly rejected the conflict. Publication was
continued by `complete_publication.py`, which verifies the original local and
remote receipts, preserves rejected request bytes, restores only role-only
duplicates to their original requests, and checks authenticated downloads.
Use that continuation tool for this completed batch; do not rerun the frozen
publisher and recreate the rejected duplicates. A first download-verification
attempt also expected the wrong receipt shape; the corrected tool uses the
canonical result `id`, with both tool snapshots retained. Neither issue affected
simulation, original evidence or the running /4 host.
`record_cost.py --output <new-managed-json-path>` provides a read-only revision
of database-reference byte accounting that separates this adjunct by resource
identity. Retain the frozen r4 publisher's earlier snapshot; do not silently
charge these diagnostic files/references to the matched-course experiment.

Saved complete parent systems retain Core, personal peripheral/learning state,
body, mappings, history and random state. The intervention traces and terminal
summaries are forensic question records, not new resumable trained individuals.
