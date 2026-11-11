# Sensory/probe calibration and experiment storage audit

[中文](../zh/v2-probe-calibration.md)

2026-09-10: this entry now opens [Temporal observation experiments](v2-temporal-research.md) by default, inheriting complete recovery state, learning settings and reader configuration without an initial wait. The structure-only birth, fixed window, sham controls and projected integrals described below apply exclusively to the retained **Fixed-window probes and sensory calibration** tab and legacy protocols without a `mode`. They are not temporal convergence results. Histories are queried separately; previous results are not recomputed.

Open a consciousness → Manual experiments → Sensory and probe calibration. Submit texts, observation terms and doses against a saved checkpoint. Leaving the checkpoint blank freezes the latest saved checkpoint at admission. A worker advertising `worker.probe_calibration_v1` computes independent copies; it never advances or edits the source. Results and full evidence are stored in PostgreSQL.

The default uses inherited structure with cleared activity and disables learning during probes. Continuing a checkpoint, with its activity and in-flight events, is an explicit alternative. Each probe and sham has its own copy. Evidence includes sensory version/seed, all frames and amplitudes, hashes, transport counters, full activation samples including zeros, and source/final model files. Scoring alone excludes shared term channels and channels directly stimulated by any probe. Unavailable masks and already-dead copies are unscorable rather than zero. A disabled text sensor stays disabled.

The endpoint is a trapezoidal time average within the declared simulation window, subtracting sham. It measures an observation projection, not semantic accuracy or causal discovery. Arrival groups may aggregate accepted edges: they are not per-edge pass counts and cannot establish rejected-edge counts. No Core equations or thresholds change.

Use separate vocabulary and encoding seeds for calibration. Select based on physical transmission, coverage and saturation, then freeze before validation. Do not tune using desired term hits. Test pair specificity and role composition independently.

Database-free CLI: `.venv/Scripts/python.exe -m threemind_runtime.calibration_cli --model model.tmind --protocol probes.json --output calibration.zip`. Models without a sensory profile require explicit `--seed` and `--sensor-config`. Existing files are never overwritten. Minimal protocol: `{"cues":["甲","乙"],"terms":["松子","铃铛"],"intensities":[1,2,4]}`. The graphical form exposes the full JSON protocol.

Per request: 2,000 nodes, 100,000 edges, 2,000,000 raw node samples, 64 MiB compressed evidence, 60 seconds computation; Lab execution also enforces 2 GiB process RSS. Exceeding these limits fails explicitly, without a truncated success or altered dynamics. All text frames are encoded; choose a window covering their delivery. Pending frames remain in the final state and bus evidence.

Settings → Experiment storage audit performs a read-only, paginated metadata inspection of the current project. It distinguishes keep, deletion risk and empty-record candidates. Referenced evidence, failed experiments and zero results are never assumed worthless. Projects containing studies, research documents or the caller's notes are conservatively retained. Free-text references, analysis JSON, media and old bulk data are not expanded. Byte totals are not reclaimable space. Download results for review; the page creates no deletion tokens and deletes nothing. Any cleanup remains a separate user decision after the model library's full reference preview. Archiving does not free disk space.
