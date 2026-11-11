# Candidate-kernel study, 2026-09-29

[中文](README_CN.md) · [English report](report.en.md) · [中文报告](report.zh.md) · [Delivery and measured resources](delivery.en.md)

For a plain-language account of findings and priorities, read [Supplementary interpretation: what improved and what to investigate next](interpretation.en.md). It adds research judgments separately without replacing the original report or evidence.

Project `cb3a2d4a-f8a2-440e-9182-75148e9454a8`, named “2026-09-29 多内核初步对照”. The platform's notebooks contain the design and amendments; Records and Reports contain six block records, bilingual reports, frozen temporal evidence and raw-data links.

This directory contains protocols, orchestration, analysis and authored summaries. Model states and inputs live in the project database; file evidence is in ignored `.work/candidates-20260929/`. Previous experiments were not scanned, pooled or cleaned up.

## Reproducibility

- `design.md` preserves preregistration version 1. Before formal execution, notebook revision 2 froze dose 1.0, interval 1 s, cue 0.5 and the age-matched `trained-aged` control.
- Revision 3 documents instrumentation only: lightweight safety checks remain per-second, metadata/storage scans become per-minute. Immutable `runner-v2/`, `runner-v3/`, source hashes and exact replay parity evidence are retained. Kernel formulas and sensory mappings did not change.
- Six blocks use distinct channels and genuine host recordings. Each within-block contrast shares its recording. No repeated/interpolated telemetry substitutes for a recording; channel renaming does not imply independent mechanism samples.
- Twelve tiny Transformers are isolated probability controls, with no Core feedback. Rehearsed contexts do not establish unseen-rule generalization.
- Probes receive independent identities and do not write learning back into their training parents. A resource stop is not death.

## Tools and files

See the [shared UI/CLI/MCP guide](../../../docs/en/v2-research-tools.md). These scripts orchestrate this particular registered study:

|File|Role|
|---|---|
|`common.py`|Runtime/Lab services, checkpoints and resource guards|
|`run.py`|prepare / calibrate / capture / block; read completed cases without overwriting|
|`freeze.py`|Publish the pre-formal dose selection and age-matched control|
|`transformer.py`|Bounded independent CPU/auto probability controls|
|`analyze.py`|Condition-specific summaries; missing primary values are not zero, ties are not wins|
|`audit.py`|Verify prior metadata, case/repetition counts, background doses and training-parent topology|
|`write_report.py`|Generate bilingual reports from all six completed blocks|
|`publish.py`|Publish evidence, records, reports and exports through Lab services|

Inspect existing completed results without starting training:

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-candidates/analyze.py --partial
```

Final summaries and reports use exclusive creation. A fresh replication needs a new dedicated directory, project and preregistration while retaining the original seeds, recordings, timing and implementation. Do not reuse this study's hard-coded identities or run `prepare` against its existing directory. General experiment snapshots restore a separately identified paused instance.

## Evidence boundaries

The ZIP manifest records paths, sizes and SHA-256 digests for observations, input recordings, executor versions, calibration, statistics and state hashes. **Core states remain database checkpoints; this evidence ZIP is not an importable `.tmexperiment` snapshot.** Export such a snapshot separately when full transfer is needed.

`closure.json` is the pre-publication resource/metadata snapshot. `post-publication-closure.json` is saved afterward and therefore is not inside the earlier ZIP. Host envelope payloads retain encoder output; authoritative scheduled/delivered frames record the applied intensity, verified as 0.2.

No real CUDA execution or live OCI registry round trip occurred. CPU/fallback and distribution-protocol checks are separate from hardware and external-service validation.
