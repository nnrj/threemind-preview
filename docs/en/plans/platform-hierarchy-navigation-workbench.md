# ThreeMind hierarchy, navigation and consciousness workbench restoration plan

[简体中文](../../zh/plans/platform-hierarchy-navigation-workbench.md)

**Latest same-day implementation, October 11, 2026: kernel/template hierarchy acceptance is complete, local schema68 was explicitly applied, and scientific witnesses match.** Preserve all five original chapters and later decisions; this delivery is in chapter six and [acceptance](kernel-creation-hierarchy-delivery.md). Earlier implementation-start statements remain stage records.

**Implementation resumed, 2026-10-11:** The user explicitly requested implementation of this final plan. The earlier pause remains a historical stage record. Validate in an isolated database before explicit schema migration; do not change Core dynamics or take over user-run services.

**Same-day implementation decision: continuous experiments.** The user confirms that session expiry, lost network and closing a page do not automatically pause admitted individual tasks. Explicit logout defaults to leaving them running; the user may select independently controllable individuals for which they have pause authority, pause them and then log out. Managed experiments retain their own controller. Authentication expiry refuses new operations without injecting a Core pause or reset.

**Final revision: October 11, 2026.** This edition uses the complete original Plan supplied again by the user. It retains the original five chapters, functional scope, implementation order and acceptance requirements, incorporating confirmed decisions from all subsequent discussions into their corresponding sections. See the [original-plan source](../history/sources/2026-10-11-platform-plan-original.md). The earlier condensed repository rewrite is not the basis of this edition.

**Same-day addition: AI/script experiment access.** After checking whether login/permissions would obstruct conversation-authorized experiments, the user explicitly requests non-interactive authentication, reusable sessions or delegated credentials and complete-workflow acceptance. Additions are in chapters III, IV and V; the original source is unchanged. These are implementation requirements, not already accepted functionality.

**State at revision (preserved): code implementation remained paused.** Some incomplete, uncommitted code changes already exist. No real database migration for this task has been executed. This revision does not resume implementation, modify individuals or experimental results, or operate running services. Implementation and measured acceptance will be recorded separately.

**Implementation record, October 11, 2026.** Authorized workbench, configuration boundaries and platform access are implemented; explicit local schema 67 migration retains scientific witnesses. See [acceptance](platform-hierarchy-delivery.md) and [guide](../platform-workbench.md). Earlier paused/unimplemented statements are preserved as planning-stage evidence.

**Same-day closeout: implementation and scoped acceptance are complete.** Twenty-four UI, ten automatic-AI/scheduler and eight production-login tests pass. Single-user deployments use the superadministrator directly; per-action applications and limited delegation are not mandatory. The user's convenience advice does not expand ordinary roles or remove scientific preconditions. Production no-login bypasses are removed; legacy injection is isolated in test fixtures.

## I. Audit findings and goals

### October 11, 2026 addition: kernel, template and parameter hierarchy

The user confirms that the kernel identity is the parent choice; templates and manual edits configure that kernel. This is a same-page hierarchy, not a wizard. Implement this revision while preserving the original plan and completed-stage records.

- Show kernel versions and descriptions outside the ordinary parameter table. Filter templates by kernel, select its system-default template initially, and integrate research presets into that layer. Project ownership never replaces the draft.
- Correct stale creation provenance, duplicate kernel selectors and accidental cross-kernel parameter carryover. Confirm replacement only for dirty drafts; cancellation preserves them and stale requests cannot overwrite a newer choice.
- Support multiple templates per kernel, saving the draft and deriving a template from an instance's saved configuration. Do not copy identity, weights, checkpoints or study bindings. Preserve historical revisions; future edits retain template kernel ownership.
- Restore creation for every actual historical kernel. Recover the historical Python/Rust causal/1-8 implementations. Integrate the original unified-associative frame kernel in Python without a new Rust port. Historical UI V1/V2/V3 are its templates, not invented dynamics versions.
- Bind implementation and rules through existing creation/restoration routing. Isolate historical code by algorithm compatibility while sharing compatible infrastructure. Withdraw the requirement to split the Rust continuous family into four version objects: no measured evidence establishes that arrangement caused regression.
- Retain current shared continuous implementations and approved mechanism switches. Audit identity, operators, configuration and state boundaries. Distinct frame, LIF and memory/4 implementations remain separate. Physical packaging, plugin management and deep restructuring are deferred; equations, default kernel and dynamics values stay unchanged.
- Persist the host backend outside scientific configuration. Route Python-only kernels to matching workers, never to native-only workers, without silently substituting kernel identities. Backends run independently.
- Verify creation/restoration across versions, frozen behavior, provenance, templates, permissions, prepared creation and observation boundaries. Perform engineering validation only, then update bilingual guides, backlog and required histories; commit locally without pushing.

**Status: approved and implementation started; acceptance has not yet been claimed.** Originals, historical individuals and user-run services are not automatically migrated or taken over.

**The user's diagnosis holds: system capabilities, creation defaults, project resources and instance operations currently share an implicit Current project context.** The problem mainly concerns Lab interfaces and management services. The Core/Runtime creation and restoration paths examined for the original draft do not inherently depend on a research project.

The original audit identified:

- The [settings page](../../../threemind-ui/src/v2/settings.tsx) wraps six categories in an ownership-project selector, obstructing otherwise independent capabilities.
- Platform AI providers, global execution management and the adapter catalogue have backend capabilities, but the interface first requires a project.
- Notification configuration mixes transport credentials, project event rules and recipients. This requires backend separation.
- Consciousness creation automatically reads project defaults; independent creation defaults and configuration templates are missing.
- URL parameters switch one material menu into a different set of project tools, making browsing, creation and management inconsistent.
- System pages wait for project lists. A welcome page blocks some global functions when no projects exist.
- Administration mixes in selected-project membership; experiment registration can automatically select the first project.
- The legacy interface has a first-level Consciousness image menu. The current [instance detail](../../../threemind-ui/src/v2/research.tsx) retains graphs, chat and sensory controls; the missing element is the primary entrance.

### Product positioning and component boundaries

ThreeMind is a **local-first research application with a Web interface**. Cloud capabilities support its kernel and research. A self-hosted team deployment is optional; cloud registration is not required. Technical frontend/backend separation remains, but there is no separate administration website. Management is presented within the same application according to permissions.

| Component | Boundary |
|---|---|
| Core | Nodes, edges and consciousness dynamics; no awareness of accounts, roles, projects, tokens or login state |
| Independent Runtime | Independently buildable, installable and publishable model host/library/CLI; local use does not depend on platform login or the Lab database |
| Research platform Lab | Users, permissions, projects, service configuration, research records and interface; authorizes resource access and management operations |

A team may share one self-hosted platform. Separate local installations are separate deployments and exchange formal data packages. This phase promises neither cross-deployment account recognition nor live synchronization or distributed consciousness.

Retain the original configuration layers:

| Layer | Contents |
|---|---|
| System/host | Storage, execution processes, backend capabilities, network exposure, shared services, platform accounts and roles |
| User/device | Language, theme, display budget, interaction preferences and personal notifications |
| Creation defaults/templates | Kernel versions and parameters used to create new individuals |
| Research project | Ownership, membership, project templates, research rules and quotas |
| Consciousness instance | Its version, effective parameters, senses, body, state and complete recovery points |

**Projects belong to this platform deployment and serve as organizational and authorization containers. They do not gate system capabilities.** Creator, responsible person, membership and research provenance remain recorded. Platform ownership does not grant every user access to everything: roles and resource grants determine scope. The later explicit decision grants superadministrators access to all projects and private research materials.

The original statement that no files, database or running state had changed described that original planning stage. The current status is stated at the beginning of this edition.

## II. Navigation and consciousness workbench

### Reorganize navigation

| First-level entry | Contents |
|---|---|
| **Consciousness workbench** | Default home; create, open, observe and directly interact with consciousness |
| Research centre | Overview, projects, experiments/training, comparisons, worlds/bodies and specialized dialogue experiments |
| Materials centre | Individual archives/models, data queries, records/reports, notes and data management |
| System settings | Creation defaults/templates, devices, AI/mail services, execution resources, storage, users and permissions |
| Documentation/help | Manuals, kernel/adapter references, research history and CLI/Agent interfaces |

Preserve existing functions while consolidating, splitting and naming entries clearly. Project filters appear only in research and material pages, not as a global gate on system pages. Menus, pages, functions and buttons reflect permissions; hiding buttons does not replace backend authorization. After login, the workbench is the default even without projects.

### Restore the primary entrance

Use a player-like layout:

```text
Navigation | Central view                         | Right panel
           | No instance: create / open           | Properties
           | Open instance: actual graph          | Text stimuli / actual readout
           | Start / pause / continue / switch    | Eyes / ears / mouth
```

- Do not automatically select a recent instance. Recent items are explicit shortcuts.
- Open from all authorized instances, reading state and graph only. Opening does not start, pause, restore or copy.
- Show an already running instance's actual state. Viewing does not alter background execution.
- Default to Create and prepare; also offer an explicit Create and start.
- Reuse existing graph components. Zoom, layout and image freezing are separate from pausing consciousness.
- Show instance/selected-node properties, stimulus chat, actual readout and sensory/output controls. Advanced protocols, recovery, events and research tools remain in details.
- Distinguish Not started, No nodes yet, No matches and Read failure. Do not show unmeasured values as zero.
- At narrow widths, use drawers or tabs for the right panel while keeping the graph and execution controls accessible.

### Correct workbench interactions

- Distinguish **persistent instance enablement, current capture connection and page-local playback**. A disconnected browser does not mean the instance's senses are disabled.
- Opening a page requests neither camera/microphone permission nor capture/playback.
- Live capture requires the existing Running + realtime conditions. Explain unmet conditions before requesting permissions; do not automatically continue or change clocks.
- Fix sensory enablement before a file chooser opens. Perform required actions only after selection and confirmed submission; cancellation changes nothing.
- Leaving releases page-local capture/playback, without pausing consciousness. Record capture interruptions accurately.
- Use the existing input service; chat displays genuinely saved readout. Label external AI interpretation separately.
- Managed ecology and frozen-evaluation objects remain observable, but their owning experiment controls them. The workbench must not bypass restrictions.
- Separate historical viewing, continuing the current instance, historical branching and importing. Core-only packages cannot substitute for complete individual restoration.
- Check pause, continue, stimulus, intervention, restoration and export separately. Graph access or pause permission does not imply other control rights.
- Logout, expired sessions and revoked permissions do not reset, clear or upgrade an individual, or turn navigation into a pause command. Later control/capture requests recheck permissions; existing execution follows its established execution and saving rules.

## III. Separate configuration, services and materials

### Creation defaults, templates and instance configuration

- Add per-kernel creation defaults and named templates with stable identities and revisions.
- Initialize from actual current kernel-catalogue defaults. **This task changes neither the default kernel nor numerical dynamics parameters.**
- Resolve factory defaults → system creation defaults → one explicitly selected template → draft changes. A project preset is an explicitly selected source, not another implicit layer.
- Preserve former project defaults as explicit project presets; ownership selection must not overwrite a draft.
- Allow viewing/editing before selecting ownership. Require an explicit project at save, permitting inline project creation. Never select the first project automatically.
- Save the complete effective configuration and template identity/revision/provenance. Templates contain configuration, not learned weights or whole-individual state.
- Existing instances use their own saved version, configuration and full checkpoints. Updated defaults/templates do not affect them.
- Describe configuration layer, target, provenance and activation rules: display-only, new instances only, effective after pause, or restart required.
- Correct adapter-catalogue creation defaults mistakenly derived from historical missing-field parsing; preserve the historical parsing semantics.

### System versus project functions

| Function | Separation |
|---|---|
| AI | **One platform service catalogue; remove project-private providers as a distinct configuration type.** Separate management, viewing/use grants and project/instance/tool selection; retain calls and consumption against their actual objects |
| Notifications | Transport service, personal inbox and project event rules; global bell aggregates authorized notifications without first selecting a project |
| Execution | Host queues/concurrency in system settings; project quotas/tasks in project details. Host scheduling is not Core energy |
| Devices | Installation/capability/adapter catalogue at system level; wiring, tokens and sensory control on instances |
| Storage | Locations, policies, migration and backup at system level; evidence integrity and cleanup in material management |
| Users/permissions | Platform users/roles/grants in system settings; project membership in project details, never a gate on platform settings |
| Tools | Compute capabilities, operation catalogue and Agent documentation need no project; research execution names its target/ownership and checks operation permissions |

Implement all later AI-service decisions:

- Project-private providers came from an earlier multi-tenant configuration approach, not an inherent project-import requirement. Replace that distinction with the platform catalogue and resource grants.
- The same supplier may have multiple connections using different accounts or keys. Do not merge on matching endpoint, model name or supplier.
- Preserve service identity, revisions, encrypted credentials, historical public configuration, calls and costs. Convert former project scope into grant provenance without widening ordinary-user use.
- Service-view permission is no longer obstructed by former project location. Management and calling require their own permissions. Superadministrators see/manage all services; plaintext credentials are still not returned.
- Projects, instances and tools select authorized services and invocation parameters instead of maintaining separate provider-management systems. Global diagnostics must not fabricate a research project.
- Formal project/model packages exclude platform accounts, keys, sessions and grants. Imports neither create providers automatically nor bind by source name; bind explicitly to an authorized service in this deployment when needed.

Former project credentials **do not become usable by everyone automatically**. After notification separation, former project transports retain their original project grant. Preserve rules, revisions and queued notifications without resending. Superadministrator management rights and ordinary use grants are distinct.

### Platform accounts, roles and permissions

- Provide platform login and remembered sessions using existing authentication/session capabilities. Login policy is independent of local/network exposure; login does not automatically open LAN access.
- Preserve the stable existing `local` identity and ownership links. Initialize its password through local first setup, with no universal default password and no replacement identity that loses old materials.
- Built-in superadministrator, administrator and ordinary-user roles; superadministrators may create roles and grants; users may hold multiple roles. Support concrete menu/function/button operations together with resource scope.
- Each grant expresses both action and resources. Multiple roles must not combine one role's read scope with another's write ability to create extra write rights.
- As explicitly decided, superadministrators access **all projects, personal notes, attachments and private packages**. Ordinary administrators do not automatically receive all research materials; other roles follow explicit grants.
- This deployment is unreleased and currently used by the user and assisting AI. Do not invent legacy-user notification requirements or parallel old permission modes. Preserve authors, creators and scientific provenance.
- REST, CLI, MCP/Agent, downloads, import/export and background-task boundaries share backend authorization. Aggregates filter objects and fields; menu hiding and one generic write permission are insufficient.
- Protect the last active superadministrator, prevent unauthorized delegation and retain permission-change provenance. Encrypt credentials; expose masked values/configured flags and explicit update operations.
- An application superadministrator is not a database superuser. The role cannot bypass scientific revisions, frozen objects, version conflicts, continuity, reference protection or managed-experiment control.
- Display preferences remain browser-local this phase and isolated by logged-in user in a shared browser. Do not claim cross-device synchronization.

### Non-interactive experiment access for AI, scripts and CLI

- AI and humans use the same experiment interfaces, permissions and recording standards. Explicitly authorized ordinary experiments must run continuously through REST, CLI, MCP/Agent or Python without step-by-step human Web actions.
- Conversation authorization and service authentication are distinct: chat instructions do not constitute login credentials. Use an explicitly authorized account or delegated identity bound to it; record the authorizing principal and AI/script execution source separately, without an automatic globally privileged AI account.
- Provide shared non-interactive authentication and protected reusable CLI sessions, with revocable action/resource-scoped delegated credentials. After initial setup, clients carry their session/token and required CSRF automatically instead of prompting for passwords at every step.
- Lab CLI provides login/status/logout and delegation creation/revocation channels; REST, CLI, MCP and Python share identity resolution and authorization. These are new planned commands, not claims that they already exist.
- Browser remembered sessions are not CLI authentication; do not extract browser cookies silently. Preserve explicitly host-configured username/password compatibility while adding protected credential storage/session references. Secrets must not pass through chat, command arguments, logs or Git.
- Delegations cannot exceed the account's current permissions. Role/project changes, deactivation and revocation take effect; renewal stays within a valid grant and cannot broaden scope or evade revocation. Credentials do not enter Core/scientific checkpoints or research exports.
- Provide explicit non-interactive mode. Missing credentials, expired sessions and denied permissions return useful errors/recovery instructions without waiting at password prompts, falling back to local superadministrator identity or bypassing APIs through database writes. Explicit interactive CLI login remains available.
- Cover authorized creation, control, stimulus, teaching/training, observation, restoration, registration, reports/notes, evidence and finalization while preserving scientific prerequisites. Ordinary steps within valid authorization do not require repeated human approval; genuinely sensitive operations or expanded task scope are handled separately.
- Review MCP/catalogue human-only hardcoding. Ordinary experiments and recording cannot be blocked solely because the executor is AI. Credentials/accounts/destructive cleanup retain their established permission and confirmation requirements.
- Authentication/authorization failures do not reset, clear, upgrade or secretly pause individuals; running tasks keep existing execution rules. Unknown submissions use original receipt queries rather than repeated stimuli. Persist pending record synchronization; unreliable original saving still invokes existing host-stop rules rather than producing unrecorded formal experiments.
- Independent local Runtime computation still requires no platform login. Formal research conducted with it still uses unified registration/evidence services rather than bypassing recording.

### Material pages and context

- Separate browsing filters, ownership, creation destination and system permissions.
- Keep one stable list per menu; project selection only filters, not swaps the entire tool.
- Use concrete actions such as New experiment, Write note or Import model.
- Resolve object details/permissions by identity; sidebar filters must not switch an object to another project.
- Data management lists authorized resources by default and explicitly shows batch selections. Report insufficient host permission rather than requesting a project.
- Users with zero projects can enter the workbench, settings, kernel catalogue and help. Slow/failed project requests must not block them.
- Global entrances follow the approved superadministrator scope and other roles' grants. A project filter is neither an authorization boundary nor permission for everyone to see all resources.

### Independent Runtime and publication access

- **Publishing, exporting or locally running a model does not require accounts/passwords.** Independent libraries, SDKs, CLI and trusted in-process use run directly, without platform activation or cloud validation.
- Library availability and network exposure are separate. The independent Runtime does not add a default remote-management listener. RuntimeHost/the carrier application decides which interfaces to expose and their access policies.
- Define business/input/output access separately from pause, configuration, intervention, recovery and export. A host may explicitly allow anonymous business access; login is not mandatory for every interface. Hosts may use accounts, scoped tokens, operating-system IPC permissions or external authentication, without embedding a full role system in every model.
- Multiple Lab instances share platform login with their own resource grants. Independent deployments have their own trust boundary; source users, sessions and credentials do not transfer automatically. Authentication code may be reused without sharing account data.
- Loopback HTTP alone does not establish the local user's identity or a trusted browser. Local Web access may use automatically established local tokens/sessions and origin checks. Trusted-proxy authentication must prevent direct backend bypass.
- Model/research packages do not embed platform or universal default passwords. Hosts initialize access controls for network deployment; ordinary export does not require prior password setup.
- Current deployment declarations checking model hashes/static intervention constraints are scientific/deployment checks, not authentication boundaries. They do not establish equal Python/Rust network-management security.
- This phase defines the contract, preserves independent use and tests platform boundaries; **it does not build an independent network-maintenance server as part of navigation work**. That server and real network-deployment acceptance are separate later work. Authorization stays outside Core configuration, scientific state and dynamics.

## IV. Backend, compatibility, implementation and acceptance

### Interface/data adjustments

- Add project-independent configuration validation using existing validators, without creating an engine or running a model.
- Shared creation-default/template saving service for UI, CLI and Agent.
- Add `start_immediately`: omitted in old calls remains `true`; new workbench preparation sends `false`, storing an unstarted instance without a job.
- Reuse `paused + revision=0`, shown as Not started. Explicit first start initializes from saved configuration.
- Complete prepared-state editing with metadata-version checks when no checkpoint/job exists. Never fabricate checkpoints; birth-fixed constraints remain.
- Add authorized global notification, queue and available-service queries. Keep project APIs, row-level authorization and ordinary-role private-data protection while explicitly implementing approved superadministrator access.
- Add unified user/multi-role/action-and-scope authorization. Handle login, setup, remembered sessions, logout, deactivation and revocation without putting authentication state in Core or scientific checkpoints.
- Add shared non-interactive authentication, protected reusable sessions and revocable delegation services to experiment/record/data commands and MCP/Python clients; expose status, expiry diagnostics and granted scope while preserving existing environment-configured login.
- Explicit AI/mail migrations preserve identities, revisions, grant provenance and queues, with no unauthorized merging or repeated sends.
- Show masked effective host settings and provenance. Editable items use existing services; startup-fixed items clearly require restart, without hidden hot changes.
- Retain old links/project APIs. Append migrations preserving former defaults, notification revisions and provenance. Do not create a permanent parallel permission system for an unreleased deployment.
- Queries/configuration organization do not advance simulation, reinitialize peripherals or change old individuals, results or kernel identities. Basic independent Runtime use gains no Lab-account dependency.
- Before real migrations, verify existing local backup/recovery paths. Test in isolation, then migrate explicitly. Do not take over, restart or stop user-run services.

### Implementation order

Preserve the original five stages, integrating later decisions:

1. **Bilingual plan and page matrix:** specify browsing scope, configuration layer, operation target and permission per page; preserve the original draft and revision decisions; clarify platform/project/instance/independent-Runtime boundaries.
2. **Workbench and basic navigation:** first deliver the primary entrance, read-only opening, graph/right panel and removal of system project gates. Retain sensory, empty-state and legacy-link acceptance.
3. **Configuration and backend separation:** prepared state, defaults/templates, notifications/global queries, unified AI catalogue and platform accounts/roles; include AI/script non-interactive authentication, reusable sessions and delegation so Web login alone does not obstruct experiments; validate in isolation before explicit migration.
4. **Stable material/project entrances:** remove dual page modes, complete project details and old-link compatibility, and apply shared permissions to materials, controls, CLI/Agent, attachments and background actions.
5. **Acceptance/delivery:** update manuals, bilingual research progress and required histories; report measured and unfinished work. Stage local commits without pushing, after the research-data/Git guard.

### Acceptance

Retain the original requirements and add all discussion boundaries:

- Zero-project users enter workbench/system pages; failed project queries do not block them.
- Opening, graphs, panels and layout changes submit no stimuli or execution commands.
- Preparation creates no job or simulated-time advancement; first start initializes once.
- Prepared edits versus start correctly handle version conflicts; restoration uses original configuration and whole-system state.
- Project filters do not change open objects, drafts or stimulus targets.
- No automatic sensory enablement; invalid capture requests no device permission; media cancellation writes no configuration.
- Global navigation does not widen ordinary-role private-data/credential access. Superadministrators can read all approved private originals; no plaintext keys are returned.
- Notification migration sends no duplicates; old queues, versions and links remain traceable.
- Identical inputs yield unchanged Python/Rust simulation results despite UI/storage metadata changes.
- Validate desktop, 390px narrow layouts, Chinese/English, backend and relevant regressions; correct old tests that endorse project-gated settings.
- Login/setup/remembered sessions/logout/deactivation/last-superadministrator protection and multi-role action/scope behave correctly, with no crossed grants.
- Direct API, CLI, MCP/Agent, downloads, packages and tasks cannot bypass authorization. Pause-only permission cannot stimulate/intervene; aggregates do not leak hidden fields/objects.
- Logout, expiry or revocation do not reset, clear, upgrade or secretly pause consciousness. Later operations use updated grants while preserving execution/save continuity.
- AI migration preserves identities/revisions/keys/calls/costs, without sharing, false merging or silent import binding. Diagnostics require no fabricated project.
- Defaults/templates affect creation only; ownership does not overwrite drafts. Preserve old kernels/individuals, frozen fixtures and historical missing-field restoration semantics.
- Local independent Runtime works without platform login; ordinary exports require no account and contain no platform secrets. Export does not open network management; do not claim the unbuilt server is delivered.
- Preserve ecology/frozen-evaluation control, revisions and reference protection, even for superadministrators. Backup/migration/reading preserve experimental identities/results.
- With preauthorized test accounts/delegations and no browser or repeated human login, validate CLI, MCP and Python paths through registration → prepared creation → start → text stimuli/repetition/teaching → observation → reports/notes/evidence → finalization. Verify database records/original links. This is isolated engineering acceptance, not a new scientific result.
- Verify cross-command/process/client-restart reuse and renewal within valid authorization. Repeated manual password entry or browser-cookie assumptions cannot make acceptance pass.
- Verify missing/expired/revoked credentials, deactivation, wrong project and insufficient action permissions: non-interactive calls return clearly without prompts or privileged fallback; delegations do not expand authority.
- Verify interrupted synchronization, lost responses and original receipt reconciliation without duplicated input, lost queued records or individual resets. Original-saving failures retain established scientific safeguards.
- Check that actual MCP operations in the experiment chain work under valid authorization; human-only tags do not block ordinary creation/stimulus/training/report/evidence saving, while sensitive-operation checks remain.

## V. Final decisions from the subsequent discussions

The original next-day choices have been answered. Retain them here and include later decisions instead of leaving settled choices to implementation.

| Question | Final decision |
|---|---|
| Default home? | **Consciousness workbench**; research overview stays in Research |
| Start immediately after creation? | **Create and prepare by default**, with explicit Create and start |
| Automatically apply project presets? | **No**; explicit selection and provenance |
| Must new consciousness belong to a project? | **Yes at save**, with inline project creation; no gate on configuration browsing/system use |
| Platform and project-private AI services together? | **Revise original recommendation: unified platform catalogue plus grants**, preserving original identities/use scope |
| Cross-device display preferences now? | **Browser-local**, isolated per login; synchronization later |
| Product positioning? | **Local-first plus optional self-hosted team platform**; Web UI/cloud capabilities serve kernel and research |
| Separate administration website? | **No; management within the same application by permission**, with technical frontend/backend division retained |
| Platform/project relationship? | **Projects belong to this deployment**; authorship, responsibility and provenance remain |
| Login/roles? | **Platform login and remembered sessions**, built-ins/custom roles, multiple roles and backend operation/scope grants |
| Direct AI experiment calls after conversation authorization? | **Yes, through complete non-interactive access:** one setup, protected reusable session or scoped delegation, existing account permissions and no per-step human login |
| Separate AI experiment/permission-bypass system? | **No:** shared REST/CLI/MCP/Python services, separate principal/executor provenance and equal formal recording standards |
| Superadministrator access to private originals? | **All**, while ordinary grants remain bounded and plaintext credentials stay hidden |
| Legacy users/parallel permissions? | **No fictitious compatibility/notice process** for this unreleased deployment; preserve scientific identities/data |
| Independent Runtime depends on platform accounts? | **No**; local libraries/SDK/CLI/in-process use remain direct |
| Published model requires a password/account? | **Revise earlier idea: no requirement** for ordinary export/local use or activation |
| Independent remote management open by default? | **No new default listener**; host explicitly exposes interfaces and access policies, separating business/management |
| Who authenticates? | **RuntimeHost/carrier**, with accounts, tokens, OS permissions or trusted external authentication; not Core |
| Full roles per model? | **No**; Lab shares platform grants, independent hosts use their own trust boundaries |
| Logout/permissions alter model life? | **No automatic reset/upgrade/pause**; authorize operations while preserving execution rules |
| Independent network-maintenance server this phase? | **No**; contract and platform acceptance now, implementation/measurement later |
| Change kernel defaults/dynamics or start training? | **Not through this task**; original hierarchy/navigation/related-service scope remains |

No settled product choice awaits another user decision. If implementation discovers a new conflict with established scientific boundaries, report it separately. Native desktop UI, cross-deployment synchronization, independent network maintenance and full remote storage/device deployment remain future work.

Parameter tuning, new kernel mechanisms, long training and existing independent-restoration gaps are not automatically included. At delivery, synchronize bilingual progress, modern histories and both Classical Chinese adaptations, distinguishing user decisions, implementation, measurement and unverified inference. This plan revision is not completed implementation.

## VI. October 11, 2026 implementation addendum: kernels, templates and parameters

This section records the subsequently discussed and approved kernel-hierarchy repair without replacing the original five chapters or their decisions. Evidence for the earlier platform 65 → 67 migration remains separate from this 67 → 68 migration.

- Creation, system defaults and template editing use actual kernel version → matching template → parameters. Options show version identity and a brief description. Multiple templates may belong to one kernel. The selected kernel's system defaults are initially selected, or its own factory defaults if none exist. Project presets are explicit; ownership does not overwrite drafts.
- All 16 actual identities support creation: `threemind.causal/1` through `/9`, `threemind.continuous/1`, `threemind.continuous-memory/1` through `/4`, `threemind.lif/1`, and `unified-associative`. The default remains `/3`. Built-in research parameters are not presented as kernels, and historical creation is not disabled.
- The later approved decision preserves compatible shared implementations rather than splitting continuous-family Rust code by business version. Isolate historical implementations only where incompatible with modern interfaces. Preserve historical causal birth rules from each version's source. Do not invent unified structural-birth rules where absent; blank creation and exact forks remain available.
- `unified-associative` retains the original `97d8592` Python implementation, epoch/tick and senses. V1/V2/V3 are templates for this single kernel. The full JSON package, random state and pending input remain intact; separate encoding and query projections avoid coercion into modern node schemas.
- Templates can be saved from current parameters or an instance's saved configuration. Clear research-condition membership; save configuration and provenance without learned state. Every source must match the actual kernel. Future template revisions fix the kernel while historical revisions remain intact. REST, the operation catalogue and existing CLI/Agent share services. Copying instance parameters requires system write and source-instance read, without additional runtime-control permission.
- Record the backend in host `runs.execution`, outside scientific `spec`. Match workers by kernel and backend; reject explicitly unsupported choices without silent kernel conversion. Schema 68 is an explicit migration, never startup DDL.

This deployment completed isolated acceptance, offline installation into its everyday virtual environment and explicit schema 67 → 68 migration. Real-database scientific witnesses match before and after, and `doctor` passes. Detailed counts, usage and validation scope appear in the [delivery record](kernel-creation-hierarchy-delivery.md) and [workbench guide](../platform-workbench.md). This is UI, host and historical-implementation compatibility work; no new formal training was conducted, and it establishes no scientific advantage for a kernel.
