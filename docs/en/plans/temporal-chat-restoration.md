# Temporal readout and conversation restoration

[中文](../../zh/plans/temporal-chat-restoration.md)

2026-09-10. Implemented and accepted within the scope below.

## Confirmed boundaries

- Connect temporal readouts to chat, research records/reports, the standalone Runtime and calibration CLI.
- Freeze the `0c5e64a` interface and `97d8592` presentation functions in the [reference](../../benchmarks/chat-restoration-reference.json).
- Show the first seven temporal candidates in recorded scientific order by default, with complete measurements expandable in the same message. Restore passive activation ordering and its switch. Label deduplication never removes node evidence.
- Restore continuous bubbles, media/organ toolbar, composer and scrolling. Retain bounded loading, exact provenance, idempotent sending, failure recovery and IME handling.
- No changes to Core, sensory mapping, simulation time or readout classification/scoring. An observation deadline never limits an ordinary consciousness instance's lifetime.
- Use a separate acceptance project. Do not scan, backfill, reinterpret, convert or clean historical data. No pre-upgrade cleanup is required.

## Existing tradeoffs and deviations

The code at `db4e0a4` and the previous documentation establish that the UI reused a paginated evidence browser: cursors, 20 messages per page and 128 preview nodes bounded costs. Complete evidence, transactional indexes, exact provenance and failure recovery remain useful.

That browser replaced continuous conversation. Although the category selector supports all messages, it occupies the primary interaction; frequent readouts replace inputs in the latest page; metadata crowds out text; node-ID order replaces readable readout ordering. Prior tests established that controls and APIs existed, not that the experience faithfully matched the original. The previous completion claim was too broad and is corrected here.

These interaction regressions are not required by research rigor. Undocumented author motives remain unknown. Complete current observations will not be reduced to the legacy subsets: presentation changes neither raw activity nor candidate computation.

## Implementation and acceptance

| Area | Implementation and evidence |
| --- | --- |
| Frozen source and formatting | Actual legacy functions produce the reference fixture; ordering, readable text and label deduplication are checked without deleting nodes |
| Conversation APIs | Forward cursors recover a 145-input burst; separate live receipts, project isolation and read-only presentation checks pass |
| Runtime and temporal experiments | Native/reference state parity, pending-event/window continuation, explicit censoring and model source-policy inheritance pass |
| Chat and organs | Mixed bubbles, legacy passive ordering, full-node expansion, IME, failed-send drafts, three media entries, four organ controls and mobile layout pass |
| Records and reports | Window, all-node and single-window-series sources; graphical/JSON configuration, fixed provenance, templates and four export formats pass |
| Resource bounds | Finite 60-second small-model operation and screenshots accepted; no claim about hours-long or server-scale capacity |
| Documentation and deployment | Bilingual guides, corrected earlier completion scope and manual backup advice; only schema 49 → 50 applied locally, doctor passed |

The [machine-readable record](../../benchmarks/temporal-chat-acceptance.json) contains commands, source hashes and limitations. The affected regression suite passed 71 tests. After the final CLI source-policy fix, 24 related tests passed again, including the added regression; these overlap the first suite. Four browser tests passed, the final localized experiment-status check passed separately, and the final layout passed a 60-second soak. TypeScript/Vite, Ruff, translation auditing and whitespace checks passed.

At 10-second intervals the chat viewport mounted at most six bubbles. Heap growth from seconds 10 to 60 was 829,796 bytes (about 0.79 MiB); DOM growth was nine nodes. See [samples](../../benchmarks/temporal-chat-soak.json). Tests used PostgreSQL 55439, new acceptance instances and simulated microphone/camera devices. They are not physical-device certification or long-running capacity evidence. Existing Vite chunk-size and third-party font deprecation warnings remain.

Screenshots: [inline chat](../../images/temporal-inline-chat.png), [mobile](../../images/temporal-inline-chat-mobile.png), [mixed conversation](../../images/temporal-mixed-chat.png), [temporal experiment](../../images/temporal-observation.png), [graphical report draft](../../images/temporal-report-draft.png).

## Retained behavior and boundaries

Exact provenance, complete evidence, transactional indexing, bounded browsing, idempotent sending and failure recovery remain. The category browser, missing readable ordering and metadata crowding were corrected. Screenshot review also caught and fixed a narrow standalone chat and overflowing mobile toolbar; clickable controls alone do not establish successful interaction restoration.

Core, sensory mapping, sampling, candidate selection, scoring and convergence formulas are unchanged. No new scientific training run was performed. Historical experiments were not backfilled, repaired, reanalyzed or cleaned. Historical chat/1 evidence retains its original presentation; new chat/2 records use the restored presentation. The bare Rust CLI does not acquire the Python host's observer flags. Missing measurements never become fabricated answers.

See the [user guide](../v2-temporal-research.md) and [manual backup/project cleanup guide](backup-and-cleanup.md). Cleanup remains the user's decision and action; no new research jobs were started in the main workstation.
