# Lasting experience and autonomous-activity study

[中文](README_CN.md) · [Report](report.en.md) · [Delivery verification](delivery.en.md)

2026-09-29: 802 instances complete, simulation stopped. All four preregistered operational criteria pass; this is not direct verification of subjective experience.

Base design: [722 instances](design.en.md). Registered follow-up: [80 retention copies](retention-extension.en.md). Lab project: `92548061-22c0-4bd9-b283-c4e1e7f4360d`, named `2026-09-29 经历保持、内部通路与自主活动判据`. Evidence resides in `.work/experience-autonomy-20260929` and the platform archive linked from four records and both reports. The previous report received an appended discussion at revision 2; its original evidence archive remains intact.

## Commands

From the repository root, use `.work/kernel-venv/Scripts/python.exe` followed by a path in this folder:

- `experiment.py register`: create and freeze a new registration; refuses an existing one.
- `experiment.py local|memory|sequence|environment|novelty`: stage-specific public-API simulation commands.
- `retention_extension.py register|run`: separately registered causal retention follow-up.
- `analyze.py all|audit`: recompute saved contrasts/decision or verify all DB model states; no Core execution.
- `retention_analysis.py`: birth and selective-blocking retention analysis.
- `diagnostics.py`: exclude motor-output nonlinearity alone as the sequence effect.
- `secondary_analysis.py`: full texture-node vectors and unprompted behavior.
- `evidence.py`: export and verify input envelopes, deliveries and matched streams.
- `figures.py`, `write_report.py`: rebuild scientific figures and bilingual reports from saved evidence.
- `publish.py publish|verify --usage N`: publish through versioned Lab services and read back the whole archive; N is an actually checked shared-account usage percentage.

These are reproducibility entry points, not an instruction to rerun a completed study. Existing cases are loaded; STOP prevents new simulation. For an independent replication, create a distinct study folder/WORK identity and a new registration. Never overwrite completed cases or remove STOP merely to change parameters.

## Integrity

Each case retains final state, configuration, intervention events, observations, actual input envelopes/delivery times, temporal windows and end-activation ranks. Probe cases include full node/body traces. Registration and frozen sources preserve the original execution basis; follow-up registration does not replace it. `criteria-decision.json` states the proposition outcome; `analysis.json` and `input-export-audit.json` verify evidence; `publication-verification.json` verifies platform delivery.

Canonical StateImage digests are distinguished from compressed-file hashes. No Core, runtime default, UI or mapping change was required. Existing public clone/birth/input/advance/reconfigure/intervene/save APIs provided the necessary operational access.
