# Experiment overview and unified recording

[简体中文](../zh/research-records.md) · [Backfill plan](plans/experiment-record-backfill.md) · [Full delivery and gaps](plans/experiment-record-backfill-delivery.md) · [Data management](data-management.md)

AI and human research use the same recording service and requirements. Executor is searchable metadata. The database stores the index, small original texts, fixed revision references and evidence links; original scientific files remain intact. Backfill neither recreates missing observations nor runs historical subjects.

## Finding experiments

The **Experiment overview** sidebar entry searches all accessible projects by original ID, title, project, date, kernel, executor, execution status and evidence completeness. A subsequent October 10, 2026 adjustment makes reports, notes and other main resource menus global by default, with project fields and explicit filters. An empty project is not an empty database. See [global browsing and ownership](global-resource-browsing.md).

Revision reason: the preceding delivery added a global experiment index while retaining scoped pages elsewhere. The user approved extending global browsing. Backfill records, reports and original delivery evidence remain intact.

Historical related-kernel tags come from explicit identities in original texts and native run configurations. Each group's executed version and parameters remain in its protocol and saved configuration; unresolved identities stay unknown. N01–N13 are later search labels, displayed alongside original notebook numbers 001–013.

Details combine protocol, original reports and revisions, notes, subjects, stages and evidence. Personal notes retain author permissions. Supported text and JSONL have bounded previews; opaque files remain downloadable in their original format. Runtime and checkpoint links reuse existing viewing and replay without advancing a simulation.

Completed execution, failure, interruption, unstarted proposals and negative findings are distinct. “Indexed” is not full validation; a verified index covers registered originals, not proof that the original collection was complete.

## CLI, REST and Agents

Start the local workstation normally, then use its Python environment:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --query E64
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --kernel threemind.continuous-memory/3
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records --help
```

The default API URL is `http://127.0.0.1:8877`; override with `--url`. Server mode reuses existing authentication. Credentials never belong in request JSON, evidence or Git.

`list` also accepts `--classification`, `--from-date` and `--through-date` with `YYYY-MM-DD` dates. Development checks require an explicit `--classification development` filter and stay outside the default formal register.

`register`, `append`, `attach`, `text`, `finalize`, `verify`, `backfill-plan`, `backfill-apply` and `receipt` share the canonical REST service. Writers read a request file with `--json`. Use a fresh UUID `request_id` for each new operation, retaining both ID and body on retry. Conflicting reuse fails. Query committed receipts with `receipt --project <UUID> --request-id <UUID>`.

Registration uses `{ "request_id": "<UUID>", "spec": { "source_key": "<stable original key>", "title": "<title>", "executor": "ai", "classification": "formal", "execution_status": "planned", "question": "<actual question>", "protocol": "<preregistered protocol>" } }`. Register before execution; append actual stages and evidence; verify at closeout.

Global reads use `GET /api/v2/research-experiments`; project writers live under `/api/v2/projects/{project}/records`. `/api/v2/operations/catalog` exposes the `records.*` request schemas, prerequisites and permissions. The existing MCP server reuses that catalog.

Evidence supports authorized registered storage resources, fixed document/note revisions, attachments, runs and checkpoints. File references record bytes and SHA-256 rather than accepting arbitrary host paths. A host administrator explicitly grants registered resources through `POST /api/v2/storage/record-evidence-grants`. Missing evidence has a reason; it is never replaced with an invented empty file.

Text revisions retain `identity`, specify `expected_revision` and require `revision_reason`. Old revisions and hashes remain. Historical Markdown containing relative notebook links is retained as literal source when necessary, preserving exact text without weakening URL validation.

## Python scripts and execution entry points

`ResearchRecorder` in `threemind_lab.research_recorder` accepts either the canonical service or an existing `OperationsClient`. It provides `register`, `append`, `attach`, `text`, `synchronize`, `finalize` and immutable `save_original`. Large files may keep their existing scientific writer and attach a registered storage reference afterward.

The experiment’s `.research-records` directory durably retains pending requests, status and receipts. Database outages preserve the queue; strict synchronization records the error before raising. `resume_recording()` resumes the journal only. Failed original writes must stop host advancement rather than skipping inputs or clearing a subject.

Manual runs, paired studies, developmental training, directed selection, ecological training and independent assessments register their frozen protocol in the creation/enqueue transaction. Completion records existing state and checkpoints. Host-only `record_executor` defaults to `human` and also accepts `ai`, `mixed`, `unknown`; `record_classification` defaults to `formal`, with `calibration` and `development` alternatives. Temporary development entries are hidden from the formal overview. Researchers still supply scientific questions, explanatory notes and closeout reports.

Maintained `lab/tools/service_study.py` and publication tooling now use the recorder. Frozen historical scripts are unchanged and never rerun for backfill.

## Transfers and historical backfill

Experiment details generate formal export previews using `kind=experiment`. Transfers preserve revisions, permissions, hashes and read-only runtime dependencies. Imports create new index identities with provenance and do not construct running subjects. Re-exporting an imported index preserves original runtime table members, not only a descriptor that points elsewhere.

Existing capacity limits and disk reserves apply. Large selections need existing narrower export facilities or their complete original archive; limits are not silently bypassed. A full local database backup consumes substantial disk space and can cause transfers to stop explicitly when reserves are insufficient.

`scripts/backfill-research-records.py inventory|preview|apply` builds fixed inventories, previews and receipts. Apply requires a complete backup plus an isolated recovery witness. Restore creates a new temporary database only; it never replaces the daily database, switches hosts or starts models. Schema migration remains explicit with `threemind migrate`. Retried backfills reuse their frozen preview instead of mistaking newly added texts for historical originals.

A completed batch checks the frozen source and committed database completion receipt on retry, reusing its original verification without reattaching every file. Loss of a local receipt is recoverable. Use `records verify --project <UUID> --experiment <UUID> --hashes` for a fresh check of current originals, separate from backfill replay.

Consult the delivery document for actual inventory, missing sources and validation. Directory counts are not counts of completed experiments.
