# Global resource browsing and project ownership

[简体中文](../zh/global-resource-browsing.md) · [Approved plan and acceptance](plans/global-resource-browsing.md) · [Research records](research-records.md)

After the October 10, 2026 adjustment, the overview and main resource menus initially show all authorized projects. Projects retain ownership and member permissions. Browsing no longer requires guessing where a resource was saved.

## Browsing, filtering and operations

- **Research overview** aggregates authorized resources and presents a searchable, paginated project list. “Browse this project” explicitly narrows the scope.
- **Browsing scope → All projects** is the default. An explicitly selected project filters subsequent menus; reloading starts globally. The old `tm2.project` browser preference no longer silently applies.
- Experiments, comparisons, worlds, dialogue, data, models, notes, reports and data management have cross-project lists with project, type, status and update date, search and pagination. Personal notes, private bundles and their carriers retain existing permissions.
- Records/reports, notes/drafts and model types have category/type filters. Archived resources require the archive filter.
- A resource opens its owning project's details or existing tools, with an explicit **Project** banner. Legacy individual links resolve authorized ownership and add it to the URL; editor tab changes retain ownership. “Back to all resources” clears the detail and browsing filter.
- Creating an individual first displays a destination project. Global browsing does not select the first project automatically. Other create/import/manage operations choose a project before entering the existing workspace. An explicitly selected browsing project appears as a visible destination to confirm.
- Opening an old resource does not move it into the browsing filter's project. Project defaults, external tools, notifications and execution-resource settings select their destination. Display, devices and host storage keep their previous scope.

Materials available only through an index, evidence reference or historical protocol remain accessible from experiment details. Browsing does not fabricate native worlds, runs or models. Resource counts do not count successful experiments.

## Activation and read-only API

The everyday local database was explicitly migrated to schema 63 and the frontend built in this task. If ThreeMind is running, stop/restart it normally and refresh the browser. This task does not take over that service. Other local checkouts should update and run:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
```

This updates schema/metadata SELECT policies rather than relocating experimental data. Originals, historical individuals, reports and revision chains remain intact.

Three new GET endpoints use existing authentication:

- `/api/v2/browse/overview`: resource totals and projects, with `project`, `q`, `offset`, `limit`; 12 projects per page by default.
- `/api/v2/browse/resources`: `kinds`, optional `project`, `q`, `subtype`, `archived=active|archived|all`, `offset`, `limit`; 50 resources by default, at most 100.
- `/api/v2/browse/location/{kind}/{id}`: authorized ownership resolution; unavailable resources return an explicit error.

Omitting `project` queries all authorized projects; supplying it requires membership. Fixed metadata projections and read-only transactions do not load complete trajectories/checkpoint bytes, stimulate, restore, learn or create notebooks. There is no cross-project bulk write endpoint.

## Reproducing engineering acceptance

Backend tests use the isolated PostgreSQL cluster declared by `tests_v2/conftest.py` (default port 55439), creating and dropping temporary databases.

Start that test cluster, then run in one terminal:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe tools/browsing_acceptance_server.py
```

The helper never reads `.env`, creates synthetic data in the fixed test cluster, serves `127.0.0.1:8898`, and starts no simulation worker. In another terminal:

```powershell
cd threemind-ui
npm run build
$env:THREEMIND_E2E_URL = 'http://127.0.0.1:8898'
$env:THREEMIND_BROWSE_FIXTURE = "$PWD\..\.work\global-browse-ui-fixture.json"
node node_modules/@playwright/test/cli.js test e2e/globalBrowsing.spec.ts
```

At the repository root, write `Set-Content .work/global-browse-ui.stop stop` or press Ctrl+C in the helper's terminal. It exits and drops its temporary database. Synthetic fixtures/screenshots are engineering evidence, not formal research experiments or Git data.
