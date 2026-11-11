# Depletion, facilitation and consolidation: execution and results

[中文](README_CN.md)

2026-09-29: 598 whole-network instances completed, including independent controls, exact reproduction, the eight-group short/retention studies, bounded follow-ups and checkpoint audit.

- [English report and figures](report.en.md)
- [Chinese report](report.zh.md)
- [Energy wording, persistent activity and researcher remarks](discussion.en.md): post-study addendum appended to the report, without altering results.
- [Next autonomous-activity discussion plan](../../../docs/en/plans/autonomous-activity.md): not executed.

`publish_discussion.py --apply` published both report addenda as revision 2, retaining revision 1, and added bilingual discussion/design notes in the same notebook. Readback is in `.work/memory-timescales-20260929/discussion-publication.json`: instance count remains 598 and archive identity/hash metadata are unchanged. No new experiment or whole-archive byte reread occurred; the original delivery retains the full byte verification. These addenda are outside the immutable evidence ZIP.

- [Delivery, platform report IDs and final resources](delivery.en.md)
- [Frozen preregistration](design.en.md): its unimplemented status describes registration time.
- [Previous report, discussion and seven primary sources](../2026-09-29-continuous-mechanisms/report.en.md)

Project: `cbde2d48-284d-4294-9184-89f439923547`. Its original display title remains `2026-09-29 耗竭、易化与连接巩固（实验设计）`. Design, execution notes and results share this project. Original design-note revisions are retained.

Execution entry points: `run.py prepare`, `run.py validate`, `run.py short`, `run.py retention`; registered extensions use `extend.py history`, `readout`, `diagnostic`, `residual`, `sustain`. These are namespaced study scripts, not permission to overwrite an existing project. Do not repeat prepare/register; use a new project and work directory for a new experiment.

Read-only evidence review and regeneration of derived analysis:

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/analyze.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/audit.py
```

Analysis rewrites only derived tables/figures; audit decodes this study's database checkpoints through public Lab services and checks hashes. Raw evidence, frozen sources, registrations and execution manifests reside under `.work/memory-timescales-20260929` and are not committed to Git.

The versioned `continuous-memory/1` research candidate is available through the shared kernel catalog, parameter UI, Runtime CLI and Python/Rust implementations. Existing kernels remain intact. Isolation tests are in `tests_v2/test_memory_candidate.py`.

A storage-only amendment records all task nodes at 10 ms plus network summaries and full endpoint states in retention/follow-ups, rather than redundant high-frequency background detail. Stage one retains all-node 10 ms trajectories. Complete temporal outputs remain unchanged. The original stage-one script, kernel sources and hashes are archived.

`publish.py` writes reports, notes and eight factorial records through Lab services. The ZIP is assembled in memory, member hashes verified, and streamed into the database without an additional local archive copy. Platform IDs are in `publication.json`; final resources are recorded separately in delivery documents.
