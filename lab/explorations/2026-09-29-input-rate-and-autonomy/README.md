# Input timing, selection and autonomous activity

[中文](README_CN.md) · [Results](report.en.md)

448 completed instances, 2026-09-29. Simulation expansion stopped. A new project preserves old data and unchanged Core/defaults.

Lab project: **2026-09-29 刺激间隔、自主活动与环境选择**, ID `59aee7a1-5248-417f-a03b-b56f858a04d9`. Notebook entries contain registrations and bilingual results. Records and Reports contain four topical records, two reports and the raw archive. The consciousness list exposes checkpoints, configurations, parentage and delivered inputs. No dedicated interactive ring-world panel was built; public Python services write evidence into the same Lab database.

Use `.work/kernel-venv/Scripts/python.exe` from the repository root. Actual order: `calibrate.py register`, `validate`, `screen`, `analyze`; no interval qualified for `holdout`. Then `activity.py`, `world.py preflight`, `selection.py`, `recovery.py`, `attribution.py`. These create experiments and must not be rerun in place after publication. The database URL comes from local `.env`, never printed; existing processes were not managed.

`analyze.py` audits existing checkpoints; `figures.py` plots saved observations. `read_world.py` separately applies the temporal observer to saved world samples with ambient triggering. `publish.py` uses Lab notebook/report/artifact services; `verify_publication.py` reads reports and the full archive back. Later report changes require revisions, not overwriting evidence.

Frozen execution code/configurations reside in `.work/input-rate-autonomy-20260929/frozen-tools/` and the archive. Formatted working files do not substitute for execution-time hashes. Independent repetition requires a new project, evidence directory and registration. No distributed orchestrator or generic world UI is claimed.

Each `result.json` identifies its model/configuration; `parent-state.json.gz` contains full state. `trajectory.jsonl.gz` holds cue trajectories and LIF physical state, with spike events separate. `activity.jsonl.gz` records withdrawal. `world.json.gz` contains physics, stimuli, all nodes, proposed/applied actions and supply state. `recovery.jsonl.gz` records local recovery; `derived-readouts/` contains explicitly post-hoc windows with end-activation ranks. Selection decisions list scores and parent identities; evaluation learning never writes back.

Canonical model hashes preserve float semantics; archive-member SHA-256 hashes check bytes. A `STOP` file blocks further simulation, not reading/publication. Total storage budget is 3 GiB including database/archive growth. Shared account usage starts at 44%, with expansion stop at 47% and hard wrap-up at 48%. Old data are not scanned or deleted.
