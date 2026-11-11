# Source: platform implementation and continued execution

[简体中文](../../../zh/history/sources/2026-10-11-platform-implementation.md) · [Original five chapters](2026-10-11-platform-plan-original.md) · [Final plan](../../plans/platform-hierarchy-navigation-workbench.md) · [Acceptance](../../plans/platform-hierarchy-delivery.md)

Recorded October 11, 2026. Separate contemporary authorization, implementation and engineering measurements. The original plan's first date remains unknown; its preserved copy is not rewritten by delivery.

## Contemporary decisions

The user explicitly requested implementation. During development, the user added that accounts are authentication entry points and session loss/logout should not interrupt continuous experiments; voluntary logout could offer pause.

The direct answer to the choice was:

> 采用：默认继续运行，可选择暂停实例

The approved behavior defaults to logout with continued execution, optionally selecting permitted independently controlled instances to pause first. Expiry, disconnection and closing the page do not automatically pause. Ecological, frozen-evaluation and managed-experiment control boundaries remain.

## Implementation evidence

Platform roles and protected non-interactive access, the workbench/navigation, creation defaults/templates, unified AI catalogue and separated mail transports/project rules were implemented. Accounts do not enter Core. Shared authorization helpers initially caused non-AI reports to depend on AI permissions; integration review separated them and verified a report-only role.

Two old tests also needed correction: project demotion cannot remove platform superadministrator authority, and ordinary run cancellation cannot bypass a controlled plan. Updated tests retain unexpected host termination and genuine ordinary-role revocation checks rather than simply removing failures.

The real local schema explicitly advanced from 65 to 67, retaining scoped configuration/schema rollback evidence in ignored storage. Witnesses for 20,581 runs, 24,821 checkpoints, 84 experiments and fixed report/note/notification/AI records match. A normal-account CLI/MCP/Python workflow delivered three real text inputs and linked records; separate acceptance verifies admitted execution after logout. These isolated engineering subjects are not formal research experiments or historical reruns.

AI version sources `current_import` and `call_snapshot` establish old configuration or call-snapshot provenance, not the actual historical editor. Missing editing history is not claimed restored. Batches, external-path limits and defaults boundaries are detailed in [acceptance](../../plans/platform-hierarchy-delivery.md).

## Closeout review and convenience

The frontend build and 24 browser cases passed, as did a 12-test configuration/plan batch, 11 cross-project preset/permission tests and 10 automatic-AI identity/scheduler tests. Review corrected mocked-route mismatches, specific-action checks and incomplete delegation propagation. Failed sent requests retain partial replies without resending. Counts are recorded by batch without double counting.

The user additionally suggested convenient single-user deployment without approval at every step, explicitly treating this as advice for discussion. The existing superadministrator can act directly and AI reuses an initialized profile; this does not remove login, resource boundaries or operation confirmations. Other existing pages still contain 207 untranslated strings; new main pages have none, so whole-site completion is not claimed.

Final review found that the old test convenience `authentication=local` remained selectable in deployment configuration and ignored restricted tokens. Production settings and authentication now reject/remove it; legacy identity injection exists only in isolated pytest fixtures, and real Cookie/Bearer credentials still use production authentication. This requires no new schema migration and does not remove login for single-user convenience.
