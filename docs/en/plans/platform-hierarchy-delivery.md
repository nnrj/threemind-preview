# Platform hierarchy, workbench and authorization acceptance

[简体中文](../../zh/plans/platform-hierarchy-delivery.md) · [Complete plan](platform-hierarchy-navigation-workbench.md) · [User guide](../platform-workbench.md) · [AI/script access](../platform-access.md)

Implemented October 11, 2026. This adds implementation and measured evidence while preserving the original five chapters, historical recommendations and research materials. No new formal experiment or Core/Runtime dynamics, default kernel or old-individual change is included.

## Implementation

- The default home is the consciousness workbench, with New, read-only Open, graph, properties, text and senses. Navigation separates workbench, research, materials, system and help. System pages require no project; old tools remain in independent project details. Material filtering does not replace page functionality.
- Creation defaults and named templates are versioned. Project presets are explicit and do not replace drafts. Default Create and prepare constructs no engine, job or fabricated checkpoint; editing and first start check concurrent revisions. Old callers retain immediate-start default.
- Login, multiple roles, exact action/resource pairs, full superadministrator access and limited delegation share backend authorization. Ordinary roles retain project/private-data boundaries. Menu visibility is not backend authority. Authentication is absent from Core and scientific checkpoints.
- The unified AI catalogue preserves IDs, revisions, keys, grants and call/cost relations. Managing configuration does not authorize paid use; diagnostics need no invented project and research purposes need their concrete research permissions. Reports, ordinary tools and calibration no longer depend on AI-use authorization.
- Mail transports and project event/recipient rules are distinct, retaining old policies and pending queues without resending. The global bell aggregates authorized personal notifications.
- Browser sessions, protected non-interactive profiles, expiring delegation and admitted background runs have separate lifecycles. Explicit logout defaults to continued execution; permitted independent instances may instead pause before logout. Retrying an accepted, unconfirmed pause only polls. Expiry, disconnection and closing a page do not automatically pause admitted runs.
- CLI, MCP and Python use canonical REST storage. Origin-bound profiles use Windows DPAPI and save no passwords. Missing credentials fail non-interactively without anonymous privileged fallback. Authentication/account administration are excluded from ordinary MCP experiment tools.

## Explicit local migration

A separate database was populated under schema 65 with old private providers, encrypted keys, completed calls, notification history/pending delivery, private notes and account relations, then upgraded through 66/67. Original IDs, password hashes, ciphertext and call/notification/note rows remained; a repeated migration created no duplicate service or revision.

After confirming no pending/leased jobs or other real-database connections, saved a 145,101-byte affected-configuration snapshot and 363,691-byte schema definition, then explicitly upgraded **65 → 67**. These are small configuration rollback evidence, not another full copy of large originals. Existing complete backups and originals were not deleted.

Real before/after witnesses:

| Object | Count | Verified fields/result |
|---|---:|---|
| Consciousness runs | 20,581 | Identity, project, name, actual configuration, status, revision, time, state hash and lineage unchanged |
| Checkpoints | 24,821 | Identity, subject, revision, time, state hash and host context unchanged |
| Formal research indices | 84 | Source, ownership, title, execution status, protocol and content hash unchanged |
| Fixed report versions | 629 | Original-row witnesses match |
| Fixed note versions | 719 | Original-row witnesses match |
| Notification versions/notices | 23/16 | Original rows match; no resend |
| AI calls | 41 | Original rows match; responses and costs unchanged |

Large Core/media originals were not individually reread and rehashed; no related write path changes, and acceptance covers the listed logical records and persisted scientific hashes. Receipts/snapshots remain ignored in `.work/t14-migration/`, outside Git. User services were neither started nor taken over.

Missing AI edit history is not fabricated: `current_import` actor comes from old `created_by`, and `call_snapshot` actor from the requester, neither proving who edited that revision. Only new `saved` entries record a new save. Imported mail transports derive from old project-policy snapshots rather than reconstructed edit history.

## Engineering acceptance

Actual batches are listed without adding repeated reruns into a fictitious unique total:

| Batch | Measurement |
|---|---|
| Platform permissions | 8 passed, including normal AI Bearer registration, three text inputs, continued Worker execution after logout, checkpoint/report/note/evidence links and idempotent finalization |
| Report-only role HTTP test | 1 passed; export/share needs no AI grant, and AI-only authorization cannot replace report permissions |
| Populated schema 65 → 67 | 1 passed, including repeat migration, ciphertext, versions and pending queue preservation |
| CLI/MCP/Python workflow | 1 passed; one normal-account login, real CLI registration/creation/repeated text, MCP observation/save, persistent Python recorder recovery/finalization and CLI verification |
| Defaults/preparation and mail split | 2 passed, covering pure validation, conflicts, first start and frozen mail rules |
| Initial configuration/notification integration | Initially 15 passed/2 failed; authorization/error sanitization fixed and targeted reruns passed |
| Research plans/language/ecology/host lifecycle | Initially 12 passed/2 failed; tests assumed project demotion removed superadministrator authority and direct cancellation bypassed plan control. Updated to approved boundaries; these and operation catalogue passed in a five-test batch |
| Independent Runtime and Python/Rust interoperability | 27 passed, including versioned bundles, SQLite and next-input restoration without Lab login |
| Configuration, public documents and plan closeout | 12 passed, covering per-step authorization, stimulus revocation after admission, source revisions and existing interrupted-plan recovery |
| Cross-project presets and permission closeout | 11 passed; destination access does not substitute for source read rights, an all-project reader can explicitly copy, and edited drafts remain separate from source snapshots |
| Automatic AI identity and existing schedulers | 10 passed; revoked stimulus/observation rights block sending, expired/revoked delegation never borrows full account authority, explicit new delegation permits renewal, and sent requests retain partial replies without resending |
| Production login boundary closeout | 8 passed; configuration/environment rejects no-login mode, loopback and identity headers do not replace sessions, actual restricted Bearer remains restricted under old fixtures, with server isolation/setup/CSRF/revocation coverage |
| Frontend build and browser acceptance | `npm run build` succeeded; 24 passed, covering zero projects, read-only Open, prepared-state dual revisions, registered AI routes, logout pagination/accepted-pause retry and Chinese/English at 390px |

Files include `test_platform_configuration.py`, `test_platform_permissions.py`, `test_platform_permission_migration.py`, `test_authenticated_client_pipeline.py`, `test_client_auth.py`, `test_ai_catalogue.py` and related regressions. Text cases are isolated engineering subjects, not new scientific findings or historical reruns.

Closeout corrected mismatched mocked/registered AI routes, coarse project-management/fork authorization, per-step plan permission checks and missing delegation fences before AI sending and automatic scheduling. Initial targeted runs also found an inconsistent permission-helper parameter and missing partial replies on a sent-request failure branch; both were corrected before the complete batches above passed. Original requests and uncertain evidence remain preserved.

Production configuration accepts session authentication only; old identity injection moved into pytest fixtures. The first login-closeout batch had 7 passes/1 failure: the adapter fixture used the default user role as a project viewer without system rights, although the new default user has read-only host access. Replacing it with an explicit project-read role preserved host-hiding/project-isolation assertions; its targeted rerun and the complete eight-test batch passed without changing applied role defaults or SQL. All 66 changed/new Python files passed static checking and compilation.

Desktop workbench and English 390px service catalogue were visually checked; screenshots stay ignored under `.work/browser-results/`. New main pages have no missing translations, duplicate keys or placeholder mismatches; 207 pre-existing untranslated strings remain elsewhere, so whole-site translation is not claimed complete. Real cameras/microphones, SMTP/paid AI and remote team deployment were not invoked; mock UI acceptance does not prove those external paths. Existing recovery gaps T12, memory findings and future network-maintenance service remain separate.

## Using and reverting

Use the existing workstation start command and set the platform password in the first browser visit. The account identity is retained; the user chooses the password, which this task neither generated nor printed. AI uses a protected initialized profile or limited delegation, as documented in the [access guide](../platform-access.md).

New API, workers and built UI must be used together; the service operator restarts any old service normally. This task does not take over processes. Defaults, templates and service edits cannot reinitialize old individuals.

Failed migration transactions do not commit. Reverting a successful schema requires explicit maintenance after stopping related writers and checking new dependencies. The scoped snapshot cannot restore a complete database. Do not delete new tables or merely change the schema version back to 65.
