# Global resource browsing

2026-10-10, implementation approved by the user. Projects retain ownership and access boundaries, but cease to be the implicit default filter for every menu.

- Research overview aggregates authorized projects and presents project counts and a project list.
- Experiments, comparisons, worlds, dialogue, data, models, notes, reports and data management provide searchable, paginated cross-project metadata lists with a project field. Existing project editors and operational tools remain available.
- The sidebar explicitly selects a browsing scope, initially All projects. The old browser preference cannot silently narrow the new default.
- Resource links carry their owning project. Legacy run links resolve authorized ownership by identity. Creation requires an explicit destination rather than implicitly choosing the first project.
- The shared read-only service preserves membership, personal-note authorship, private bundles and carriers. Reading does not create notebooks, advance simulations or load large originals.
- An explicit migration adds cross-project SELECT policies for metadata only; writes and raw-data tables retain their boundaries. Validate with an isolated database without taking over user services.
- Verify pagination, filtering, permissions, privacy, direct links, creation ownership, both languages and narrow screens. Update guides, tooling backlog and dated historical corrections without rewriting previous evidence.

Source: the user identified misleading empty pages caused by the Current project filter, accepted project metadata, filters and a project overview, and authorized this adjustment. The preceding global experiment index did not make every menu global.

## October 10, 2026 implementation and acceptance

Delivered the shared metadata query service, global pages, explicit destinations and legacy ownership resolution. The local database was explicitly migrated to schema 63 and the frontend built. See the [browsing guide](../global-resource-browsing.md). No user workstation was started/stopped; an existing service needs a normal restart to load the new API, and page reloads start globally.

Migration adds 24 metadata SELECT policies while preserving every previous policy, raw trajectory/checkpoint boundaries and write rules. Metadata witnesses match for 20,581 runs, 24,821 checkpoints, 84 indices, 442 documents/500 revisions, 635 notes/719 revisions, 19,417 entries, 59,118 evidence references and 3,615 artifacts: identities, saved state/content hashes, time and revision fields remain unchanged. No originals were copied or scientific findings modified.

Actual local global queries expose 573 accessible projects, 20,574 unarchived runs, 84 indices, 442 records/reports and 635 personally visible notes. Seven archived runs remain available through the archive filter. Pages contain at most 100 metadata rows, with defaults of 50 resources and 12 projects. A single local measurement gives approximately 10 ms for documents, 37 ms for notes, 118 ms for artifacts and 132 ms for overview; the initial run query including connection-pool establishment takes about 828 ms. These are tool-query timings, not Core benchmarks or universal performance guarantees.

45 distinct isolated backend cases pass (35 and 14 in two batches, with four shared cases), covering permissions, private carriers, read-only transactions, pagination, documents/notes/bundles and research indices. Six Edge browser cases pass: global defaults ignoring old preferences, nine resource menus, explicit filtering across menus, note reload/report preview, legacy ownership independent of browsing scope, explicit creation project, and English 390 px layout. Frontend build, Ruff and history validation pass. New browsing messages have no missing translations; existing site-wide omissions remain, so local acceptance is not complete site-wide translation.

Fixtures/screenshots remain ignored. `tools/browsing_acceptance_server.py` reproduces synthetic acceptance without a simulation worker; temporary services/databases are cleaned afterward. Core, historical individuals/reports and negative results remain intact. T12 host issues still await a separate user decision.
