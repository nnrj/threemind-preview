# Activity processes and reusable tools

[中文](../zh/v2-observation-tools.md)

This update changes observation, not Core dynamics. Historical steady-state and activity V1 results retain their meaning. New configurations explicitly select V2 with 20 ms sampling; omitted versions restore V1 without silent upgrades.

## Interface and measurements

The readout page adds stimulus-free observation, process summaries, process analysis and full-trajectory comparison. Paused instances begin after resumption; markers are not Core inputs. Existing research/ecology control boundaries apply. Chat displays process summaries alongside convergence. Complete V1 recordings can be reanalyzed without rewriting their evidence.

V2 observes the full bounded window (12 simulated seconds by default), including activity after first convergence or early response cessation. Death, termination and budget exhaustion remain explicit cutoffs. Curves and nodes are paged with their scope identified. The new maximum of 60 period samples at 20 ms retains the previous 1.2-second searched period range.

Raw full vectors, signed baseline deviations, per-node peaks and times, durations, integrals, recurrence, cumulative absolute change and distribution transfer are separate measurements. Constant total activation can conceal transfer between nodes; equal endpoints can conceal different trajectories. Per-node peaks are not assembled into an invented simultaneous state. Values at the actual maximum-increase sample are recorded separately.

Decreases do not prove inhibitory causation. Missing, partial and zero baselines are identified. Integrals use left-hold estimates between samples without extrapolation; input/post-input integrals are unavailable without a delivery boundary. The `1e-12` reporting tolerance changes change flags/counts, not raw data, raw activity presence or Core thresholds. Sampling cannot recover unrecorded events. Process coverage only concerns the requested finite interval. Activity, task success and consciousness remain distinct claims.

Comparison uses exact shared timestamps, absolute or relative to first samples; unmatched times are not filled with zero. Corresponding identities are required. Convergence rankings and historical classifications stay separate.

## Reuse and composition

The shared layer consists of a Python library, fixed registry and declarative batch runner. Existing research plans handle stimuli, waits, snapshots and experimental control; existing operations expose the same REST capabilities through CLI/MCP. No parallel experiment manager or arbitrary-code plugin loader is introduced.

`observation_tools.analyze_record`, `compare_records` and `run_tool` work without Lab. `observation_probe.probe_copy` restores a `StateImage`, optionally applies explicit interventions only to the copy, observes existing decoded frames, and returns source/intervention/final hashes with evidence. Default limits: 60 simulated seconds, 120 wall seconds, 64 MiB evidence, 4 GiB process memory. Exhaustion raises `ProbeLimit`, not a negative result. Core pending events remain; coupled world/device state requires World/Ecology Runtime. Reversibility must be tested rather than assumed.

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.observation_cli list
& $py -m threemind_runtime.observation_cli process --input old-window.json --output process.jsonl
& $py -m threemind_runtime.observation_cli compare --input cue.json --right no-cue.json --relative --output comparison.jsonl
& $py -m threemind_runtime.cli --model model.tmind --clock unbounded --until-us 12000000 --readouts new-observation.jsonl --observe
```

`--until-us` is an absolute simulation deadline, greater than restored model time. Without `--observe`, CLI defaults remain unchanged; restored observer configurations are not upgraded. The installed command is `threemind-observation`; ecological `threemind-observe` remains available.

Inputs accept JSON, JSONL and gzip. Select `--window` / `--right-window` for multi-window inputs. Outputs must be new files. Limits: 64 MiB uncompressed per input, two million activation values per offline trajectory, 256 MiB output.

A batch is a `threemind.observation-batch/1` object with `steps`. Each step names `tool` (`process` or `compare`), `inputs` (`record`, or `left` and `right`, each with `path` and optional `window`) and optional `options` (`epsilon`, plus `relative` for comparison). Run `python -m threemind_runtime.observation_cli batch --input plan.json --output results.jsonl`. Paths resolve relative to the manifest directory; at most 32 steps. Completed steps survive a later failure. New tools require code registration and tests.

Online operations: `observation.process`, `observation.compare`; stimulus-free windows use `consciousness.command` with `readout_observe`. Migration 054 gates V2 jobs by worker capability. Use the normal migration/restart procedure.

Environment selection, matched-edge policies, cross-seed alignment and population statistics remain experiment-dependent rather than silently generalized.

[Calibration report](../../lab/validations/2026-09-30-process-readouts/report.en.md)
# 2026-10-02 addition: target response and local convergence

The process-tools panel now accepts explicit node IDs and configurable local stability criteria. It shows target peaks/integrals/endpoints, first local pattern convergence, first local steady activity and terminal local status alongside the unchanged global classification. Charts are paged; full JSON export includes criteria and the source hash.

The separate `threemind.target-observation/1` tool defaults to 800 ms continuous samples, pattern distance <=0.08 and amplitude span <=0.12 for steady activity. Proportional decay can be pattern-stable without being steady. Empty activity and missing samples cannot establish convergence. The 1e-8 normalization floor never trims raw peaks/integrals. Target scope applies only to derived analysis; global evidence remains available. Brief responses need not converge.

Python: `from threemind_runtime.observation_tools import analyze_targets`; then `analyze_targets(record, node_ids=[1, 2])`. CLI: `python -m threemind_runtime.observation_cli target --input readout.json --node-ids 1 2 --output target.jsonl`. Batch plans use tool `target`, input `record` and option `node_ids`. The shared online operation is `observation.target`, GET `.../readouts/{record_id}/target?node_ids=1,2`; `download=true` exports all derived values under existing project authorization. Unknown identities are rejected, not imputed as inactive. Preregister confirmatory targets; mark later selections exploratory. Preserve coverage/censoring. [E24 design](plans/target-response-background-20261002.md)

Verified on 2026-10-02 against 80 actual E23 windows: 16 globally unresolved windows contain target activity, but no A/B trace meets the 800 ms local stability condition. E24 likewise preserves brief target responses with differing global classifications. These are not relabeled as convergence. The UI target curve uses the recorded time range, while original records and full JSON remain independently available. [Results and usage](../../lab/explorations/2026-10-02-target-background/README.md)

