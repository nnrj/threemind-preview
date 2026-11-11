# M4 continuation from the complete 111-second boundary

2026-10-17. Applies to `m4-balanced-v2`, original freeze a9a76c8 and research record `9d3589f3-663f-5a1a-be9a-5a8c6fcaf443`. This is a host implementation adjustment, without Core, individual identity, curriculum, peripheral, learning-mechanism or G1/G2/G3 changes.

## Preserved safe pause

Host 31484 completed o0 `teach-0-7` after approximately 917.75 wall seconds: internal time 111 seconds and 960 motor updates. Its measured private-memory peak was 3,221,241,856 bytes, just above the registered 3 GiB host cap. The per-second guard requested STOP and the host exited after a complete save, with no in-flight marker. System reserves all passed at the request; this was a host-budget pause, not an allocation crash or disk exhaustion.

Current full-state SHA256: `144670e21efb4454ba3a01aa81a9694813cfa8168bf68bf72f80559b4a3d5840`. Seven state files, 24 external corpus dependencies and 144 examples were independently verified. The state retains 338 Core nodes, 112138 edges, 32 recent frames, body, mappings, personal weights, Adam/RNG and actuators. Exact STOP, status, host, resource summary and original logs are archived under `pauses/c111-private3-20261017/`. Active STOP remains until the new entry's locked verification.

A new process loaded exactly this current state read-only, without input or simulated advancement, and reproduced its full hash. Post-load private memory was 1,829,519,360 bytes; observed peak 2,148,347,904 bytes over 16.03 seconds. The current individual therefore does not itself require the entire 3 GiB allowance. This supports releasing long-lived host allocations by switching processes at existing complete boundaries; it does not identify a particular library or allocator as the cause.

## Host adjustment and fixed boundaries

`m4_continuation_host.py` holds the global serial study lock. Each existing complete stage receives one fresh worker, requiring the supervisor's actual PID, creation time, command and a single-use ticket. It delegates trials, saving, actions and learning to the frozen v2 methods and authentic /5.1 implementation. Ordinary stages restore the latest complete current state. The first remaining action is `teach-1-0`; no earlier block is taught again.

Each stage saves the complete individual and evidence before its worker exits. Process replacement contributes no simulated time, stimulus or learning update. Loading must reproduce the complete hash. Only the seven already registered causal copies branch from the 255-second reference; these are distinct from ordinary current-state continuation. Group selection remains before confirmation, and failed behavioral/matching gates still prevent uninterpretable lesions.

The scientific worker's 3 GiB private cap, 4 GiB originals cap, cumulative eight-hour budget and system commit/RAM/C/E reserves of 5/4/5/25 GiB **remain unchanged**. The supervisor has a separate 1 GiB cap and shares the same live system reserve checks. Startup requires an additional 4 GiB commit/physical headroom. The original 917.7488071 host seconds count toward the cumulative budget. Fresh processes do not reset scientific clocks, RNGs, optimizers or budgets.

Under locks, recheck current files/dependencies, absent old hosts/in-flight, frozen continuation sources and live capacity. Archive and active STOP bytes, SHA and cause must match exactly before retiring only this active STOP into the new continuation directory. Preserve all originals and launch one unique log. Any later resource STOP ends the supervisor without automatic retries. Any new dead in-flight is preserved and escalated, never cleared.

## Acceptance and interpretation

Fifteen non-simulation checks cover the correct post-111-second stage, ordinary ordering, selection before confirmation, seven causal branches, no replay of completed work, invalid order rejection, 3 GiB/cumulative time/probe-failure guards and preservation of an existing STOP.

Separate N0 seed 1123010 executes two fixed balanced demonstration blocks. The uninterrupted path reaches 18 internal seconds and 240 motor updates. A separate instrument copy resumes from the complete 9-second/120-update state in a new process and executes the second block. Final whole state, three second-block raw trajectories, personal weights/Adam/RNG, body and input history must match exactly, with independent file verification. Failed acceptance forbids scientific continuation. N0 contributes no scientific score and cannot tune the curriculum.

Use actual acceptance receipts as execution evidence. Scientific continuation requires passed acceptance, local source freeze, this appended note on the same research record and pending=0. The original frozen analyzer and auditor still evaluate all eight origins before bilingual scientific conclusions and full API delivery. This change neither labels an incomplete origin negative nor changes success criteria.

Acceptance added on 2026-10-17: the continuous N0 reference and separate-process continuation each completed18 internal seconds and240 motor updates. Both final whole-state hashes are b5337341450440d25272fa7e5a9c742c018045bf2ca4f4dcba9e61a5d8f8c824; all three second-block trajectories match exactly, with independent file-arithmetic verification. Peak private memory was2,709,487,616 and2,799,497,216 bytes, both below3GiB. Sixteen non-simulation scheduling, guard and analysis-compatibility checks passed. The explicit conclusion is that complete fresh-process continuation preserves the individual's experience and outcomes on the tested learning path, meeting its preregistered acceptance requirement. The formal individual remains at111 seconds and was neither loaded nor advanced by this instrument.
