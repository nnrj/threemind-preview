# E27 delivery and database verification

2026-10-03. [Report](report.en.md) · [Execution record](execution-notes.md) · [Tools](../../../docs/en/plans/robot-survival-selection.md)

- Project: `e4859f89-ab18-4d78-bf7c-c70d71bfc38e` — E27 free-cup grasping, granular transfer and finite-energy survival selection, accessible through existing notebook/report pages.
- Chinese report: `a357a66a-d152-58f0-b267-9b40cbfb7680`; English report: `5f46b8cb-4eb1-5204-9ad7-c661abfe8ffe`.
- Execution record: `13841b60-95dc-5c4c-b057-9ae7effb8682`.
- Evidence artifact: `5edb3fd7-2dbe-4a8e-a6f0-9487cde60d51`, 861,960,485 bytes (822.03 MiB), 654 verified members.
- SHA-256: `0bbae8f93fc76f4f10db5cd8998c792684c29bc480f80bf721849944c55478a1`.
- All archive members verified. PostgreSQL chunk readback matched total bytes and hash; report content hashes also matched.

At sealing, local growth was 1.858 GiB including the local archive copy, database growth 0.834 GiB, combined 2.692 GiB, below the 8 GiB expansion threshold. Account usage moved from 12% to 14%, conservatively including shared-account activity; this is not exclusive per-task attribution. Last measured free RAM was about 13 GiB, C disk 9.77 GiB and E disk 105.03 GiB. No old evidence was deleted.

Twenty-four formal cases accumulated 88.16 simulated minutes and 3.57 summed process-wall hours. Two successful full Core replays separately took 317.98 and 312.14 wall seconds; an earlier 300-second verification timeout remains recorded and is not a new learning sample. Core and historical instances were unchanged. Eighteen tests passed and three isolated database cases were skipped; actual publication had independent database readback verification.

Python/CLI tools and report visualization are delivered; complete granular cohort launch UI remains T08. Changes are committed locally without push. This receipt and the sampling-wording clarification are appended after sealing; the archive and report revision 1 are preserved.
