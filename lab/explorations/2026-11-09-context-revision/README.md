# Context judgments, evidence revision, and active observation

This is the separately authorized 2026-11-09 study (R43), using genuine `continuous-memory/5.1` without production changes. Eight independent sources, their opposite-history copies, and seven declared intervention conditions are distinct levels of the lineage. The study is an exploration.

[中文协议](protocol.zh.md) · [English protocol](protocol.en.md) · [Current handoff](HANDOFF.md) · [Apparatus preparation](preparation.md)

Completed results: [中文报告](report.zh.md) · [English report](report.en.md) · [Delivery verification](delivery.md). G2 passes in 8/8 individuals; G1/G3/G4 pass in 0/8. Formal output uses personal temporal Transformers and four activity fields. The mean-activation projection is a separately labeled post-result diagnostic.

Scientific originals: `E:/ThreeMindData/experiments/2026-11-09-context-revision/v1`.

Project `09e358fa-b05a-4bc0-93b2-643148fb72ab`; record `4159a847-5671-504a-b0dc-800fca835e96`. The recorded hashes, not a moving repository revision, identify the runner, protocols, adapters, and kernel implementation. Preparation was committed locally as `0f271c4` after registration; file hashes remained unchanged.

## Inspect without advancing a subject

From the repository root:

```powershell
& '.work/kernel-venv/Scripts/python.exe' -X utf8 'lab/explorations/2026-11-09-context-revision/experiment.py' status --work 'E:/ThreeMindData/experiments/2026-11-09-context-revision/v1'
```

Also compare host PID, creation time, and full command with the actual process. `current.json` points to the latest complete state; an in-flight unit with a living matching host is normal. Do not launch another host. A new dead in-flight requires preserving evidence and asking the author; do not clear it or replay a unit.

## After computation

`analyze.py` checks frozen primary metrics and complete trial evidence. `audit_integrity.py` independently checks boundaries, full-state digests, curriculum timing, correction coverage, and contemporaneous effective-weight matching. `summarize.py` provides report tables and explicitly descriptive per-output decompositions. These tools do not restore or advance an individual.

`audit_scores.py` independently recounts all primary scores. `port_diagnostic.py` and `signal_audit.py` describe the later explanatory checks; `inventory.py` measures physical allocation separately from logical file size. None controls the organism or changes its original score.

After reviewing bilingual reports, `publish.py --review <review-receipt>` archives the originals, reads them completely through the unified local research API, compares both protocols and both reports, and finalizes only with verified coverage and pending=0. It does not publish a paper or use external services. Live API access logs remain outside the scientific archive; they are retained separately at the work root.

The original run supports only a fresh registered start. A resource pause needs a separately reviewed continuation from its current complete state. The absence of a resume shortcut is intentional; it prevents silent replay or rollback. None of these commands resumes older studies or automations.
