# E67 correction: per-question restoration is not continuous testing

Audit date: 12 October 2026. This corrects the scope of existing evidence; it is not a new experiment, replacement protocol or rescoring. Original protocols, reports, videos, checkpoints and personal peripherals remain intact. [简体中文](continuity-audit.zh.md)

## Reason for the audit

The user noticed simulated time moving backwards between questions in the `/2` and `/3.1` replays and reiterated continuity as a fundamental research assumption. Read-only inspection confirmed actual restoration before each question, rather than a video display defect. Conflating complete-state preservation and continuous teaching with continuous evaluation was an assistant design and interpretation error. Documenting independent copies in a protocol does not establish that the user agreed to substitute them for a continuous exam. [Dialogue and subsequent clarification](../../../docs/en/history/sources/2026-10-11-shape-color-comparison.md)

## Executed procedure

- In `experiment.py`, `collect()` calls `load_system(source, meter)` inside the loop for every unfinished question. It discards the resulting copy after that question and restores the same stage source for the next one.
- Initial and subsequent calibration collections, development evaluations and final evaluation all use this function. The personal reader subsequently learns from the collected activity; the mainline individual does not thereby retain those complete testing experiences.
- `teach()` restores once at the start of a teaching stage and advances continuously through its lessons, including questions within corrective teaching. The next teaching round continues the prior `fit` mainline state, without reconnecting the development evaluation's end state.
- Preserving Core, personal reader, optimizer/RNG, body, mappings and recent state remains valuable. Nevertheless, **restoring the complete state for every question is not one individual continuously experiencing those questions**.
- `continue_four.py` reuses the same `collect()`, so both `/4` arms have the same evaluation limitation. This audit changed neither frozen sources nor the running host.

## Original-data verification

Resource: `research:e67-shape-color-kernels`. Root: `E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels`.

| Item | `/2` | `/3.1` |
| --- | --- | --- |
| Mainline time in `arms/<arm>/fit-3/result.json` | 865,500,000 µs | 865,500,000 µs |
| `timing.restore_calls` in `arms/<arm>/final/result.json` | 72 | 72 |
| Final replay originals inspected | 72/72 | 72/72 |
| First and last activity time of every question | 865,550,000 → 866,500,000 µs | 865,550,000 → 866,500,000 µs |
| Frames per question | 20 in every case | 20 in every case |
| Original score, unchanged | 71/72 | 67/72 |

All144 `final/clips/*.json.gz` files across the two arms were decoded and matched this table; this is not solely a visual inference from selected replay segments. Replay `core_t` comes from stored `activity.time_us`. The current `experiment.py` hash also matches the original revision3 frozen manifest: this behavior was not introduced later during execution. Inspection did not instantiate engines, rerun questions or modify originals.

## Supported and unsupported conclusions

1. The scores remain **independently restored, single-question recognition measurements from a fixed teaching checkpoint**. Under this fixture, curriculum and reader, `/2` has better measured scores and computation cost than `/3.1`. That ranking is not established for a continuous exam.
2. A single individual's score across72 consecutive questions, cross-question interference, order effects and post-exam retention have not been measured. The865.5 seconds mark the teaching-mainline endpoint; simulated work performed by independent question branches must not be added as that mainline individual's lifetime.
3. Development results influence the teacher's later correction selection, and calibration activity trains the personal reader. Neither effect means that mainline Core experienced and retained each exam.
4. The completed twelve-case reversible interventions remain causal diagnoses on single-question copies. They neither repair continuous-testing evidence nor show that Core determines every answer. Their original reports and limitations remain.
5. A new continuous shape/color experiment needs a distinct agreed protocol and registration. Switching the existing host midway and combining both procedures would not supply that evidence. The user said a new experiment could be arranged another day; none was started on that basis.

## Constraints on subsequent delivery

The final four-arm reports and replay descriptions must cite this correction and distinguish the teaching mainline from independent evaluation branches. Preserve existing reports and manuscript drafts. Later revisions must narrow continuity claims without overwriting the author's actively edited Word file. Saving this supplement does not mean that existing platform reports or manuscripts have already been revised; later publication must record its own receipts. Never make displayed time monotonic by rewriting original simulated timestamps.

Read-only status at23:25 China time: original `/4` worker PID3116 was advancing `4-adaptive/calibration-1`, with43 saved trials/clips, zero pending synchronization, zero stderr bytes and approximately120.60GiB free on E. PID11420 was its virtual-environment launcher. This snapshot does not claim completion of all four arms. No duplicate start, stop, reset or curriculum change occurred.
