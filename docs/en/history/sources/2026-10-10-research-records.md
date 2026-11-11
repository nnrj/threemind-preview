# 2026-10-10: equal recording requirements and authorization to backfill

[中文](../../../zh/history/sources/2026-10-10-research-records.md) · [Chronicle](../chronicles/12-research-records.md)

Recorded 2026-10-10. The quotations below are the original Chinese from visible user messages in this conversation. Separate timestamps were not supplied for the earlier turns; none are invented. Credentials, connection URLs and private notebook bodies are excluded.

## Original user statements

> 我一直强调，由AI进行的实验与由人手动进行的实验地位是一样的，记录要求是一样的。

> 如果缺少方便AI进行实验记录录入的接口、命令或其他工具，本次可顺便实现，实现方案也列到计划中

> 我已配置好了THREEMIND_BACKUP_DATABASE_URL，你可继续实施

## Summary of the approved scope

The user required coverage of all historical formal research through one index and references to originals, preserving the additional scientific formats used by AI experiments. Existing reports, notebooks and artifacts are reused. Missing registrations enter the database and global UI. Execution status and material completeness remain separate; unknown identities, dates, traces and checkpoints are recorded as gaps, without reruns or invented detail.

REST, CLI, the existing MCP operation catalog, the Python recorder and human UI use the same save service. Stable requests and content hashes support retries. Original-byte failures stop the host from advancing; database outages preserve a durable synchronization queue. Live backfill requires a full backup and an independently verified restore, followed by explicit migration. Local phase commits are authorized, with no push. Recording and queries do not authorize changes to Core, old individuals, historical criteria or running services.

The approved plan's earlier planning-only wording belonged to the preceding planning stage. The subsequent “PLEASE IMPLEMENT THIS PLAN” and completed backup configuration authorize implementation; the earlier boundary must not obstruct work already approved.

## Sources

- [Full plan](../../plans/experiment-record-backfill.md)
- [Recording and query guide](../../research-records.md)
- [Delivery, complete ledger and gaps](../../plans/experiment-record-backfill-delivery.md)
- Implementation: `migrations/062_research_records.sql`, `research_records.py`, `research_recorder.py`, `record_api.py`, `native_records.py`, the external historical adapter and the research overview UI.

The delivery records implementation and acceptance facts. Original statements, later inventory notes, measured engineering behavior and unrecovered scientific materials remain distinct. Backfill does not change the negative retention findings.

## Later the same day: correcting the default browsing scope

The user objected to most menus implicitly filtering by Current project and appearing empty, while accepting projects as fields, explicit filters and an overview list. These quotations are from the current visible conversation, not an earlier experimental dialogue:

> 可以有项目概念，只要用字段标识出来，总览或者什么地方有个项目列表，再不济，菜单栏加个项目切换下拉列表也行啊

> 开始进行此合理调整。

The [global browsing adjustment](../../plans/global-resource-browsing.md) retains project ownership/access boundaries while making main resource menus global across authorized projects. Details bind original ownership; creation explicitly selects a project. Old browser preferences no longer silently narrow the scope. This corrects the assistant's decision to retain scoped defaults elsewhere, without modifying original experiments, Core or subject state. The plan records acceptance and local migration; the [guide](../../global-resource-browsing.md) explains activation and operation.
