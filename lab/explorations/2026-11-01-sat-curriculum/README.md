# SAT curriculum v2

The author's authorized rerun under training protocol v3. Read the bilingual protocol, report and HANDOFF before using commands. This directory adds isolated research tools; it does not change Core, installed modules, production APIs or historical subjects.

- [中文协议](protocol.zh.md) / [English protocol](protocol.en.md)
- [中文报告](report.zh.md) / [English report](report.en.md)
- [完整交付 / Delivery](delivery.md)
- [v1流程更正](v1-procedure-correction.zh.md) / [v1 correction](v1-procedure-correction.en.md)
- [Host budget amendment](host-budget-note.en.md)

Originals and complete student dependencies live at `E:/ThreeMindData/experiments/2026-11-01-sat-curriculum/v2`, registered resource `sat-curriculum-20261101-v2`. Only code, protocols and small aggregate summaries are tracked. The first archive of this v2 study is named `originals-v1.zip`; its archive revision is separate from the experiment version.

Read-only status:

```powershell
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-01-sat-curriculum/driver.py status
```

`student.py` preserves whole state and uses the existing personal temporal Transformer with continued Adam/RNG. `driver.py` freezes materials and conducts serial curriculum/development/final stages. `host_budget.py` was the continuation entry under the separately hashed 2 GiB host policy; this batch is now completed. `analyze.py` independently checks every trace and complete input chain; `verify_readers.py` replays saved activity through frozen readers without loading Core. `publish.py` verifies loopback API/database and the exact registered E-drive resource before local record keeping and full archive readback.

Do not repeat prepare, prepare-resume, apparatus or an already-completed student run. A dead-host in-flight marker is not permission to replay. Ordinary tests never restore per question. Postprocessing errors do not justify rerunning students. A new replication needs a separate preregistration, identities/resource, seeds and materials; repeating these exact seeds is reproducibility, not additional independent N.

No automatic successor experiment or half-life change is part of this delivery.


## 2026-11-01: separately authorized v3 exclusions delivered

The original v2 study and archive are unchanged. [New Core-necessity report](../2026-11-01-sat-core-exclusion/report.en.md) / [中文](../2026-11-01-sat-core-exclusion/report.zh.md) identifies the sufficient components of the current SAT solver. No v2 subject was rerun or overwritten.
